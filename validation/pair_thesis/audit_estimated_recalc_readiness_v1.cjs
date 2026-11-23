'use strict';
/* Read-only, point-in-time audit for the existing FX Next G8/28 estimated receipt.
 * A source-change "pending" result must not block the worker that will repair it.
 * Never mutates the repository, FX Core, positions, prices, or report text.
 */
const fs=require('node:fs');
const {createHash}=require('node:crypto');
const {evaluate}=require('../../site/fx-quant-v2/next/macro-strength-estimated-v1.js');
const {currencyRanking}=require('../../site/fx-quant-v2/next/pair-rankings.js');
const receiptUI=require('../../site/fx-quant-v2/next/home-thesis-recalc-v1.js');
const paths={
 observed:'site/control-room-preview/macro-v3-current-evidence.json',
 prices:'live_data/sections/ECB_G8_PRICE_HISTORY.json',
 ois:'site/fx-quant-v2/ois-pricing-snapshot.json',
 rates:'live_data/sections/NATIVE_RATES_DATA.json',
 model:'live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'
};
const pathReceipt='site/fx-quant-v2/next/pair-estimate-recalc-receipt-v1.json';
const sha256=x=>createHash('sha256').update(x).digest('hex');
const dayNow=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',
 year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
function inspect({receipt,estimate,sourceHashes,method,day}){
 if(!receiptUI.receiptOK(receipt))
  return {status:'RECEIPT_INVALID',checkedDay:day,changedSources:null,
   changedPairs:null,changedRanks:null};
 const changedSources=Object.keys(paths).filter(k=>
  !sourceHashes||sourceHashes[k]!==receipt.sourceHashes[k]);
 const methodChanged=receipt.method!==method;
 const pairDelta=(estimate?.pairs||[]).filter(p=>{
  const r=receipt.pairs[p.key];
  return !r||r.favored!==p.favored||r.thesis!==p.thesisStrength||
   r.timing!==p.tradeAttractiveness;
 }).map(p=>p.key);
 const rankDelta=(estimate?.currencies||[]).filter(c=>{
  const r=receipt.currencies.find(r=>r.ccy===c.ccy);
  return !r||r.rank!==c.rank;
 }).map(c=>c.ccy);
 const outputsMatch=receiptUI.outputMatches(receipt,estimate);
 const datesMatch=estimate?.asof===receipt.macroAsOf&&
  estimate?.priceAsOf===receipt.fixingAsOf;
 const state=estimate?.status!=='STIMA_OPERATIVA_NON_VALIDATA'?
  'ESTIMATE_SUSPENDED':
  changedSources.length?'INPUT_CHANGED_PENDING_RECALC':
  methodChanged?'METHOD_CHANGED_PENDING_RECALC':
  !datesMatch||!outputsMatch?'OUTPUT_CHANGED_PENDING_RECALC':
  receipt.checkedDay>day?'FUTURE_RECEIPT_INVALID':
  receipt.checkedDay<day?'DAY_CHECK_PENDING':
  'CURRENT';
 return {
  status:state,checkedDay:day,receiptDay:receipt.checkedDay,
  receiptCheckedAtUtc:receipt.checkedAtUtc,
  macroAsOf:estimate?.asof??null,fixingAsOf:estimate?.priceAsOf??null,
  changedSources,methodChanged,outputsMatch,datesMatch,
  changedPairs:pairDelta,changedRanks:rankDelta,
  coverage:{currencies:estimate?.currencies?.length??0,pairs:estimate?.pairs?.length??0},
  governance:{estimatedResearchOnly:true,recomputedCanonicalD:false,tradeSignal:false}
 };
}
function live(){
 const files=Object.fromEntries(Object.entries(paths).map(([key,path])=>[
  key,fs.readFileSync(path,'utf8')]));
 const sourceHashes=Object.fromEntries(Object.entries(files).map(([key,s])=>[
  key,sha256(s)]));
 const inputs=Object.fromEntries(Object.entries(files).map(([key,s])=>[
  key,JSON.parse(s)]));
 const method=sha256(fs.readFileSync('site/fx-quant-v2/next/macro-strength-estimated-v1.js','utf8')+
  '\n'+currencyRanking.toString());
 const today=dayNow();
 const estimate=evaluate({...inputs,now:today,rankingFn:currencyRanking});
 const receipt=JSON.parse(fs.readFileSync(pathReceipt,'utf8'));
 return inspect({receipt,estimate,sourceHashes,method,day:today});
}
if(require.main===module){
 const result=live();
 console.log('G8_28_RECEIPT_READINESS '+JSON.stringify(result));
 if(process.env.GITHUB_STEP_SUMMARY){
  fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,
   '\n### G8/28 estimated FX reconciliation (read-only)\n'+
   'Status: **'+result.status+'**; source changes: '+
   (result.changedSources?.join(', ')||'none')+
   '; pair changes: '+(result.changedPairs?.length??'n/a')+
   '; G8 rank changes: '+(result.changedRanks?.length??'n/a')+'\n\n'+
   'A pending status is *not* a new trading signal; the capture job must complete before it can be reported as verified.\n');
 }
 if(result.status==='RECEIPT_INVALID'||result.status==='FUTURE_RECEIPT_INVALID')
  process.exitCode=1;
}
module.exports={inspect,live,paths};
