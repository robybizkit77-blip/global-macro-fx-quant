'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {ratesContinuity,continuityHtml}=require('../site/control-room-preview/ois-pricing-estimates-v1.js');
const x=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const rates=x('live_data/sections/NATIVE_RATES_DATA.json'),
chf=x('live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json'),
old=x('live_data/sections/NZD_B2_GOVT_WEB_REVIEW_CONTEXT.json'),
latest=x('live_data/sections/NZD_B2_GOVT_LATEST_WEB_RESEARCH.json');
const now='2026-10-31';
const result=ratesContinuity(rates,chf,old,now,latest);
assert(result.CHF&&result.NZD);
assert.equal(result.NZD.unapproved_pair_date,'2026-10-29');
assert.equal(result.NZD.reviewed_2y,3.77);
assert.equal(result.NZD.reviewed_10y,4.87);
assert.equal(result.NZD.no_observations_claimed_after,'2026-10-29');
assert.equal(result.NZD.independent_xlsx_crosscheck,false);
assert.equal(result.NZD.latest_is_official_canonical,false);
assert.equal(result.NZD.source_quality,'RBNZ_B2_OFFICIAL_SINGLE_WEB_TEXT__XLSX_PENDING');
const h=continuityHtml(result);
assert(h.includes('2026-10-29')&&h.includes('3,77%')&&h.includes('4,87%'));
assert(h.includes('non ancora riconciliata con XLSX'));
assert(!h.includes('NZD · B2 ufficiale'));
assert.equal(rates.NZD.date,'2026-10-16');
assert.equal(old.as_of,'2026-10-22');
assert.equal(result.official_rates_modified,false);
assert.equal(result.official_spread_signals,false);
assert.equal(result.fx_effect,'NONE');
function noPromotion(description,edit){
 const q=structuredClone(latest);edit(q);
 const bad=ratesContinuity(rates,chf,old,now,q);
 assert(bad.NZD&&bad.NZD.unapproved_pair_date==='2026-10-22',
        'Invalid newer RBNZ evidence must leave independently retained Oct22 candidate: '+description);
}
noPromotion('unapproved falsely approved',o=>o.governance.eligible_for_official_canonical_promotion=true);
noPromotion('independent spreadsheet falsely passed',o=>o.governance.independent_xlsx_reconciliation_completed=true);
noPromotion('source URL replaced',o=>o.source_url='https://example.org');
noPromotion('source latest date modified',o=>o.latest_official_web_read_only.date='2026-10-28');
noPromotion('2026-10-16 anchor altered',o=>o.historical_approved_anchor['2Y']+=.01);
noPromotion('Oct22 prior double-read disagreement',o=>o.website_rows[5]['10Y']+=.01);
noPromotion('new 2Y no longer matches last table row',o=>o.latest_official_web_read_only['2Y']+=.01);
noPromotion('government 10Y vs 2Y spread inconsistency',o=>o.latest_official_web_read_only.curve_bp=95);
noPromotion('not RBNZ government bonds',o=>o.basis='swap rate');
noPromotion('duplicate observation',o=>o.website_rows[9].date=o.website_rows[8].date);
noPromotion('invented new source date',o=>o.latest_observation_date='2026-10-31');
noPromotion('false pair FX effect',o=>o.governance.pair_engine_effect='TRADE');
const future=ratesContinuity(rates,chf,old,now,{...latest,latest_observation_date:'2026-11-04'});
assert.equal(future.NZD.unapproved_pair_date,'2026-10-22');
const fallback=ratesContinuity(rates,chf,old,now,null);
assert.equal(fallback.NZD.unapproved_pair_date,'2026-10-22');
console.log('NZD_RBNZ_B2_OCT29_HTML_RESEARCH_NO_OFFICIAL_PROMOTION_PASS',
 JSON.stringify({asof:result.NZD.unapproved_pair_date,y2:result.NZD.reviewed_2y,
   y10:result.NZD.reviewed_10y,source_research_only:true,negative_cases:12}));
