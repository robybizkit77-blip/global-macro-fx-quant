#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import pathlib
import tempfile

from macro_pit_registry_promotion import build_proposal, load

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "validation" / "macro" / "MACRO_SOURCE_REGISTRY_2026-10-08.json"


def evidence_for(key: str, macro_series_id: str, candidate_series_id: str, frequency: str, transformation: str) -> dict:
    currency, dimension = key.split(".")
    return {
        "schema": "GMFQ_MACRO_PIT_ANCHOR_EVIDENCE_V1",
        "status": "PASS",
        "target": {"currency": currency, "dimension": dimension, "macro_series_id": macro_series_id},
        "candidate": {
            "currency": currency,
            "dimension": dimension,
            "macro_series_id": macro_series_id,
            "observation_date": "2099-01",
            "value": 1.23,
            "source": "SELF_TEST_ONLY",
            "series_id": candidate_series_id,
            "frequency": frequency,
            "transformation": transformation,
        },
        "anchor": {
            "before_git_head": "0" * 40,
            "after_git_head": "1" * 40,
            "before_sha256": {},
            "after_sha256": {},
        },
        "atomic_delta": {
            "changed_rows": [{"currency": currency, "macro_series_id": macro_series_id, "changed_paths": ["/last_value"]}],
            "changed_heatmap_cells": [f"/currencies/{currency}/{dimension}/latest_value"],
        },
        "macro_series_exact_match": True,
        "heatmap_exact_match": True,
        "live_data_written_by_replay": False,
        "engine_or_source_infrastructure_changed": False,
        "registry_promotion": "NOT_ATTEMPTED",
        "builder_summary": {"status": "PASS"},
    }


def expect_fail(registry: dict, evidence: dict, label: str) -> None:
    try:
        build_proposal(registry, evidence)
    except Exception:
        return
    raise AssertionError(f"expected failure: {label}")


def main() -> int:
    registry = load(REGISTRY)
    target = "JPY.inflation"
    row = registry["series"][target]
    ev = evidence_for(target, "JP_CPI_HEADLINE_YOY_RUNTIME", row["series_id"], row["frequency"], row["transformation"])

    proposed, receipt = build_proposal(registry, ev)
    assert registry["series"][target]["historical_replay_certified"] is False
    assert proposed["series"][target]["historical_replay_certified"] is True
    ref = proposed["series"][target]["historical_replay_evidence"]
    assert ref["schema"] == "GMFQ_MACRO_PIT_CERTIFICATION_REF_V1"
    assert ref["promotion_mode"] == "EXPLICIT_REVIEW_REQUIRED"
    assert receipt["promotion_action"] == "PROPOSAL_CREATED"
    assert receipt["canonical_registry_modified"] is False
    assert receipt["registry_promotion"] == "REVIEW_REQUIRED"

    bad = copy.deepcopy(ev)
    bad["status"] = "FAIL"
    expect_fail(registry, bad, "non-PASS evidence")
    bad = copy.deepcopy(ev)
    bad["atomic_delta"]["changed_rows"].append(copy.deepcopy(bad["atomic_delta"]["changed_rows"][0]))
    expect_fail(registry, bad, "non-atomic evidence")
    bad = copy.deepcopy(ev)
    bad["candidate"]["series_id"] = "WRONG"
    expect_fail(registry, bad, "registry provenance mismatch")

    with tempfile.TemporaryDirectory(prefix="gmfq-promotion-test-") as tmp:
        p = pathlib.Path(tmp) / "proposed.json"
        p.write_text(json.dumps(proposed), encoding="utf-8")
        assert p.exists()

    print(json.dumps({
        "status": "PASS",
        "schema": "GMFQ_MACRO_PIT_REGISTRY_PROMOTION_SELFTEST_V1",
        "positive_target": target,
        "negative_cases": 3,
        "canonical_registry_modified": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
