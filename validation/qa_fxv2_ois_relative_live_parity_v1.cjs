'use strict';
/* Deterministic 28-pair OIS page parity tests, no market fetch or Core writes. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const load=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const {compare,rateDiffBp}=require('../site/fx-quant-v2/assets/ois-relative-parity-v1.js');
const snap=load('site/fx-quant-v2/ois-pricing-snapshot.json');
const rel=load('site/fx-quant-v2/pricing-relative-28pairs-research.json');
const op=load('live_data/sections/OIS_OPERATIONAL_VIEW.json');
const est=load('live_data/sections/CB_PRICING_ESTIMATED.json');
const asShown=JSON.parse(JSON.stringify(snap.currencies));
for(const x of Object.values(asShown)){
 for(const t of ['3m','6m','12m'])Object.assign(x.horizons[t],
   {kind:x.kind,quality:x.quality,origin:'snapshot'});
}
const initial=compare(rel,asShown);
assert.ok(['MATCHED_PUBLISHED_RESEARCH','RECALCULATED_FROM_DISPLAYED_TENORS'].includes(initial.status));
assert.equal(initial.compared,84);
assert.equal(initial.rows.length,28);
assert.equal(initial.mismatches.length===0,initial.status==='MATCHED_PUBLISHED_RESEARCH');
assert.equal(initial.changedLegs.length===0,initial.mismatches.length===0);
for(const r of initial.rows)for(const h of Object.values(r.horizons)){
 assert.equal(h.fx_signal,null);
 assert.equal(h.policy_repricing_bp,null);
 assert.equal(h.spread_bp,rateDiffBp(h.base_rate_pct,h.quote_rate_pct));
}
const moving=JSON.parse(JSON.stringify(asShown));
for(const c of ['USD','EUR']){
 const old=moving[c].horizons['12m'];
 // Independent per-tenor quote source; all other tenors remain untouched.
 old.rate+=c==='USD'?-0.155:0.0075;
 old.as_of='2026-11-05';
 old.origin='live';
}
const different=compare(rel,moving);
assert.equal(different.status,'RECALCULATED_FROM_DISPLAYED_TENORS');
assert.ok(different.changedLegs.includes('EUR:12m'));
assert.ok(different.changedLegs.includes('USD:12m'));
assert.equal(different.compared,84);
assert.ok(different.mismatches.length>=13); // updated 12M legs affect 7+7 pairs less EUR/USD overlap; historical differences can coexist
const eurusd=different.rows.find(p=>p.name==='EUR/USD');
assert.ok(eurusd);
assert.equal(eurusd.horizons['12m'].spread_bp,
 rateDiffBp(moving.EUR.horizons['12m'].rate,moving.USD.horizons['12m'].rate));
assert.equal(eurusd.horizons['12m'].base_as_of,'2026-11-05');
assert.equal(eurusd.horizons['12m'].quote_as_of,'2026-11-05');
assert.equal(eurusd.horizons['6m'].spread_bp,initial.rows.find(p=>p.name==='EUR/USD').horizons['6m'].spread_bp);
const missing=JSON.parse(JSON.stringify(asShown));
missing.CHF.horizons['6m'].rate=null;
assert.equal(compare(rel,missing).status,'WAITING_FOR_24_DATED_LEVELS');
assert.equal(compare({...rel,eligible_for_fx_engine:true},asShown).status,'INVALID_RESEARCH_SOURCE');
// For the checked-in live secondary source, any newer same-contract 12M
// must not be hidden by a lagging fallback; do not freeze today-specific prices.
const current=JSON.parse(JSON.stringify(asShown));
for(const c of ['USD','EUR','CHF']){
 const e=est.currencies?.[c];if(e?.status!=='ESTIMATED_ACTIVE')continue;
 for(const t of ['3m','6m','12m']){
  const f=e.horizons?.[t],h=current[c].horizons[t];
  if(!f||!f.quote_as_of||!Number.isFinite(f.rate))continue;
  if(f.quote_as_of>=h.as_of){
   Object.assign(h,{rate:f.rate,as_of:f.quote_as_of,
      contract:f.contract||null,kind:'FUTURES SECONDARI',
      quality:'STIMA INDICATIVA',origin:'live'});
  }
 }
}
const actual=compare(rel,current);
assert.equal(actual.compared,84);
assert.equal(actual.rows.length,28);
assert.equal(actual.read_only,true);
assert.equal(actual.fx_signal_generated,false);
assert.equal(actual.policy_repricing_generated,false);
console.log('FXV2_OIS_28PAIR_RECONCILIATION_PASS',
 JSON.stringify({pairs:actual.rows.length,comparisons:actual.compared,
 mismatches:actual.mismatches.length,changedLegs:actual.changedLegs,
 stale_saved_pair_recomputations:different.mismatches.length}));
