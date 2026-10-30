/* Stable, deterministic PR QA for the additive OIS research readout.
   Mutable market feeds are copied and given synthetic, explicitly dated QA cutoffs.
   No fixture observations are written back into production files. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const {matrix,view,matchedResearchMoves,fresh,coverage,indicativeSixMonth,auditDatedFuture,calibratedNzdCarry,NZD_REFERENCE_ROWS,NZD_RECENT_ROWS,NZD_HOLDOUT_ROWS}=require(path.join(root,'site/control-room-preview/ois-pricing-estimates-v1.js'));
const liveOis=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/OIS_OPERATIONAL_VIEW.json'),'utf8'));
const liveBb=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),'utf8'));
const ois=structuredClone(liveOis),bb=structuredClone(liveBb);
const TODAY='2026-10-21',FRESH='2026-10-20',EARLIER='2026-10-19';
const tenors=['3m','6m','12m'];
// The first 23 source-verified research bars are a deterministic 16/19/20 Oct
// replay. The production append-only archive can grow without altering this QA.
const observedHistory=fs.readFileSync(path.join(root,
 'validation/cb_pricing/history/OIS_SAME_CONTRACT_QUOTES_V1.jsonl'),'utf8')
 .split('\n').filter(Boolean).map(x=>JSON.parse(x));
assert(observedHistory.length>=23);
const fixedBars=observedHistory.slice(0,23);
assert.equal(new Set(fixedBars.map(x=>[x.currency,x.contract,x.observation_date].join('|'))).size,23);
// Freeze official scope, never alter source files or production Rates.
for(const ccy of ['GBP','JPY','AUD','CAD']){
 assert.equal(ois.currencies[ccy].operational_status,'GREEN_OFFICIAL');
 ois.currencies[ccy].as_of=FRESH;
}
for(const ccy of ['USD','EUR','CHF']){
 const row=ois.currencies[ccy];
 // Exercise the historical synchronized proxy path using verified original
 // quotes, even when today's real operational runtime is appropriately WITHHELD.
 if(ccy!=='EUR'){
   assert(['WITHHELD','GREEN_ESTIMATED'].includes(row.operational_status));
   row.operational_status='GREEN_ESTIMATED';
   row.quality='ESTIMATED_INFORMATIONAL';
   row.official_status='WITHHELD';
   row.backtest_eligible_as_official=false;
   row.method_id='TRADINGVIEW_DATED_FUTURES_SSR_V2';
   row.as_of=FRESH;
 }else{
   // Deterministic 16/19/20 October *historical* fixture, deliberately
   // independent of whether the live EUR dated-futures overlay has since
   // become GREEN_ESTIMATED. Preserve no-OIS-promotion invariants.
   assert(['WITHHELD','GREEN_ESTIMATED'].includes(row.operational_status));
   row.operational_status='WITHHELD';
   row.quality='ESTIMATED_INFORMATIONAL';
   row.official_status='WITHHELD';
   row.backtest_eligible_as_official=false;
   row.secondary_quote_context={
     status:'INDICATIVE_OBSERVATIONS_NON_OIS',
     full_curve_usable:false,cross_date_join_allowed:false,
     policy_delta_allowed:false,repricing_signal_allowed:false,
     backtest_eligible_as_official:false,
     horizons:Object.fromEntries(tenors.map(t=>[t,{}]))
   };
 }
 for(const t of tenors){
   const history=fixedBars.filter(x=>x.currency===ccy&&x.observed_under_horizon===t)
     .sort((a,b)=>a.observation_date.localeCompare(b.observation_date));
   const bar=history.at(-1);
   assert(bar,'missing frozen futures source '+ccy+' '+t);
   const h=row.horizons[t];
   Object.assign(h,{contract:bar.contract,symbol:bar.symbol,
     expiration:bar.expiration,futures_price:bar.futures_price,
     rate:ccy==='EUR'?null:bar.implied_rate,
     quote_as_of:bar.observation_date,
     quote_timestamp_verified:true,
     quote_timestamp_source:'SSR_DAILY_BAR_DATA_UPDATE_TIME'});
   if(ccy==='EUR'){
     Object.assign(row.secondary_quote_context.horizons[t],{
       contract:bar.contract,rate_indicative:bar.implied_rate,
       quote_as_of:bar.observation_date,source_quality:'SECONDARY_VERIFIED_DAILY_BAR'});
   }
 }
}
bb.as_of=FRESH;
// Verify current PUBLIC inputs remain purely individual, independently dated
// information whenever a live quote mismatch withholds a complete curve.
const current=matrix(liveOis,liveBb,TODAY);
for(const ccy of ['USD','EUR','CHF']){
 const source=liveOis.currencies[ccy],item=current.find(r=>r.ccy===ccy);
 if(source.operational_status==='WITHHELD'&&
    source.secondary_quote_context?.status==='INDICATIVE_OBSERVATIONS_NON_OIS'){
   // Real input dates advance independently of this fixed 21 Oct QA replay.
   // If the individual public quote is future-dated or too old for the
   // replay, the correct result is no published research estimate.
   assert(['MIXED','WITHHELD'].includes(item.tier),ccy+' research source not approved');
   assert.equal(item.official_ois,false);
   const available=tenors.filter(t=>item.points[t]);
   assert(available.every(t=>item.points[t].source_quote_verified===true));
   if(item.tier==='MIXED')assert(available.length>0,ccy+' MIXED requires audited observations');
   else assert.equal(available.length,0,'WITHHELD cannot show fake quotes');
   const six=indicativeSixMonth(liveOis,TODAY)[ccy];
   if(item.points['6m']?.source_quote_verified===true){
     assert.equal(six?.type,'MIXED');
     assert.equal(six?.policy_delta_allowed,false);
     assert.equal(six?.core_effect,'NONE');
     assert(six?.label.includes(ccy));
   }else{
     assert.equal(six,undefined,ccy+' must not promote unverified 6M quote');
   }
 }
}
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

// Distinguish an unavailable official policy delta from a verified, explicitly
// non-operative futures level. Reuse the exact Rates addon provenance guard.
const pair6m=indicativeSixMonth(ois,TODAY);
assert.deepEqual(Object.keys(pair6m).sort(),['CHF','EUR','USD']);
assert.equal(pair6m.USD.type,'PROXY');
assert.equal(pair6m.USD.value,ois.currencies.USD.horizons['6m'].rate);
assert.equal(pair6m.CHF.type,'PROXY');
assert.equal(pair6m.CHF.value,ois.currencies.CHF.horizons['6m'].rate);
assert.equal(pair6m.EUR.type,'MIXED');
assert.equal(pair6m.EUR.value,ois.currencies.EUR.secondary_quote_context.horizons['6m'].rate_indicative);
for(const x of Object.values(pair6m)){
 assert.equal(x.is_official_ois,false);
 assert.equal(x.policy_delta_allowed,false);
 assert.equal(x.core_effect,'NONE');
 assert.equal(x.pair_effect,'NONE');
 assert(x.contract&&x.expiry);
}
assert.equal(pair6m.GBP,undefined);
assert.equal(pair6m.NZD,undefined);
const altered6m=structuredClone(ois);
altered6m.currencies.USD.horizons['6m'].quote_timestamp_verified=false;
assert.equal(indicativeSixMonth(altered6m,TODAY).USD,undefined);
const alteredPrice6m=structuredClone(ois);
alteredPrice6m.currencies.CHF.horizons['6m'].futures_price+=0.1;
assert.equal(indicativeSixMonth(alteredPrice6m,TODAY).CHF,undefined);
const alteredEUR=structuredClone(ois);
alteredEUR.currencies.EUR.secondary_quote_context.cross_date_join_allowed=true;
assert.equal(indicativeSixMonth(alteredEUR,TODAY).EUR,undefined);
assert.deepEqual(indicativeSixMonth(ois,'2026-11-12'),{});
const pairAdapter=fs.readFileSync(path.join(root,'site/control-room-preview/home-navigation-v10.js'),'utf8');
assert(pairAdapter.includes('indicativeSixMonth('));
assert(pairAdapter.includes('NON ΔOIS, solo contesto'));
assert(pairAdapter.includes('6M pricing WITHHELD'));


// Source-level 100-price identity and expiry-proximity: same dated contract,
// not an observed OIS basis or a truly synchronized 3M/6M/12M cash curve.
// Anchor expiry to each contract's VERIFIED quote day, never the viewer's day.
const targetDays={'3m':90,'6m':180,'12m':365};
const expectedGap=(expiry,quoted,term)=>
 (Date.parse(expiry+'T00:00:00Z')-Date.parse(quoted+'T00:00:00Z'))/86400000-targetDays[term];
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
  assert(Math.abs(research.tenor_gap_days)<=46, 'One-day SSR bar-to-collection tolerance must be explicitly bounded');
  assert.equal(research.tenor_gap_days,expectedGap(p.expiration,p.quote_as_of,t));
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
// A quote must NOT lose its 12M tenor because the site was opened one day later.
const eurBoundary={
 contract:'FST3M2027',symbol:'EUREX:FST3M2027',
 mapping:'nearest dated listed contract expiry to today+365d; no interpolation',
 expiration:'2027-09-15',futures_price:97.35,
 quote_as_of:'2026-10-30',quote_timestamp_verified:true,
 quote_timestamp_source:'SSR_DAILY_BAR_DATA_UPDATE_TIME'
};
const boundarySame=auditDatedFuture('EUR','12m',eurBoundary,2.65,'2026-10-30','2026-10-30');
const boundaryNext=auditDatedFuture('EUR','12m',eurBoundary,2.65,'2026-10-30','2026-10-31');
assert(boundarySame&&boundaryNext,'Overnight calendar rollover must not drop the validated quote');
assert.equal(boundarySame.tenor_gap_days,boundaryNext.tenor_gap_days);
assert.equal(boundaryNext.source_quote_verified,true);
const borderlineCHF={
 contract:'SA3U2027',symbol:'ICEEUR:SA3U2027',
 mapping:'nearest dated listed contract expiry to today+365d; no interpolation',
 expiration:'2027-12-14',futures_price:100.01,
 quote_as_of:'2026-10-29',quote_timestamp_verified:true,
 quote_timestamp_source:'SSR_DAILY_BAR_DATA_UPDATE_TIME'
};
const chfEdge=auditDatedFuture('CHF','12m',borderlineCHF,-0.01,'2026-10-29','2026-10-31');
assert(chfEdge&&Math.abs(chfEdge.tenor_gap_days)===46,
 'CHF one-day collection mismatch should show audited approximate contract, not disappear');
const chfStale=auditDatedFuture('CHF','12m',borderlineCHF,-0.01,'2026-10-29','2026-11-12');
assert.equal(chfStale,null,'One-day tolerance must never override source recency');

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
// Input rates for certified instruments can be legitimately WITHHELD
// independently of the original four-source provenance. Require three actual
// tenors for every reported full curve; an incomplete official feed is never
// counted as a complete, fresh curve or silently supplied from a future.
const expectedComplete=result.filter(x=>x.tier!=='WITHHELD'&&
  tenors.every(t=>typeof x.points[t]?.value==='number'&&
    Number.isFinite(x.points[t].value)&&fresh(x.points[t].date,TODAY)));
const expectedOfficial=expectedComplete.filter(x=>x.tier==='OFFICIAL');
const expectedOther=expectedComplete.filter(x=>x.tier!=='OFFICIAL');
assert.equal(home.official_count,expectedOfficial.length);
assert.equal(home.context_count,expectedOther.length);
assert.equal(home.covered_count,expectedComplete.length);
assert.deepEqual(home.official_codes.sort(),expectedOfficial.map(x=>x.ccy).sort());
assert.deepEqual(home.context_codes.sort(),expectedOther.map(x=>x.ccy).sort());
assert.deepEqual(home.incomplete_codes.sort(),
  result.filter(x=>!expectedComplete.includes(x)).map(x=>x.ccy).sort());
for(const ccy of ['GBP','JPY','CAD','AUD']){
  if(!tenors.every(t=>typeof ois.currencies[ccy].horizons[t]?.rate==='number'))
    assert(home.incomplete_codes.includes(ccy),ccy+' incomplete official curve must be visible as incomplete');
}
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
// Deterministic verified same-contract archive: never join futures rolls or
// synthesize daily OIS deltas from method-only operational snapshots.
const historicalRows=observedHistory;
assert(historicalRows.length>=23,'The 23 verified initial source bars must be preserved');
assert(['e5a3cede0df','a611277716c','195ab3c45d9'].every(
  sha=>historicalRows.some(r=>r.source_commit===sha)));
assert(historicalRows.every(r=>r.official_ois_quote===false &&
  r.backtest_eligible_as_official===false &&
  r.policy_delta_eligible===false));
const archive=fixedBars.map(x=>JSON.stringify(x)).join('\n')+'\n'; // Frozen PIT replay.
const moves=matchedResearchMoves(archive,result,TODAY);
assert.equal(moves.length,9,JSON.stringify(moves));
const expectation={
 USD:{'3m':{code:'ZQZ2026',bp:-1,from:'2026-10-19',to:'2026-10-20'},
      '6m':{code:'ZQJ2027',bp:0,from:'2026-10-19',to:'2026-10-20'},
      '12m':{code:'ZQV2027',bp:2.5,from:'2026-10-19',to:'2026-10-20'}},
 EUR:{'3m':{code:'FST3V2026',bp:0.25,from:'2026-10-16',to:'2026-10-19'},
      '6m':{code:'FST3G2027',bp:-1,from:'2026-10-16',to:'2026-10-19'},
      '12m':{code:'FST3M2027',bp:-1,from:'2026-10-19',to:'2026-10-20'}},
 CHF:{'3m':{code:'SA3U2026',bp:0.25,from:'2026-10-19',to:'2026-10-20'},
      '6m':{code:'SA3Z2026',bp:0,from:'2026-10-19',to:'2026-10-20'},
      '12m':{code:'SA3M2027',bp:1.5,from:'2026-10-19',to:'2026-10-20'}}
};
for(const [ccy,terms] of Object.entries(expectation)){
 for(const [term,expected] of Object.entries(terms)){
  const matches=moves.filter(x=>x.ccy===ccy&&x.tenor===term);
  assert.equal(matches.length,1,ccy+' '+term);
  const r=matches[0];
  assert.equal(r.contract,expected.code);
  assert.equal(r.from,expected.from);
  assert.equal(r.to,expected.to);
  assert.equal(r.delta_bp,expected.bp);
  assert(r.calendar_gap_days>=1&&r.calendar_gap_days<=7);
  assert.equal(r.research_only,true);
  assert.equal(r.policy_delta_allowed,false);
  assert.equal(r.official_ois,false);
 }
}
const sameContractHtml=view(result,moves);
assert(sameContractHtml.includes('data-same-contract="RESEARCH_ONLY"'));
assert(sameContractHtml.includes('stessi contratti futures'));
assert.equal((sameContractHtml.match(/class="gmfq-same-value" data-term=/g)||[]).length,9);
assert(sameContractHtml.includes('FST3G2027'));
assert(sameContractHtml.includes('SA3M2027'));
assert(sameContractHtml.includes('Non sono ΔOIS ufficiali'));
assert(!sameContractHtml.includes('GREEN_OFFICIAL'));
// Reject duplicate, official-promotion, fake futures price, fake listed symbol,
// mismatched roll and stale date; a missing tenor cannot borrow another tenor.
assert.deepEqual(matchedResearchMoves(archive+archive.split('\n')[0]+'\n',result,TODAY),[]);
assert.deepEqual(matchedResearchMoves(archive.replace('"official_ois_quote":false',
  '"official_ois_quote":true'),result,TODAY),[]);
assert.deepEqual(matchedResearchMoves(archive.replace('"backtest_eligible_as_official":false',
  '"backtest_eligible_as_official":true'),result,TODAY),[]);
assert.deepEqual(matchedResearchMoves(archive,result,'2026-11-10'),[]);
const rolled=structuredClone(result);
rolled.find(x=>x.ccy==='USD').points['6m'].contract='ZQH2027';
assert(!matchedResearchMoves(archive,rolled,TODAY).some(x=>x.ccy==='USD'&&x.tenor==='6m'));
const badMaturity=structuredClone(result);
badMaturity.find(x=>x.ccy==='CHF').points['12m'].expires='2028-12-31';
assert(!matchedResearchMoves(archive,badMaturity,TODAY).some(x=>x.ccy==='CHF'&&x.tenor==='12m'));
const partialResearchFixture=structuredClone(result);
delete partialResearchFixture.find(x=>x.ccy==='EUR').points['6m'];
const partialMoves=matchedResearchMoves(archive,partialResearchFixture,TODAY);
assert.equal(partialMoves.length,8);
assert(!partialMoves.some(x=>x.ccy==='EUR'&&x.tenor==='6m'));
const absent=view(result,[]);
assert(absent.includes('osservazioni confrontabili non disponibili'));

const html=view(result);
assert(html.includes('<details class="gmfq-est-disclosure" open data-default="OPEN">'));
assert(html.includes('<summary>Tabella G8 · 3M / 6M / 12M'));
assert(html.includes('8/8 valute con riferimenti numerici'));
assert(html.includes('4 fonti certificate'));
assert(html.includes('1 scenario NZD'));
assert(!html.includes(' senza fonte attendibile'));
assert.equal((html.match(/class="gmfq-est-row" data-ccy=/g)||[]).length,8);
assert(html.includes('</div></details>'));
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
