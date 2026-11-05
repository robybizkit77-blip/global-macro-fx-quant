'use strict';
// Verify V2 research overlays only: observed RBA F2 weekly data and
// CHF/NZD scenario/proxy must never overwrite canonical FX Core.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
require('../site/fx-quant-v2/assets/rates-working-model-v1.js');
const {apply,load}=require('../site/fx-quant-v2/assets/rates-research-overlay-v1.js');
const read=path=>JSON.parse(fs.readFileSync(ROOT+'/'+path,'utf8'));
// Actual feeds are allowed to advance: verify current source contracts
// separately, never assert that live observations remain frozen on Nov 4.
const canonicalLive=read('live_data/sections/NATIVE_RATES_DATA.json');
const researchLive=read('site/fx-quant-v2/chf-nzd-benchmark-research.json');
const audLive=read('site/fx-quant-v2/aud-rba-f2-research.json');
const proxyLive=read('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json');
const anchor=read('site/fx-quant-v2/nzd-asx-government-anchor-v1.json');
const clone=x=>JSON.parse(JSON.stringify(x));
assert.equal(researchLive.schema,'GMFQ_FXV2_CHF_NZD_BENCHMARK_RESEARCH_V1');
assert.equal(researchLive.eligible_for_fx_pair_engine,false);
assert.equal(researchLive.eligible_for_backtests,false);
assert.equal(researchLive.canonical_government_rates_untouched,true);
assert.equal(audLive.schema,'GMFQ_FXV2_AUD_RBA_F2_RESEARCH_V1');
assert.equal(audLive.eligible_for_core,false);
assert.equal(audLive.eligible_for_fx_pair_engine,false);
assert.equal(audLive.eligible_for_backtests,false);
assert.equal(audLive.source_download_verified,true);
assert.equal(audLive.same_date_same_source,true);
assert.equal(proxyLive.schema,'GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1');
assert.equal(proxyLive.governance.pair_engine_effect,'NONE');
assert.equal(proxyLive.governance.policy_delta_from_proxy_allowed,false);
assert.equal(proxyLive.source_quality,'OFFICIAL_EXCHANGE_DIRECTIONAL_PROXY');
assert.ok(proxyLive.as_of>=anchor.asx_6m_as_of,
 'New genuine exchange data may advance from the scenario anchor');
assert.ok(audLive.as_of>='2026-10-28',
 'A newly published RBA F2 observation must not roll back');
assert.ok(researchLive.NZD.latest_date>=anchor.government_as_of,
 'Source-verified RBNZ B2 research can advance, not roll backwards');

// Static regression fixture: never reuse changing live rates/dates as
// assumptions in the deterministic Nov 2026 scenario tests.
const original=clone(canonicalLive);
original.AUD={...original.AUD,date:'2026-10-28','2Y':4.951,'10Y':5.208};
original.CHF={...original.CHF,date:'2026-09-30','2Y':0.287,'10Y':0.586};
original.NZD={...original.NZD,date:'2026-10-16','2Y':3.89,'10Y':5.00};
const research=clone(researchLive);
research.CHF={
 pair_status:'OFFICIAL_SNBSAMEBASIS_RESEARCH_REVIEW_REQUIRED',
 paired_date:'2026-10-30','2Y':0.238,'10Y':0.505,curve_bp:26.7,
 separate_10y:{as_of:'2026-11-04','10Y':0.525,not_joinable_with_paired_2y:true},
 eligible_for_core:false,eligible_for_automatic_promotion:false
};
research.NZD={
 status:'RBNZ_GOVT_B2_WEB_RESEARCH_UNAPPROVED',
 roll_date:'2026-10-30',latest_date:'2026-11-04',
 latest_2Y:3.83,latest_10Y:4.81,
 new_benchmark:{'2Y':anchor.gov_benchmark_2y,'10Y':anchor.gov_benchmark_10y},
 after_roll:[{date:'2026-10-30','2Y':3.96,'10Y':4.90},
             {date:'2026-11-04','2Y':3.83,'10Y':4.81}],
 cross_roll_change_allowed:false,independent_xlsx_reconciled:false,
 eligible_for_core:false
};
const aud=clone(audLive);
Object.assign(aud,{
 as_of:'2026-10-28',publication_date:'2026-10-30',
 previous_same_series_as_of:'2026-10-27',
 '2Y':4.951,'10Y':5.208,curve_bp:25.7,
 change_2y_bp:6.8,change_10y_bp:5.6,
 status:'OFFICIAL_F2_CSV_FETCHED_RESEARCH_ONLY',
 source_download_verified:true,same_date_same_source:true,
 research_only:true,eligible_for_core:false,eligible_for_fx_pair_engine:false,
 eligible_for_backtests:false,canonical_government_rates_untouched:true,
 source_url:'https://www.rba.gov.au/statistics/tables/csv/f2-data.csv',
 series_2Y:'FCMYGBAG2D',series_10Y:'FCMYGBAG10D'
});
const proxy=clone(proxyLive);
proxy.as_of=anchor.asx_6m_as_of;
proxy.horizons['6m'].implied_bank_bill_rate=anchor.asx_6m_rate;
proxy.horizons['6m'].expiration=anchor.asx_6m_expiration;
proxy.horizons['6m'].expiry_label=anchor.asx_6m_contract;
proxy.status='LIVE_DIRECTIONAL_PROXY_READY';
const before=JSON.stringify(original);
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
assert.ok(valute.includes('async function refreshValuteRatesOnly()'),
 'ECB failure must not freeze dated Rates/COT context');
assert.ok(valute.includes('try{await refreshValuteRatesOnly();}'),
 'Rates/COT fallback should execute after ECB failure without rewriting FX fixing');
const macro=fs.readFileSync(ROOT+'/site/fx-quant-v2/macro.html','utf8');
assert.ok(macro.includes('const ratesView=effective?.rates||rates'));
assert.ok(macro.includes("r.tenor_quality?.['10Y']"));
assert.ok(macro.includes('async function refreshMacroRatesOnly()'),
 'A failed MACRO_SERIES source should not freeze sovereign/CB context');
assert.ok(macro.includes('try{await refreshMacroRatesOnly();}'),
 'Rates/CB recovery should execute after macro source failure');
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
