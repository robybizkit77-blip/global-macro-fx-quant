#!/usr/bin/env python3
"""One-shot, fail-closed reviewed GBP labour first-vintage migration.

Must be run only in dedicated migration branch by a workflow after checking two
separate official ONS first-release page hashes. Writes canonical GBP core
observation and the corresponding heatmap via existing direct-section updater.
Macro D structural baseline and Pair Setup cannot be written by this script.
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from datetime import date

from validation.macro.gbp_ons_temporal_guard_v1 import ROOT
from validation.macro.stage_gbp_ons_dual_period_repair_v1 import stage
from validation.macro.materialize_gbp_latest_first_release_v1 import (
    verify_materialization,
)
from validation.materialize_gbp_labour_strict_pit_v1 import one

ATTEST = ROOT / "validation/macro/CORE_G8_OFFICIAL_RELEASE_WEB_ATTESTATIONS_2026-10-20.json"
WINDOW = ROOT / "validation/macro/GBP_MGSX_ROLLING_WINDOW_FIRST_RELEASE_MAP_2026-10-20.json"
PINNED_HASHES = {
    "2026-07": "03e892cceeca6897ef4cef3b4d84a3a2bc8cf73c160cc3a5165f3ace48909ceb",
    "2026-08": "70d2913ddad08cdb19be2c7467beb5e5f992041ae9bbd2763a1f55e70cbac8a2",
}
ALLOWED_UPDATES = {
    "live_data/sections/MACRO_SERIES.json",
    "live_data/sections/MACRO_THERMOMETER_DATA.json",
    "live_data/manifest.v2.json",
    "payload/part-00.txt",
    "payload/part-01.txt",
    "validation/macro/CORE_G8_OFFICIAL_RELEASE_WEB_ATTESTATIONS_2026-10-20.json",
}


def require(ok, why):
    if not ok:
        raise ValueError("GBP_LFS_VERIFIED_PROMOTION_REJECTED: " + why)


def cmd(*argv):
    return subprocess.run(argv, cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout


def promote(outdir: Path):
    contract=json.loads(WINDOW.read_text(encoding="utf-8"))
    official_rows=[one(2026,7),one(2026,8)]
    audit=verify_materialization(official_rows,contract)
    require(audit["status"]=="TWO_FIRST_RELEASE_PAGES_VERIFIED" and
            audit["official_pages_independently_hashed"] == 2,
            "freshly fetched official ONS period-specific bulletin semantics invalid")
    # The official publisher may change page bytes after the prior audit.
    # Do NOT mistake raw HTML-byte stability for release-vintage correctness.
    # In this case only allow exact dated source period, exact headline value,
    # official route and source URL, and retain BOTH sets of fingerprints.
    # A value/period/date change still raises in verify_materialization().
    observed_hashes={r["reference_month"]:r["page_sha256"] for r in official_rows}
    raw_page_hashes_changed={m:observed_hashes[m]!=PINNED_HASHES[m]
                             for m in PINNED_HASHES}
    print(json.dumps({
        "ONS_PUBLISHER_HTML_BYTE_DRIFT":raw_page_hashes_changed,
        "first_release_semantic_period_value_date":"PASS",
        "pinned_reference_hashes":PINNED_HASHES,
        "newly_fetched_hashes":observed_hashes},ensure_ascii=False),flush=True)
    proposal=stage(ROOT,date(2026,10,20))
    require(proposal["status"]=="STAGED_DUAL_PERIOD_NOT_PUBLISHED" and
            proposal["safe_to_publish_without_archival_PIT"] is False and
            proposal["builder_receipt"]["series_action"]=="APPEND_NEW" and
            proposal["builder_receipt"]["prior_revision"]["series_value"]==4.9,
            "dual period candidate differs from reviewed source values")
    original_attest=json.loads(ATTEST.read_text(encoding="utf-8"))
    contradictions=original_attest.get("contradictions",[])
    require(len(contradictions)==1 and contradictions[0]["key"]=="GBP.labour"
            and contradictions[0]["canonical_value"]==4.7
            and contradictions[0]["official_first_release_value"]==4.9,
            "existing UK first-release quarantine diagnosis changed")
    dated_audit=copy.deepcopy(original_attest)
    dated_audit["contradictions"]=[]
    dated_audit["resolved_historical_period_errors"]=[{
        "key":"GBP.labour",
        "source_period":"2026-07","canonical_july_old":4.7,
        "canonical_july_repaired":4.9,
        "august_new":4.7,
        "July_May_to_July_original_release_date":"2026-09-15",
        "August_June_to_August_original_release_date":"2026-10-20",
        "official_first_release_page_sha256":observed_hashes,
        "previously_observed_page_sha256":PINNED_HASHES,
        "source_html_bytes_changed_since_previous_review":raw_page_hashes_changed,
        "first_release_pages_verified":2,
        "source_content_hashes_not_signature_attested":True,
        "historical_D_baseline_not_rebased":True,
        "audit_scope":"FIRST_RELEASE_SPECIFIC_2026_JULY_AUGUST_NOT_ALL_HISTORICAL_VINTAGES",
    }]
    dated_audit["attestations"].append({
        "key":"GBP.labour",
        "observation_period":"2026-08",
        "release_date":"2026-10-20",
        "release_timestamp_local":None,
        "published_value":4.7,
        "raw_series_value":4.7,
        "transform":"level",
        "publisher":"Office for National Statistics",
        "url":official_rows[1]["source_url"],
        "source_locator":"ONS first published June to August 2026 16+ unemployment 4.7% on 20 October 2026; official October 2026 bulletin, original page SHA256 pinned separately",
        "official_source_page_sha256":official_rows[1]["page_sha256"],
    })
    outdir.mkdir(parents=True,exist_ok=True)
    series_file=outdir/"MACRO_SERIES.CANDIDATE.json"
    heat_file=outdir/"MACRO_THERMOMETER_DATA.CANDIDATE.json"
    series=proposal.pop("candidate_series")
    heat=proposal.pop("candidate_heatmap")
    series_file.write_text(json.dumps(series,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    heat_file.write_text(json.dumps(heat,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    (outdir/"official_first_release_receipt.json").write_text(
        json.dumps(audit,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (outdir/"stage_receipt.json").write_text(
        json.dumps(proposal,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    # Apply both sections with the already existing runtime payload mirror
    # contract. The workflow commits only once AFTER every validation succeeds.
    cmd(sys.executable,"validation/update_live_direct_section.py",
        "--section","MACRO_THERMOMETER_DATA","--replacement",str(heat_file),"--apply")
    cmd(sys.executable,"validation/build_live_manifest_v2.py",
        "--write","live_data/manifest.v2.json")
    cmd(sys.executable,"validation/update_live_direct_section.py",
        "--section","MACRO_SERIES","--replacement",str(series_file),"--apply")
    ATTEST.write_text(json.dumps(dated_audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    cmd(sys.executable,"validation/build_live_manifest_v2.py",
        "--write","live_data/manifest.v2.json")

    # Fail-closed audit: all 16 source mappings, exact 21 Growth sources,
    # 16 first-release dates, replay and manifest. Historical D is unchanged.
    from validation.macro.latest_release_pit_ledger_v1 import build_ledger
    from validation.macro.gbp_ons_temporal_guard_v1 import build as temporal_guard
    from validation.macro.rebase_readiness_v1 import g8_coverage, PATHS
    new_inputs={k:json.loads((ROOT/p).read_text()) for k,p in PATHS.items()}
    gate=g8_coverage(*(new_inputs[k] for k in PATHS),date(2026,10,20))
    require(gate["source_lineage"]=="PASS" and
            gate["safe_to_publish_D"] is False,"Macro model scored without approval")
    outcome=build_ledger(ROOT,date(2026,10,20))
    require(outcome["counts"]=={
        "FULL_RELEASE_INSTANT":4,"DATE_ONLY":12,
        "WITHHELD_EXACT_PERIOD_EVIDENCE":0,
        "WITHHELD_OFFICIAL_SOURCE_VALUE_CONFLICT":0
    },"UK first-release period still not certified")
    temporal=temporal_guard(ROOT,date(2026,10,20))
    require(temporal["status"]=="ALLOW_GBP_LABOUR_SOURCE_REFRESH"
            and temporal["safe_to_persist_gbp_labour"] is True,
            "GBP first-release period quarantine not resolved")
    cmd(sys.executable,"validation/macro/check_macro_source_registry.py")
    cmd(sys.executable,"validation/check_live_update_contract.py")
    cmd(sys.executable,"validation/rebuild_live_data_runtime.py","--verify-only")

    changed=set(cmd("git","diff","--name-only").splitlines())
    require(changed and changed.issubset(ALLOWED_UPDATES) and
            {"live_data/sections/MACRO_SERIES.json",
            "live_data/sections/MACRO_THERMOMETER_DATA.json",
            "validation/macro/CORE_G8_OFFICIAL_RELEASE_WEB_ATTESTATIONS_2026-10-20.json"
            }.issubset(changed),
            "unexpected code / FX D / site / price mutations: "+repr(sorted(changed)))
    return {
        "schema":"GMFQ_GBP_VERIFIED_FIRST_RELEASE_PROMOTION_RECEIPT_V1",
        "status":"READY_FOR_ATOMIC_SINGLE_GIT_COMMIT",
        "on_reviewed_branch_only":True,
        "source_page_hashes":observed_hashes,
        "previously_observed_source_page_hashes":PINNED_HASHES,
        "source_HTML_byte_drift":raw_page_hashes_changed,
        "economic_first_release_semantics_verified":True,
        "GBP_labour_asof_after":"2026-08",
        "GBP_labour_july":4.9,
        "GBP_labour_august":4.7,
        "macro_series_count":16,
        "release_evidence_counts":outcome["counts"],
        "source_lineage":"PASS",
        "D_macro_rebased":False,
        "pair_preferences_rebased":False,
        "changed_paths":sorted(changed),
        "candidate_artifacts":str(outdir),
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out-dir",required=True,type=Path)
    args=p.parse_args()
    receipt=promote(args.out_dir)
    (args.out_dir/"verified_promotion_receipt.json").write_text(
        json.dumps(receipt,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
