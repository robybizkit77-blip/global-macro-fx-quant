'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
const {derive}=require('../site/fx-quant-v2/assets/rates-working-model-v1.js');
const research=JSON.parse(fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/chf-nzd-benchmark-research.json')));
const canonical=JSON.parse(fs.readFileSync(path.join(ROOT,'live_data/sections/NATIVE_RATES_DATA.json')));
const today='2026-11-04',before=JSON.stringify(canonical);
const working=derive(canonical,research,today);
assert.equal(working.schema,'GMFQ_FXV2_WORKING_RATES_V1');
assert.equal(working.eligible_for_fx_engine,false);
assert.equal(working.eligible_for_backtests,false);
assert.deepEqual(Object.keys(working.rates).sort(),['CHF','NZD']);
const chf=working.rates.CHF,nzd=working.rates.NZD;
assert.equal(chf['2Y'],.242);
assert.equal(chf['10Y'],.509);
assert.equal(chf.curve_bp,26.7);
assert.equal(chf.chg2_bp,.4);
assert.equal(chf.chg10_bp,.4);
assert.equal(chf.estimated,true);
assert.equal(chf.tenor_quality['2Y'],'STIMATO');
assert.equal(chf.tenor_quality['10Y'],'OSSERVATO');
assert.equal(chf.date,'2026-11-03');
assert.equal(chf.source_date,'2026-10-30');
assert.equal(nzd['2Y'],3.95);
assert.equal(nzd['10Y'],4.88);
assert.equal(nzd.curve_bp,93);
assert.equal(nzd.chg2_bp,-1);
assert.equal(nzd.chg10_bp,-2);
assert.equal(nzd.date,'2026-11-03');
assert.equal(nzd.no_cross_roll_change,true);
assert.equal(JSON.stringify(canonical),before,'Canonical source must remain unmodified');
assert.equal(research.NZD.source_capture_method,'OFFICIAL_WEB_PAGE_RESEARCH_CAPTURE_NOT_GITHUB_DOWNLOAD');
assert.equal(research.NZD.source_release_date,'2026-11-04');
assert.equal(research.NZD.independent_xlsx_reconciled,false);
assert.equal(Math.round((chf['2Y']-nzd['2Y'])*1000)/10,-370.8,'2Y CHF-NZD working spread in bp');
assert.equal(Math.round((chf['10Y']-nzd['10Y'])*1000)/10,-437.1,'10Y CHF-NZD working spread in bp');
const copy=x=>JSON.parse(JSON.stringify(x));
let future=copy(research);
future.CHF.separate_10y.as_of='2026-11-05';
assert.equal(derive(canonical,future,today).rates.CHF,undefined,'Never use future market data');
let bad=copy(research);
bad.CHF.curve_bp=95;
assert.equal(derive(canonical,bad,today).rates.CHF,undefined,'Mismatched SNB same-date curve rejected');
bad=copy(research);bad.NZD.after_roll[0].date='2026-10-29';
assert.equal(derive(canonical,bad,today).rates.NZD,undefined,'Do not bridge NZD old/new benchmark');
bad=copy(research);bad.NZD.independent_xlsx_reconciled=true;
assert.equal(derive(canonical,bad,today).rates.NZD,undefined,'Review status must agree with source provenance');
const updated=copy(canonical);
updated.CHF.date='2026-11-04';updated.NZD.date='2026-11-04';
assert.equal(Object.keys(derive(updated,research,today).rates).length,0,'Official newer source takes priority');
const wrong=copy(research);wrong.eligible_for_fx_pair_engine=true;
assert.equal(Object.keys(derive(canonical,wrong,today).rates).length,0,'Reject write-permission drift');
const stale=derive(canonical,research,'2026-12-01');
assert.deepEqual(Object.keys(stale.rates).sort(),['CHF','NZD'],
  'Preserve signed historical research levels when new source access is unavailable');
for(const c of ['CHF','NZD']){
  const row=stale.rates[c];
  assert.equal(row.stale_source,true,'Must explicitly label stale '+c);
  assert.equal(row.freshness,'DATED_RESEARCH_NO_CURRENT_MARKET_MOVE');
  assert.ok(row.quality.includes('RIFERIMENTO STORICO'));
  assert.equal(row.date,'2026-11-03','Never relabel old quote as current');
  assert.equal(row.chg2_bp,null,'Historical move must not be represented as today');
  assert.equal(row.chg10_bp,null,'Historical move must not be represented as today');
  assert.equal(row.no_core_effect,true,'Scenario does not alter Core');
  assert.equal(row.source_age_days,28);
}
assert.equal(JSON.stringify(canonical),before,'Stale research must never rewrite canonical source');
const futureAsOf=copy(research);
futureAsOf.NZD.latest_date='2026-12-02';
assert.equal(derive(canonical,futureAsOf,'2026-12-01').rates.NZD,undefined,
  'No future government quote in stale fallback');
const tassi=fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/tassi.html'),'utf8');
assert.ok(tassi.includes("svgCurves(r);if(r.estimated)"),'Estimate caveat must remain after SVG rendering');
assert.ok(tassi.includes("I differenziali sono calcoli aritmetici"),'V2 comparison must label estimates');
assert.ok(tassi.includes('const local="./chf-nzd-benchmark-research.json"') &&
          tassi.includes('try{x=await read(local);}'),
  'Tassi must prefer the version-matched published research copy');
assert.ok(tassi.includes('x=await read(remote)'),
  'Tassi should recover from a broken local publication');
assert.ok(tassi.includes("RIFERIMENTO STORICO")===false,
  'Stale classification belongs in the shared working model, not hardcoded HTML');
const coppie=fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/coppie.html'),'utf8');
assert.ok(coppie.includes('rates-working-model-v1.js?v=1'),'Coppie must reuse the validated Tassi estimator');
assert.ok(coppie.includes("const local='./chf-nzd-benchmark-research.json'") &&
          coppie.includes("try{research=await load(local);}"),
  'Coppie must prefer version-matched local research');
assert.ok(coppie.includes('research=await load(remote)'),
  'Coppie must retain an external recovery route');
assert.ok(coppie.includes('STIMA/PROXY INDICATIVO'),'Coppie must visibly label scenario levels');
assert.ok(coppie.includes('model.eligible_for_fx_engine!==false'),'Coppie must keep estimates out of the engine');
assert.ok(coppie.includes('id="pairRatesSourceNote"'),'Coppie must expose research caveats');
console.log('FXV2_WORKING_RATE_TESTS PASS CHF 2Y '+chf['2Y']+'% (estimate), CHF 10Y '+chf['10Y']+'% (observed); NZD 2Y '+nzd['2Y']+'%, NZD 10Y '+nzd['10Y']+'% (B2 web research); computed spread '+(-370.8)+' bp; canonical unchanged');
