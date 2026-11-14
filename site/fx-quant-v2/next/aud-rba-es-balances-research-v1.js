'use strict';
/* Independent official RBA weekly balance-sheet ES balances, research only.
 * Matched once with canonical AUD liquidity at 2026-09-16 (173965 AUD mn).
 * NOT the A3 daily AESAT acquisition, loan creation or an FX signal.
 * Fail closed until collector verifies exact official field and dated movement.
 */
(function(root){
 const data={
  schema:'GMFQ_NEXT_AUD_RBA_ES_BALANCES_V1',
  status:'WITHHELD_UNTIL_ISSUER_VALIDATION',
  country:'AUD',publisher:'Reserve Bank of Australia',
  source_url:'https://www.rba.gov.au/statistics/balance-sheet/',
  source_contract:'RBA weekly balance sheet / Exchange Settlement balances',
  a3_comparison_contract:'A3 AESAT / Total ES Balances, same reporting definition, different frequency',
  source_period:null,source_release_timestamp_verified:false,
  latest_balance_million_aud:null,weekly_movement_million_aud:null,
  previous_implied_million_aud:null,unit:'milioni AUD',frequency:'W',
  asof_canonical_overlap:'2026-09-16',value_canonical_overlap:173965,
  first_release_pit_verified:false,eligible_for_fx_core:false,
  eligible_for_backtest:false,observation_is_not_publication_date:true,
  inference:'RBA settlement reserve stock; not net liquidity injections, loan creation, reserve availability to nonbanks or proof of AUD buying.'
 };
 root.FXQuantAUDESBalancesResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
