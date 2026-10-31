"""Fail-closed tests for exact seven-calendar-day 2Y / ECB FX context."""
import copy
import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from validation.macro.v2_fx_exact_weekly_2y_ecb_context_v1 import build, DATA

FILES = ["NATIVE_RATES_DATA.json", "ECB_G8_PRICE_HISTORY.json",
         "PAIR_SETUP_OPERATIONAL_VIEW.json", "D.json"]


class WeeklyReferenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads((Path(__file__).parent / "fixtures" /
            "v2_exact_weekly_2y_ecb_oct31_vintage_snapshot_v1.json").read_text())
        cls.inputs = [fixture["rates"], fixture["fx"], fixture["setup"], fixture["core"]]
        cls.source_shas = fixture["sources"]

    def report(self, values=None, audit_day="2026-10-31"):
        return build(*(values or copy.deepcopy(self.inputs)), audit_day=audit_day)

    def test_current_source_exact_window_not_trading_signal(self):
        r = self.report()
        self.assertEqual(r["observation_window"], ["2026-10-22", "2026-10-29"])
        self.assertEqual(r["eligible_currency_codes"], ["USD", "EUR", "GBP", "JPY", "CAD"])
        self.assertEqual(r["summary"]["pairs"], 28)
        self.assertEqual(r["summary"]["eligible_pairs"], 10)
        self.assertEqual(r["summary"]["excluded_pairs"], 18)
        self.assertEqual(r["summary"]["FX_signals"], 0)
        self.assertEqual(r["summary"]["Core_rebased"], 0)
        self.assertEqual(r["original_macro_baseline_as_of"], "2026-09-25")
        self.assertTrue(r["source_vintage_is_as_retrieved_not_historic_PIT"])
        self.assertTrue(r["ECB_reference_is_not_executable_price_or_intraday_reaction"])
        self.assertTrue(r["sovereign_2Y_instrument_conventions_not_identical"])
        self.assertEqual(sum(v["status"] == "EXACT_DATE_MATCH_DESCRIPTIVE_ONLY"
                             for v in r["pair_observations"].values()), 10)
        a = r["pair_observations"]["EURUSD"]
        self.assertEqual(a["interval"], ["2026-10-22", "2026-10-29"])
        self.assertAlmostEqual(a["relative_2Y_change_bp"], 4.050612, delta=0.00015)
        self.assertTrue(a["fx_reference_change_pct"] < 0)
        self.assertEqual(r["pair_observations"]["AUDCAD"]["relative_2Y_change_bp"], None)
        self.assertEqual(r["pair_observations"]["CHFJPY"]["fx_reference_change_pct"], None)

    def test_reciprocal_orientation_is_algebraically_correct(self):
        data = copy.deepcopy(self.inputs)
        pairs = data[2]["pairs"]
        x = pairs.pop("EURUSD")
        x["canonical_pair"] = "USD/EUR"
        pairs["USDEUR"] = x
        r = self.report(data)
        fx = r["pair_observations"]["USDEUR"]
        self.assertAlmostEqual(fx["relative_2Y_change_bp"],
                               -self.report()["pair_observations"]["EURUSD"]["relative_2Y_change_bp"], 5)
        return_pct = self.report()["pair_observations"]["EURUSD"]["fx_reference_change_pct"]
        self.assertAlmostEqual((1 + fx["fx_reference_change_pct"] / 100) *
                               (1 + return_pct / 100), 1, delta=2e-8)

    def test_incomplete_rate_date_does_not_synthesize_2y(self):
        r, fx, s, d = copy.deepcopy(self.inputs)
        for i,day in enumerate(r["USD"]["history2"]["dates"]):
            if day == "2026-10-22":
                r["USD"]["history2"]["dates"].pop(i)
                r["USD"]["history2"]["values"].pop(i)
                break
        out = self.report([r, fx, s, d])
        self.assertNotIn("USD", out["eligible_currency_codes"])
        self.assertEqual(out["summary"]["eligible_pairs"], 6)

    def test_mismatched_core_baseline_fails(self):
        a = copy.deepcopy(self.inputs)
        a[2]["macro_baseline_asof"] = "2026-10-30"
        with self.assertRaisesRegex(ValueError, "baseline dates mismatch"):
            self.report(a)

    def test_duplicate_ecb_fixing_day_fails(self):
        a = copy.deepcopy(self.inputs)
        a[1]["rows"].insert(-1, copy.deepcopy(a[1]["rows"][0]))
        a[1]["row_count"] += 1
        with self.assertRaisesRegex(ValueError, "duplicate ECB"):
            self.report(a)

    def test_missing_28pair_and_fake_fx_value_fails(self):
        a = copy.deepcopy(self.inputs)
        a[2]["pairs"].pop("EURUSD")
        a[2]["pair_count"] = 27
        with self.assertRaisesRegex(ValueError, "28 canonical pairs"):
            self.report(a)
        a = copy.deepcopy(self.inputs)
        for row in a[1]["rows"]:
            if row["Date"] == "2026-10-29":
                row["USD"] = -1
                break
        with self.assertRaisesRegex(ValueError, "invalid ECB"):
            self.report(a)

    def test_future_source_and_cutoff_fails(self):
        a = copy.deepcopy(self.inputs)
        a[0]["USD"]["date"] = "2026-11-01"
        with self.assertRaisesRegex(ValueError, "after research cutoff"):
            self.report(a)
        with self.assertRaisesRegex(ValueError, "latest official FX evidence"):
            self.report(audit_day="2026-10-28")

    def test_live_source_contract_is_also_available_without_frozen_date_assumption(self):
        today = datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        live = [json.loads((DATA / f).read_text()) for f in FILES]
        current = build(*live, audit_day=today)
        self.assertEqual(current["summary"]["pairs"], 28)
        self.assertEqual(current["summary"]["eligible_pairs"] +
                         current["summary"]["excluded_pairs"], 28)
        self.assertEqual(current["summary"]["FX_signals"], 0)
        self.assertTrue(current["no_D_or_pair_updates"])

    def test_source_fixture_provenance_is_explicit_not_pit(self):
        self.assertEqual(set(self.source_shas), set(FILES))
        self.assertTrue(all(len(sha) == 40 for sha in self.source_shas.values()))
        sample = self.report()
        self.assertTrue(sample["source_vintage_is_as_retrieved_not_historic_PIT"])

    def test_corrupted_2y_value_or_date_fails(self):
        a = copy.deepcopy(self.inputs)
        a[0]["USD"]["history2"]["last_value"] += 0.01
        with self.assertRaisesRegex(ValueError, "2Y last point metadata mismatch"):
            self.report(a)
        a = copy.deepcopy(self.inputs)
        a[0]["JPY"]["history2"]["dates"][1] = a[0]["JPY"]["history2"]["dates"][0]
        with self.assertRaisesRegex(ValueError, "duplicate history date"):
            self.report(a)


if __name__ == "__main__":
    unittest.main()
