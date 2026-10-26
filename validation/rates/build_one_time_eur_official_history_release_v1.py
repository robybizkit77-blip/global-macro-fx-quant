#!/usr/bin/env python3
"""One-time, fail-closed official ECB EUR 2Y + 10Y SOURCE release payload.

Reads original 2 official CSV bytes, builds the previously approved candidate,
and validates an explicit source-history publication transition. Does not
write live_data or publish by itself: the staged GitHub workflow must perform
source-controlled candidate apply, runtime QA and independent PR review.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import hashlib
import json

from validation.rates.build_eur_full_2y_10y_ecb_history_candidate_v1 import build_candidate
from validation.build_rates_candidate_from_audit import (
    EUR_LEGACY_STATUS, EUR_APPROVED_STATUS, eur_daily_append_source_gate,
)

BASE=Path(__file__).resolve().parents[2]
RATES=BASE/"live_data/sections/NATIVE_RATES_DATA.json"
EXPECTED={"2Y":"2d5b0e884b0d3728c29d935e0982e761896102bd401f4ae406a17680f6079bab",
          "10Y":"c536410864ee8f873533509167ab350a189ed0987201b09b490f158aa85b9b4e"}
G8={"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"}

def build_release(original,raw2,raw10):
    if set(original)!=G8:
        raise ValueError("source G8 coverage changed")
    euro=original["EUR"]
    if (euro.get("date")!="2026-10-22" or euro.get("history_status")!=EUR_LEGACY_STATUS
        or euro.get("2Y")!=3.0074951382 or euro.get("10Y")!=3.3844008945
        or len(euro["history2"]["dates"])!=271
        or len(euro["history10"]["dates"])!=271
        or euro.get("historical_curve_rebase") is not None):
        raise ValueError("live EUR starting snapshot changed; manual rebase required")
    if hashlib.sha256(raw2).hexdigest()!=EXPECTED["2Y"]:
        raise ValueError("official ECB 2Y source bytes changed from tested candidate")
    if hashlib.sha256(raw10).hexdigest()!=EXPECTED["10Y"]:
        raise ValueError("official ECB 10Y source bytes changed from tested candidate")
    result,proof=build_candidate(original,raw2,raw10)
    report=proof["per_tenor_official_parity"]
    for tenor in ("2Y","10Y"):
        if (report[tenor]["official_observations"]!=282
            or report[tenor]["stored_observations"]!=271
            or report[tenor]["overlap_yield_mismatches"]!=260
            or report[tenor]["new_publisher_date_count"]!=11):
            raise ValueError("unexpected original ECB publisher difference "+tenor)
    if (proof["candidate_chg2_bp"]!=euro["chg2_bp"] or
        proof["candidate_chg10_bp"]!=euro["chg10_bp"] or
        proof["candidate_curve_bp"]!=euro["curve_bp"]):
        raise ValueError("published snapshot last-week delta changed unexpectedly")
    candidate=result["EUR"]
    if (candidate["historical_curve_rebase"]["status"]!="RESEARCH_CANDIDATE_NOT_PUBLISHED"
        or candidate["historical_curve_rebase"]["requires_explicit_release"] is not True):
        raise ValueError("source research candidate publication flag drift")
    candidate["history_status"]=EUR_APPROVED_STATUS
    candidate["historical_curve_rebase"]["status"]="PUBLISHED_AFTER_SOURCE_AND_BROWSER_QA"
    candidate["historical_curve_rebase"]["requires_explicit_release"]=False
    candidate["history_note"]=(
        "Serie storiche EUR 2Y/10Y sostituite con la curva spot AAA Svensson BCE "
        "originale (282 date, 2025-09-16–2026-10-22); valori ricavati "
        "dall'ultima serie pubblicata, NON vintage point-in-time. "
        "La revisione del beta CHF è metodologica, NON una variazione osservata "
        "dei rendimenti della Confederazione svizzera."
    )
    eligible=eur_daily_append_source_gate(candidate,"2026-10-23")
    if eligible["history_status"]!=EUR_APPROVED_STATUS:
        raise ValueError("daily EUR append cannot adopt reviewed publisher original")
    if any(original[c]!=result[c] for c in G8 if c!="EUR"):
        raise ValueError("unexpected non-EUR G8 rates change")
    if any(original["EUR"][k]!=candidate[k] for k in
           ("2Y","10Y","date","quality","source","tenors")):
        raise ValueError("EUR latest official 2Y/10Y or other tenors changed")
    proof["actual_production_promotion"]=False  # only the PR staging step.
    proof["status"]="APPROVED_SOURCE_CANDIDATE_FOR_ATOMIC_PR_REVIEW_NOT_DEPLOYED"
    proof["release_reviewed_source_hashes"]=EXPECTED
    proof["ready_for_atomic_pr_branch_commit"]=True
    proof["verified_daily_append_adopts_publisher_source"]=True
    proof["baseline_source_release_requires_main_merge"]=True
    proof["chf_10y_rebase_estimate_not_official"]=True
    return result,proof

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--official-2y",type=Path,required=True)
    p.add_argument("--official-10y",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    a=p.parse_args()
    if any(not x.resolve().is_relative_to(Path("/tmp")) for x in (a.output,a.receipt)):
        p.error("only isolated /tmp staging paths accepted")
    obj=json.loads(RATES.read_text(encoding="utf-8"))
    release,proof=build_release(obj,a.official_2y.read_bytes(),a.official_10y.read_bytes())
    a.output.write_text(json.dumps(release,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    a.receipt.write_text(json.dumps(proof,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(proof,sort_keys=True))

if __name__=="__main__":
    main()
