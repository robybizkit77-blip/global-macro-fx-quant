'use strict';
/* Deterministic production-engine -> receipt -> Home scenario on CLONED inputs.
 * This DOES NOT mutate any market files or publish a synthetic FX signal.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {createHash}=require('node:crypto');
const ROOT=path.resolve(__dirname,'../..');
const rd=p=>fs.readFileSync(path.join(ROOT,p),'utf8');
const json=p=>JSON.parse(rd(p));
const clone=x=>structuredClone(x);
const hash=s=>createHash('sha256').update(s).digest('hex');
const engine=require('../../site/fx-quant-v2/next/macro-strength-estimated-v1.js');
const rank=require('../../site/fx-quant-v2/next/pair-rankings.js');
const proof=require('../../site/fx-quant-v2/next/home-thesis-recalc-v1.js');
const {build}=require('../pair_thesis/build_estimated_recalc_receipt_v1.cjs');
const paths={
 observed:'site/control-room-preview/macro-v3-current-evidence.json',
 prices:'live_data/sections/ECB_G8_PRICE_HISTORY.json',
 ois:'site/fx-quant-v2/ois-pricing-snapshot.json',
 rates:'live_data/sections/NATIVE_RATES_DATA.json',
 model:'live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'
};
const raw=Object.fromEntries(Object.entries(paths).map(([k,p])=>[k,rd(p)]));
const sources=Object.fromEntries(Object.entries(raw).map(([k,v])=>[k,hash(v)]));
const inputs=Object.fromEntries(Object.entries(raw).map(([k,v])=>[k,JSON.parse(v)]));
const now=inputs.observed.generated_europe_rome_day;
const compute=(observed,ois)=>engine.evaluate({
 ...inputs,observed,ois,now,rankingFn:rank.currencyRanking
});
const original=compute(inputs.observed,inputs.ois);
assert.equal(original.status,'STIMA_OPERATIVA_NON_VALIDATA',original.reason);
const history={snapshots:[]},method='test-engine-method',commit='test-commit';
const base=build({history,estimate:original,
 checked:{day:now,utc:now+'T09:00:00.000Z'},commit,method,sourceHashes:sources});
assert.equal(base.status,'BASELINE_RECALC');
assert.equal(proof.receiptOK(base.receipt),true);
const view=(receipt,estimate,observed,sourceHashes)=>proof.render({
 receipt,estimate,observed,sourceHashes,prices:inputs.prices,today:now
});
assert.match(view(base.receipt,original,inputs.observed,sources),/data-recalc-state="baseline"/);
const syntheticMacro=clone(inputs.observed),syntheticOis=clone(inputs.ois);
// Controlled release/repricing shock within the SAME reference date. No source
// file is changed and the engine retains all its real gates and weights.
syntheticMacro.countries.GBP.growth.nonannualized_qoq_descriptive_pct=-0.9;
syntheticMacro.countries.GBP.labour.change_over_three_observation_intervals_pp=0.8;
syntheticMacro.countries.GBP.labour.change_direction='UP';
syntheticOis.currencies.GBP.horizons['6m'].change_1w_bp=-35;
const after=compute(syntheticMacro,syntheticOis);
assert.equal(after.status,'STIMA_OPERATIVA_NON_VALIDATA',after.reason);
const beforeGBP=original.currencies.find(c=>c.ccy==='GBP');
const afterGBP=after.currencies.find(c=>c.ccy==='GBP');
assert(afterGBP.score<beforeGBP.score,'Real estimator must respond to a lower GBP economic and rates score');
const updatedSources={...sources,
 observed:hash(JSON.stringify(syntheticMacro)),
 ois:hash(JSON.stringify(syntheticOis))};
const outdated=view(base.receipt,after,syntheticMacro,updatedSources);
assert.match(outdated,/data-recalc-state="UNVERIFIED"/);
assert.doesNotMatch(outdated,/data-recalc-state="baseline"/);
const changed=build({previous:base.receipt,history,estimate:after,
 checked:{day:now,utc:now+'T10:00:00.000Z'},commit,method,
 sourceHashes:updatedSources});
assert.equal(changed.status,'RECALCULATED_WITH_CHANGES',
 'The controlled shock must change the current 28 pair thesis or G8 ranks');
assert((changed.receipt.changedPairs?.length||0)>0,
 'A real estimated FX pair judgment must change in the shock fixture');
assert((changed.receipt.changedRanks?.length||0)>0,
 'A real G8 currency rank must change in the shock fixture');
assert.deepEqual(changed.receipt.inputChanges,['observed','ois']);
const updated=view(changed.receipt,after,syntheticMacro,updatedSources);
assert.match(updated,/data-recalc-state="changed"/);
assert.match(updated,/Cambiamenti da verificare/);
assert.match(updated,/Nuove impronte nei file: Macro G8, OIS \/ futures/);
assert.match(updated,/Classifica 28 coppie/);
// Change the policy observation again with the same date and retain the old
// receipt: no stale "new FX thesis" is allowed to survive content divergence.
const further=clone(after);
further.pairs[0].thesisStrength='NON DISTINTA';
assert.match(view(changed.receipt,further,syntheticMacro,updatedSources),
 /data-recalc-state="UNVERIFIED"/);
console.log('NEXT_HOME_G8_28_ENDTOEND_SHOCK_PASS: real engine recalculated on cloned macro/OIS inputs; receipt detected GBP rank and FX thesis revisions; same-day stale proof withheld; no production mutation');
