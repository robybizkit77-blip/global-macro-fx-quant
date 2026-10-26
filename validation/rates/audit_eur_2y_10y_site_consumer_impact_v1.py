#!/usr/bin/env python3
"""Pin down UI/data implications BEFORE any ECB historical source promotion."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LIVE=ROOT/"live_data/sections/NATIVE_RATES_DATA.json"
HOME=ROOT/"site/control-room-preview/home-navigation-v10.js"
LEGACY_CHART=ROOT/"site/website-v1/tassi.js"
LEGACY_DASH=ROOT/"site/website-v1/dashboard-rates-g8.js"
DATA_ADAPTER=ROOT/"site/website-v1/data-adapter.js"
SCHEMA="GMFQ_EUR_2Y_10Y_PUBLISHING_IMPACT_GATE_V1"


def assess(original,candidate,home,legacy,legacy_dash,adapter):
    if set(original)!=set(candidate) or any(
        original[x]!=candidate[x] for x in original if x!="EUR"
    ):
        raise ValueError("unexpected other-G8 change in official history candidate")
    before=original["EUR"];after=candidate["EUR"]
    unchanged=("2Y","10Y","date","quality","source","tenors")
    for key in unchanged:
        if before.get(key)!=after.get(key):
            raise ValueError("current official FX rates/other tenors changed")
    changed=sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
    permitted={
      "history2","history10","chg2_bp","chg10_bp","curve_bp",
      "curve_state","weekly2_validation","weekly10_validation",
      "history2_quality","history10_quality","history_status","history_note",
      "historical_curve_rebase"
    }
    if not changed or set(changed)-permitted:
        raise ValueError("candidate scope invalid: "+str(set(changed)-permitted))
    if "historical_curve_rebase" in changed:
        note=after.get("historical_curve_rebase")
        if (not isinstance(note,dict) or
            note.get("schema")!="GMFQ_EUR_2Y_10Y_HISTORY_REBASE_NOTICE_V1" or
            note.get("status")!="RESEARCH_CANDIDATE_NOT_PUBLISHED" or
            note.get("source_authority")!="European Central Bank" or
            note.get("original_point_count")!=282 or
            note.get("original_history_start")!="2025-09-16" or
            note.get("original_history_end")!="2026-10-22" or
            note.get("historical_first_release_pit_certified") is not False or
            note.get("requires_explicit_release") is not True or
            note.get("source_rebase_not_market_move") is not True):
            raise ValueError("unapproved or malformed historical source rebase notice")
        ds=after["history2"]["dates"]
        if (ds!=after["history10"]["dates"] or len(ds)!=282 or
            ds[0]!="2025-09-16" or ds[-1]!="2026-10-22"):
            raise ValueError("ECB rebase metadata not backed by complete paired history")
        paired=[[dt,after["history2"]["values"][i],after["history10"]["values"][i]]
                for i,dt in enumerate(ds)]
        digest=hashlib.sha256(
            json.dumps(paired,separators=(",",":"),ensure_ascii=False).encode()
        ).hexdigest()
        if digest!=note.get("original_paired_values_sha256"):
            raise ValueError("ECB source rebase fingerprint does not match original rates")
    # The current 2Y/10Y are already official. Replacing older dates must
    # not silently alter the rate quote displayed in daily market snapshots.
    for script,label,tokens in (
         (home,"active control room",["function estimate(", "function pairMarketReactionAudit(",
                                      "function pairWhatChangedEvidence(", "function yieldChart(",
                                      "NATIVE_RATES_DATA.json"]),
         (legacy,"legacy rates",["history2","history10","NATIVE_RATES_DATA.json"]),
         (legacy_dash,"legacy dashboard",["history2","NATIVE_RATES_DATA.json"]),
         (adapter,"data adapter",["history2","NATIVE_RATES_DATA.json"])):
        if not all(token in script for token in tokens):
            raise ValueError(label+" consumer shape needs manual re-audit")
    hist=lambda obj,key:dict(zip(obj[key]["dates"],obj[key]["values"]))
    impacts={}
    for tenor in ("2Y","10Y"):
        before_rows=hist(before,"history"+tenor[:-1])
        after_rows=hist(after,"history"+tenor[:-1])
        if not set(before_rows)<=set(after_rows):
            raise ValueError("unexpected deletion from historical rates")
        differences=[d for d in before_rows if before_rows[d]!=after_rows[d]]
        impacts[tenor]={
          "before_days":len(before_rows),
          "after_days":len(after_rows),
          "changed_stored_historical_days":len(differences),
          "newly_published_observation_days":len(set(after_rows)-set(before_rows)),
        }
    risk=[
       {"consumer":"active Control Room / EUR government-yield charts",
        "direct_history_change":True,"must_test":True},
       {"consumer":"active Control Room / CHF scenarios based on EUR reference beta",
        "direct_history_change":True,"must_test":True,
        "source_function":"estimate(target,ref,which)"},
       {"consumer":"active Control Room / G8 pair market reaction, particularly seven EUR crosses",
        "direct_history_change":True,"must_test":True,
        "source_function":"pairMarketReactionAudit"},
       {"consumer":"active Control Room / pair-change observed 2Y layer",
        "direct_history_change":True,"must_test":True,
        "source_function":"pairWhatChangedEvidence"},
       {"consumer":"legacy rates and homepage 2Y charts",
        "direct_history_change":True,"must_test":True},
    ]
    return {
        "schema":SCHEMA,
        "status":"CONTROLLED_RELEASE_REQUIRED_NO_AUTO_PROMOTION",
        "consumer_classes":risk,
        "impacts":impacts,
        "changed_eur_fields":changed,
        "unchanged_latest_official_EUR_2Y_10Y":True,
        "unchanged_non_EUR_G8":True,
        "unchanged_5Y_30Y_tenors":True,
        "freshness_and_source_label_not_full_historical_pit_attestation":True,
        "quantified_derived_CHF_beta_estimate_reaction":False,
        "browser_active_preview_1440_and_390_verified_after_candidate":False,
        "full_live_manifest_payload_roundtrip_checked":False,
        "source_origin_defect_resolved":False,
        "publisher_candidate_applied":False,
        "core_score_recomputed":False,
        "safe_to_publish_now":False,
    }


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    if not args.out.resolve().is_relative_to(Path("/tmp")):
        ap.error("release impact audit receipt must remain under /tmp")
    a=assess(json.loads(LIVE.read_text()),json.loads(args.candidate.read_text()),
        HOME.read_text(),LEGACY_CHART.read_text(),LEGACY_DASH.read_text(),
        DATA_ADAPTER.read_text())
    args.out.write_text(json.dumps(a,indent=2,sort_keys=True)+"\n")
    print(json.dumps(a,sort_keys=True))


if __name__=="__main__":
    main()
