"""Adversarial US October 2025 BLS nonrelease / calendar-gap tests."""
from __future__ import annotations

import copy
import json
import unittest

from validation.macro.v2_us_shutdown_2025_calendar_gap_v1 import (
    audit, SCHEMA, SLOTS,
)
from validation.macro.v2_g8_observed_feature_bridge_v1 import ROOT, run as observed_run


class USOfficialShutdownCalendarGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src=json.loads((ROOT/"live_data/sections/MACRO_SERIES.json").read_text())
        cls.series={"USD":[copy.deepcopy(row) for row in src["USD"]
                   if row["id"] in {v["macro_series"] for v in SLOTS.values()}]}
        reg=json.loads((ROOT/"validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json").read_text())
        cls.registry={"series":{k:copy.deepcopy(reg["series"][k]) for k in SLOTS}}
        cls.day="2026-10-31"
        cls.observed=observed_run(as_of=cls.day)

    def run_audit(self,**kwargs):
        data={name:copy.deepcopy(getattr(self,name)) for name in ("series","registry","observed")}
        data.update(kwargs)
        return audit(data["series"],data["registry"],data["observed"],checked_as_of=self.day)

    def test_us_CPI_and_CPS_october_2025_nonrelease_is_two_strict_calendar_gaps(self):
        r=self.run_audit()
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["summary"]["officially_uncollected_US_2025_10_series"],2)
        self.assertEqual(r["summary"]["strict_24_calendar_missing_slots"],
                         ["USD.inflation","USD.labour"])
        self.assertFalse(r["safe_to_publish_D"])
        self.assertFalse(r["writes_live_data"])
        for key in SLOTS:
            with self.subTest(key=key):
                entry=r["slots"][key]
                self.assertEqual(entry["prior_24_missing_periods"],["2025-10"])
                self.assertEqual(entry["economic_period_last_available"],"2026-09")
                self.assertEqual(entry["never_published_reference_period"],"2025-10")
                self.assertFalse(entry["oct_2025_observation_exists"])
                self.assertTrue(entry["strict_current_research_z_is_null"])
                self.assertTrue(entry["no_BLS_shutdown_month_imputation"])
                self.assertIn("bls.gov",entry["official_BLS_evidence"])

    def test_fake_october_2025_unemployment_is_never_treated_as_retrieved(self):
        src=copy.deepcopy(self.series)
        row=next(x for x in src["USD"] if x["id"]=="US_UNRATE_history_value")
        row["dates"].append("2025-10-01")
        row["values"].append(4.4)
        with self.assertRaisesRegex(ValueError,"fabricated original observation"):
            self.run_audit(series=src)

    def test_fake_october_2025_CPI_index_is_never_treated_as_retrieved(self):
        src=copy.deepcopy(self.series)
        row=next(x for x in src["USD"] if x["id"]=="US_CPIAUCSL_history_value")
        row["dates"].append("2025-10-01")
        row["values"].append(324.5)
        with self.assertRaisesRegex(ValueError,"fabricated original observation"):
            self.run_audit(series=src)

    def test_rejects_false_complete_z_and_source_definition_changes(self):
        obs=copy.deepcopy(self.observed)
        obs["inflation_labour"]["USD.labour"]["missing_prior_periods"]=[]
        with self.assertRaisesRegex(ValueError,"calendar reconstruction disagrees"):
            self.run_audit(observed=obs)
        obs=copy.deepcopy(self.observed)
        obs["inflation_labour"]["USD.inflation"]["research_robust_z"]=1.0
        with self.assertRaisesRegex(ValueError,"incorrectly scored"):
            self.run_audit(observed=obs)
        reg=copy.deepcopy(self.registry)
        reg["series"]["USD.labour"]["series_id"]="PAYEMS"
        with self.assertRaisesRegex(ValueError,"definition drift"):
            self.run_audit(registry=reg)

    def test_missing_month_not_equated_to_first_web_vintage_certification(self):
        r=self.run_audit()
        self.assertTrue(r["summary"]["first_web_release_count_is_not_same_as_consecutive_month_count"])
        self.assertTrue(r["no_historical_PIT_certification"])
        self.assertEqual(r["summary"]["model_z_scores_recovered"],0)


if __name__ == "__main__":
    unittest.main()
