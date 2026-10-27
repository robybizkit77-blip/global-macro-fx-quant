"""Deterministic negative and production-fixture tests for research Macro V2."""
from __future__ import annotations

import copy
import math
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    ROOT, FX, build, growth_research, pillar_feature, run,
)


def fixture():
    # 26 contiguous months, with enough variation to give a nonzero MAD.
    months = [(2024 + i // 12, i % 12 + 1) for i in range(26)]
    dates = [f"{y:04d}-{m:02d}" for y, m in months]
    values = [4.0 + 0.03 * i + 0.05 * (i % 4) for i in range(26)]
    registered = {
        "series_id": "TEST_UNEMP", "frequency": "M", "transformation": "level",
        "historical_replay_evidence": {"macro_series_id": "TEST_UNEMP_history_value"},
    }
    row = {"id": "TEST_UNEMP_history_value", "dates": dates, "values": values}
    heat = {
        "series_id": "TEST_UNEMP", "frequency": "M", "transformation": "level",
        "latest_value": values[-1], "as_of": dates[-1],
        "validation": {"source": True, "history": True,
                       "latest": True, "transformation": True},
    }
    return registered, row, heat


class ObservedBridgeTests(unittest.TestCase):
    def test_synthetic_prior_only_24m_robust_research_not_fx(self):
        reg, row, heat = fixture()
        result = pillar_feature("USD", "labour", reg, row, heat, date(2026, 10, 27))
        self.assertEqual(result["status"],
                         "DESCRIPTIVE_REVISED_HISTORY_ROBUST_Z_NOT_PIT")
        self.assertEqual(result["required_prior_consecutive_periods"], 24)
        self.assertTrue(result["research_current_excluded_from_training"])
        self.assertTrue(math.isfinite(result["research_robust_z"]))
        self.assertFalse(result["eligible_for_macro_score"])
        self.assertFalse(result["eligible_for_historical_backtest"])

    def test_missing_middle_period_does_not_shift_window(self):
        reg, row, heat = fixture()
        row["dates"].pop(8)
        row["values"].pop(8)
        result = pillar_feature("USD", "labour", reg, row, heat, date(2026, 10, 27))
        self.assertEqual(result["status"], "NO_Z_MISSING_PRIOR_ECONOMIC_PERIODS")
        self.assertIn("2024-09", result["missing_prior_periods"])
        self.assertIsNone(result["research_robust_z"])

    def test_identical_date_alias_is_not_extra_training_observation(self):
        reg, row, heat = fixture()
        i = row["dates"].index("2025-06")
        row["dates"].insert(i + 1, "2025-06-01")
        row["values"].insert(i + 1, row["values"][i])
        result = pillar_feature("USD", "labour", reg, row, heat, date(2026, 10, 27))
        self.assertEqual(result["date_precision_aliases_collapsed_with_equal_values"], 1)
        self.assertEqual(result["status"],
                         "DESCRIPTIVE_REVISED_HISTORY_ROBUST_Z_NOT_PIT")

    def test_conflicting_alias_and_fake_heat_are_rejected(self):
        reg, row, heat = fixture()
        row["dates"].append("2025-06-01")
        row["values"].append(999.0)
        with self.assertRaisesRegex(ValueError, "conflicting aliases"):
            pillar_feature("USD", "labour", reg, row, heat, date(2026, 10, 27))
        reg, row, heat = fixture()
        heat["latest_value"] = 55.0
        with self.assertRaisesRegex(ValueError, "disagrees"):
            pillar_feature("USD", "labour", reg, row, heat, date(2026, 10, 27))
        reg, row, heat = fixture()
        heat["transformation"] = "reported_yoy_rate"
        with self.assertRaisesRegex(ValueError, "identity"):
            pillar_feature("USD", "labour", reg, row, heat, date(2026, 10, 27))

    def test_no_future_economic_periods(self):
        reg, row, heat = fixture()
        with self.assertRaisesRegex(ValueError, "future"):
            pillar_feature("USD", "labour", reg, row, heat, date(2026, 1, 1))

    def test_gdp_us_saar_math_and_swiss_sports_not_ranked(self):
        gdp = growth_research(date(2026, 10, 27))
        self.assertEqual(set(gdp), set(FX))
        us = gdp["USD"]
        self.assertAlmostEqual(us["descriptive_qoq_nonannualized_pct"],
                               100 * (1.015 ** 0.25 - 1), places=9)
        self.assertEqual(us["reported_unit"], "PERCENT_SAAR_ANNUALIZED")
        self.assertTrue(gdp["CHF"]["sports_adjusted_not_directly_comparable"])
        self.assertTrue(all(row["growth_score"] is None for row in gdp.values()))
        self.assertEqual(gdp["EUR"]["publication_stage"],
                         "REGULAR_ESTIMATE_REVISED")

    def test_actual_16_sources_8_growth_and_no_production_writes(self):
        from pathlib import Path
        source = ROOT / "live_data/sections"
        guarded = ("D.json", "PAIR_SETUP_OPERATIONAL_VIEW.json")
        before = {name: (source / name).read_bytes() for name in guarded}
        today = datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        observed = run(as_of=today)
        after = {name: (source / name).read_bytes() for name in guarded}
        self.assertEqual(before, after)
        self.assertEqual(set(observed["inflation_labour"]),
                         {f"{c}.{d}" for c in FX for d in ("inflation", "labour")})
        self.assertEqual(set(observed["growth_quarterly_gdp_web"]), set(FX))
        self.assertEqual(observed["summary"]["economic_dimension_slots"], 24)
        self.assertEqual(observed["summary"]["fx_strength_scores_computed"], 0)
        self.assertEqual(observed["summary"]["growth_scores_computed"], 0)
        self.assertFalse(observed["safe_to_publish_new_D"])
        self.assertFalse(observed["safe_to_update_pair_theses"])
        self.assertFalse(observed["safe_to_use_for_beta"])
        self.assertFalse(observed["safe_to_use_for_forward"])
        self.assertTrue(all(x["eligible_for_macro_score"] is False
                            for x in observed["inflation_labour"].values()))
        self.assertTrue(all(x["research_robust_z"] is None or
                            -3.0 <= x["research_robust_z"] <= 3.0
                            for x in observed["inflation_labour"].values()))
        # A clean CI run must NEVER be mistaken for an authorized D recalibration.
        self.assertEqual(observed["status"],
                         "OBSERVED_G8_RESEARCH_FEATURES_NOT_CERTIFIED_MACRO_MODEL")


if __name__ == "__main__":
    unittest.main()
