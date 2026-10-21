/* Stable, deterministic PR QA for the additive OIS research readout.
   Mutable market feeds are copied and given synthetic, explicitly dated QA cutoffs.
   No fixture observations are written back into production files. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const {matrix,view,fresh,coverage,auditDatedFuture,calibratedNzdCarry,NZD_REFERENCE_ROWS,NZD_RECENT_ROWS,NZD_HOLDOUT_ROWS}=require(path.join(root,'site/control-room-preview/ois-pricing-estimates-v1.js'));
const liveOis=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/OIS_OPERATIONAL_VIEW.json'),'utf8'));
const liveBb=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),'utf8'));
const ois=structuredClone(liveOis),bb=structuredClone(liveBb);
const TODAY='2026-10-21',FRESH='2026-10-20',EARLIER='2026-10-19';
const tenors=['3m','6m','12m'];
// Convert moving input dates to synthetic cutoff dates without changing source
// status/identities, values, contract mappings or policy restrictions.
for(const ccy of ['GBP','JPY','AUD','CAD']){
 assert.equal(ois.currencies[ccy].operational_status,'GREEN_OFFICIAL');
 ois.currencies[ccy].as_of=FRESH;
}
for(const ccy of ['USD','CHF']){
 assert.equal(ois.currencies[ccy].operational_status,'GREEN_ESTIMATED');
 for(const t of tenors)ois.currencies[ccy].horizons[t].quote_as_of=FRESH;
}
const ctx=ois.currencies.EUR.secondary_quote_context;
assert.equal(ois.currencies.EUR.operational_status,'WITHHELD');
assert.equal(ctx.status,'INDICATIVE_OBSERVATIONS_NON_OIS');
for(const t of tenors)ctx.horizons[t].quote_as_of=t==='12m'?FRESH:EARLIER;
bb.as_of=FRESH;
const manifest=JSON.parse(fs.readFileSync(path.join(root,
 'validation/cb_pricing/NZD_BB_CASH_RESEARCH_CALIBRATION_V1_2026-10-21.json'),'utf8'));
const stored=part=>part.rows.map(x=>[x.month,x.ocr_pct,x.bank_bill_90d_pct]);
assert.equal(manifest.schema,'GMFQ_NZD_BB_VS_CASH_EMPIRICAL_CALIBRATION_RESEARCH_V1');
assert.deepEqual(NZD_REFERENCE_ROWS,stored(manifest.reference_plateau));
assert.deepEqual(NZD_RECENT_ROWS,stored(manifest.recent_plateau));
assert.deepEqual(NZD_HOLDOUT_ROWS,stored(manifest.holdout_2026_q3));
assert.equal(manifest.holdout_2026_q3.independent_test_of_central_point,true);
assert.equal(manifest.holdout_2026_q3.not_out_of_sample_for_expanded_envelope,true);
const cal=calibratedNzdCarry();
assert.equal(cal.basis_bp,24);
assert.equal(cal.low_bp,10);
assert.equal(cal.high_bp,50);
assert.equal(cal.observations,19);
assert.equal(cal.holdout_months,3);
assert.equal(cal.holdout_point_mae_bp,16.33);
assert.equal(cal.holdout_max_absolute_error_bp,24);
assert.equal(cal.holdout_original_band_coverage,2);
assert.equal(cal.holdout_expanded_band_coverage,3);
assert.equal(cal.expanded_band_selected_after_observing_holdout,true);
assert.equal(cal.holdout_is_real_ois_spread,false);
assert.equal(cal.reference_median_bp,14);
assert.equal(cal.recent_median_bp,28.5);
assert.equal(cal.direct_nzbo_ois_quote,false);
assert.equal(cal.forward_ois_curve,false);
assert.equal(cal.statistical_confidence_interval,false);
assert.equal(cal.policy_delta_allowed,false);
assert.equal(cal.forward_ois_curve,false);
assert.equal(cal.policy_delta_allowed,false);
assert.equal(cal.core_effect,'NONE');
const result=matrix(ois,bb,TODAY),rows=Object.fromEntries(result.map(x=>[x.ccy,x]));
assert.equal(result.length,8);
for(const code of ['GBP','JPY','CAD','AUD'])assert.equal(rows[code].tier,'OFFICIAL',code);
for(const code of ['USD','CHF'])assert.equal(rows[code].tier,'PROXY',code);
assert.equal(rows.EUR.tier,'MIXED');
assert.equal(rows.EUR.points['3m'].date,EARLIER);
assert.equal(rows.EUR.points['12m'].date,FRESH);
assert.equal(rows.NZD.tier,'SCENARIO');

// Source-level 100-price identity and expiry-proximity: same dated contract,
// not an observed OIS basis or a truly synchronized 3M/6M/12M cash curve.
const expectedGap={USD:{'3m':-15,'6m':14,'12m':11},
 CHF:{'3m':-36,'6m':-34,'12m':-37},
 EUR:{'3m':0,'6m':30,'12m':-36}};
for(const ccy of ['USD','EUR','CHF']){
 const src=ois.currencies[ccy];
 for(const t of tenors){
  const p=src.horizons[t];
  const research=rows[ccy].points[t];
  assert(research,'missing '+ccy+' '+t);
  assert.equal(research.source_quote_verified,true);
  assert.equal(research.policy_repricing_allowed,false);
  assert.equal(research.direct_ois_quote,false);
  assert.equal(research.contract,p.contract);
  assert.equal(research.expires,p.expiration);
  assert(Math.abs(100-p.futures_price-research.value)<=0.0002);
  assert(Math.abs(research.tenor_gap_days)<=45);
  const displayDay=ccy==='EUR'?src.secondary_quote_context.horizons[t].quote_as_of:p.quote_as_of;
  assert.equal(research.date,displayDay);
 }
}
const invalidPrice=structuredClone(ois);
invalidPrice.currencies.USD.horizons['3m'].futures_price+=0.025;
assert.equal(matrix(invalidPrice,bb,TODAY).find(r=>r.ccy==='USD').points['3m'],undefined);
const spoof=structuredClone(ois);
spoof.currencies.CHF.horizons['6m'].symbol='FAKE:SA3Z2026';
assert.equal(matrix(spoof,bb,TODAY).find(r=>r.ccy==='CHF').points['6m'],undefined);
const expiredHorizon=structuredClone(ois);
expiredHorizon.currencies.USD.horizons['12m'].expiration='2028-12-15';
assert.equal(matrix(expiredHorizon,bb,TODAY).find(r=>r.ccy==='USD').points['12m'],undefined);
const quoteDay=structuredClone(ois);
quoteDay.currencies.EUR.secondary_quote_context.horizons['3m'].quote_as_of='2026-10-18';
assert.equal(matrix(quoteDay,bb,TODAY).find(r=>r.ccy==='EUR').points['3m'],undefined);
const spoofTicker=structuredClone(ois);
spoofTicker.currencies.EUR.secondary_quote_context.horizons['12m'].contract='FST3U2027';
assert.equal(matrix(spoofTicker,bb,TODAY).find(r=>r.ccy==='EUR').points['12m'],undefined);
const dollarQuote=ois.currencies.USD.horizons['3m'];
assert.equal(auditDatedFuture('USD','3m',dollarQuote,dollarQuote.rate,
  dollarQuote.quote_as_of,TODAY)?.source_quote_verified,true);

for(const t of tenors){
 const raw=bb.horizons[t].implied_bank_bill_rate;
 assert.equal(rows.NZD.points[t].value,Math.round((raw-cal.basis_bp/100)*100)/100);
 assert.deepEqual(rows.NZD.points[t].range,
  [Math.round((raw-cal.high_bp/100)*100)/100,Math.round((raw-cal.low_bp/100)*100)/100]);
}
for(const row of result){
 assert.equal(row.allow_official_promotion,false);
 assert.equal(row.allow_repricing,false);
 assert.equal(row.bias_effect,'NONE');
 assert.equal(row.pair_effect,'NONE');
 assert.equal(row.backtest_official,false);
}
assert.equal(rows.GBP.official_ois,true);
for(const code of ['USD','EUR','CHF','NZD'])assert.equal(rows[code].official_ois,false);
assert.equal(fresh(FRESH,TODAY),true);
assert.equal(fresh('2026-10-22',TODAY),false);
assert.equal(fresh('2026-10-10',TODAY),false);
assert.equal(fresh('invalid',TODAY),false);
// Home research coverage is complete ONLY with 3 dated tenors, and never
// upgrades the actual 4/8 certified source count.
const home=coverage(ois,bb,TODAY);
assert.equal(home.schema,'GMFQ_OIS_G8_RESEARCH_COVERAGE_V1');
assert.equal(home.official_count,4);
assert.equal(home.context_count,4);
assert.equal(home.covered_count,8);
assert.deepEqual(home.official_codes.sort(),['AUD','CAD','GBP','JPY']);
assert.deepEqual(home.context_codes.sort(),['CHF','EUR','NZD','USD']);
assert.deepEqual(home.incomplete_codes,[]);
assert.equal(home.currency_tiers.NZD,'SCENARIO');
assert.equal(home.currency_tiers.EUR,'MIXED');
assert.equal(home.no_ois_official_promotion,true);
assert.equal(home.core_effect,'NONE');
assert.equal(home.pair_effect,'NONE');
assert.equal(home.backtest_estimated_as_official,false);
// Partial or stale quotes never count as whole G8 research curves.
const partial=structuredClone(ois);
partial.currencies.CHF.horizons['6m'].quote_timestamp_verified=false;
const missing=coverage(partial,bb,TODAY);
assert.equal(missing.covered_count,7);
assert(missing.incomplete_codes.includes('CHF'));
assert.equal(missing.currency_tiers.CHF,'INCOMPLETE_OR_STALE');
const late=coverage(ois,bb,'2026-11-12');
assert.equal(late.covered_count,0);
assert.equal(late.official_count,0);
assert.equal(late.context_count,0);
assert.equal(matrix(ois,bb,'2026-11-12').filter(x=>x.tier!=='WITHHELD').length,0);
// EUR cannot join mismatched first-party futures quotes into a fake OIS curve.
const invalidEUR=structuredClone(ois);
invalidEUR.currencies.EUR.secondary_quote_context.cross_date_join_allowed=true;
assert.equal(matrix(invalidEUR,bb,TODAY).find(x=>x.ccy==='EUR').tier,'WITHHELD');
// Missing verification disqualifies the individual tenor, never falls back to an old quote.
const invalidCHF=structuredClone(ois);
invalidCHF.currencies.CHF.horizons['6m'].quote_timestamp_verified=false;
assert.equal(matrix(invalidCHF,bb,TODAY).find(x=>x.ccy==='CHF').points['6m'],undefined);
// No unlicensed conversion of NZD Bank Bill levels into policy deltas.
const invalidBB=structuredClone(bb);
invalidBB.governance.substitutes_for_ois_level=true;
assert.equal(matrix(ois,invalidBB,TODAY).find(x=>x.ccy==='NZD').tier,'WITHHELD');
const html=view(result);
assert(html.includes('data-ccy="NZD"'));
assert(html.includes('DATE NON SINCRONIZZATE'));
assert(html.includes('non intervallo statistico'));
assert(!html.includes('GREEN_OFFICIAL'));
const navigation=fs.readFileSync(path.join(root,'site/control-room-preview/home-navigation-v10.js'),'utf8');
const loader=fs.readFileSync(path.join(root,'site/control-room-preview/index.html'),'utf8');
const publisher=fs.readFileSync(path.join(root,'.github/workflows/publish-control-room-home-v10.yml'),'utf8');
assert(navigation.includes('api.coverage(ois,proxy,'));
assert(navigation.includes('Contesto '));
assert(loader.indexOf('./ois-pricing-estimates-v1.js')<loader.indexOf('./home-navigation-v10.js'));
assert(publisher.includes('cp site/control-room-preview/ois-pricing-estimates-v1.js'));
assert(!/\bcron:/.test(publisher));
assert.deepEqual(liveBb,JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),'utf8')));
console.log('GMFQ_OIS_G8_HOME_DUAL_PROVENANCE_PASS: certified 4, context 4, stale fail-closed, no trade effect');
