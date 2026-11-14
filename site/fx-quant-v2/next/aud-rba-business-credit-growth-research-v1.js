'use strict';
/* RBA official growth, source-dated, research-only. */
(function(root){
 const data={
 "schema": "GMFQ_NEXT_AUD_RBA_BUSINESS_CREDIT_GROWTH_V1",
 "status": "VERIFIED_RBA_FIN_AGG_BUSINESS_GROWTH_RESEARCH_ONLY",
 "country": "AUD",
 "publisher": "Reserve Bank of Australia",
 "source_archive": "https://www.rba.gov.au/statistics/frequency/fin-agg/2026/",
 "source_url": "https://www.rba.gov.au/statistics/frequency/fin-agg/2026/fin-agg-0926.html",
 "label": "Business credit growth (non-financial businesses), break-adjusted",
 "category": "business_credit_growth_adjusted",
 "frequency": "M",
 "unit": "percent",
 "source_table": "RBA Financial Aggregates — Business",
 "breaks_adjusted": true,
 "seasonally_adjusted": true,
 "is_credit_stock": false,
 "observation_is_not_publication_date": true,
 "first_release_pit_verified": false,
 "eligible_for_fx_core": false,
 "eligible_for_backtest": false,
 "last_checked_rome": "2026-11-14",
 "observation_period": "2026-09",
 "release_date": "2026-10-30",
 "monthly_growth_pct": 0.9,
 "prior_month_growth_pct": 0.9,
 "annual_growth_pct": 11.3,
 "prior_year_growth_pct": 9.4,
 "inference": "Official adjusted monthly and year-ended business credit growth (D1 economic meaning); never infer this from D2 stocks, and no causal FX claim."
};
 root.FXQuantAUDBusinessCreditGrowthResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
