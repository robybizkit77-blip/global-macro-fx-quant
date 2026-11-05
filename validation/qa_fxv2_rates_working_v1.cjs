'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
const {derive}=require('../site/fx-quant-v2/assets/rates-working-model-v1.js');
const research=JSON.parse(fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/chf-nzd-benchmark-research.json')));
const canonical=JSON.parse(fs.readFileSync(path.join(ROOT,'live_data/sections/NATIVE_RATES_DATA.json')));
const asx=JSON.parse(fs.readFileSync(path.join(ROOT,'live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json')));
const anchor=JSON.parse(fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/nzd-asx-government-anchor-v1.json')));
const copy=x=>JSON.parse(JSON.stringify(x));
const shiftDays=(day,days)=>new Date(Date.parse(day+'T00:00:00Z')+
  86400000*days).toISOString().slice(0,10);
const maxDate=(...days)=>[...days].sort().at(-1);
// Real source dates are data, not expectations pinned in a QA script.
// A new official SNB 10Y publication must not break the browser gate.
const today=maxDate(research.CHF.paired_date,
                    research.CHF.separate_10y.as_of,research.NZD.latest_date);
const before=JSON.stringify(canonical);
// Working-rate scenarios are research-only, so use a deliberately old
// canonical date fixture for regression, while independently checking that
// the real canonical priority is never overridden.
const fixture=copy(canonical);
fixture.CHF.date=shiftDays(research.CHF.paired_date,-1);
fixture.NZD.date=shiftDays(research.NZD.latest_date,-1);
const working=derive(fixture,research,today);
assert.equal(working.schema,'GMFQ_FXV2_WORKING_RATES_V1');
assert.equal(working.eligible_for_fx_engine,false);
assert.equal(working.eligible_for_backtests,false);
assert.deepEqual(Object.keys(working.rates).sort(),['CHF','NZD']);
const chf=working.rates.CHF,nzd=working.rates.NZD;
const pair=research.CHF, isolated=pair.separate_10y;
const pairedIsLatest=pair.paired_date>=isolated.as_of;
const independentlyExpected2=pairedIsLatest?pair['2Y']:
 Number((pair['2Y']+isolated['10Y']-pair['10Y']).toFixed(4));
const independentlyExpected10=pairedIsLatest?pair['10Y']:isolated['10Y'];
const independentlyExpectedDate=pairedIsLatest?pair.paired_date:isolated.as_of;
assert.equal(chf['2Y'],independentlyExpected2,
 'CHF 2Y must follow the same-date SNB pair or the explicitly estimated parallel shift');
assert.equal(chf['10Y'],independentlyExpected10);
assert.equal(chf.curve_bp,Number(((independentlyExpected10-independentlyExpected2)*100).toFixed(1)));
assert.equal(chf.estimated,true);
assert.equal(chf.tenor_quality['2Y'],pairedIsLatest?'OSSERVATO':'STIMATO');
assert.equal(chf.tenor_quality['10Y'],'OSSERVATO');
assert.equal(chf.date,independentlyExpectedDate);
assert.equal(chf.source_date,pair.paired_date);
assert.equal(chf.no_core_effect,true);
if(pairedIsLatest){
 assert.equal(chf.research_observed,true);
 assert.equal(chf.chg2_bp,null,'One same-date pair does not prove a daily move');
 assert.equal(chf.chg10_bp,null,'One same-date pair does not prove a daily move');
}else{
 const expectedShift=Number(((isolated['10Y']-pair['10Y'])*100).toFixed(2));
 assert.equal(chf.working_method,'PARALLEL_10Y_SHIFT_2Y');
 assert.equal(chf.chg2_bp,null,'CHF multi-session hypothetical shift is not a 1D change');
 assert.equal(chf.chg10_bp,null,'CHF isolated 10Y movement is not a 1D change');
 assert.deepEqual(chf.comparison_window,{
  start:pair.paired_date,end:isolated.as_of,
  observed_10y_bp:expectedShift,assumed_2y_bp:expectedShift,
  kind:'MULTI_SESSION_PARALLEL_SHIFT_SCENARIO_NOT_1D'});
 assert.equal(chf.no_inferred_market_move,true);
}
const first=research.NZD.after_roll[0],last=research.NZD.after_roll.at(-1);
assert.equal(first.date,research.NZD.roll_date);
assert.equal(last.date,research.NZD.latest_date);
assert.equal(nzd['2Y'],research.NZD.latest_2Y);
assert.equal(nzd['10Y'],research.NZD.latest_10Y);
assert.equal(nzd.curve_bp,Number(((last['10Y']-last['2Y'])*100).toFixed(1)));
assert.equal(nzd.chg2_bp,null,'NZD post-roll window cannot be represented as 1D');
assert.equal(nzd.chg10_bp,null,'NZD post-roll window cannot be represented as 1D');
assert.deepEqual(nzd.comparison_window,{
 start:first.date,end:last.date,
 observed_2y_bp:Number(((last['2Y']-first['2Y'])*100).toFixed(2)),
 observed_10y_bp:Number(((last['10Y']-first['10Y'])*100).toFixed(2)),
 kind:'POST_ROLL_CUMULATIVE_NOT_1D'});
assert.equal(nzd.date,research.NZD.latest_date);
assert.equal(nzd.no_cross_roll_change,true);
assert.equal(nzd.chg2_bp,null);
assert.equal(chf.chg2_bp,null);

assert.equal(research.NZD.independent_xlsx_reconciled,false);
assert.equal(research.NZD.eligible_for_core,false);
assert.equal(JSON.stringify(canonical),before,'Canonical source must remain unmodified');
const bp=v=>Math.round(v*1000)/10;
assert.equal(bp(chf['2Y']-nzd['2Y']),
 bp(independentlyExpected2-research.NZD.latest_2Y),'CHF-NZD working spread arithmetic');
assert.equal(bp(chf['10Y']-nzd['10Y']),
 bp(independentlyExpected10-research.NZD.latest_10Y),'CHF-NZD 10Y spread arithmetic');

// A current daily 10Y must remain usable even when the statistically
// published same-basis 2Y/10Y anchor is >14 days but <=45 days old.
const monthEnd=copy(research);
const monthlyAsOf=shiftDays(monthEnd.CHF.paired_date,30);
monthEnd.CHF.separate_10y.as_of=monthlyAsOf;
monthEnd.CHF.separate_10y.not_joinable_with_paired_2y=true;
const monthlyToday=shiftDays(monthlyAsOf,1);
const monthScenario=derive(fixture,monthEnd,monthlyToday).rates.CHF;
assert.equal(monthScenario.stale_source,false,
 'Fresh daily SNB 10Y cannot be discarded because month-end spot curve is >14d old');
assert.equal(monthScenario.source_date,monthEnd.CHF.paired_date);
assert.equal(monthScenario.evidence_date,monthlyAsOf);
assert.equal(monthScenario.source_age_days,1);
assert.equal(monthScenario.anchor_age_days,31);
assert.equal(monthScenario.anchor_cadence,'STATISTICAL_MONTH_END');
assert.equal(monthScenario.tenor_quality['2Y'],'STIMATO');
assert.equal(monthScenario.tenor_quality['10Y'],'OSSERVATO');
assert.equal(monthScenario.chg2_bp,null);
const monthExpired=copy(monthEnd);
monthExpired.CHF.separate_10y.as_of=shiftDays(monthEnd.CHF.paired_date,46);
const monthlyTooOld=derive(fixture,monthExpired,shiftDays(monthEnd.CHF.paired_date,47)).rates.CHF;
assert.equal(monthlyTooOld.source_age_days,1);
assert.equal(monthlyTooOld.anchor_age_days,47);
assert.equal(monthlyTooOld.stale_source,true,
 '45-day statistical anchor expiry must be enforced even with a 1-day-old observed 10Y');
// An official same-date SNB pair newer than the isolated 10Y must replace the
// estimate; a single newly paired reading never manufactures an observed delta.
const newerPair=copy(research);
const pairDate=shiftDays(maxDate(pair.paired_date,isolated.as_of),1);
newerPair.CHF.paired_date=pairDate;
newerPair.CHF['2Y']=.247;
newerPair.CHF['10Y']=.510;
newerPair.CHF.curve_bp=26.3;
const latest=derive(fixture,newerPair,pairDate).rates.CHF;
assert.equal(latest.date,pairDate);
assert.equal(latest['2Y'],.247);
assert.equal(latest['10Y'],.510);
assert.equal(latest.curve_bp,26.3);
assert.equal(latest.research_observed,true);
assert.equal(latest.working_method,'SNB_SAME_DATE_OBSERVED_PAIR_RESEARCH');
assert.deepEqual(latest.tenor_quality,{'2Y':'OSSERVATO','10Y':'OSSERVATO'});
assert.equal(latest.chg2_bp,null);
assert.equal(latest.chg10_bp,null);
assert.equal(latest.stale_source,false);
assert.equal(latest.no_core_effect,true);
assert.equal(latest.no_inferred_market_move,true);
assert.equal(latest.estimated,true,'Research observations cannot be promoted to FX Core');
const staleAt=shiftDays(maxDate(pairDate,today),50);
const late=derive(fixture,newerPair,staleAt).rates.CHF;
assert.equal(late.date,pairDate);
assert.equal(late.stale_source,true);
assert.equal(late.chg2_bp,null);
assert.equal(late.chg10_bp,null);
assert.ok(late.quality.includes('RIFERIMENTO STORICO'));
const same=copy(newerPair);
same.CHF.separate_10y.as_of=pairDate;
same.CHF.separate_10y.not_joinable_with_paired_2y=false;
same.CHF.separate_10y['10Y']=.510;
assert.equal(derive(fixture,same,pairDate).rates.CHF.research_observed,true);
same.CHF.separate_10y['10Y']=.520;
assert.equal(derive(fixture,same,pairDate).rates.CHF,undefined,
 'Contradictory isolated SNB 10Y on the SAME date must be rejected');
same.CHF.separate_10y.not_joinable_with_paired_2y=true;
assert.equal(derive(fixture,same,pairDate).rates.CHF,undefined,
 'Contradictory joinable metadata must never be trusted');
const canonicalAdvanced=copy(fixture);
canonicalAdvanced.CHF.date=shiftDays(pairDate,1);
assert.equal(derive(canonicalAdvanced,newerPair,canonicalAdvanced.CHF.date).rates.CHF,undefined,
 'Newer canonical source has priority over dated research');
const real=derive(canonical,research,today);
if(canonical.CHF.date>=maxDate(pair.paired_date,isolated.as_of))
 assert.equal(real.rates.CHF,undefined,'Real canonical CHF must supersede research');
if(canonical.NZD.date>=research.NZD.latest_date)
 assert.equal(real.rates.NZD,undefined,'Real canonical NZD must supersede research');
let future=copy(research);
future.CHF.separate_10y.as_of=shiftDays(today,1);
assert.equal(derive(fixture,future,today).rates.CHF,undefined,'Never use future quotes');
let bad=copy(research);
bad.CHF.curve_bp=95;
assert.equal(derive(fixture,bad,today).rates.CHF,undefined,'Mismatched same-date SNB curve rejected');
bad=copy(research);bad.NZD.after_roll[0].date=shiftDays(research.NZD.roll_date,-1);
assert.equal(derive(fixture,bad,today).rates.NZD,undefined,'Do not bridge NZD old/new benchmark');
bad=copy(research);bad.NZD.independent_xlsx_reconciled=true;
assert.equal(derive(fixture,bad,today).rates.NZD,undefined,'Review status must agree with provenance');
const updated=copy(fixture);
updated.CHF.date=maxDate(pair.paired_date,isolated.as_of);
updated.NZD.date=research.NZD.latest_date;
assert.equal(Object.keys(derive(updated,research,today).rates).length,0,
 'Official same/newer canonical source takes priority');
const stale=derive(fixture,research,staleAt);
assert.deepEqual(Object.keys(stale.rates).sort(),['CHF','NZD'],
 'Preserve historical research levels when source access is unavailable');
for(const c of ['CHF','NZD']){
 const row=stale.rates[c];
 const originalDate=c==='CHF'?independentlyExpectedDate:research.NZD.latest_date;
 assert.equal(row.stale_source,true,'Must explicitly label stale '+c);
 assert.equal(row.freshness,'DATED_RESEARCH_NO_CURRENT_MARKET_MOVE');
 assert.ok(row.quality.includes('RIFERIMENTO STORICO'));
 assert.equal(row.date,originalDate,'Never relabel old quote as current');
 assert.equal(row.chg2_bp,null,'Historical move must not be represented as today');
 assert.equal(row.chg10_bp,null,'Historical move must not be represented as today');
 assert.equal(row.no_core_effect,true);
 assert.equal(row.source_age_days,
  Math.round((Date.parse(staleAt)-Date.parse(originalDate))/86400000));
}
assert.equal(JSON.stringify(canonical),before,'Stale research must never rewrite canonical source');
// ASX settlement AFTER B2 research observation: 6M bank-bill futures only,
// a hypothetical parallel 2Y/10Y shift, never a sovereign daily movement.
// Current external feeds advance independently of the historical starting
// point. Never pin automated daily ASX or refreshed RBNZ observations to the
// Nov 4 initial scenario anchor: that would fail on the FIRST good update.
assert.equal(asx.schema,'GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1');
assert.equal(asx.currency,'NZD');
assert.equal(asx.source_quality,'OFFICIAL_EXCHANGE_DIRECTIONAL_PROXY');
assert.equal(asx.governance.pair_engine_effect,'NONE');
assert.equal(asx.governance.policy_delta_from_proxy_allowed,false);
assert.ok(asx.as_of>=anchor.asx_6m_as_of,
 'Actual ASX feed may advance but must not regress behind the dated anchor');
assert.ok(Number.isFinite(asx.horizons['6m'].implied_bank_bill_rate));
assert.ok(research.NZD.latest_date>=anchor.government_as_of,
 'New official B2 research may advance but must not regress behind its anchor');
assert.ok(Number.isFinite(research.NZD.latest_2Y)&&
          Number.isFinite(research.NZD.latest_10Y));
// Freeze a synthetic INITIAL research-source fixture for regression tests.
// New market observations are tested against a reference fixture, never
// against assumed unchanged live source files.
const frozenResearch=copy(research);
frozenResearch.NZD={
 status:'RBNZ_GOVT_B2_WEB_RESEARCH_UNAPPROVED',
 cross_roll_change_allowed:false,independent_xlsx_reconciled:false,
 eligible_for_core:false,roll_date:'2026-10-30',
 new_benchmark:{'2Y':anchor.gov_benchmark_2y,'10Y':anchor.gov_benchmark_10y},
 latest_date:anchor.government_as_of,
 latest_2Y:anchor['2Y'],latest_10Y:anchor['10Y'],
 after_roll:[{date:'2026-10-30','2Y':3.96,'10Y':4.90},
             {date:anchor.government_as_of,'2Y':anchor['2Y'],'10Y':anchor['10Y']}]
};
const frozenAsx={
 schema:'GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1',
 currency:'NZD',status:'LIVE_DIRECTIONAL_PROXY_READY',
 source_quality:'OFFICIAL_EXCHANGE_DIRECTIONAL_PROXY',
 governance:{pair_engine_effect:'NONE',policy_delta_from_proxy_allowed:false},
 as_of:anchor.asx_6m_as_of,
 horizons:{'6m':{implied_bank_bill_rate:anchor.asx_6m_rate,
                 expiration:anchor.asx_6m_expiration,
                 expiry_label:anchor.asx_6m_contract}}
};
const frozenCanonical=copy(fixture);
frozenCanonical.NZD.date=shiftDays(anchor.government_as_of,-1);
const quote=copy(frozenAsx);
quote.as_of=shiftDays(anchor.asx_6m_as_of,1);
quote.horizons['6m'].implied_bank_bill_rate=Number((anchor.asx_6m_rate-.12).toFixed(4));
const scenarioToday=maxDate(today,quote.as_of);
const z=derive(frozenCanonical,frozenResearch,scenarioToday,quote,anchor).rates.NZD;
assert.equal(z.date,quote.as_of);
assert.equal(z['2Y'],Number((anchor['2Y']-.12).toFixed(4)));
assert.equal(z['10Y'],Number((anchor['10Y']-.12).toFixed(4)));
assert.equal(z.estimated,true);
assert.deepEqual(z.tenor_quality,{'2Y':'STIMATO','10Y':'STIMATO'});
assert.equal(z.working_method,'NZD_ASX_6M_PARALLEL_SHIFT_SCENARIO');
assert.equal(z.chg2_bp,null);
assert.equal(z.chg10_bp,null);
assert.equal(z.comparison_window.futures_6m_bp,-12);
assert.equal(z.no_core_effect,true);
assert.equal(z.no_inferred_market_move,true);
assert.ok(z.quality.includes('NON GOVERNATIVO QUOTATO'));
assert.equal(derive(frozenCanonical,frozenResearch,scenarioToday,frozenAsx,anchor).rates.NZD.date,
 frozenResearch.NZD.latest_date,'Same-day ASX observation must retain B2 observed date');
const rolled=copy(quote);rolled.horizons['6m'].expiration='2027-09-15';
assert.equal(derive(frozenCanonical,frozenResearch,scenarioToday,rolled,anchor).rates.NZD.date,
 frozenResearch.NZD.latest_date,'A different futures maturity must not be chained');
const abnormal=copy(quote);abnormal.horizons['6m'].implied_bank_bill_rate=anchor.asx_6m_rate+1;
assert.equal(derive(frozenCanonical,frozenResearch,scenarioToday,abnormal,anchor).rates.NZD.date,
 frozenResearch.NZD.latest_date,'Guard against 100bp jump since anchor');
const fake=copy(quote);fake.status='WITHHELD';
assert.equal(derive(frozenCanonical,frozenResearch,scenarioToday,fake,anchor).rates.NZD.date,
 frozenResearch.NZD.latest_date,'Unvalidated futures status must not displace dated B2');
const canonicalNewer=copy(frozenCanonical);canonicalNewer.NZD.date=quote.as_of;
assert.equal(derive(canonicalNewer,frozenResearch,scenarioToday,quote,anchor).rates.NZD,undefined,
 'Fresh official canonical yields supersede a model scenario');
const researchAdvanced=copy(frozenResearch);researchAdvanced.NZD.latest_date=quote.as_of;
researchAdvanced.NZD.after_roll.at(-1).date=quote.as_of;
const advanced=derive(frozenCanonical,researchAdvanced,scenarioToday,quote,anchor).rates.NZD;
assert.equal(advanced.date,researchAdvanced.NZD.latest_date);
assert.equal(advanced.working_method,'POST_ROLL_B2_SAME_BENCHMARK',
 'A new B2 research date must supersede old futures-anchor modelling');
// When live RBNZ research advances beyond the frozen ASX anchor, the
// hypothesis is disabled without breaking either the model or this QA.
const laterB2=copy(frozenResearch);
laterB2.NZD.latest_date=shiftDays(anchor.government_as_of,2);
laterB2.NZD.after_roll.at(-1).date=laterB2.NZD.latest_date;
laterB2.NZD.latest_2Y=3.81;
laterB2.NZD.latest_10Y=4.79;
laterB2.NZD.after_roll.at(-1)['2Y']=laterB2.NZD.latest_2Y;
laterB2.NZD.after_roll.at(-1)['10Y']=laterB2.NZD.latest_10Y;
const laterQuote=copy(frozenAsx);
laterQuote.as_of=shiftDays(anchor.asx_6m_as_of,3);
laterQuote.horizons['6m'].implied_bank_bill_rate=
 Number((anchor.asx_6m_rate-.08).toFixed(4));
const laterResult=derive(frozenCanonical,laterB2,laterQuote.as_of,laterQuote,anchor).rates.NZD;
assert.equal(laterResult.working_method,'POST_ROLL_B2_SAME_BENCHMARK',
 'A newer B2 research observation must deactivate the old ASX scenario');
assert.equal(laterResult.date,laterB2.NZD.latest_date);
assert.equal(laterResult['2Y'],3.81);
assert.equal(laterResult['10Y'],4.79);
assert.equal(JSON.stringify(canonical),before,'ASX scenario must not mutate canonical rates');
const futureAsOf=copy(frozenResearch);
futureAsOf.NZD.latest_date=shiftDays(staleAt,1);
assert.equal(derive(frozenCanonical,futureAsOf,staleAt).rates.NZD,undefined,
 'No future government quote in stale fallback');
const tassi=fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/tassi.html'),'utf8');
assert.ok(tassi.includes('state.nzdAsxProxy=val(3)'));
assert.ok(tassi.includes('nzd-asx-government-anchor-v1.json'));
assert.ok(tassi.includes('state.nzdAsxProxy,anchor'));

assert.ok(tassi.includes("svgCurves(r);if(r.research_observed)"),
 'Observed research source must be distinguished from an estimated curve');
assert.ok(tassi.includes("else if(r.estimated)") &&
          tassi.includes("Non è una curva ufficiale osservata."),
 'Estimated CHF scenario must retain its separate caveat');
assert.ok(tassi.includes("Differenziali aritmetici")&&
          tassi.includes("DATE DIVERSE, spread indicativo non sincronizzato"),
 'V2 comparison must label estimates and asynchronous tenor dates');
assert.ok(tassi.includes('const local="./chf-nzd-benchmark-research.json"') &&
          tassi.includes('try{x=await read(local);}'),
  'Tassi must prefer the version-matched published research copy');
assert.ok(tassi.includes('x=await read(remote)'),
  'Tassi should recover from a broken local publication');
assert.ok(tassi.includes("RIFERIMENTO STORICO")===false,
  'Stale classification belongs in the shared working model, not hardcoded HTML');
const coppie=fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/coppie.html'),'utf8');
assert.ok(coppie.includes("get('NZD_CB_PRICING_DIRECTIONAL_PROXY.json')"));
assert.ok(coppie.includes('nzd-asx-government-anchor-v1.json'));
assert.ok(coppie.includes('derive(state.rates,research,today,proxy,anchor)'));
assert.ok(coppie.includes('rates-working-model-v1.js?v=1'),'Coppie must reuse the validated Tassi estimator');
assert.ok(coppie.includes("const local='./chf-nzd-benchmark-research.json'") &&
          coppie.includes("try{research=await load(local);}"),
  'Coppie must prefer version-matched local research');
assert.ok(coppie.includes('research=await load(remote)'),
  'Coppie must retain an external recovery route');
assert.ok(coppie.includes('STIMA/PROXY INDICATIVO'),'Coppie must visibly label scenario levels');
assert.ok(coppie.includes('model.eligible_for_fx_engine!==false'),'Coppie must keep estimates out of the engine');
assert.ok(coppie.includes('id="pairRatesSourceNote"'),'Coppie must expose research caveats');
console.log('FXV2_WORKING_RATE_TESTS PASS CHF 2Y '+chf['2Y']+'% ('+chf.tenor_quality['2Y']+'), CHF 10Y '+chf['10Y']+'% ('+chf.date+'); NZD 2Y '+nzd['2Y']+'%, NZD 10Y '+nzd['10Y']+'% ('+nzd.date+'); source dates verified, canonical unchanged');
