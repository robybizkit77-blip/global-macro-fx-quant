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

    def test_bls_attested_october_gap_yields_only_explicit_estimate(self):
        from validation.macro.v2_us_shutdown_gap_research_v1 import (
            shadow_gap_estimate, BLS_EVIDENCE
        )
        reg, row, heat = fixture()
        reg["series_id"] = "UNRATE"
        reg["historical_replay_evidence"]["macro_series_id"] = "US_UNRATE_history_value"
        row["id"] = "US_UNRATE_history_value"
        heat["series_id"] = "UNRATE"
        i = row["dates"].index("2025-10")
        row["dates"].pop(i)
        row["values"].pop(i)
        strict = pillar_feature("USD", "labour", reg, row, heat, date(2026, 10, 27))
        self.assertIsNone(strict["research_robust_z"])
        self.assertIn("2025-10", strict["missing_prior_periods"])
        gap = shadow_gap_estimate(
            "labour", reg, row, heat, strict, date(2026, 10, 27))
        self.assertEqual(gap["status"],
                         "BLS_SHUTDOWN_GAP_AWARE_RESEARCH_ESTIMATE_NOT_PIT")
        self.assertEqual(gap["training_observed_months_used"], 24)
        self.assertEqual(gap["missing_calendar_periods"], ["2025-10"])
        self.assertTrue(-3 <= gap["estimated_research_robust_z"] <= 3)
        self.assertFalse(gap["original_missing_value_imputed"])
        self.assertFalse(gap["allow_macro_score"])
        self.assertFalse(gap["allow_beta"])
        self.assertEqual(gap["official_evidence_url"],
                         BLS_EVIDENCE["labour"]["primary_reference"])

    def test_extra_gap_does_not_get_hidden_by_structural_exception(self):
        from validation.macro.v2_us_shutdown_gap_research_v1 import shadow_gap_estimate
        reg, row, heat = fixture()
        reg["series_id"] = "UNRATE"
        reg["historical_replay_evidence"]["macro_series_id"] = "US_UNRATE_history_value"
        row["id"] = "US_UNRATE_history_value"
        heat["series_id"] = "UNRATE"
        for d in ("2025-10", "2025-09"):
            i = row["dates"].index(d)
            row["dates"].pop(i)
            row["values"].pop(i)
        strict = pillar_feature("USD", "labour", reg, row, heat, date(2026, 10, 27))
        gap = shadow_gap_estimate("labour", reg, row, heat, strict,
                                  date(2026, 10, 27))
        self.assertIsNone(gap["estimated_research_robust_z"])
        self.assertEqual(gap["status"],
                         "NO_GAP_ESTIMATE_UNLESS_EXACT_BLS_MISSING_MONTH")
        self.assertEqual(gap["missing_calendar_periods"], ["2025-09", "2025-10"])

    def test_missing_month_must_really_be_absent_and_correct_source(self):
        from validation.macro.v2_us_shutdown_gap_research_v1 import shadow_gap_estimate
        reg, row, heat = fixture()
        reg["series_id"] = "UNRATE"
        reg["historical_replay_evidence"]["macro_series_id"] = "US_UNRATE_history_value"
        row["id"] = "US_UNRATE_history_value"
        heat["series_id"] = "UNRATE"
        # A different month cannot borrow the BLS October official exception.
        i = row["dates"].index("2025-09")
        row["dates"].pop(i)
        row["values"].pop(i)
        strict = pillar_feature("USD", "labour", reg, row, heat, date(2026, 10, 27))
        with self.assertRaisesRegex(ValueError, "fabricated"):
            shadow_gap_estimate("labour", reg, row, heat, strict,
                                date(2026, 10, 27))
        reg["series_id"] = "FAKE"
        with self.assertRaisesRegex(ValueError, "exact registered"):
            shadow_gap_estimate("labour", reg, row, heat, strict,
                                date(2026, 10, 27))

    def test_cpi_index_yoy_uses_actual_12_month_reference_not_shifted_row(self):
        from validation.macro.v2_us_shutdown_gap_research_v1 import shadow_gap_estimate
        dates = []
        values = []
        for i in range(39):  # Jan 2023 through Mar 2026
            y, m = 2023 + i // 12, i % 12 + 1
            raw = f"{y:04d}-{m:02d}"
            if raw != "2025-10":
                dates.append(raw)
                values.append(290 + i * 0.5 + 0.02 * (i % 4))
        reg = {
            "series_id": "CPIAUCSL", "frequency": "M",
            "transformation": "yoy_pct_from_index",
            "historical_replay_evidence": {
                "macro_series_id": "US_CPIAUCSL_history_value"},
        }
        row = {"id": "US_CPIAUCSL_history_value",
               "dates": dates, "values": values}
        actual_map = dict(zip(dates, values))
        true_yoy = 100 * (actual_map["2026-03"] / actual_map["2025-03"] - 1)
        heat = {
            "series_id": "CPIAUCSL", "frequency": "M",
            "transformation": "yoy_pct_from_index",
            "as_of": "2026-03", "latest_value": true_yoy,
            "validation": dict.fromkeys(("source", "history", "latest",
                                         "transformation"), True),
        }
        strict = pillar_feature("USD", "inflation", reg, row, heat,
                                date(2026, 10, 27))
        self.assertEqual(strict["status"], "NO_Z_MISSING_PRIOR_ECONOMIC_PERIODS")
        self.assertAlmostEqual(strict["observation_value"], true_yoy)
        est = shadow_gap_estimate("inflation", reg, row, heat,
                                  strict, date(2026, 10, 27))
        self.assertEqual(est["status"],
                         "BLS_SHUTDOWN_GAP_AWARE_RESEARCH_ESTIMATE_NOT_PIT")
        self.assertEqual(est["training_observed_months_used"], 24)
        self.assertEqual(est["missing_calendar_periods"], ["2025-10"])
        self.assertTrue(math.isfinite(est["estimated_research_robust_z"]))
        self.assertFalse(est["allow_pair_ranking"])

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
        self.assertIn("additional_us_gap_aware_estimates", observed["summary"])
        self.assertEqual(set(observed["us_bls_shutdown_research_estimates"]),
                         {k for k in ("USD.inflation", "USD.labour")
                          if observed["inflation_labour"][k]["research_robust_z"] is None})
        self.assertTrue(all(x["allow_macro_score"] is False and
                            x["allow_pair_ranking"] is False
                            for x in observed["us_bls_shutdown_research_estimates"].values()))

        self.assertEqual(observed["summary"]["growth_scores_computed"], 0)
        self.assertEqual(observed["summary"]["gdp_descriptive_research_growth_features"], 8)
        self.assertEqual(set(observed["growth_quarterly_gdp_initial_web_research_features"]), set(FX))
        self.assertEqual(observed["summary"]["gdp_features_with_definition_caveats"], 2)
        self.assertTrue(observed["gdp_initial_web_features_not_model_growth_scores"])
        self.assertTrue(all(z["numeric_model_growth_score"] is None and
                            z["actual_PIT_backtest_eligible"] is False
                            for z in observed["growth_quarterly_gdp_initial_web_research_features"].values()))
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
