'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const live=n=>JSON.parse(fs.readFileSync(path.join(root,'live_data/sections',n+'.json'),'utf8'));
const site=n=>JSON.parse(fs.readFileSync(path.join(root,'site/fx-quant-v2',n),'utf8'));
const {readiness}=require('./fxv2_research_core_readiness_v1.cjs');
const args={
 today:'2026-11-04',
 gov:live('NATIVE_RATES_DATA'),
 govResearch:site('chf-nzd-benchmark-research.json'),
 oisCore:live('OIS_OPERATIONAL_VIEW'),
 oisResearch:site('ois-pricing-snapshot.json'),
 macroObserved:JSON.parse(fs.readFileSync(path.join(root,'site/control-room-preview/macro-v3-current-evidence.json'),'utf8')),
 fxPairs:live('PAIR_SETUP_OPERATIONAL_VIEW'),
 sourceAudit:{status:'DATA_GAPS_PRESENT',summary:{v2_pages:12,gaps:7,review_notes:4}}
};
const clone=x=>JSON.parse(JSON.stringify(x));
const x=readiness(args);
assert.equal(x.research.website_pages,12);
assert.equal(x.research.rate_pricing_horizons,24);
assert.deepEqual(x.research.official_ois_currencies,['GBP']);
assert.equal(x.research.other_futures_or_proxy_currencies.length,7);
assert.equal(x.trading_core.state,'NOT_REVALIDATED_FROM_RESEARCH');
assert.equal(x.trading_core.baseline_macro_as_of,'2026-09-25');
assert.equal(x.trading_core.baseline_was_recomputed,false);
assert(x.trading_core.noncertified_policy_pricing_currencies.includes('CHF'));
assert(x.trading_core.noncertified_policy_pricing_currencies.includes('NZD'));
assert(x.research.source_as_of_mismatches.some(y=>y.ccy==='USD'));
assert(x.research.source_as_of_mismatches.some(y=>y.ccy==='EUR'));
assert.equal(x.research.nzd_post_roll_research,'2026-11-03');
assert.equal(x.research.chf_same_date_research,'2026-10-30');
assert.equal(x.trading_core.source_data_used_for_backtests,false);
let bad=clone(args);bad.oisResearch.currencies.CHF.kind='OIS';
assert.throws(()=>readiness(bad),/OIS/);
bad=clone(args);bad.macroObserved.safe_to_recompute_structural_pair_theses=true;
assert.throws(()=>readiness(bad),/isolation/);
bad=clone(args);bad.oisResearch.currencies.USD.horizons['3m'].as_of='2026-11-05';
assert.throws(()=>readiness(bad),/invalid/);
bad=clone(args);bad.govResearch.eligible_for_fx_pair_engine=true;
assert.throws(()=>readiness(bad),/not isolated/);
bad=clone(args);bad.sourceAudit.summary.v2_pages=11;
assert.throws(()=>readiness(bad),/twelve/);
console.log('FXV2_DUAL_TRACK_READINESS_PASS research=12pages/24levels/8currencies, GBP-only OIS, FX Core not recertified');
