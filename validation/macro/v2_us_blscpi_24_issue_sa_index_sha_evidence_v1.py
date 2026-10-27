#!/usr/bin/env python3
"""Audit 24 official BLS issue-month CPI-U workbooks captured 2026-10-27.

24 precise SA index + SAME-issue 12-month bases, each indexed by original
BLS issuer news release day and archived XLSX byte SHA, but XLSX downloads
happened on 2026-10-27, NOT on historical issue days. This is strong
issuer-month candidate evidence, NOT fully original PIT issuer-day bytes
or 24 consecutive calendar first-release observations. October 2025 missing.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_us_bls_cpi_first_news_archive_v1 import PATH as BLS_NEWS
from validation.macro.v2_us_cpiau_alfred_seven_release_day_index_v1 import PATH as ALFRED

PATH=ROOT/"validation/macro/fixtures/v2_us_cpi_24_issue_sa_index_sha_2026_10_27.json"
SCHEMA="GMFQ_MACRO_V2_US_CPI_25_CALENDAR_24_ISSUE_XLSX_SA_INDEX_AND_BASE_CANDIDATES_V1"

def check(ok,reason):
    if not ok: raise ValueError("US_CPI_24_ISSUE_SA_PUBLISHER_EVIDENCE_REJECTED: "+reason)

def audit(*,fixture=None):
    d = fixture if fixture is not None else json.loads(PATH.read_text(encoding="utf-8"))
    check(d.get("schema")==SCHEMA and d.get("evidence_as_of_date")=="2026-10-27",
          "source evidence version and current retrieval date")
    check(d.get("original_issuer_day_HTTP_capture_not_proven") is True
          and d.get("source_retrieval_method")=="GITHUB_ACTIONS_ISSUER_DOMAIN_DIRECT_2026_10_27"
          and d.get("series_semantics")=="BLS_CUSR0000SA0_ALL_ITEMS_SA_INDEX_MATCHES_FRED_CPIAUCSL"
          and d.get("unadjusted_series_not_substitutable")=="CUUR0000SA0"
          and d.get("source_issuer_url")=="https://www.bls.gov/cpi/tables/supplemental-files/"
          and d.get("BLS_2025_OCT_original_all_items_index_unpublished") is True
          and d.get("prior_24_calendar_first_release_contiguous_PIT_ready") is False
          and d.get("pit_backtest_or_live_score_approved") is False,
          "source quality, semantic identity or PIT gate")
    check(d.get("run_url")=="https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40587426321"
          and d.get("job_id")==122482495412,"CI source receipt anchors")
    for forbidden in ("safe_to_publish_new_D","safe_to_change_28_pairs",
                      "safe_for_beta","safe_for_forward","writes_live_data"):
        check(d.get(forbidden) is False,"unsafe model/production write flag: "+forbidden)

    all_rows=d.get("records")
    check(type(all_rows) is list and len(all_rows)==25, "25-month calendar frame")
    expected=[f"{(2024*12+9-1+i)//12:04d}-{(2024*12+9-1+i)%12+1:02d}"
              for i in range(25)]
    check([r.get("economic_month") for r in all_rows]==expected
          and expected[-1]=="2026-09", "duplicate/unordered/missing calendar month")
    news=json.loads(BLS_NEWS.read_text(encoding="utf-8"))
    news_by={r["reference_month"]:r for r in news["records"]}
    check(len(news_by)==25,"need 25 BLS issue-date source labels")
    s=d.get("summary",{})
    check(s.get("published_month_workbooks_captured")==24
          and s.get("calendar_months")==25
          and s.get("missing_unpublished_periods")==["2025-10"]
          and s.get("exact_SA_index_and_12m_base_candidates")==24
          and s.get("source_raw_byte_sha256_observed_2026_10_27")==24
          and s.get("ALFRED_release_date_anchor_matches")==7
          and s.get("original_issuer_day_byte_certifications")==0
          and s.get("model_joint_PIT_training_slots_approved")==0
          and s.get("source_window_numerical_completeness_22_of_24_UNCHANGED") is True,
          "audit counts must be research-only and complete")

    for row in all_rows:
        month=row["economic_month"]
        if month=="2025-10":
            check(row.get("evidence_quality")==
                  "UNPUBLISHED_ALL_ITEMS_CPI_REFERENCE_MONTH_DO_NOT_IMPUTE"
                  and all(row.get(k) is None for k in (
                     "publisher_release_day","source_url","raw_xlsx_sha256",
                     "SA_index_at_issue","same_issue_SA_12m_base",
                     "SA_index_yoy_pct_same_issue")),
                  "October 2025 is missing, never zero or invented")
            continue
        release=news_by[month]["publisher_release_day"]
        check(row.get("publisher_release_day")==release
              and isinstance(release,str),"issuer news matching published day")
        check(date.fromisoformat(release)>date.fromisoformat(month+"-01"),
              "issuer release cannot be before economic observation")
        check(row.get("source_url")==
              "https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-"+month.replace("-","")+".xlsx",
              "official publisher issue-month filename")
        sh=row.get("raw_xlsx_sha256")
        check(isinstance(sh,str) and re.fullmatch("[a-f0-9]{64}",sh),
              "expected byte-level downloaded source SHA")
        check(type(row.get("captured_bytes"))==int
              and 10000<row["captured_bytes"]<5000000,
              "byte count missing or not XLSX sized")
        check(row.get("evidence_quality")==
              "ORIGINAL_PUBLISHER_ISSUE_MONTH_FILENAME_BINARY_CAPTURED_2026_10_27_NOT_ON_RELEASE_DAY",
              "source captured later cannot be mislabelled historical PIT issuer day")
        for k in ("SA_index_at_issue","same_issue_SA_12m_base"):
            val=row.get(k)
            check(isinstance(val,str) and re.fullmatch(r"[0-9]{3}\.[0-9]{3}",val),
                  "numeric 3-decimal SA index required: "+k)
        c=Decimal(row["SA_index_at_issue"])
        b=Decimal(row["same_issue_SA_12m_base"])
        expect=((c/b-1)*100).quantize(Decimal("0.000001"))
        check(row.get("SA_index_yoy_pct_same_issue")==str(expect),
              "same-edition SA YoY/index base incoherent; NSA substituted?")
        check(100<c<500 and 100<b<500,"unexpected index level or scale")
    anchors=json.loads(ALFRED.read_text(encoding="utf-8"))["records"]
    checks=d.get("ALFRED_7_independent_same_release_page_anchor_checks")
    check(isinstance(checks,list) and len(checks)==len(anchors)==7,
          "seven ALFRED independent observations expected")
    by_period={r["economic_month"]:r for r in all_rows}
    for reference,verify in zip(anchors,checks):
        month=reference["economic_month"]
        check(verify.get("economic_month")==month
              and verify.get("match") is True
              and verify.get("alfred_release_date_page_url")==reference["alfred_release_date_page_url"]
              and Decimal(verify.get("bls_index_SA","0"))==
                  Decimal(verify.get("alfred_release_page_index","0"))==
                  Decimal(str(reference["alfred_release_page_last_observation_SA_CPIAUCSL_index"]))==
                  Decimal(by_period[month]["SA_index_at_issue"]),
              "ALFRED mirror and official issuer workbook index mismatch")
    check(by_period["2025-09"]["SA_index_at_issue"]=="324.368"
          and by_period["2025-11"]["SA_index_at_issue"]=="325.031"
          and by_period["2025-12"]["SA_index_at_issue"]=="326.030"
          and by_period["2026-09"]["SA_index_at_issue"]=="336.298",
          "BLS publisher original dated row anchors changed")
    return {
      "schema":SCHEMA,
      "status":"24_BLS_ISSUE_MONTH_SA_INDEX_AND_12M_BASES_BYTE_HASHED_2026_NOT_SOURCE_DAY_PIT",
      "records":all_rows,
      "summary":s,
      "ALFRED_7_same_release_day_index_anchor_checks":7,
      "issuer_day_original_bytes_certified":0,
      "2025_10_unpublished_BLS_all_items_index_still_missing":True,
      "cannot_claim_strict_consecutive_24m_training":True,
      "safe_to_publish_new_D":False,
      "safe_to_change_28_pairs":False,
      "safe_for_beta":False,"safe_for_forward":False,"writes_live_data":False,
      "receipt_sha256":hashlib.sha256(json.dumps(d,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    }

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--output",type=Path)
    args=cli.parse_args()
    if args.output: check(args.output.resolve().is_relative_to(Path("/tmp")),
                          "only research receipts in /tmp")
    obj=audit()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":obj["status"],**obj["summary"],
                      "safe_to_publish_new_D":False},sort_keys=True))

if __name__=="__main__":
    main()
