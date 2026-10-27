#!/usr/bin/env python3
"""Research-only BLS CPI annual SA revision evidence and missing-month policy.

15 paired, three-decimal all-items CPI-U SA index values from ORIGINAL
ISSUE-MONTH FILENAMES, with all publisher XLSX bytes SHA256-captured LATE
on 2026-10-27. This is not equivalent to source-day historical PIT bytes.

Critical two separate economic observation failures:
2025-10 SA CPI-U index never published (BLS shutdown);
2026-10 SA CPIAUCSL YoY cannot have a 2025-10 denominator.
As of 2026-10-26, 2026-10 is future and only a prospective policy block.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_us_blscpi_24_issue_sa_index_sha_evidence_v1 import (
    PATH as ISSUER_XLSX_FIXTURE, audit as issuer_audit
)

PATH = ROOT / "validation/macro/fixtures/v2_us_cpi_sa_seasonal_revisions_shutdown_gap_policy_2026_10_27.json"
SCHEMA = "GMFQ_MACRO_V2_US_CPI_SA_INDEX_ANNUAL_REVISIONS_AND_SHUTDOWN_GAP_POLICY_V1"
ASOF = "2026-10-26T23:59:59Z"
REVISION_COUNTS = {"2025-01":4, "2026-01":11}
SOURCE_BLS_SHUTDOWN = "https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm"

def check(ok,reason):
    if not ok: raise ValueError("US_CPI_SEASONAL_REVISIONS_GAP_POLICY_REJECTED: "+reason)

def period_index(period):
    check(isinstance(period,str) and re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])",period),
          "invalid monthly calendar period")
    yr,mo=map(int,period.split("-"))
    return 12*yr+mo-1

def month_label(index):
    return f"{index//12:04d}-{index%12+1:02d}"

def rolling_prior_months(reference,window=24):
    i=period_index(reference)
    return [month_label(k) for k in range(i-window,i)]

def audit(*,fixture=None,issuer=None):
    d=fixture if fixture is not None else json.loads(PATH.read_text(encoding="utf-8"))
    check(d.get("schema")==SCHEMA
          and d.get("as_of_research_utc")==ASOF
          and d.get("verified_snapshot_acquired")=="2026-10-27"
          and d.get("source_BLS_shutdown_FAQ")==SOURCE_BLS_SHUTDOWN
          and d.get("source_BLS_annual_seasonal_adjustment")==
              "https://www.bls.gov/cpi/seasonal-adjustment/"
          and d.get("source_BLS_annual_revision_2026")==
              "https://www.bls.gov/cpi/notices/2026/seasonal-adjustment.htm",
          "fixed evidence and trusted official BLS references")
    check(d.get("historical_comparison_pair_quality")==
          "TWO_OFFICIAL_PUBLISHER_ISSUE_MONTH_XLSX_FILES_ACQUIRED_2026_10_27_NOT_HISTORIC_RELEASE_DAY_RAW_BYTES",
          "do not promote recent publisher downloads to source-day PIT")
    b=issuer if issuer is not None else issuer_audit()
    check(b["summary"]["published_month_workbooks_captured"]==24
          and b["summary"]["original_issuer_day_byte_certifications"]==0
          and b["safe_to_publish_new_D"] is False,
          "source publisher workbook receipt must remain research only")
    originals={r["economic_month"]:r for r in b["records"]}
    rows=d.get("revisions")
    check(isinstance(rows,list) and len(rows)==15,"exact 15 independently paired annual SA revisions")
    check(len({r.get("economic_month") for r in rows})==15
          and [r["economic_month"] for r in rows]==sorted(r["economic_month"] for r in rows),
          "no duplicate, stale or unordered revision observation")
    counts={k:0 for k in REVISION_COUNTS}
    differences=[]
    for r in rows:
        month=r["economic_month"]
        later=r.get("subsequent_annual_seasonal_rebase_issue_month")
        check(later in REVISION_COUNTS,"only 2025 and 2026 annual revision vintages")
        counts[later]+=1
        original=originals.get(month)
        newer=originals.get(later)
        check(original is not None and newer is not None
              and r.get("first_issue_month")==month
              and r.get("first_issued_sa_index")==original["SA_index_at_issue"]
              and r.get("first_issue_xlsx_sha256")==original["raw_xlsx_sha256"]
              and r.get("subsequent_issue_xlsx_sha256")==newer["raw_xlsx_sha256"]
              and r.get("publisher_annual_seasonal_revision_issuer_day")==newer["publisher_release_day"],
              "must refer to actual differently dated BLS issue-month SHA evidence")
        check(period_index(later)>period_index(month) and
              later==("2025-01" if month.startswith("2024") else "2026-01"),
              "later seasonal vintage must never be treated as earlier known data")
        check(r.get("quality")==
              "BLS_ISSUE_MONTH_LATE_CAPTURE_XLSX_PAIR_NOT_SOURCE_DAY_IMMUTABLE_BYTES",
              "later 2026 archival source is not original issue day historical byte capture")
        for key in ("subsequent_issued_sa_index","delta_index_points"):
            check(type(r.get(key))==str
                  and re.fullmatch(r"-?\d{1,3}\.\d{3}",r[key]),
                  "signed precise three-decimal vintage index comparison required")
        delta=Decimal(r["subsequent_issued_sa_index"])-Decimal(r["first_issued_sa_index"])
        check(delta==Decimal(r["delta_index_points"]) and delta!=0,
              "reported difference must equal subsequent minus original index")
        differences.append(delta)
    check(counts==REVISION_COUNTS and max(abs(x) for x in differences)==Decimal("0.170"),
          "known 4 + 11 annual vintage revisions and max delta guard")
    g=d.get("gap_policy") or {}
    check(g.get("missing_original_index_month")=="2025-10"
          and g.get("missing_original_CPIAUCSL_sa_yoy_months")==["2025-10","2026-10"]
          and g.get("October_2026_yoy_is_forecast_unavailable_not_yet_published_asof")==ASOF
          and g.get("internal_BLS_oct2025_seasonal_factor_geometric_mean_is_not_public_all_items_index") is True
          and g.get("never_impute_month_as_original_first_release") is True
          and g.get("permitted_research_proxy")==
          "24_PRIOR_PUBLISHED_OBSERVATIONS_ACROSS_25_CALENDAR_MONTHS_LABEL_AS_ESTIMATE_NON_PIT"
          and g.get("strict_24_consecutive_month_calendar_training_tolerates_gap") is False
          and g.get("without_verified_future_data_eligibility_is_NOT_asserted") is True
          and g.get("FX_signal_or_original_PIT_training_approved") is False,
          "missing October index versus dependent October-next-year SA YoY")
    check(g.get("rolling_index_24_calendar_prior_gap_earliest_reference_month_if_no_new_missing")
          =="2027-11" and
          g.get("rolling_SA_index_yoy_24_calendar_prior_gap_earliest_reference_month_if_no_new_missing")
          =="2028-11","rolling future gap exit dates")
    # First period whose preceding 24 calendar slots EXCLUDE missing month.
    check("2025-10" in rolling_prior_months("2027-10")
          and "2025-10" not in rolling_prior_months("2027-11"),
          "index structural source gap window boundary")
    check("2026-10" in rolling_prior_months("2028-10")
          and all(m not in rolling_prior_months("2028-11")
                  for m in ("2025-10","2026-10")),
          "YoY structural source gap window boundary")

    summary=d.get("summary") or {}
    check(summary.get("sample_historic_index_pairs")==15
          and summary.get("annual_2025_revision_pair_count")==4
          and summary.get("annual_2026_revision_pair_count")==11
          and summary.get("revisions_observed_nonzero")==15
          and summary.get("max_abs_index_revision_points")=="0.170"
          and summary.get("source_day_original_binary_hash_confirmations")==0
          and summary.get("pit_core_scores_approved")==0
          and summary.get("usd_inflation_canonical_24_prior_source_window_complete") is False
          and summary.get("g8_research_numerical_windows_remain")==22,
          "archive revision counts cannot certify historical PIT model")
    for k in ("safe_to_publish_new_D","safe_to_change_28_pairs",
              "safe_for_beta","safe_for_forward","writes_live_data"):
        check(d.get(k) is False,"forbidden production/core mutation: "+k)
    out={"schema":SCHEMA,
         "status":"TWO_BLS_ANNUAL_CPI_SA_REVISIONS_AND_SHUTDOWN_SOURCE_GAP_RESEARCH_ONLY",
         "sampled_cross_issuer_month_revision_pairs":15,
         "historical_2024_annual_revision_values_checked":4,
         "historical_2025_annual_revision_values_checked":11,
         "maximum_SA_index_revision_points":"0.170",
         "issue_month_source_binary_sha256_captured_LATE":True,
         "original_issuer_day_source_bytes_PIT_certified":0,
         "structurally_missing_2025_10_SA_index":True,
         "prospectively_missing_2026_10_SA_yoy_when_oct26_index_published":True,
         "nearest_clean_future_index_window_if_new_data_complete":"2027-11",
         "nearest_clean_future_SA_yoy_window_if_new_data_complete":"2028-11",
         "future_first_vintage_eligibility_not_yet_certified":True,
         "original_CPIAUCSL_24m_strict_training_approved":False,
         "revised_late_xlsx_not_used_to_backdate_issuer_vintage":True,
         "summary":summary,
         "safe_to_publish_new_D":False,"safe_to_change_28_pairs":False,
         "safe_for_beta":False,"safe_for_forward":False,"writes_live_data":False}
    out["receipt_sha256"]=hashlib.sha256(json.dumps(d,sort_keys=True,
                                    separators=(",",":")).encode()).hexdigest()
    return out

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--output",type=Path)
    args=cli.parse_args()
    if args.output:check(args.output.resolve().is_relative_to(Path("/tmp")),
                         "research receipts only under /tmp")
    obj=audit()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":obj["status"],"sampled_pairs":obj["sampled_cross_issuer_month_revision_pairs"],
                      "index_gap":obj["structurally_missing_2025_10_SA_index"],
                      "yoy_gap_oct26":obj["prospectively_missing_2026_10_SA_yoy_when_oct26_index_published"],
                      "safe_to_publish_new_D":False},sort_keys=True))

if __name__=="__main__":
    main()
