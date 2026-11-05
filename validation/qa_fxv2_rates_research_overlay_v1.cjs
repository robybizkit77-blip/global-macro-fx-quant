'use strict';
// Verify V2 research overlays only: observed RBA F2 weekly data and
// CHF/NZD scenario/proxy must never overwrite canonical FX Core.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
require('../site/fx-quant-v2/assets/rates-working-model-v1.js');
const {apply,load}=require('../site/fx-quant-v2/assets/rates-research-overlay-v1.js');
const read=path=>JSON.parse(fs.readFileSync(ROOT+'/'+path,'utf8'));
const original=read('live_data/sections/NATIVE_RATES_DATA.json');
const research=read('site/fx-quant-v2/chf-nzd-benchmark-research.json');
const aud=read('site/fx-quant-v2/aud-rba-f2-research.json');
const anchor=read('site/fx-quant-v2/nzd-asx-government-anchor-v1.json');
const proxy=read('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json');
const clone=x=>JSON.parse(JSON.stringify(x)), before=JSON.stringify(original);
const observed=apply({canonical:original,research,aud,proxy,anchor,today:'2026-11-05'});
assert.equal(observed.schema,'GMFQ_FXV2_RESEARCH_RATES_SHARED_V1');
assert.equal(observed.eligible_for_fx_engine,false);
assert.equal(observed.eligible_for_backtests,false);
assert.equal(observed.no_core_effect,true);
assert.equal(observed.rates.CHF.date,research.CHF.separate_10y.as_of);
assert.equal(observed.rates.CHF.tenor_quality['2Y'],'STIMATO');
assert.equal(observed.rates.CHF.tenor_quality['10Y'],'OSSERVATO');
assert.equal(observed.rates.CHF.chg2_bp,null);
assert.equal(observed.rates.CHF.no_core_effect,true);
assert.equal(observed.rates.NZD.date,research.NZD.latest_date);
assert.equal(observed.rates.NZD['2Y'],research.NZD.latest_2Y);
assert.equal(observed.rates.NZD.chg2_bp,null);
assert.equal(observed.rates.NZD.no_core_effect,true);
assert.equal(observed.rates.AUD.date,original.AUD.date,
 'An unchanged weekly RBA observation does not imply a new quote');
assert.deepEqual(observed.applied.sort(),['CHF','NZD']);
assert.equal(JSON.stringify(original),before,'V2 must never mutate canonical rates');
const futureF2=clone(aud);
futureF2.as_of='2026-11-04';futureF2.previous_same_series_as_of='2026-11-03';
futureF2.publication_date='2026-11-06';
futureF2['2Y']=4.921;futureF2['10Y']=5.211;futureF2.curve_bp=29;
futureF2.change_2y_bp=-2;futureF2.change_10y_bp=1.5;
const publishDay='2026-11-07';
const published=apply({canonical:original,research,proxy,anchor,aud:futureF2,today:publishDay});
assert.ok(published.applied.includes('AUD'));
assert.equal(published.rates.AUD.date,'2026-11-04');
assert.equal(published.rates.AUD.working_method,'RBA_F2_SAME_DATE_OBSERVED_RESEARCH');
assert.equal(published.rates.AUD.tenor_quality['2Y'],'OSSERVATO');
assert.equal(published.rates.AUD.tenor_quality['10Y'],'OSSERVATO');
assert.equal(published.rates.AUD['2Y'],4.921);
assert.equal(published.rates.AUD.chg2_bp,-2);
assert.equal(published.rates.AUD.no_core_effect,true);
assert.equal(published.rates.AUD.eligible_for_fx_engine,undefined);
const bad=clone(futureF2);bad.eligible_for_core=true;
assert.equal(apply({canonical:original,aud:bad,today:publishDay}).rates.AUD.date,original.AUD.date);
bad.eligible_for_core=false;bad.source_url='https://untrusted.invalid/f2';
assert.equal(apply({canonical:original,aud:bad,today:publishDay}).rates.AUD.date,original.AUD.date);
bad.source_url=aud.source_url;bad.curve_bp=999;
assert.equal(apply({canonical:original,aud:bad,today:publishDay}).rates.AUD.date,original.AUD.date);
bad.curve_bp=29;bad.publication_date='2026-11-08';
assert.equal(apply({canonical:original,aud:bad,today:publishDay}).rates.AUD.date,original.AUD.date);
const superseding=clone(original);
superseding.AUD.date='2026-11-05';
assert.equal(apply({canonical:superseding,aud:futureF2,today:publishDay}).rates.AUD.date,
 superseding.AUD.date,'Canonical same/newer official rate always wins');
