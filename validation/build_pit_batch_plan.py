#!/usr/bin/env python3
import json, re, urllib.request, datetime as dt
from pathlib import Path

OUT=Path("validation/pit_batch")
OUT.mkdir(parents=True, exist_ok=True)

# This script does not fabricate values. It creates provider-group batch jobs and
# records whether a provider supports structured vintage or dated-release recovery.
PROVIDERS = {
  "USD": {
    "providers":["BEA","BLS","Federal Reserve G.17","Census Retail Trade","U.S. Department of Labor UI Claims"],
    "series":[
      "US_PCEC96_history_value","US_NEWORDER_history_NEWORDER","US_INDPRO_history_value",
      "US_DSPIC96_history_DSPIC96","US_PI_history_PI","US_RRSFS_history_value",
      "US_JTSHIR_history_JTSHIR","US_JTSJOL_history_value","US_JTSQUR_history_JTSQUR",
      "US_PAYEMS_history_value","US_OPHNFB_history_OPHNFB","US_AHE_TOTAL_PRIVATE_history_value",
      "US_CCSA_history_CCSA","US_ICSA_history_value"
    ]
  },
  "EUR": {
    "providers":["Eurostat","ECB"],
    "series":["EA_IP_history_value","EA_RETAIL_VOL_history_value","EA_UNEMP_history_value","EA_EMPLOYMENT_history_value","EA_NEGOTIATED_WAGES_YOY_history_value"]
  },
  "GBP": {
    "providers":["ONS","HMRC"],
    "series":["UK_PRODUCTION_history_value","UK_RETAIL_VOL_history_value","UK_UNEMP_RATE_history_value","UK_PAYE_PAYROLLED_EMPLOYEES_SA_history_value","UK_EMPLOYMENT_RATE_history_value"]
  },
  "JPY": {
    "providers":["Statistics Bureau of Japan","METI"],
    "series":["JP_IIP_history_value","JP_RETAIL_history_value","JP_UNEMP_RATE_history_value","JP_EMPLOYED_history_value"]
  },
  "CHF": {
    "providers":["Swiss FSO","SECO"],
    "series":["CH_PRODUCTION_history_value","CH_RETAIL_REAL_history_value","CH_UNEMP_RATE_history_value","CH_EMPLOYMENT_history_value"]
  },
  "CAD": {
    "providers":["Statistics Canada"],
    "series":["CA_REAL_GDP_M_history_value","CA_RETAIL_VOLUME_history_value","CA_UNEMP_RATE_history_value","CA_EMPLOYMENT_history_value"]
  },
  "AUD": {
    "providers":["ABS"],
    "series":["AU_REAL_GDP_QOQ_ABS_history_value","AU_HOUSEHOLD_SPENDING_history_value","AU_UNEMP_RATE_history_value","AU_EMPLOYMENT_history_value","AU_WPI_YOY_history_value"]
  },
  "NZD": {
    "providers":["Stats NZ","RBNZ"],
    "series":["NZ_REAL_GDP_Q_history_value","NZ_RETAIL_VOLUME_Q_history_value","NZ_UNEMP_RATE_history_value","NZ_EMPLOYED_history_value","NZ_RBNZ_EXP_UNEMP_1Y_history_value","NZ_RBNZ_EXP_UNEMP_2Y_history_value","NZ_RBNZ_EXP_WAGE_1Y_history_value","NZ_RBNZ_EXP_WAGE_2Y_history_value"]
  }
}

# Provider strategy registry. Keep conservative statuses.
STRATEGIES = {
  "Eurostat":"STRUCTURED_VINTAGE",
  "Statistics Canada":"STRUCTURED_OR_DATED_RELEASE",
  "Federal Reserve G.17":"STRUCTURED_VINTAGE",
  "BEA":"DATED_RELEASE_ARCHIVE",
  "BLS":"DATED_RELEASE_ARCHIVE",
  "Census Retail Trade":"DATED_RELEASE_ARCHIVE",
  "U.S. Department of Labor UI Claims":"DATED_RELEASE_ARCHIVE",
  "ECB":"DATED_RELEASE_OR_SERIES_MATCH_PENDING",
  "ONS":"DATED_RELEASE_ARCHIVE",
  "HMRC":"DATED_RELEASE_ARCHIVE",
  "Statistics Bureau of Japan":"DATED_RELEASE_ARCHIVE",
  "METI":"DATED_RELEASE_ARCHIVE",
  "Swiss FSO":"DATED_RELEASE_ARCHIVE",
  "SECO":"DATED_RELEASE_OR_SERIES_MATCH_PENDING",
  "ABS":"DATED_RELEASE_ARCHIVE",
  "Stats NZ":"DATED_RELEASE_ARCHIVE",
  "RBNZ":"DATED_RELEASE_ARCHIVE"
}

jobs=[]
for ccy, cfg in PROVIDERS.items():
    strategies=[{"provider":p,"strategy":STRATEGIES.get(p,"UNKNOWN")} for p in cfg["providers"]]
    jobs.append({
      "currency":ccy,
      "series_count":len(cfg["series"]),
      "series":cfg["series"],
      "providers":strategies,
      "target_start":"2020-08-31",
      "target_end":"2026-09-30",
      "checkpoint_frequency":"month-end",
      "status":"READY_FOR_BATCH_EXTRACTION_PLAN"
    })

report={
  "schema":"GMFQ_PIT_BATCH_PLAN_V1",
  "created_at":"2026-10-02",
  "purpose":"Industrialize point-in-time Macro Core reconstruction by provider/currency instead of manual series-by-series pilots.",
  "totals":{
    "currencies":len(jobs),
    "series":sum(j["series_count"] for j in jobs)
  },
  "execution_order":[
    "Structured vintage providers first: Fed G.17, Eurostat, Statistics Canada.",
    "Then dated-release providers grouped by institution.",
    "Resolve exact-series-match pending families separately.",
    "Normalize every recovered observation to market-availability date.",
    "Build per-currency Crescita/Lavoro PIT blocks.",
    "Run frozen-engine sensitivity harness before full backtest."
  ],
  "jobs":jobs,
  "guardrails":[
    "No revised current-history substitution for missing first release.",
    "No guessed publication lag.",
    "No threshold tuning during PIT reconstruction.",
    "Any unrecoverable series becomes WITHHELD_PIT or is formally excluded from that test."
  ]
}
(OUT/"PIT_BATCH_PLAN_V1_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report["totals"]))
