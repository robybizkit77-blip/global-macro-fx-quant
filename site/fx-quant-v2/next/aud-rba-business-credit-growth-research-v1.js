'use strict';
/* RBA monthly financial-aggregates release, break-adjusted business credit growth.
 * Separate from D2 stock levels and FX Core. The verified monthly RBA release
 * is the preferred source for credit growth; never derive growth from D2 levels.
 */
(function(root){
 const data={
  schema:'GMFQ_NEXT_AUD_RBA_BUSINESS_CREDIT_GROWTH_V1',
  status:'WITHHELD_UNTIL_OFFICIAL_RELEASE_VERIFIED',
  country:'AUD',
  publisher:'Reserve Bank of Australia',
  source_archive:'https://www.rba.gov.au/statistics/frequency/fin-agg/2026/',
  source_url:'https://www.rba.gov.au/statistics/frequency/fin-agg/2026/fin-agg-0926.html',
  label:'Business credit growth (non-financial businesses), break-adjusted',
  category:'business_credit_growth_adjusted',
  frequency:'M',
  unit:'percent',
  source_table:'RBA Financial Aggregates — Business',
  breaks_adjusted:true,
  seasonally_adjusted:true,
  is_credit_stock:false,
  observation_is_not_publication_date:true,
  first_release_pit_verified:false,
  eligible_for_fx_core:false,
  eligible_for_backtest:false,
  observation_period:null,
  release_date:null,
  monthly_growth_pct:null,
  prior_month_growth_pct:null,
  annual_growth_pct:null,
  prior_year_growth_pct:null,
  inference:'RBA D1 adjusted credit growth, not D2 unadjusted loan stock or bank lending flows. FX causality and market pricing must be verified separately.'
 };
 root.FXQuantAUDBusinessCreditGrowthResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