const stale=apply({canonical:original,aud:futureF2,today:'2026-11-28'});
assert.ok(stale.rates.AUD.quality.includes('RIFERIMENTO STORICO'));
assert.equal(stale.rates.AUD.date,'2026-11-04','Do not relabel last observed rate as current');
const fakeASX=clone(proxy);
fakeASX.as_of='2026-11-05';
fakeASX.horizons['6m'].implied_bank_bill_rate=
 Number((anchor.asx_6m_rate-.08).toFixed(4));
const shifted=apply({canonical:original,research,proxy:fakeASX,anchor,today:'2026-11-05'});
assert.equal(shifted.rates.NZD.working_method,'NZD_ASX_6M_PARALLEL_SHIFT_SCENARIO');
assert.equal(shifted.rates.NZD.tenor_quality['2Y'],'STIMATO');
assert.equal(shifted.rates.NZD.tenor_quality['10Y'],'STIMATO');
assert.equal(shifted.rates.NZD.chg2_bp,null);
assert.equal(shifted.rates.NZD.no_inferred_market_move,true);
const moved=clone(original);
moved.NZD.date='2026-11-06';
const kept=apply({canonical:moved,research,proxy:fakeASX,anchor,today:'2026-11-06'});
assert.equal(kept.rates.NZD.date,moved.NZD.date,'Never displace newer sovereign canonical');
assert.equal(JSON.stringify(original),before);
for(const page of ['valute','macro','coppie']){
 const html=fs.readFileSync(ROOT+'/site/fx-quant-v2/'+page+'.html','utf8');
 assert.ok(html.includes('assets/rates-research-overlay-v1.js?v=1'),
  page+' must use the shared versioned V2 rates overlay');
}
const valute=fs.readFileSync(ROOT+'/site/fx-quant-v2/valute.html','utf8');
assert.ok(valute.includes('const ratesView=effective?.rates||rates'));
assert.ok(valute.includes("q2==='STIMATO'"));
assert.ok(valute.includes('Δ giornaliera non inferita'));
const macro=fs.readFileSync(ROOT+'/site/fx-quant-v2/macro.html','utf8');
assert.ok(macro.includes('const ratesView=effective?.rates||rates'));
assert.ok(macro.includes("r.tenor_quality?.['10Y']"));
const coppie=fs.readFileSync(ROOT+'/site/fx-quant-v2/coppie.html','utf8');
assert.ok(coppie.includes("update?.applied?.includes('AUD')"));
assert.ok(coppie.includes('RBA F2 2Y · RICERCA'));
(async()=>{
 const sources={
  './chf-nzd-benchmark-research.json':research,
  './aud-rba-f2-research.json':futureF2,
  './nzd-asx-government-anchor-v1.json':anchor
 };
 const fetchJson=async url=>{
  if(url in sources)return clone(sources[url]);
  if(url.endsWith('/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'))return clone(fakeASX);
  throw Error('Unexpected source request '+url);
 };
 const live=await load({canonical:original,today:publishDay,fetchJson});
 assert.deepEqual(live.applied.sort(),['AUD','CHF','NZD']);
 assert.equal(live.rates.NZD.working_method,'NZD_ASX_6M_PARALLEL_SHIFT_SCENARIO');
 assert.equal(JSON.stringify(original),before);
 console.log('FXV2_SHARED_RATES_RESEARCH_PASS: Valute Macro Coppie; CHF/NZD/AUD dated research, future RBA F2, ASX scenario, source guards and Core isolation');
})().catch(error=>{console.error(error);process.exitCode=1});
