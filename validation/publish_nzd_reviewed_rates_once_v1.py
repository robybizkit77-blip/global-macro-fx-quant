#!/usr/bin/env python3
"""One-time NZD reviewed publication gate; executed ONLY inside guarded release workflow.

Human authorization is necessary but not sufficient. Refuse without fully matched
official page evidence, independent recorded review, advancing date and exact
canonical known base. Never use a proxy or estimate as the source of these yields.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage_rbnz_b2_official_html_evidence_v1 import EVIDENCE, BASE, verify
from check_rbnz_b2_second_review_v1 import SECOND, check
from build_chf_nzd_official_rates_staging_v1 import make_candidate

OLD_DATE="2026-10-05"
NEW_DATE="2026-10-16"
VALUES=(3.89,5.0)

def candidate(today=None):
    now=today or dt.date.today()
    old=json.loads(BASE.read_text())
    if old["NZD"]["date"]!=OLD_DATE or (old["NZD"]["2Y"],old["NZD"]["10Y"])!=(3.83,5.04):
        raise ValueError("NZD canonical head drift: release not valid on this base")
    a=json.loads(EVIDENCE.read_text())
    b=json.loads(SECOND.read_text())
    obs=verify(a,old,today=now)
    review=check(a,b,old)
    if review["state"]!="SOURCE_PUBLISHED_TABLE_CROSS_CHECK_PASS_STAGING_ONLY":
        raise ValueError("independent review missing")
    if obs["date"]!=NEW_DATE or (obs["2Y"],obs["10Y"])!=VALUES:
        raise ValueError("official RBNZ B2 contract changed")
    new,receipt=make_candidate(old,"NZD",obs,source_sha256=hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),
       mode="HUMAN_AUTHORIZED_RBNZ_B2_OFFICIAL_HTML_SECOND_REVIEW",today=now)
    if new is None or receipt["review"]!="REQUIRED" or receipt["eligible_for_automatic_promotion"] is not False:
        raise ValueError("stage preflight policy violation")
    old_nzd=old["NZD"]; row=new["NZD"]
    # This is a manually reviewed official historical snapshot, not live-feed certification.
    row["quality"]="FULL_CURRENT_OFFICIAL_MANUAL_VERIFIED"
    row["freshness_status"]="CURRENT_OFFICIAL_SAME_BASIS_MANUAL_VERIFIED"
    row["freshness_note"]=(
      "RBNZ B2 government bond closing yields; 16 Oct 2026. "
      "Manual public-page verification and separate recorded cross-check. "
      "GitHub-hosted direct RBNZ fetch remains HTTP 403; no automatic feed certification.")
    row["source"]="Reserve Bank of New Zealand · B2 government bond closing yields · 2026-10-16 · reviewed public table"
    for tenor in ("2","10"):
        row["weekly"+tenor+"_validation"]["source"]=row["source"]
        row["weekly"+tenor+"_validation"]["note"]="Reviewed official same-basis RBNZ B2 source; weekly reference on/before 7 calendar days."
    assert [k for k in old if old[k]!=new[k]]==["NZD"]
    assert row["date"]==NEW_DATE and row["2Y"]==VALUES[0] and row["10Y"]==VALUES[1]
    assert row["quality"]=="FULL_CURRENT_OFFICIAL_MANUAL_VERIFIED"
    return new,{"schema":"GMFQ_NZD_REVIEWED_ONE_TIME_RELEASE_V1",
        "old_date":old_nzd["date"],"new_date":NEW_DATE,"values":{"2Y":VALUES[0],"10Y":VALUES[1]},
        "source":"RBNZ B2 public government bond close table, independently recorded",
        "approval":"USER_EXPLICIT_VAI_2026-10-19",
        "promotion_mode":"ONE_TIME_MANUAL_REVIEW_NOT_AUTOMATED_SOURCE",
        "changed_currencies":["NZD"],"all_other_currencies_unchanged":True}

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: python publish_nzd_reviewed_rates_once_v1.py /tmp/candidate.json")
    new,receipt=candidate()
    out=Path(sys.argv[1]).resolve()
    if BASE.parents[2].resolve() in out.parents:
        raise SystemExit("release candidate output must be outside repo")
    out.write_text(json.dumps(new,ensure_ascii=False,separators=(",",":"))+"\n")
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=="__main__":main()
