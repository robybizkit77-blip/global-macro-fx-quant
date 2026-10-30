"""Pure synthetic EUR labour scale diagnostics; real sources remain read-only."""
from __future__ import annotations
import copy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from validation.macro import v2_eur_labour_zero_mad_diagnostic_v1 as diag


def fixture(prior=None, current=6.5):
    # 2024-09 through 2026-08 => 24 prior months, 2026-09 current.
    historical = prior if prior is not None else [6.3]*11 + [6.4]*13
    assert len(historical) == 24
    base = 2024 * 12 + 8
    months = [f"{(base+i)//12:04d}-{((base+i)%12)+1:02d}" for i in range(25)]
    row = {
        "id": "EA_UNEMP_history_value",
        "dates": months,
        "values": historical + [current],
    }
    registered = {
        "series_id": "EA_UNEMP",
        "transformation": "level",
        "frequency": "M",
        "historical_replay_evidence": {
            "macro_series_id": "EA_UNEMP_history_value"
        },
    }
    return row, registered


class ZeroMadDiagnosticTests(unittest.TestCase):
    def test_rounded_plateau_makes_mad_zero_but_ordinal_change_is_observed(self):
        row, reg = fixture()
        receipt = diag.assess(row, reg, as_of=date(2026,10,30))
        self.assertEqual(receipt["status"], "ROBUST_Z_UNDEFINED_ZERO_MAD")
        self.assertEqual(receipt["current_economic_period"], "2026-09")
        self.assertEqual(receipt["prior_economic_periods"], 24)
        self.assertEqual(receipt["prior_distribution"], [
            {"value": 6.3, "count": 11}, {"value": 6.4, "count": 13}
        ])
        self.assertEqual(receipt["prior_median_pct"], 6.4)
        self.assertEqual(receipt["prior_mad_pct"], 0)
        self.assertEqual(receipt["current_vs_prior_max"],
                         "ABOVE_ALL_PRIOR_OBSERVATIONS")
        self.assertEqual(receipt["current_percentile_midrank_prior"], 1)
        self.assertAlmostEqual(receipt["not_approved_std_scale_z_sensitivity"], 1.9647, places=3)
        self.assertAlmostEqual(receipt["not_approved_iqr_scale_z_sensitivity"], 1.349, places=3)
        self.assertIsNone(receipt["authorized_fallback_method"])
        self.assertFalse(receipt["safe_to_use_as_forward_v2_numeric_feature"])
        self.assertFalse(receipt["writes_frozen_forward_journals"])

    def test_all_prior_levels_identical_still_no_division_by_zero(self):
        row, reg=fixture(prior=[6.4]*24)
        receipt=diag.assess(row,reg,as_of=date(2026,10,30))
        self.assertIsNone(receipt["not_approved_std_scale_z_sensitivity"])
        self.assertIsNone(receipt["not_approved_iqr_scale_z_sensitivity"])
        self.assertEqual(receipt["prior_mad_pct"],0)
        self.assertIsNone(receipt["authorized_fallback_method"])

    def test_missing_prior_month_and_future_economic_period_are_rejected(self):
        row, reg=fixture()
        row["dates"].pop(6)
        row["values"].pop(6)
        with self.assertRaisesRegex(ValueError,"missing prior economic periods"):
            diag.assess(row,reg,as_of=date(2026,10,30))
        row, reg=fixture()
        with self.assertRaisesRegex(ValueError,"future economic observation"):
            diag.assess(row,reg,as_of=date(2026,8,1))

    def test_identity_conflicts_and_fake_same_period_alias_rejected(self):
        row, reg=fixture()
        bad=copy.deepcopy(row)
        bad["id"]="EUR_OTHER_RATE"
        with self.assertRaisesRegex(ValueError,"identity mismatch"):
            diag.assess(bad,reg,as_of=date(2026,10,30))
        bad=copy.deepcopy(reg)
        bad["transformation"]="yoy_pct_from_index"
        with self.assertRaisesRegex(ValueError,"wrong series definition"):
            diag.assess(row,bad,as_of=date(2026,10,30))
        bad=copy.deepcopy(row)
        bad["dates"].append("2026-08-01")
        bad["values"].append(99.)
        with self.assertRaisesRegex(ValueError,"conflicting aliases"):
            diag.assess(bad,reg,as_of=date(2026,10,30))

    def test_live_read_is_research_only_does_not_touch_forward_or_core(self):
        root=diag.ROOT
        protect=[root/"live_data/sections/D.json",
                 root/"live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
                 root/"validation/forward/candidate_shadow_snapshots/V2_MACRO_EVIDENCE_SNAPSHOTS_V1.jsonl"]
        before={str(p):p.read_bytes() for p in protect}
        result=diag.run()
        after={str(p):p.read_bytes() for p in protect}
        self.assertEqual(before,after)
        self.assertEqual(result["schema"],diag.SCHEMA)
        self.assertEqual(result["registered_slot"],"EUR.labour")
        self.assertTrue(result["not_PIT_or_FX_predictive_validation"])
        self.assertFalse(result["safe_to_use_as_forward_v2_numeric_feature"])
        self.assertTrue(len(result["input_sha256"])==64)


if __name__=="__main__":
    unittest.main()
