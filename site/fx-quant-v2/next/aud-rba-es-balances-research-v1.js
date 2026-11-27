'use strict';
/* Official RBA weekly settlement balances; separate research source. */
(function(root){
 const data={
 "schema": "GMFQ_NEXT_AUD_RBA_ES_BALANCES_V1",
 "status": "VERIFIED_RBA_WEEKLY_ES_BALANCE_RESEARCH_ONLY",
 "country": "AUD",
 "publisher": "Reserve Bank of Australia",
 "source_url": "https://www.rba.gov.au/statistics/balance-sheet/",
 "source_contract": "RBA weekly balance sheet / Exchange Settlement balances",
 "a3_comparison_contract": "A3 AESAT / Total ES Balances, same category, different source frequency",
 "unit": "milioni AUD",
 "frequency": "W",
 "asof_canonical_overlap": "2026-09-16",
 "value_canonical_overlap": 173965,
 "last_checked_rome": "2026-11-27",
 "source_period": "2026-11-25",
 "latest_balance_million_aud": 163941,
 "weekly_movement_million_aud": -24074,
 "previous_implied_million_aud": 188015,
 "source_release_timestamp_verified": false,
 "first_release_pit_verified": false,
 "eligible_for_fx_core": false,
 "eligible_for_backtest": false,
 "observation_is_not_publication_date": true,
 "inference": "Riserve presso RBA, non credito nuovo, non liquidità netta disponibile a nonbanche, non flussi Forex. Movimento settimanale pubblicato direttamente, precedente ricavato per sottrazione."
};
 root.FXQuantAUDESBalancesResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
