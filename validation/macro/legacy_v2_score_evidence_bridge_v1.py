#!/usr/bin/env python3
"""Bridge the frozen 24 Macro scalars to the actual 24-slot V2 source evidence.

No retrospective fitting, scoring, factor weights, policy inference or updates.
A frozen numeric scalar is an OUTPUT of an unknown model, not a training label
from which its causal source-to-score formula may be inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.score_formula_provenance_v1 import run as score_run, ROOT
from validation.macro.v2_pit_g8_control_plane_v1 import run as v2_run

SCHEMA = "GMFQ_LEGACY_MACRO_24_SCORE_TO_V2_EVIDENCE_BRIDGE_V1"
FX = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
PILLARS = ("growth", "labour", "inflation")
FROZEN = "2026-09-25"


def check(predicate, message):
    if not predicate:
        raise ValueError("MACRO_SCORE_EVIDENCE_BRIDGE_REJECTED: " + message)


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def bridge(model, legacy, v2):
    check(model.get("asOf") == FROZEN and legacy.get("model_as_of") == FROZEN,
          "frozen baseline identity changed")
    check(legacy.get("status") ==
          "PASS_HISTORICAL_SCORE_READERS_IDENTIFIED_NO_SCORE_GENERATOR_CERTIFIED"
          and legacy.get("historical_scalar_scores") == 24
          and legacy.get("historical_regimes") == 8
          and legacy.get("ready_for_numeric_macro_rebase") is False
          and legacy.get("safe_to_publish_new_D") is False,
          "legacy score formula provenance is not certified")
    check(v2.get("schema") ==
          "GMFQ_MACRO_V2_G8_SHARED_PIT_CONTROL_PLANE_V1"
          and v2.get("status") ==
          "G8_24_SLOT_SOURCE_CONTROL_PLANE_READ_ONLY_NOT_PIT_CERTIFIED"
          and v2.get("scores_computed") is False
          and v2.get("model_parameters_fitted") is False
          and v2.get("safe_to_publish_new_D") is False,
          "V2 sources cannot be treated as new Macro model scores")
    old = model.get("macro")
    check(isinstance(old, dict) and set(old) == set(FX),
          "frozen scalar currency coverage incomplete")
    rows = v2.get("rows")
    check(isinstance(rows, list) and len(rows) == 24,
          "V2 source slot coverage incomplete")
    mapping = {}
    for row in rows:
        check(isinstance(row, dict), "malformed V2 source slot")
        key = (row.get("currency"), row.get("pillar"))
        check(key[0] in FX and key[1] in PILLARS and key not in mapping,
              "duplicate or foreign V2 currency-pillar source")
        check(row.get("eligible_for_macro_score") is False
              and row.get("eligible_for_backtest") is False
              and row.get("safe_to_publish_new_D") is False
              and row.get("canonical_first_release_chain_certified") is False
              and row.get("original_release_day_immutable_bytes_verified") is False,
              "candidate data illegally promoted as a certified score")
        mapping[key] = row
    check(set(mapping) == {(c, p) for c in FX for p in PILLARS},
          "G8 24 original numeric slots do not join V2 sources")
    check(v2.get("summary", {}).get("pillar_slots") == 24
          and v2.get("summary", {}).get("slots_eligible_for_new_live_scores") == 0,
          "V2 coverage/eligibility summary mismatch")

    out = []
    for currency in FX:
        for pillar in PILLARS:
            historical = old[currency].get(pillar)
            check(finite(historical), "unverifiable frozen scalar value")
            evidence = mapping[(currency, pillar)]
            source = evidence.get("candidate_evidence_source_id")
            same = bool(source is not None
                        and evidence.get("canonical_series_id_matches_candidate") is True
                        and evidence.get("canonical_frequency_matches_candidate") is True)
            first_count = evidence.get("candidate_documented_first_periods_visible")
            check(type(first_count) is int and first_count >= 0,
                  "invalid reported candidate first-release count")
            target = evidence.get("minimum_training_first_releases_per_canonical_frequency")
            check(target is None or (type(target) is int and target >= 2),
                  "invalid canonical training requirement")
            # Only compare like-for-like registered source and frequency.
            gap = max(0, target - first_count) if same and target is not None else None
            reason = ("NO_CANDIDATE_SOURCE" if source is None else
                      "CANDIDATE_SOURCE_ID_OR_FREQUENCY_MISMATCH" if not same else
                      "CANDIDATE_MATCHES_ID_AND_FREQUENCY_BUT_NOT_PIT_CERTIFIED")
            out.append({
                "currency": currency, "pillar": pillar,
                "frozen_score_as_of": FROZEN,
                "frozen_historical_scalar": historical,
                "old_formula_source_to_score": "NOT_FOUND_IN_VERIFIED_REPOSITORY",
                "candidate_source_id": source,
                "canonical_source_id": evidence.get("canonical_series_id"),
                "source_id_and_frequency_match": same,
                "candidate_first_release_periods_visible": first_count,
                "minimum_required_canonical_first_releases": target,
                "same_source_periods_still_needed_descriptive_only": gap,
                "candidate_source_status": evidence.get("source_status"),
                "open_source_gate": reason,
                "candidate_history_archived_original_bytes": False,
                "approved_source_to_score_formula": False,
                "independent_second_dated_score_replay": False,
                "safe_to_regenerate_pillar_score": False,
            })
    first_total = sum(r["candidate_first_release_periods_visible"] for r in out)
    check(first_total ==
          v2["summary"]["candidate_first_release_reference_periods_visible"],
          "candidate source coverage counts do not reconcile")
    source_match = sum(r["source_id_and_frequency_match"] for r in out)
    no_source = sum(r["candidate_source_id"] is None for r in out)
    mismatch = 24 - source_match - no_source
    check(no_source == v2["summary"]["slots_without_shared_candidate_stream"],
          "source stream count mismatch")
    return {
        "schema": SCHEMA,
        "status": "HISTORICAL_SCALARS_JOINED_RESEARCH_SOURCE_EVIDENCE_NO_FORMULA",
        "historical_baseline_as_of": FROZEN,
        "legacy_source_commit": legacy["historical_snapshot_commit"],
        "legacy_historical_scores_sha256": legacy["historical_scores_sha256"],
        "v2_research_source_review_sha256": v2["source_review_fingerprint_sha256"],
        "summary": {
            "historical_scalar_values": len(out),
            "v2_currency_pillar_evidence_slots": len(out),
            "source_id_and_frequency_matches": source_match,
            "candidate_missing": no_source,
            "candidate_wrong_id_or_frequency": mismatch,
            "documented_web_first_release_periods_not_archived_pit": first_total,
            "eligible_for_new_numeric_scores": 0,
            "independent_historical_formula_replays": 0,
        },
        "rows": out,
        "next_actual_blockers": [
            "Locate independent original source-to-score generator OR preregister a separately versioned new research model; never fit the 24 outputs.",
            "Choose exact economically comparable canonical indicator per pillar and currency.",
            "Certify actual release-day first-publication vintages, revisions, clock, and required historical training spans.",
            "Replay at least two independent dated frozen inputs and held-out periods before any promotion.",
            "Only after independent certification review a new D.json, 28 pairs, Beta and forward baseline restart.",
        ],
        "method": "CROSSWALK_ONLY_NO_INVERSE_REGRESSION_ON_24_FROZEN_OUTPUTS",
        "no_new_scores": True,
        "no_bespoke_weights": True,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "writes_live_data": False,
    }


def run():
    now = datetime.now(timezone.utc)
    model = json.loads((ROOT / "live_data/sections/D.json").read_text(encoding="utf-8"))
    legacy = score_run(today=now.astimezone(ZoneInfo("Europe/Rome")).date())
    control = v2_run(as_of=now.isoformat())
    return bridge(model, legacy, control)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out is not None:
        check(args.out.resolve().is_relative_to(Path("/tmp")),
              "receipt output must remain under /tmp")
    receipt = run()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, sort_keys=True, ensure_ascii=False,
                                       indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": receipt["status"], **receipt["summary"],
        "safe_to_publish_new_D": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
