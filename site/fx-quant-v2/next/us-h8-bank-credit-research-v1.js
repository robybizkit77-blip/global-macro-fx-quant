'use strict';
/* Validated Fed H.8 and SLOOS via FRED; research-only. */
(function(root){
 const data={
 "schema": "GMFQ_NEXT_US_H8_CREDIT_RESEARCH_V1",
 "status": "VERIFIED_FED_H8_FRED_MIRROR_RESEARCH_ONLY",
 "country": "USD",
 "publisher": "Board of Governors of the Federal Reserve System (US)",
 "mirror": "FRED (Federal Reserve Bank of St. Louis)",
 "series_id": "TOTBKCR",
 "source_url": "https://fred.stlouisfed.org/series/TOTBKCR",
 "api_url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=TOTBKCR&cosd=2026-06-01",
 "label": "Bank Credit, All Commercial Banks",
 "category": "bank_credit_stock",
 "unit": "miliardi USD",
 "frequency": "W",
 "seasonally_adjusted": true,
 "first_release_pit_verified": false,
 "eligible_for_fx_core": false,
 "eligible_for_backtest": false,
 "observation_is_not_publication_date": true,
 "last_checked_rome": "2026-11-22",
 "latest_observation": "2026-11-11",
 "reference_week_revision_pct": 0.153,
 "dates": [
  "2026-06-03",
  "2026-06-10",
  "2026-06-17",
  "2026-06-24",
  "2026-07-01",
  "2026-07-08",
  "2026-07-15",
  "2026-07-22",
  "2026-07-29",
  "2026-08-05",
  "2026-08-12",
  "2026-08-19",
  "2026-08-26",
  "2026-09-02",
  "2026-09-09",
  "2026-09-16",
  "2026-09-23",
  "2026-09-30",
  "2026-10-07",
  "2026-10-14",
  "2026-10-21",
  "2026-10-28",
  "2026-11-04",
  "2026-11-11"
 ],
 "values": [
  19588.1281,
  19646.069,
  19660.3214,
  19684.2237,
  19656.0844,
  19681.286,
  19774.8299,
  19749.5097,
  19779.1086,
  19795.1134,
  19806.5435,
  19846.5214,
  19853.4355,
  19860.0585,
  19897.0439,
  19911.2898,
  19891.6143,
  19907.8564,
  19950.9531,
  19990.9722,
  20016.9282,
  20022.4133,
  20070.9042,
  20133.1843
 ],
 "inference": "Stock Fed H.8 rivisto via FRED; non nuovi prestiti, prestiti originati o easing automatico. Ricerca separata dalla serie canonica.",
 "lending_standards": {
  "series_id": "DRTSCILM",
  "source_url": "https://fred.stlouisfed.org/series/DRTSCILM",
  "frequency": "Q",
  "observations": [
   [
    "2024-01-01",
    14.5
   ],
   [
    "2024-04-01",
    15.6
   ],
   [
    "2024-07-01",
    7.9
   ],
   [
    "2024-10-01",
    0.0
   ],
   [
    "2025-01-01",
    6.2
   ],
   [
    "2025-04-01",
    18.5
   ],
   [
    "2025-07-01",
    9.5
   ],
   [
    "2025-10-01",
    6.5
   ],
   [
    "2026-01-01",
    5.3
   ],
   [
    "2026-04-01",
    8.1
   ],
   [
    "2026-07-01",
    0.0
   ],
   [
    "2026-10-01",
    1.7
   ]
  ]
 }
};
 root.FXQuantUSBanksCreditResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
