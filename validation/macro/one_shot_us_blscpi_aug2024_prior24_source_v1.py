#!/usr/bin/env python3
"""One-time BLS Aug-2024 CPI-U source XLSX retrieval: research bytes, no production.

Required since 24 issuer-month files Sep-2024..Sep-2026 contain only
23 PRIOR published points before Sep-2026. Aug-2024 adds the 24th
previous published point over 25 months (Oct-2025 missing). Never
pretend 24 consecutive calendar months or original issue-day bytes.
"""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen

from validation.macro.one_shot_us_cpi_issue_xlsx_sa_index_extract_v1 import read_candidate_index

URL="https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-202408.xlsx"
NEWS="https://www.bls.gov/news.release/archives/cpi_09112024.htm"
DAY="2024-09-11"
PATH=Path("/tmp/macro-v2-aug24-issuer-workbook")

def main():
    PATH.mkdir(parents=True,exist_ok=True)
    with urlopen(Request(URL,headers={"User-Agent":"Mozilla/5.0","Accept":"*/*"}),timeout=20) as response:
        if response.status!=200 or response.geturl()!=URL: raise ValueError("BLS URL/status changed")
        data=response.read(350001)
    if len(data)<10000 or len(data)>350000 or data[:4]!=b"PK\x03\x04":
        raise ValueError("incorrect original BLS XLSX payload")
    facts=read_candidate_index(data,"2024-08")
    if facts["current_index_SA"] in (None,"") or facts["same_issue_vintage_12mo_base"] is None:
        raise ValueError("BLS Aug-2024 US all items SA index or 12-month base missing")
    digest=hashlib.sha256(data).hexdigest()
    raw=PATH/"bls_cpi_u_202408.xlsx"
    raw.write_bytes(data)
    result={
      "schema":"GMFQ_MACRO_V2_BLS_CPI_AUG24_ISSUE_WORKBOOK_ONESHOT_BYTES_V1",
      "publisher_url":URL,"original_BLS_archive_news_url":NEWS,
      "publisher_release_day":DAY,"economic_month":"2024-08",
      "captured_utc":datetime.now(timezone.utc).isoformat(),
      "download_SHA256":digest,"downloaded_bytes":len(data),
      "sa_index":facts["current_index_SA"],
      "same_issuer_month_12mo_base_SA":facts["same_issue_vintage_12mo_base"],
      "same_issuer_month_SA_yoy_pct":facts["same_issue_vintage_SA_index_yoy_pct"],
      "BLS_first_issuer_day_binary_sha256_proven":False,
      "missing_2025_10_filled":False,
      "safe_to_publish_D":False,
      "safe_for_backtest_or_pair_ranking":False
    }
    (PATH/"receipt.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("BLS_AUG24_RECEIPT: "+json.dumps(result,sort_keys=True))

if __name__=="__main__":
    main()
