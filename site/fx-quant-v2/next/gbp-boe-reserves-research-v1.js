'use strict';
/* Official Bank of England weekly reserves, RPWB56A-equivalent, research-only.
 * Publisher's weekly report: current and prior balances, GBP millions.
 * Source dates are observations, not first-release timing; never FX Core.
 */
(function(root){
 const data={
  schema:'GMFQ_NEXT_GBP_BOE_WEEKLY_RESERVES_V1',
  status:'WITHHELD_UNTIL_ISSUER_VALIDATION',
  country:'GBP',publisher:'Bank of England',
  source_index:'https://www.bankofengland.co.uk/weekly-report/balance-sheet-and-weekly-report',
  source_url:null,series_id:'RPWB56A',source_contract:'BoE Weekly Report / Sterling Liabilities / Reserves balances',
  source_period:null,previous_period:null,published_on:null,
  latest_balance_million_gbp:null,previous_balance_million_gbp:null,weekly_change_million_gbp:null,
  unit:'milioni GBP',frequency:'W',seasonally_adjusted:false,
  asof_canonical_overlap:'2026-09-16',value_canonical_overlap:638012,
  first_release_pit_verified:false,eligible_for_fx_core:false,
  eligible_for_backtest:false,observation_is_not_publication_date:true,
  inference:'Riserve BoE detenute dalle banche: passività della banca centrale, non prestiti o flussi di acquisto GBP. Fonte separata da NATIVE_LIQ_DATA.'
 };
 root.FXQuantGBPBoEReservesResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
