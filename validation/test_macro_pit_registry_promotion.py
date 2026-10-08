#!/usr/bin/env python3
from __future__ import annotations

import copy

from macro_pit_registry_promotion import build_proposal


def evidence(head: str = "first-head") -> dict:
    return {
        "schema": "GMFQ_MACRO_PIT_ANCHOR_EVIDENCE_V1",
        "status": "PASS",
        "target": {"currency": "JPY", "dimension": "inflation", "macro_series_id": "JP_CPI"},
        "candidate": {
            "currency": "JPY", "dimension": "inflation", "macro_series_id": "JP_CPI",
            "observation_date": "2026-08", "value": 1.9,
            "source": "Statistics Bureau of Japan / e-Stat",
            "series_id": "JP_CPI_HEADLINE_YOY", "frequency": "M",
            "transformation": "reported_yoy_rate",
        },
        "anchor": {"before_git_head": head, "after_git_head": head},
        "atomic_delta": {"changed_rows": [{"currency": "JPY", "macro_series_id": "JP_CPI", "changed_paths": ["/last_date"]}]},
        "macro_series_exact_match": True,
        "heatmap_exact_match": True,
        "live_data_written_by_replay": False,
        "engine_or_source_infrastructure_changed": False,
        "registry_promotion": "NOT_ATTEMPTED",
        "bootstrap_provenance": {
            "before_state": "RECONSTRUCTED_FROM_BOUNDED_CANONICAL_AFTER_AND_OFFICIAL_PRIOR_RELEASE",
            "after_state": "CANONICAL_RUNTIME",
            "official_release_pair_verified": True,
            "manifest_sha256": "m" * 64,
        },
    }


def registry(certified: bool = False) -> dict:
    row = {
        "source_adapter_status": "READY",
        "series_id": "JP_CPI_HEADLINE_YOY",
        "frequency": "M",
        "transformation": "reported_yoy_rate",
        "historical_replay_certified": certified,
    }
    if certified:
        row["historical_replay_evidence"] = {
            "schema": "GMFQ_MACRO_PIT_CERTIFICATION_REF_V1",
            "evidence_schema": "GMFQ_MACRO_PIT_ANCHOR_EVIDENCE_V1",
            "evidence_sha256": "p" * 64,
            "macro_series_id": "JP_CPI",
            "observation_date": "2026-08",
            "value": 1.9,
            "before_git_head": "reviewed-head",
            "after_git_head": "reviewed-head",
            "promotion_mode": "EXPLICIT_REVIEW_REQUIRED",
        }
    return {"series": {"JPY.inflation": row}}


def expect_fail(registry_obj: dict, evidence_obj: dict, label: str) -> None:
    try:
        build_proposal(registry_obj, evidence_obj)
    except Exception:
        return
    raise AssertionError(f"expected failure: {label}")


def main() -> int:
    ev = evidence()
    proposed, receipt = build_proposal(registry(False), ev)
    ref = proposed["series"]["JPY.inflation"]["historical_replay_evidence"]
    assert receipt["promotion_action"] == "PROPOSAL_CREATED"
    assert receipt["evidence_class"] == "RECONSTRUCTED_HISTORICAL_REPLAY"
    assert ref["evidence_class"] == "RECONSTRUCTED_HISTORICAL_REPLAY"
    assert ref["official_release_pair_verified"] is True
    assert ref["before_state"].startswith("RECONSTRUCTED_")
    assert ref["before_git_head"] == "first-head"

    legacy = registry(True)
    proposed2, receipt2 = build_proposal(legacy, evidence("later-rerun-head"))
    ref2 = proposed2["series"]["JPY.inflation"]["historical_replay_evidence"]
    assert receipt2["promotion_action"] == "METADATA_ENRICHMENT_PROPOSED"
    assert ref2["evidence_class"] == "RECONSTRUCTED_HISTORICAL_REPLAY"
    assert ref2["evidence_sha256"] == "p" * 64
    assert ref2["before_git_head"] == "reviewed-head"
    assert ref2["after_git_head"] == "reviewed-head"

    proposed3, receipt3 = build_proposal(proposed2, evidence("another-rerun-head"))
    assert receipt3["promotion_action"] == "ALREADY_CERTIFIED"
    assert proposed3 == proposed2

    bad = copy.deepcopy(ev); bad["status"] = "FAIL"
    expect_fail(registry(False), bad, "non-PASS evidence")
    bad = copy.deepcopy(ev); bad["bootstrap_provenance"]["official_release_pair_verified"] = False
    expect_fail(registry(False), bad, "unverified reconstructed release pair")
    bad = copy.deepcopy(ev); bad["candidate"]["series_id"] = "WRONG"
    expect_fail(registry(False), bad, "registry provenance mismatch")

    print("GMFQ_MACRO_PIT_REGISTRY_PROMOTION_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
