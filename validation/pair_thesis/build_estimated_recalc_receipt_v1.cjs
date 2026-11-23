'use strict';
/* Read-only audit proof for the existing heuristic G8/28 FX re-evaluation.
 * Does not update D.json, scores, trading signals, or decision rules.
 * One receipt per materially distinct input set or Rome calendar day.
 */
const SCHEMA='GMFQ_NEXT_ESTIMATED_FX_RECALC_RECEIPT_V1';
const CURRENCIES=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const day=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s);
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function build({previous=null,history,estimate,checked,commit,method,sourceHashes}){
 if(!history||!Array.isArray(history.snapshots)||!estimate||
    estimate.status!=='STIMA_OPERATIVA_NON_VALIDATA'||
    estimate.schema!=='GMFQ_MACRO_STRENGTH_ESTIMATED_V1'||
    !Array.isArray(estimate.currencies)||estimate.currencies.length!==8||
    !Array.isArray(estimate.pairs)||estimate.pairs.length!==28||
    !day(checked?.day)||!Number.isFinite(Date.parse(checked?.utc))||
    !day(estimate.asof)||!day(estimate.priceAsOf)||
    estimate.asof>checked.day||estimate.priceAsOf>checked.day||
    typeof commit!=='string'||typeof method!=='string'||
    !sourceHashes||Object.keys(sourceHashes).sort().join(',')!=='model,observed,ois,prices,rates')
  throw Error('RECALC_RECEIPT_INVALID_INPUT');
 if(previous&&(previous.schema!==SCHEMA||!day(previous.checkedDay)||
    !previous.pairs||Object.keys(previous.pairs).length!==28||
    !Array.isArray(previous.currencies)||previous.currencies.length!==8))
  throw Error('RECALC_RECEIPT_INVALID_PRIOR');
 const pairs=Object.fromEntries(estimate.pairs.map(p=>[p.key,{
  favored:p.favored,thesis:p.thesisStrength,timing:p.tradeAttractiveness
 }]).sort(([a],[b])=>a.localeCompare(b)));
 if(Object.keys(pairs).length!==28||
    !Object.keys(pairs).every(k=>/^[A-Z]{6}$/.test(k))||
    new Set(estimate.currencies.map(x=>x.ccy)).size!==8||
    !CURRENCIES.every(c=>estimate.currencies.some(x=>x.ccy===c)))
  throw Error('RECALC_RECEIPT_G8_28_COVERAGE');
 const currencies=estimate.currencies.map(x=>({
  ccy:x.ccy,rank:x.rank,score:Number(x.score.toFixed(6)),
  macroScore:Number(x.macroScore.toFixed(6)),
  policyScore:Number(x.policyScore.toFixed(6)),
  priceScore:Number(x.priceScore.toFixed(6)),
  monetaryQuality:x.rate.quality,monetaryAsOf:x.rate.asof,
  partial:x.partial
 })).sort((a,b)=>a.ccy.localeCompare(b.ccy));
 if(currencies.some(x=>!Number.isFinite(x.score)||
    !Number.isInteger(x.rank)||x.rank<1||x.rank>8)||
    new Set(currencies.map(x=>x.rank)).size!==8)
  throw Error('RECALC_RECEIPT_G8_RANK_INVALID');
 const lastHistory=history.snapshots.at(-1)||null;
 const priorPairs=previous?.pairs||lastHistory?.pairs||null;
 const changedPairs=priorPairs?Object.entries(pairs).filter(([key,p])=>{
  const old=priorPairs[key];
  return !old||old.favored!==p.favored||old.thesis!==p.thesis||
   old.timing!==p.timing;
 }).map(([key,p])=>({key,previous:priorPairs[key]||null,current:p})):null;
 const priorRanks=new Map((previous?.currencies||[]).map(x=>[x.ccy,x.rank]));
 const changedRanks=previous?currencies.filter(x=>priorRanks.get(x.ccy)!==x.rank)
  .map(x=>({ccy:x.ccy,previous:priorRanks.get(x.ccy)??null,current:x.rank})):null;
 const inputChanges=previous?Object.keys(sourceHashes).filter(k=>
  previous.sourceHashes?.[k]!==sourceHashes[k]):null;
 const methodChanged=previous?previous.method!==method:null;
 const noChange=previous&&same(previous.sourceHashes,sourceHashes)&&
  previous.method===method&&previous.checkedDay===checked.day&&
  previous.fixingAsOf===estimate.priceAsOf&&
  previous.macroAsOf===estimate.asof&&same(previous.pairs,pairs)&&
  same(previous.currencies,currencies);
 if(noChange)return {write:false,status:'INPUTS_UNCHANGED',receipt:previous};
 const changed=(changedPairs?.length||0)+(changedRanks?.length||0);
 const status=changed?'RECALCULATED_WITH_CHANGES':
  'NO_MATERIAL_THESIS_CHANGE';
 const receipt={
  schema:SCHEMA,status,checkedAtUtc:checked.utc,checkedDay:checked.day,
  sourceCommit:commit,method,sourceHashes,
  inputChanges,methodChanged,
  comparisonBasis:previous?'PREVIOUS_RECEIPT':lastHistory?'PREVIOUS_HISTORY':'INITIAL_CAPTURE',
  previousFixingAsOf:previous?.fixingAsOf||lastHistory?.fixing||null,
  previousMacroAsOf:previous?.macroAsOf||lastHistory?.macroAsOf||null,
  fixingAsOf:estimate.priceAsOf,macroAsOf:estimate.asof,
  legacyMacroAsOf:estimate.legacyMacroAsOf,
  coverage:{currencies:8,pairs:28,official6M:estimate.coverage?.official6M??null,
   withGDPAcceleration:estimate.coverage?.withGDPAcceleration??null},
  changedPairs,changedRanks,currencies,pairs,
  governance:{estimatedNotValidated:true,recomputedCanonicalD:false,
   recomputedStructuralTheses:false,backtestCertified:false,tradeSignal:false}
 };
 return {write:true,status,receipt};
}
module.exports={SCHEMA,build};
