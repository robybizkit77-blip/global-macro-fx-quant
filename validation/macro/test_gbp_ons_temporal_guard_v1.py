"""GBP MGSX period semantics and canonical first-vintage quarantine tests."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import date

from validation.macro.gbp_ons_temporal_guard_v1 import ROOT, CONTRACT, SERIES, HEAT, build
from validation.sources.gbp_ons_core import uk_lfs_rolling_window

NOW = date(2026, 10, 20)


class GBPTemporalGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = {
            "contract":json.loads((ROOT / CONTRACT).read_text()),
            "series":json.loads((ROOT / SERIES).read_text()),
            "heat":json.loads((ROOT / HEAT).read_text()),
        }

    def run_guard(self, mutate=None):
        data=copy.deepcopy(self.original)
        if mutate:
            mutate(data)
        return build(asof=NOW,**data)

    def test_current_canonical_data_quarantined_not_relabelled(self):
        r=self.run_guard()
        self.assertEqual(r["status"], "HOLD_UNTIL_EXPLICIT_PERIOD_VINTAGE_REPAIR")
        self.assertFalse(r["safe_to_persist_gbp_labour"])
        self.assertFalse(r["historical_rebase_approved"])
        self.assertFalse(r["structural_fx_label_rebase_approved"])
        self.assertEqual(r["official_periods_checked"], 3)
        self.assertEqual(r["canonical_source_latest_period"], "2026-07")
        self.assertEqual(len(r["issues"]), 2)
        self.assertIn("VINTAGE_OR_PERIOD_VALUE_MISMATCH", {x["action"] for x in r["issues"]})
        self.assertIn("MISSING_FIRST_RELEASE_WINDOW", {x["action"] for x in r["issues"]})

    def test_complete_repaired_july_and_august_source_allows_only_refresh(self):
        def repaired(d):
            x=next(x for x in d["series"]["GBP"] if x["id"]=="UK_UNEMP_RATE_history_value")
            self.assertEqual(x["dates"][-1][:7],"2026-07")
            x["values"][-1]=4.9
            x["dates"].append("2026-08-01")
            x["values"].append(4.7)
            x["last_date"]="2026-08-01"
            x["last_value"]=4.7
            d["heat"]["currencies"]["GBP"]["labour"]["as_of"]="2026-08-01"
        r=self.run_guard(repaired)
        self.assertEqual(r["status"],"ALLOW_GBP_LABOUR_SOURCE_REFRESH")
        self.assertTrue(r["safe_to_persist_gbp_labour"])
        self.assertFalse(r["historical_rebase_approved"])
        self.assertEqual(r["issues"],[])

    def test_ons_jul_center_is_not_jul_end(self):
        value=uk_lfs_rolling_window("2026-07-01")
        self.assertEqual(value["window_start_month"],"2026-06-01")
        self.assertEqual(value["window_end_month"],"2026-08-01")
        self.assertEqual(value["ons_period_label"],"JUN-AUG 2026")

    def test_ons_december_center_cross_year_window(self):
        self.assertEqual(uk_lfs_rolling_window("2026-12-01")["window_end_month"],"2027-01-01")
        self.assertEqual(uk_lfs_rolling_window("2026-01-01")["window_start_month"],"2025-12-01")

    def test_quarantine_if_official_lfs_july_window_relabelled(self):
        def mutate(d):
            d["contract"]["official_periods"][1]["source_center_month"]="2026-07"
        with self.assertRaisesRegex(ValueError,"translation drift"):
            self.run_guard(mutate)

    def test_quarantine_if_pinned_first_release_value_forged(self):
        def mutate(d):
            d["contract"]["official_periods"][1]["unemployment_pct"]=4.7
        with self.assertRaisesRegex(ValueError,"period/value official anchor changed"):
            self.run_guard(mutate)

    def test_quarantine_if_untrusted_ons_domain(self):
        def mutate(d):
            d["contract"]["official_periods"][1]["source_url"]="https://ons.gov.uk.malicious.invalid/latest"
        with self.assertRaisesRegex(ValueError,"official domain missing"):
            self.run_guard(mutate)

    def test_quarantine_if_fake_future_release(self):
        def mutate(d):
            d["contract"]["official_periods"][1]["release_date"]="2027-01-11"
        with self.assertRaisesRegex(ValueError,"future/early first release"):
            self.run_guard(mutate)

    def test_quarantine_if_history_and_thermometer_disagree(self):
        def mutate(d):
            d["heat"]["currencies"]["GBP"]["labour"]["as_of"]="2026-06-01"
        r=self.run_guard(mutate)
        self.assertFalse(r["safe_to_persist_gbp_labour"])
        self.assertIn("HEATMAP_OBSERVATION_PERIOD_MISMATCH",{x["action"] for x in r["issues"]})

    def test_quarantine_if_duplicate_observation_month(self):
        def mutate(d):
            x=next(x for x in d["series"]["GBP"] if x["id"]=="UK_UNEMP_RATE_history_value")
            x["dates"][-1]=x["dates"][-2]
        with self.assertRaisesRegex(ValueError,"duplicate/unsorted"):
            self.run_guard(mutate)


if __name__=="__main__":
    unittest.main()
