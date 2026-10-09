#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "validation"))

from macro_pit_historical_bootstrap import reconstruct_before, validate_manifest


def base_manifest():
    return {
        "schema": "GMFQ_MACRO_HISTORICAL_BOOTSTRAP_ANCHOR_V1",
        "target": {"currency": "JPY", "dimension": "inflation", "macro_series_id": "JP_CPI"},
        "authority": "TEST",
        "source": "TEST_SOURCE",
        "series_id": "JP_CPI_HEADLINE_YOY",
        "frequency": "M",
        "transformation": "reported_yoy_rate",
        "previous": {"observation_date": "2026-07", "value": 1.9, "release_date": "2026-08-21", "official_reference": "https://example.test/july"},
        "current": {"observation_date": "2026-08", "value": 1.9, "release_date": "2026-09-18", "official_reference": "https://example.test/august"},
        "provenance": {"before_snapshot_kind": "RECONSTRUCTED", "after_snapshot_kind": "CANONICAL", "official_release_pair_verified": True},
    }


def after_state():
    series = {
        "JPY": [{
            "id": "JP_CPI",
            "dates": ["2026-05", "2026-06", "2026-07", "2026-08"],
            "values": [3.5, 3.3, 1.9, 1.9],
            "last_date": "2026-08",
            "last_value": 1.9,
            "unit": "Percent YoY",
            "frequency": "M",
        }]
    }
    heat = {
        "lookback_rule": {"preferred_years": 10},
        "thresholds": [
            {"min": 0, "max": 20, "label": "MOLTO_FREDDO"},
            {"min": 20, "max": 40, "label": "FREDDO"},
            {"min": 40, "max": 60, "label": "NORMALE"},
            {"min": 60, "max": 80, "label": "CALDO"},
            {"min": 80, "max": 100, "label": "MOLTO_CALDO"},
        ],
        "currencies": {
            "JPY": {
                "inflation": {
                    "series_id": "JP_CPI_HEADLINE_YOY",
                    "source": "TEST_SOURCE",
                    "frequency": "M",
                    "transformation": "reported_yoy_rate",
                    "latest_value": 1.9,
                    "as_of": "2026-08",
                    "history": [3.5, 3.3, 1.9, 1.9],
                    "percentile": 25.0,
                    "temperature_score": 25.0,
                    "temperature_label": "FREDDO",
                    "direction": "STABILE",
                    "acceleration": "ACCELERA",
                    "validation": {"source": True, "history": True, "latest": True, "transformation": True},
                },
                "as_of_detail": {"inflation": "2026-08"},
            }
        },
    }
    return series, heat


def expect_failure(fn, needle):
    try:
        fn()
    except Exception as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected failure containing {needle!r}")


def main():
    manifest = base_manifest()
    series, heat = after_state()
    validate_manifest(manifest)
    before_series, before_heat, meta = reconstruct_before(series, heat, manifest)
    row = before_series["JPY"][0]
    assert row["last_date"] == "2026-07"
    assert row["last_value"] == 1.9
    assert before_heat["currencies"]["JPY"]["inflation"]["as_of"] == "2026-07"
    assert before_heat["currencies"]["JPY"]["as_of_detail"]["inflation"] == "2026-07"
    assert before_heat["currencies"]["JPY"]["inflation"]["history"] == [3.5, 3.3, 1.9]
    assert meta["removed_period"] == "2026-08"

    bad = copy.deepcopy(manifest)
    bad["previous"]["value"] = 2.0
    expect_failure(lambda: reconstruct_before(series, heat, bad), "penultimate canonical series value differs")

    bad = copy.deepcopy(manifest)
    bad["current"]["observation_date"] = "2026-09"
    expect_failure(lambda: reconstruct_before(series, heat, bad), "canonical latest period differs")

    bad = copy.deepcopy(manifest)
    bad["current"]["release_date"] = "2026-08-01"
    expect_failure(lambda: validate_manifest(bad), "release dates are not increasing")

    bad_heat = copy.deepcopy(heat)
    bad_heat["currencies"]["JPY"]["inflation"]["history"][-1] = 2.1
    expect_failure(lambda: reconstruct_before(series, bad_heat, manifest), "heatmap history tail differs")

    split_manifest = copy.deepcopy(manifest)
    split_manifest["transformation"] = "yoy_pct_from_index"
    split_manifest["unit"] = "% YoY"
    split_manifest["previous"].update({"observation_date": "2026-07", "value": 3.303856050706311, "series_value": 332.813})
    split_manifest["current"].update({"observation_date": "2026-08", "value": 3.353016322755642, "series_value": 334.131})
    split_series, split_heat = after_state()
    split_series["JPY"][0].update({
        "dates": ["2026-05", "2026-06", "2026-07", "2026-08"],
        "values": [333.979, 332.568, 332.813, 334.131],
        "last_date": "2026-08", "last_value": 334.131,
        "unit": "Index 1982-1984=100",
    })
    split_heat["currencies"]["JPY"]["inflation"].update({
        "transformation": "yoy_pct_from_index",
        "latest_value": 3.353016322755642,
        "history": [4.270033, 3.72653, 3.303856050706311, 3.353016322755642],
    })
    split_before_series, split_before_heat, _ = reconstruct_before(split_series, split_heat, split_manifest)
    assert split_before_series["JPY"][0]["last_value"] == 332.813
    assert split_before_heat["currencies"]["JPY"]["inflation"]["latest_value"] == 3.303856050706311

    print("GMFQ_MACRO_PIT_HISTORICAL_BOOTSTRAP_TESTS_PASS")


if __name__ == "__main__":
    main()
