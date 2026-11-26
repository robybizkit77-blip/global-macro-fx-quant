'use strict';
/* Issuer-verified Bank of England sterling reserves, research only. */
(function(root){
 const data={
 "schema": "GMFQ_NEXT_GBP_BOE_WEEKLY_RESERVES_V1",
 "status": "VERIFIED_BOE_WEEKLY_RESERVE_STOCK_RESEARCH_ONLY",
 "country": "GBP",
 "publisher": "Bank of England",
 "source_index": "https://www.bankofengland.co.uk/weekly-report/balance-sheet-and-weekly-report",
 "series_id": "RPWB56A",
 "source_contract": "BoE Weekly Report / Sterling Liabilities / Reserves balances",
 "frequency": "W",
 "unit": "milioni GBP",
 "seasonally_adjusted": false,
 "asof_canonical_overlap": "2026-09-16",
 "value_canonical_overlap": 638012,
 "last_checked_rome": "2026-11-26",
 "source_period": "2026-11-25",
 "previous_period": "2026-11-18",
 "published_on": "2026-11-26",
 "latest_balance_million_gbp": 650276,
 "previous_balance_million_gbp": 646914,
 "weekly_change_million_gbp": 3362,
 "source_url": "https://www.bankofengland.co.uk/weekly-report/2026/25-november-2026",
 "observation_is_not_publication_date": true,
 "first_release_pit_verified": false,
 "eligible_for_fx_core": false,
 "eligible_for_backtest": false,
 "inference": "Reserves balances: stock of BoE liabilities held by banks; not new credit, not net liquidity to markets, not observed GBP flows. Weekly issuer reports both values."
};
 root.FXQuantGBPBoEReservesResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
