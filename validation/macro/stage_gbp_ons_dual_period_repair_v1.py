#!/usr/bin/env python3
"""Stage a two-period ONS UK-LFS repair; never write canonical runtime files.

The generic Macro candidate builder supports atomic prior_revision + append.
Canonical July-end 4.7 must become first-release 4.9, and August-end 4.7
must be appended. This preview is NOT a full PIT or live-publication approval.
"""
from __future__ import annotations
import argparse
import copy
import json
from datetime import date
from pathlib import Path

from validation.macro.gbp_ons_temporal_guard_v1 import ROOT, CONTRACT, SERIES, HEAT, build
from validation.build_macro_candidate import apply_candidate

SCHEMA="GMFQ_GBP_ONS_DUAL_PERIOD_REPAIR_CANDIDATE_V1"

def require(ok, reason):
    if not ok:
        raise ValueError("GBP_LFS_STAGE_FAIL_CLOSED: "+reason)

def stage(root=ROOT, today=date(2026,10,20), contract=None, series=None, heat=None):
    root=Path(root)
    contract=contract or json.loads((root/CONTRACT).read_text(encoding="utf-8"))
    series=series or json.loads((root/SERIES).read_text(encoding="utf-8"))
    heat=heat or json.loads((root/HEAT).read_text(encoding="utf-8"))
    prior=build(root,today,contract=contract,series=series,heat=heat)
    require(prior["status"]=="HOLD_UNTIL_EXPLICIT_PERIOD_VINTAGE_REPAIR",
            "canonical source not in expected pre-repair state")
    issues={(x.get("month"),x["action"]) for x in prior["issues"]}
    require(issues=={("2026-07","VINTAGE_OR_PERIOD_VALUE_MISMATCH"),
                    ("2026-08","MISSING_FIRST_RELEASE_WINDOW")},
            "unrecognized source changes require independent review")
    original=next((x for x in series["GBP"] if x.get("id")=="UK_UNEMP_RATE_history_value"),None)
    require(original is not None and original["values"][-1]==4.7 and
            str(original["last_date"])[:7]=="2026-07","unexpected latest source point")
    official={r["canonical_end_month"]:r for r in contract["official_periods"]}
    require(set(official)=={"2026-06","2026-07","2026-08"} and
            [official[x]["unemployment_pct"] for x in ("2026-06","2026-07","2026-08")]==[4.9,4.9,4.7],
            "first-release anchor values drift")
    candidate={
        "currency":"GBP","dimension":"labour",
        "macro_series_id":"UK_UNEMP_RATE_history_value",
        "observation_date":"2026-08-01","value":4.7,
        "source":"Office for National Statistics",
        "source_url":official["2026-08"]["source_url"],
        "series_id":"MGSX","frequency":"M","transformation":"level","unit":"%",
        "prior_revision":{
            "observation_date":"2026-07-01",
            "before_value":4.7,"value":4.9,
            "before_series_value":4.7,"series_value":4.9
        }
    }
    newseries=copy.deepcopy(series)
    newheat=copy.deepcopy(heat)
    receipt=apply_candidate(newseries,newheat,candidate)
    require(receipt["series_action"]=="APPEND_NEW" and
            receipt["prior_revision"] is not None and
            receipt["prior_revision"]["before_series_value"]==4.7 and
            receipt["prior_revision"]["series_value"]==4.9,
            "atomic prior-month repair and append failed")
    row=next(x for x in newseries["GBP"] if x["id"]=="UK_UNEMP_RATE_history_value")
    require([str(x)[:7] for x in row["dates"][-2:]]==["2026-07","2026-08"]
            and row["values"][-2:]==[4.9,4.7],
            "unexpected canonical first-release points")
    hr=newheat["currencies"]["GBP"]["labour"]
    require(hr["history"][-2:]==[4.9,4.7] and hr["latest_value"]==4.7 and
            str(hr["as_of"])[:7]=="2026-08",
            "thermometer failed to replay both dates")
    final=build(root,today,contract=contract,series=newseries,heat=newheat)
    require(final["status"]=="ALLOW_GBP_LABOUR_SOURCE_REFRESH",
            "after two-period candidate temporal guard remains blocked")
    require(all(series[c]==newseries[c] for c in series if c!="GBP"),
            "non-GBP Macro sources mutated")
    require(all(heat["currencies"][c]==newheat["currencies"][c]
                for c in heat["currencies"] if c!="GBP"),
            "non-GBP heatmaps mutated")
    old_other={x["id"]:x for x in series["GBP"] if x["id"]!="UK_UNEMP_RATE_history_value"}
    new_other={x["id"]:x for x in newseries["GBP"] if x["id"]!="UK_UNEMP_RATE_history_value"}
    require(old_other==new_other and
            heat["currencies"]["GBP"]["inflation"]==newheat["currencies"]["GBP"]["inflation"],
            "other GBP indicators changed")
    return {
        "schema":SCHEMA,
        "status":"STAGED_DUAL_PERIOD_NOT_PUBLISHED",
        "old_july":4.7,"first_release_july":4.9,
        "first_release_august":4.7,
        "as_of":"2026-08",
        "candidate":candidate,
        "builder_receipt":receipt,
        "temporal_guard_after_stage":final["status"],
        "safe_to_publish_without_archival_PIT":False,
        "safe_to_rebase_structural_FX_scores":False,
        "runtime_files_written":False,
        "candidate_series":newseries,
        "candidate_heatmap":newheat,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--asof",default=date.today().isoformat())
    args=p.parse_args()
    result=stage(today=date.fromisoformat(args.asof))
    folder=args.out_dir
    folder.mkdir(parents=True,exist_ok=True)
    series=result.pop("candidate_series")
    heat=result.pop("candidate_heatmap")
    (folder/"receipt.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (folder/"MACRO_SERIES.CANDIDATE.json").write_text(json.dumps(series,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    (folder/"MACRO_THERMOMETER_DATA.CANDIDATE.json").write_text(json.dumps(heat,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in
          ("status","as_of","temporal_guard_after_stage",
           "safe_to_publish_without_archival_PIT","runtime_files_written")}))

if __name__=="__main__":
    main()
