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
 "last_checked_rome": "2026-11-24",
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
 },
 "money_stock": {
  "series_id": "M2SL",
  "source_url": "https://fred.stlouisfed.org/series/M2SL",
  "frequency": "M",
  "unit": "miliardi USD",
  "seasonally_adjusted": true,
  "dates": [
   "2024-01",
   "2024-02",
   "2024-03",
   "2024-04",
   "2024-05",
   "2024-06",
   "2024-07",
   "2024-08",
   "2024-09",
   "2024-10",
   "2024-11",
   "2024-12",
   "2025-01",
   "2025-02",
   "2025-03",
   "2025-04",
   "2025-05",
   "2025-06",
   "2025-07",
   "2025-08",
   "2025-09",
   "2025-10",
   "2025-11",
   "2025-12",
   "2026-01",
   "2026-02",
   "2026-03",
   "2026-04",
   "2026-05",
   "2026-06",
   "2026-07",
   "2026-08",
   "2026-09"
  ],
  "values": [
   20808.5,
   20896.0,
   20940.9,
   20929.9,
   20995.3,
   21045.0,
   21072.7,
   21165.8,
   21249.9,
   21311.1,
   21429.3,
   21462.0,
   21513.6,
   21581.1,
   21657.4,
   21743.3,
   21808.8,
   21916.1,
   21998.1,
   22065.9,
   22149.2,
   22223.1,
   22253.2,
   22328.8,
   22386.6,
   22572.3,
   22613.9,
   22728.0,
   22980.9,
   23077.7,
   23177.4,
   23300.9,
   23413.9
  ],
  "latest_observation": "2026-09",
  "first_release_pit_verified": false,
  "eligible_for_fx_core": false
 }
};
 root.FXQuantUSBanksCreditResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
