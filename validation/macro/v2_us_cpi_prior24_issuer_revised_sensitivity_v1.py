#!/usr/bin/env python3
"""BLS CPI: 24 PRIOR observed issued months + latest Sep-2026, gap sensitivity.

Aug-2024 issuer-month XLSX acquired 2026-10-27 repairs the 23-PRIOR count
in old Sep-2024..Sep-2026 files; Oct-2025 remains unpublished.
Compare each original ISSUE-MONTH BLS XLSX SA-index YoY with Oct-2026
REVISED FRED CPIAUCSL as-of snapshot, independent robustness test.
This is NOT original-day PIT backtest and CANNOT authorize Core/FX.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_us_blscpi_24_issue_sa_index_sha_evidence_v1 import (
    PATH as ISSUER_24_PATH, audit as issuer_audit
)
from validation.macro.v2_us_cpi_two_annual_sa_vintage_revisions_gap_policy_v1 import (
    audit as revisions_audit, rolling_prior_months
)

SCHEMA="GMFQ_MACRO_V2_US_CPI_CORRECTED_24_PRIOR_PUBLISHED_ISSUER_MONTHS_VS_ASOF_REVISED_SENSITIVITY_V1"
PATH=ROOT/"validation/macro/fixtures/v2_us_cpi_24_prior_month_issuer_vs_revised_shadow_sensitivity_2026_10_27.json"
BLS_AUG_SHA="41f4de5b7035be83cec85fca05d2339bd929290683206846f9b43b46d84a3a4d"
GIT_REVISED_BLOB="0110d62ab38f9d6eb195114bcd8e0deddcf04c99"
GIT_ISSUER_24_BLOB="9d7cf7e1f07b6ce8387bf0c73c541fdf483fb78f"
AUG_RELEASE="2024-09-11"

def require(ok,why):
    if not ok: raise ValueError("US_CPI_CORRECTED_PRIOR24_SENSITIVITY_REJECTED: "+why)

def stat(vals,current):
    med=statistics.median(vals)
    mad=statistics.median(abs(x-med) for x in vals)
    require(mad>1e-9, "nonzero 24-observation sample MAD required")
    raw=(current-med)/(1.4826*mad)
    require(math.isfinite(raw), "finite robust-score comparison required")
    return {"training_median":med,"training_mad":mad,
            "current_yoy_pct":current,"unclipped_z":raw,
            "clipped_z":max(-3,min(3,raw))}

def close(actual,expected,tol=0.000003):
    return (isinstance(actual,(float,int)) and type(actual) is not bool
            and math.isfinite(actual)
            and math.isclose(actual,expected,rel_tol=0,abs_tol=tol))

def audit(*,fixture=None,original_24=None):
    d=fixture if fixture is not None else json.loads(PATH.read_text(encoding="utf-8"))
    require(d.get("schema")==SCHEMA
            and d.get("as_of_utc")=="2026-10-26T23:59:59Z"
            and d.get("research_receipt_date")=="2026-10-27",
            "fixed as-of research vintage identity")
    require(d.get("source_aug2024_workflow_run")==
            "https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40597149084"
            and d.get("source_oct2026_cpiaucsl_revised_git_blob_sha")==GIT_REVISED_BLOB
            and d.get("source_publisher_24_issue_rows_git_blob_sha")==GIT_ISSUER_24_BLOB,
            "specific source-date and Git blob provenance frozen")
    for required in ("asof_revised_history_is_NOT_first_vintage",
                     "issuer_month_workbooks_downloaded_late_not_original_day_bytes",
                     "orig_oct2025_not_published","prior_training_excludes_sep2026_current",
                     "percent_changes_derived_from_SA_index_not_NSA_annual_headline",
                     "SA_yoy_only_24_observed_across_25_calendar_months_NOT_STRICT"):
        require(d.get(required) is True, "quality/comparison guard "+required)
    aug=d.get("original_aug_2024_source") or {}
    require(aug.get("economic_month")=="2024-08"
            and aug.get("publisher_release_day")==AUG_RELEASE
            and aug.get("source_url")=="https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-202408.xlsx"
            and aug.get("source_BLS_news")=="https://www.bls.gov/news.release/archives/cpi_09112024.htm"
            and aug.get("raw_xlsx_sha256")==BLS_AUG_SHA
            and aug.get("SA_index_at_issue")=="314.121"
            and aug.get("same_issue_SA_12m_base")=="306.187"
            and aug.get("SA_index_yoy_pct_same_issue")=="2.591227"
            and aug.get("source_binary_byte_size")==150338
            and aug.get("source_binary_capture_utc")=="2026-10-27T22:45:02.536479+00:00"
            and aug.get("source_evidence_quality")==
                "BLS_OFFICIAL_ISSUE_MONTH_XLSX_SHA256_AT_2026_10_27_NOT_RELEASE_DAY_BINARY",
            "original Aug-2024 BLS issuer-month supplementary XLSX evidence")
    archived=original_24 if original_24 is not None else issuer_audit()
    require(archived["summary"]["published_month_workbooks_captured"]==24
            and archived["summary"]["original_issuer_day_byte_certifications"]==0
            and archived["safe_to_publish_new_D"] is False,
            "24 prior issuer workbook research archive cannot become PIT")
    issuer_by={r["economic_month"]:r for r in archived["records"]}
    require(len(issuer_by)==25 and issuer_by["2025-10"]["SA_index_at_issue"] is None,
            "2025-10 original BLS all-items index still unpublished")
    require(len(rolling_prior_months("2026-09",25))==25
            and rolling_prior_months("2026-09",25)[0]=="2024-08"
            and rolling_prior_months("2026-09",25)[-1]=="2026-08"
            and "2025-10" in rolling_prior_months("2026-09",25),
            "Aug24-Aug26 preceding 25 calendar months hold one structural source gap")
    revisions=revisions_audit()
    require(revisions["original_issuer_day_source_bytes_PIT_certified"]==0
            and revisions["safe_to_publish_new_D"] is False,
            "lookahead seasonal revisions cannot be used as original PIT")
    rows=d.get("comparison_samples")
    require(isinstance(rows,list) and len(rows)==25,
            "Aug2024 plus old 24 published Sep2024-Sep2026 = 25 total")
    expected=[x for x in rolling_prior_months("2026-09",25) if x!="2025-10"]+["2026-09"]
    require([r.get("economic_month") for r in rows]==expected,
            "24 previous published observations plus ONE excluded latest; no imputation")
    require(all(x.get("sample_role")=="PRIOR_TRAINING_ONLY" for x in rows[:-1])
            and rows[-1].get("sample_role")=="CURRENT_EVALUATION_ONLY",
            "no current value may leak into preceding 24 training observations")
    for x in rows:
        month=x["economic_month"]
        src=aug if month=="2024-08" else issuer_by[month]
        for srcKey,rowKey in (
            ("SA_index_at_issue","issuer_original_issue_month_sa_index"),
            ("same_issue_SA_12m_base","issuer_original_issue_month_12mo_sa_base"),
            ("SA_index_yoy_pct_same_issue","issuer_original_issue_month_SA_yoy_pct"),
            ("raw_xlsx_sha256","issuer_original_issue_month_xlsx_SHA256"),
            ("publisher_release_day","issuer_publisher_release_day")):
            require(x.get(rowKey)==src.get(srcKey),
                    "same-issue original-publisher SA evidence mismatch "+month+"/"+rowKey)
        def number(key):
            v=x.get(key)
            require(isinstance(v,str) and re.fullmatch(r"\d{3}\.\d{3}",v),
                    "SA index 3-decimal frozen vintage required "+key)
            return float(v)
        a=number("issuer_original_issue_month_sa_index")
        b=number("issuer_original_issue_month_12mo_sa_base")
        require(close(float(x["issuer_original_issue_month_SA_yoy_pct"]),100*(a/b-1)),
                "same-issue first-published SA index-derived yoy mismatch")
        revised_current=number("asof_revised_CPIAUCSL_SA_current_index")
        revised_base=number("asof_revised_CPIAUCSL_SA_12mo_base")
        revised_yoy=x.get("asof_revised_CPIAUCSL_SA_yoy_pct")
        require(close(revised_yoy,100*(revised_current/revised_base-1)),
                "as-of revised CPIAUCSL same-snapshot historical YoY mismatch")
        diff=x.get("original_and_revised_pct_point_difference")
        require(close(diff,float(x["issuer_original_issue_month_SA_yoy_pct"])-revised_yoy),
                "signed vintage difference must equal issue-month YoY minus revised YoY")
    require(rows[0]["asof_revised_CPIAUCSL_SA_current_index"]=="314.062"
            and rows[-1]["asof_revised_CPIAUCSL_SA_current_index"]=="336.298"
            and rows[-1]["issuer_original_issue_month_sa_index"]=="336.298",
            "source-current anchors match frozen 2026-10-26 revised snapshot")
    first=[float(x["issuer_original_issue_month_SA_yoy_pct"]) for x in rows[:-1]]
    revised=[float(x["asof_revised_CPIAUCSL_SA_yoy_pct"]) for x in rows[:-1]]
    fnow=float(rows[-1]["issuer_original_issue_month_SA_yoy_pct"])
    rnow=float(rows[-1]["asof_revised_CPIAUCSL_SA_yoy_pct"])
    first_stat=stat(first,fnow)
    revised_stat=stat(revised,rnow)
    delta=first_stat["clipped_z"]-revised_stat["clipped_z"]
    s=d.get("summary",{})
    require(s.get("prior_calendar_months")==25
            and s.get("official_published_prior_months")==24
            and s.get("latest_eval_period")=="2026-09"
            and s.get("missing_prior_month")=="2025-10"
            and s.get("issuer_original_day_binary_certifications")==0
            and s.get("revision_comparison_months")==24
            and s.get("current_issuer_candidate_index")=="336.298"
            and s.get("asof_revised_current_index")=="336.298"
            and s.get("model_PIT_history_certified")==0,
            "research cardinality, release gap and latest issuer index quality")
    diffs=[abs(x["original_and_revised_pct_point_difference"]) for x in rows[:-1]]
    require(close(s.get("mean_abs_yoy_revision_pp"),sum(diffs)/24)
            and close(s.get("max_abs_yoy_revision_pp"),max(diffs))
            and s.get("prior_months_abs_change_gt_0_05_pp")==sum(x>0.05 for x in diffs),
            "rounded index-derived vintage sensitivity statistics")
    for key, actual in (("issuer_month_candidate_robust_z",first_stat),
                        ("asof_revised_series_robust_z",revised_stat)):
        summary=s.get(key) or {}
        for k,v in actual.items():
            require(close(summary.get(k),v),
                    "robust Z must be recomputed from precisely 24 preceding observations "+key+"/"+k)
    require(close(s.get("robust_z_candidate_minus_revised"),delta)
            and s.get("same_direction_both_robust_z_positive") is True
            and first_stat["clipped_z"]>0 and revised_stat["clipped_z"]>0,
            "issuer vs revised test not equivalent to certified real-time PIT score")
    for key in ("safe_to_publish_D_json","safe_to_recalculate_28_pairs",
                "safe_to_claim_PIT_training","safe_for_beta","safe_for_forward",
                "writes_live_data"):
        require(d.get(key) is False,
                "research may not be promoted into live Core/FX "+key)
    result={
        "schema":SCHEMA,"status":"US_CPI_24_PRECEDING_PUBLISHED_VINTAGE_SENSITIVITY_RESEARCH_ONLY",
        "summary":s,
        "Aug_2024_new_publisher_month_SA_index":"314.121",
        "Aug_2024_new_first_issuer_day_bytes_certified":False,
        "24_prior_observed_not_24_consecutive":True,
        "latest_Sep2026_excluded_from_training":True,
        "source_2025_10_all_items_not_published":True,
        "comparison_first_issue_vs_asof_revised_never_full_PIT":True,
        "safe_to_publish_D_json":False,"safe_to_recalculate_28_pairs":False,
        "safe_to_claim_PIT_training":False,"safe_for_beta":False,
        "safe_for_forward":False,"writes_live_data":False
    }
    result["receipt_sha256"]=hashlib.sha256(
        json.dumps(d,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if args.output: require(args.output.resolve().is_relative_to(Path("/tmp")),
                            "only /tmp allowed for shadow research output")
    result=audit()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],
       "n_prior":result["summary"]["official_published_prior_months"],
       "z_issuer":result["summary"]["issuer_month_candidate_robust_z"]["clipped_z"],
       "z_revised":result["summary"]["asof_revised_series_robust_z"]["clipped_z"],
       "z_delta":result["summary"]["robust_z_candidate_minus_revised"],
       "safe_to_publish_D_json":False},sort_keys=True))

if __name__=="__main__":
    main()
