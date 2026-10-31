'use strict';
/* Live-source grounded, no fabricated rates: CHF spot+modeled 2Y and NZD B2 pending. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const {ratesContinuity,continuityHtml}=require('../site/control-room-preview/ois-pricing-estimates-v1.js');
const rates=JSON.parse(fs.readFileSync('live_data/sections/NATIVE_RATES_DATA.json'));
const chf=JSON.parse(fs.readFileSync('live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json'));
const nzd=JSON.parse(fs.readFileSync('live_data/sections/NZD_B2_GOVT_WEB_REVIEW_CONTEXT.json'));
const now='2026-10-31',view=ratesContinuity(rates,chf,nzd,now);
assert.equal(view.schema,'GMFQ_CHF_NZD_2Y10Y_DATED_RESEARCH_V1');
assert.equal(view.official_rates_modified,false);
assert.equal(view.official_spread_signals,false);
assert.equal(view.fx_effect,'NONE');
assert(view.CHF&&view.NZD,'Both CHF and NZD study-only evidence must survive');
assert.equal(view.CHF.official_pair_date,'2026-09-30');
assert.equal(view.CHF.old_2y,0.287);
assert.equal(view.CHF.old_10y,0.586);
assert.equal(view.CHF.observed_10y_date,'2026-10-30');
assert.equal(view.CHF.observed_10y,0.505);
assert.equal(view.CHF.slope_window_observations,60);
assert.equal(view.CHF.official_2y10y_spread_available,false);
assert.equal(view.CHF.percentile_band_is_forecast_interval,false);
assert.equal(view.CHF.two_year_not_observed_same_day,true);
assert(Number.isFinite(view.CHF.estimated_2y));
assert(view.CHF.illustrative_2y_range[0]<=view.CHF.estimated_2y);
assert(view.CHF.estimated_2y<=view.CHF.illustrative_2y_range[1]);
assert.equal(view.NZD.official_pair_date,'2026-10-16');
assert.equal(view.NZD.unapproved_pair_date,'2026-10-22');
assert.equal(view.NZD.reviewed_2y,3.91);
assert.equal(view.NZD.reviewed_10y,4.98);
assert.equal(view.NZD.latest_is_official_canonical,false);
assert.equal(view.NZD.incomplete_excel_and_human_review,true);
assert.equal(view.NZD.no_observations_claimed_after,'2026-10-22');
const html=continuityHtml(view);
for(const clause of ['data-continuity-ccy="CHF"','data-continuity-ccy="NZD"',
 'data-official-curve="false"','2Y <strong>stima ≈','non ancora approvate',
 'Nessun rendimento inventato','non è un intervallo di previsione validato'])
 assert(html.includes(clause),'missing explicit nonpromotional disclosure: '+clause);
assert(!html.includes('2Y ufficiale 2026-10-30'));
assert(!html.includes('NZD · B2 ufficiale'));
const baseline=JSON.stringify(rates),sourceChf=JSON.stringify(chf),sourceNzd=JSON.stringify(nzd);
function reject(label,change,check){
 const a=structuredClone(rates),b=structuredClone(chf),c=structuredClone(nzd);
 change(a,b,c);
 const x=ratesContinuity(a,b,c,now);
 assert(check(x),label);
}
reject('CHF fake 2Y present',(_,c)=>c.has_current_2y=true,x=>x.CHF===null&&x.NZD!==null);
reject('CHF false same-day curve allowed',(_,c)=>c.eligible_for_curve_spreads=true,x=>x.CHF===null);
reject('CHF tampered source SHA',(_,c)=>c.source_html_sha256='forged',x=>x.CHF===null);
reject('CHF future-dated 10Y',(_,c)=>c.as_of='2026-11-02',x=>x.CHF===null);
reject('CHF duplicate history day',(a)=>a.CHF.history2.dates[2]=a.CHF.history2.dates[1],x=>x.CHF===null);
reject('CHF historical 2Y last value altered',(a)=>a.CHF.history2.values[a.CHF.history2.values.length-1]+=0.1,x=>x.CHF===null);
reject('CHF current source 10Y inconsistent',(_,c)=>c.value_percent='NOT A NUMBER',x=>x.CHF===null);
reject('NZD unapproved web reread must never promote',(_,c)=>c.status='OFFICIAL_VERIFIED',x=>x.NZD===null);
reject('NZD source missing human approval status',(_,__,n)=>n.evidence.independent_human_reviewer_confirmed=true,x=>x.NZD===null);
reject('NZD source inconsistent existing official anchor',(_,__,n)=>n.canonical_at_review['2Y']+=.1,x=>x.NZD===null);
reject('NZD unvalidated spread status',(_,__,n)=>n.governance.eligible_for_rate_spreads=true,x=>x.NZD===null);
reject('NZD false policy effect',(_,__,n)=>n.governance.pair_engine_effect='BUY',x=>x.NZD===null);
reject('NZD future source date',(_,__,n)=>n.as_of='2026-11-06',x=>x.NZD===null);
reject('NZD curve arithmetic mismatch',(_,__,n)=>n.curve_bp=95,x=>x.NZD===null);
const stale=ratesContinuity(rates,chf,nzd,'2026-11-10');
assert(stale.CHF&&stale.CHF.estimated_2y===null,'Stale CHF cannot be represented as current synthetic 2Y');
assert(stale.NZD&&stale.NZD.no_observations_claimed_after==='2026-10-22');
const empty=ratesContinuity({},null,null,now);
assert.equal(empty.CHF,null);assert.equal(empty.NZD,null);
assert.equal(JSON.stringify(rates),baseline);
assert.equal(JSON.stringify(chf),sourceChf);
assert.equal(JSON.stringify(nzd),sourceNzd);
console.log('CHF_NZD_2Y10Y_DATED_CONTINUITY_RESEARCH_V1_GREEN',JSON.stringify({
 chf_official_pair:view.CHF.official_pair_date,chf_10y:view.CHF.observed_10y,
 chf_model_2y:view.CHF.estimated_2y,nzd_pending:view.NZD.unapproved_pair_date,
 official_changes:0,signal_changes:0,negative_fixtures:14}));
