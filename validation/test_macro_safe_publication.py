#!/usr/bin/env python3
from __future__ import annotations

import json
from macro_safe_publication import validate


def base_candidate():
    return {
        "currency": "JPY",
        "dimension": "labour",
        "macro_series_id": "JP_UNEMP_RATE_history_value",
        "observation_date": "2099-12",
        "value": 2.601,
        "source": "Statistics Bureau of Japan / e-Stat",
        "series_id": "JP_UNEMP_RATE",
        "frequency": "M",
        "transformation": "level",
        "unit": "%",
    }


def base_evidence(candidate):
    return {
        "schema": "GMFQ_MACRO_PIT_ANCHOR_EVIDENCE_V1",
        "status": "PASS",
        "target": {
            "currency": candidate["currency"],
            "dimension": candidate["dimension"],
            "macro_series_id": candidate["macro_series_id"],
        },
        "candidate": dict(candidate),
        "anchor": {"before_git_head": "before", "after_git_head": "after"},
        "atomic_delta": {
            "changed_rows": [{
                "currency": candidate["currency"],
                "macro_series_id": candidate["macro_series_id"],
                "changed_paths": ["/last_date", "/last_value"],
            }],
            "changed_heatmap_cells": ["/currencies/JPY/labour/latest_value"],
        },
        "macro_series_exact_match": True,
        "heatmap_exact_match": True,
        "live_data_written_by_replay": False,
        "engine_or_source_infrastructure_changed": False,
        "registry_promotion": "NOT_ATTEMPTED",
    }


def expect_rejected(candidate, evidence, needle):
    result = validate(candidate, evidence)
    assert result["status"] == "REJECTED", result
    assert any(needle in x for x in result["failures"]), result


def main() -> int:
    c = base_candidate()
    e = base_evidence(c)
    good = validate(c, e)
    assert good["status"] == "READY_FOR_RUNTIME_PROPOSAL", good
    assert good["publication_policy"]["automatic_publication"] is False
    assert good["publication_policy"]["review_required"] is True

    bad = base_evidence(c)
    bad["macro_series_exact_match"] = False
    expect_rejected(c, bad, "MACRO_SERIES")

    bad = base_evidence(c)
    bad["engine_or_source_infrastructure_changed"] = True
    expect_rejected(c, bad, "engine/source")

    bad = base_evidence(c)
    bad["candidate"]["value"] = 99.0
    expect_rejected(c, bad, "candidate differs")

    bad = base_evidence(c)
    bad["atomic_delta"]["changed_rows"].append({"currency": "USD", "macro_series_id": "X"})
    expect_rejected(c, bad, "atomic single-row")

    print(json.dumps({
        "schema": "GMFQ_MACRO_SAFE_PUBLICATION_SELFTEST_V1",
        "status": "PASS",
        "positive_case": True,
        "negative_cases": 4,
        "automatic_publication": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
