'use strict';
const assert=require('node:assert/strict');
const {build,SCHEMA}=require('./build_estimated_recalc_receipt_v1.cjs');
const {pairs}=require('../../live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const estimate={
 status:'STIMA_OPERATIVA_NON_VALIDATA',
 schema:'GMFQ_MACRO_STRENGTH_ESTIMATED_V1',
 asof:'2026-11-23',priceAsOf:'2026-11-20',legacyMacroAsOf:'2026-09-25',
 coverage:{official6M:4,withGDPAcceleration:5},
 currencies:FX.map((ccy,i)=>({
  ccy,rank:i+1,score:1-i/4,macroScore:.5-i/5,policyScore:i/10,
  priceScore:.2-i/10,rate:{quality:i<4?'UFFICIALE':'PROXY',asof:'2026-11-20'},partial:i>=4
 })),
 pairs:Object.keys(pairs).map(key=>({key,favored:key.slice(0,3),
  thesisStrength:'PARZIALE',tradeAttractiveness:'DA VALIDARE'}))
};
const checked={day:'2026-11-23',utc:'2026-11-23T12:00:00Z'};
const sourceHashes={observed:'a',prices:'b',ois:'c',rates:'d',model:'e'};
const args={history:{snapshots:[]},estimate,checked,commit:'test-commit',method:'method-v1',sourceHashes};
const baseline=build(args);
assert.equal(baseline.write,true);
assert.equal(baseline.status,'BASELINE_RECALC');
assert.equal(baseline.receipt.schema,SCHEMA);
assert.equal(Object.keys(baseline.receipt.pairs).length,28);
assert.equal(baseline.receipt.currencies.length,8);
assert.equal(baseline.receipt.legacyMacroAsOf,'2026-09-25');
assert.equal(baseline.receipt.factorChanges,null,'Initial receipt cannot invent previous component scores');
assert.deepEqual(baseline.receipt.governance,{estimatedNotValidated:true,
 recomputedCanonicalD:false,recomputedStructuralTheses:false,
 backtestCertified:false,tradeSignal:false});
const repeat=build({...args,previous:baseline.receipt,commit:'unrelated-main-commit'});
assert.equal(repeat.write,false,'No duplicate commit for identical source evidence on the same day');
assert.equal(repeat.status,'INPUTS_UNCHANGED');
const refreshed=build({...args,previous:baseline.receipt,
 checked:{day:'2026-11-23',utc:'2026-11-23T12:10:00Z'},
 sourceHashes:{...sourceHashes,observed:'fresh-observed'}});
assert.equal(refreshed.write,true,'Material source refresh requires an audit receipt');
assert.equal(refreshed.status,'NO_MATERIAL_THESIS_CHANGE',
 'Identical thesis outputs after changed data must be proved, not ignored');
assert.deepEqual(refreshed.receipt.inputChanges,['observed']);
assert.deepEqual(refreshed.receipt.changedPairs,[]);
assert.deepEqual(refreshed.receipt.changedRanks,[]);
assert.deepEqual(refreshed.receipt.factorChanges,[],
 'New data with unchanged model outputs must record zero factor deltas');
assert.equal(refreshed.receipt.comparisonBasis,'PREVIOUS_RECEIPT');
const dayHeartbeat=build({...args,previous:baseline.receipt,
 checked:{day:'2026-11-24',utc:'2026-11-24T07:30:00Z'}});
assert.equal(dayHeartbeat.write,true,'Once per Rome day the input check must be durable');
assert.equal(dayHeartbeat.status,'NO_MATERIAL_THESIS_CHANGE');
assert.deepEqual(dayHeartbeat.receipt.inputChanges,[]);
const revised=structuredClone(estimate);
revised.pairs[0].favored=revised.pairs[0].key.slice(3);
const usd=revised.currencies.find(x=>x.ccy==='USD');
const eur=revised.currencies.find(x=>x.ccy==='EUR');
[usd.rank,eur.rank]=[eur.rank,usd.rank];
eur.policyScore-=0.5;
eur.score-=0.15;
const changed=build({...args,previous:refreshed.receipt,estimate:revised,
 checked:{day:'2026-11-23',utc:'2026-11-23T12:20:00Z'},
 sourceHashes:{...sourceHashes,observed:'fresh-observed',prices:'new-fixing'}});
assert.equal(changed.write,true);
assert.equal(changed.status,'RECALCULATED_WITH_CHANGES');
assert.deepEqual(changed.receipt.inputChanges,['prices']);
assert.equal(changed.receipt.changedPairs.length,1);
assert.equal(changed.receipt.changedRanks.length,2);
assert.equal(changed.receipt.changedPairs[0].key,revised.pairs[0].key);
assert.equal(changed.receipt.changedPairs[0].current.favored,revised.pairs[0].favored);
const eurFactors=changed.receipt.factorChanges.find(x=>x.ccy==='EUR');
assert(eurFactors,'EUR changed its monetary factor and must get a comparison receipt');
assert.equal(eurFactors.changes.policyScore.delta,-0.5);
assert.equal(eurFactors.changes.score.delta,-0.15);
assert.equal(eurFactors.changes.macroScore.delta,0);
assert.equal(eurFactors.changes.priceScore.delta,0);
assert.deepEqual(eurFactors.rank,{previous:FX.indexOf('EUR')+1,
 current:FX.indexOf('USD')+1});
const usdFactors=changed.receipt.factorChanges.find(x=>x.ccy==='USD');
assert(usdFactors,'A pure relative rank move also needs a trace');
assert.equal(usdFactors.changes.score.delta,0);
assert.equal(usdFactors.changes.policyScore.delta,0);
assert.notEqual(usdFactors.rank.previous,usdFactors.rank.current);
const methodChanged=build({...args,previous:baseline.receipt,method:'method-v2'});
assert.equal(methodChanged.write,true);
assert.equal(methodChanged.receipt.methodChanged,true);
assert.deepEqual(methodChanged.receipt.inputChanges,[]);
assert.throws(()=>build({...args,estimate:{...estimate,pairs:estimate.pairs.slice(1)}}),/RECALC_RECEIPT_INVALID_INPUT/);
assert.throws(()=>build({...args,estimate:{...estimate,asof:'2026-11-24'}}),/RECALC_RECEIPT_INVALID_INPUT/);
assert.throws(()=>build({...args,previous:{schema:'MALFORMED'}}),/RECALC_RECEIPT_INVALID_PRIOR/);
console.log('ESTIMATED_G8_28_RECALC_RECEIPT_PASS: input delta, no-change evidence, rank/thesis changes, daily idempotence, core isolation');
