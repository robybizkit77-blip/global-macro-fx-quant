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
    frozen_values = {currency: {
        name: old[currency].get(name) for name in (*PILLARS, "cycle")
    } for currency in FX}
    frozen_hash = hashlib.sha256(json.dumps(
        frozen_values, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    check(legacy.get("historical_scores_sha256") == frozen_hash,
          "frozen 24 historical output vector not aligned with scored source receipt")
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
            canonical_id = evidence.get("canonical_series_id")
            canonical_freq = evidence.get("canonical_frequency")
            candidate_freq = evidence.get("candidate_frequency")
            sid_match = source is not None and canonical_id is not None and source == canonical_id
            freq_match = candidate_freq is not None and canonical_freq is not None and candidate_freq == canonical_freq
            check(evidence.get("canonical_series_id_matches_candidate") is sid_match
                  and evidence.get("canonical_frequency_matches_candidate") is freq_match,
                  "upstream source/frequency parity inconsistent with actual labels")
            same = sid_match and freq_match
            first_count = evidence.get("candidate_documented_first_periods_visible")
            check(type(first_count) is int and first_count >= 0,
                  "invalid reported candidate first-release count")
            target = evidence.get("minimum_training_first_releases_per_canonical_frequency")
            check(target is None or (type(target) is int and target >= 2),
                  "invalid canonical training requirement")
            # Only compare like-for-like registered source and frequency.
            gap = max(0, target - first_count) if same and target is not None else None
            # Exactly eight Growth canonical slots still have no chosen metric.
            # Their mismatches must never be counted as corrupt source mappings.
            if pillar == "growth":
                check(canonical_id is None and canonical_freq is None,
                      "Growth source selected without a reviewed versioned rule")
                category = "GROWTH_CANONICAL_INDICATOR_NOT_SELECTED"
                next_action = "Select and approve the Growth metric, unit and economic horizon before binding a V2 source"
            elif source is None:
                category = "NO_CANDIDATE_SOURCE"
                next_action = "Acquire attested publisher first releases for the exact registered indicator"
            elif not sid_match and not freq_match:
                category = "INDICATOR_AND_FREQUENCY_DIFFER"
                next_action = "Reconcile both economic metric identity and period frequency; do not substitute series"
            elif not sid_match:
                category = "INDICATOR_DIFFERS_SAME_FREQUENCY"
                next_action = "Verify metric identities and units on official source before proposing a crosswalk"
            elif not freq_match:
                category = "FREQUENCY_DIFFERS"
                next_action = "Reconcile period horizon and observation windows before proposing a mapping"
            else:
                category = "TECHNICAL_ID_FREQUENCY_MATCH_PIT_NOT_CERTIFIED"
                next_action = "Verify actual first-release original-day history and versioned score formula"
            reason = ("CANDIDATE_MATCHES_ID_AND_FREQUENCY_BUT_NOT_PIT_CERTIFIED"
                      if same else category)
            out.append({
                "currency": currency, "pillar": pillar,
                "frozen_score_as_of": FROZEN,
                "frozen_historical_scalar": historical,
                "old_formula_source_to_score": "NOT_FOUND_IN_VERIFIED_REPOSITORY",
                "candidate_source_id": source,
                "canonical_source_id": canonical_id,
                "canonical_frequency": canonical_freq,
                "candidate_frequency": candidate_freq,
                "canonical_series_id_matches_candidate": sid_match,
                "canonical_frequency_matches_candidate": freq_match,
                "source_id_and_frequency_match": same,
                "source_reconciliation_class": category,
                "recommended_source_review_action": next_action,
                "canonical_metric_unit_or_publisher_mapping_certified": False,
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
    category_counts = {name: sum(r["source_reconciliation_class"] == name for r in out)
                       for name in (
                           "GROWTH_CANONICAL_INDICATOR_NOT_SELECTED",
                           "NO_CANDIDATE_SOURCE",
                           "INDICATOR_AND_FREQUENCY_DIFFER",
                           "INDICATOR_DIFFERS_SAME_FREQUENCY",
                           "FREQUENCY_DIFFERS",
                           "TECHNICAL_ID_FREQUENCY_MATCH_PIT_NOT_CERTIFIED")}
    check(category_counts["GROWTH_CANONICAL_INDICATOR_NOT_SELECTED"] == 8,
          "unexpected Growth source-selection contract")
    check(sum(category_counts.values()) == 24,
          "missing evidence reconciliation classifications")
    other_mismatch = sum(
        r["pillar"] != "growth" and
        r["source_reconciliation_class"] not in (
            "TECHNICAL_ID_FREQUENCY_MATCH_PIT_NOT_CERTIFIED",
            "NO_CANDIDATE_SOURCE")
        for r in out
    )
    check(mismatch == category_counts["GROWTH_CANONICAL_INDICATOR_NOT_SELECTED"]
          + other_mismatch, "crosswalk mismatch decomposition inconsistent")
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
            "unselected_growth_canonical_indicators": category_counts["GROWTH_CANONICAL_INDICATOR_NOT_SELECTED"],
            "non_growth_source_or_frequency_mismatches": other_mismatch,
            "source_reconciliation_classes": category_counts,
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


def markdown(receipt):
    """Human audit: show the exact identity/frequency discrepancies first."""
    stats = receipt["summary"]
    lines = [
        "# Macro G8 - source-to-score reconciliation (read only)",
        "",
        "Historical Macro baseline: 2026-09-25. **No new scores or FX rankings authorised.**",
        "",
        f"Technical source ID and frequency matches: **{stats['source_id_and_frequency_matches']}/24**. "
        f"Unselected Growth canonical indicators: **{stats['unselected_growth_canonical_indicators']}**. "
        f"Other source/frequency mismatches: **{stats['non_growth_source_or_frequency_mismatches']}**.",
        "",
        "A matching ID/frequency does **not** prove metric equivalence, first-release PIT history "
        "or a source-to-score formula. Archived release-day proof for the full training "
        "series is still absent.",
        "",
        "| Currency | Pillar | Registered metric (frequency) | Candidate (frequency) | Visible first-release periods | Precise blocker |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    rows = sorted(receipt["rows"], key=lambda r: (
        r["source_id_and_frequency_match"], r["pillar"] != "growth",
        r["currency"], r["pillar"]))
    for r in rows:
        label = lambda key: str(r.get(key) or "NOT_SELECTED")
        lines.append(
            f"| {r['currency']} | {r['pillar']} | "
            f"{label('canonical_source_id')} ({label('canonical_frequency')}) | "
            f"{label('candidate_source_id')} ({label('candidate_frequency')}) | "
            f"{r['candidate_first_release_periods_visible']} | "
            f"{r['source_reconciliation_class']} |"
        )
    lines += [
        "",
        "**Ordering:** all pending indicators first; matching technical IDs last.",
        "",
        "## Explicit exclusions",
        "- No implied equation for Growth/Labour/Inflation was inferred from 24 historical outputs.",
        "- A reported source mismatch is not necessarily a data-provider error; it may be a different economic statistic.",
        "- A first-release webpage is not equivalent to archived immutable first-release values and revisions.",
        "- No PIT-certified rebase or current-day Macro strength is created by this dossier.",
        "",
    ]
    return "\n".join(lines)


def run():
    now = datetime.now(timezone.utc)
    model = json.loads((ROOT / "live_data/sections/D.json").read_text(encoding="utf-8"))
    legacy = score_run(today=now.astimezone(ZoneInfo("Europe/Rome")).date())
    control = v2_run(as_of=now.isoformat())
    return bridge(model, legacy, control)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    for output in (args.out, args.markdown):
        if output is not None:
            check(output.resolve().is_relative_to(Path("/tmp")),
                  "receipt output must remain under /tmp")
    receipt = run()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, sort_keys=True, ensure_ascii=False,
                                       indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(receipt) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": receipt["status"], **receipt["summary"],
        "safe_to_publish_new_D": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
