'use strict';
/* Forward-only archive of the exact estimate evaluated by the Next desk. */
const fs=require('node:fs');
const {createHash}=require('node:crypto');
const {evaluate}=require('../../site/fx-quant-v2/next/macro-strength-estimated-v1.js');
const {currencyRanking}=require('../../site/fx-quant-v2/next/pair-rankings.js');
const schema='GMFQ_NEXT_ESTIMATED_FX_THESIS_HISTORY_V1';
const version='GMFQ_MACRO_STRENGTH_ESTIMATED_V1';
const sources={
 observed:'site/control-room-preview/macro-v3-current-evidence.json',
 prices:'live_data/sections/ECB_G8_PRICE_HISTORY.json',
 ois:'site/fx-quant-v2/ois-pricing-snapshot.json',
 rates:'live_data/sections/NATIVE_RATES_DATA.json',
 model:'live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'
};
const engine='site/fx-quant-v2/next/macro-strength-estimated-v1.js';
const read=path=>JSON.parse(fs.readFileSync(path,'utf8'));
const hash=s=>createHash('sha256').update(s).digest('hex');
const day=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
const utc=x=>typeof x==='string'&&x.endsWith('Z')?Date.parse(x):NaN;
function update(history,estimate,{checked,commit,method,sourceHashes}){
 if(history.schema!==schema||!Array.isArray(history.snapshots)||
    history.snapshots.some((s,i)=>!day(s.fixing)||!day(s.macroAsOf)||!Number.isFinite(utc(s.capturedAt))||
    Object.keys(s.pairs||{}).length!==28||(i>0&&(s.fixing<history.snapshots[i-1].fixing||
    s.macroAsOf<history.snapshots[i-1].macroAsOf||utc(s.capturedAt)<=utc(history.snapshots[i-1].capturedAt)))))
  throw Error('Invalid estimated thesis archive');
 if(estimate.status!=='STIMA_OPERATIVA_NON_VALIDATA'||estimate.schema!==version||estimate.pairs.length!==28)
  return {history,status:'ESTIMATE_SUSPENDED',reason:estimate.reason};
 const fixing=estimate.priceAsOf;
 const prior=history.snapshots.at(-1);
 if(!day(fixing)||!day(estimate.asof)||fixing>checked.day||estimate.asof>checked.day||
    !Number.isFinite(utc(checked.utc)))
  throw Error('Invalid fixing, macro date or capture instant on estimate');
 if(prior&&(fixing<prior.fixing||estimate.asof<prior.macroAsOf))
  return {history,status:'OLDER_INPUTS',fixing};
 const pairs=Object.fromEntries(estimate.pairs.map(x=>[x.key,{
  favored:x.favored, thesis:x.thesisStrength, timing:x.tradeAttractiveness
 }]).sort(([a],[b])=>a.localeCompare(b)));
 if(Object.keys(pairs).length!==28)throw Error('Expected 28 distinct pairs');
 const changedPairs=prior?Object.entries(pairs).filter(([key,row])=>{
  const previous=prior.pairs[key];
  return !previous||row.favored!==previous.favored||row.thesis!==previous.thesis||row.timing!==previous.timing;
 }).length:28;
 if(prior&&fixing===prior.fixing&&method===prior.method&&changedPairs===0)
  return {history,status:'NO_MATERIAL_THESIS_CHANGE',fixing,changedPairs};
 if(prior&&utc(checked.utc)<=utc(prior.capturedAt))
  throw Error('New capture must follow the archived capture');
 const snapshot={fixing,macroAsOf:estimate.asof,capturedAt:checked.utc,commit,method,sourceHashes,pairs};
 return {history:{schema,snapshots:[...history.snapshots,snapshot].slice(-35)},status:'RECORDED',fixing,changedPairs};
}
if(require.main===module){
 const [archive,output,commit]=process.argv.slice(2);
 if(!archive||!output||!commit)throw Error('Usage: updater archive.json output.json sourceCommit');
 const now=new Date();
 const checked={utc:now.toISOString(),day:new Intl.DateTimeFormat('sv-SE',{
  timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'
 }).format(now)};
 const inputs=Object.fromEntries(Object.entries(sources).map(([key,path])=>[key,fs.readFileSync(path,'utf8')]));
 const modelInputs=Object.fromEntries(Object.entries(inputs).map(([key,body])=>[key,JSON.parse(body)]));
 // Fingerprint only the two method definitions that the estimate actually calls.
 const method=hash(fs.readFileSync(engine,'utf8')+'\n'+currencyRanking.toString());
 const sourceHashes=Object.fromEntries(Object.entries(inputs).map(([key,body])=>[key,hash(body)]));
 const estimate=evaluate({...modelInputs,now:checked.day,rankingFn:currencyRanking});
 const result=update(read(archive),estimate,{checked,commit,method,sourceHashes});
 if(result.status==='RECORDED')fs.writeFileSync(output,JSON.stringify(result.history,null,2)+'\n');
 if(result.status==='ESTIMATE_SUSPENDED'||result.status==='OLDER_INPUTS')process.exitCode=1;
 console.log(JSON.stringify({status:result.status,fixing:result.fixing,macroAsOf:estimate.asof,
  changedPairs:result.changedPairs,reason:result.reason,count:result.history.snapshots.length}));
}
module.exports={schema,version,update};
