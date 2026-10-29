"""Frozen Macro D vs daily thermometer bridge must be explicit, fail closed."""
import copy
import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from pathlib import Path
from validation.macro.check_core_daily_bridge_readiness_v1 import (
    ROOT, G8, audit, run,
)

ROOTS=ROOT/"live_data"/"sections"
def load(name):
    return json.loads((ROOTS/(name+".json")).read_text(encoding="utf-8"))

class CoreBridgeReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core=load("D")
        cls.heat=load("MACRO_THERMOMETER_DATA")
        cls.series=load("MACRO_SERIES")
        cls.pairs=load("PAIR_SETUP_OPERATIONAL_VIEW")

    def check(self,core=None,heat=None,series=None,pairs=None,when="2026-10-27"):
        return audit(core if core is not None else self.core,
                     heat if heat is not None else self.heat,
                     series if series is not None else self.series,
                     pairs if pairs is not None else self.pairs,when)

    def test_real_october_core_gap_and_28_pair_alignment(self):
        r=self.check()
        self.assertEqual(r["status"],"BLOCKED_UNCERTIFIED_CORE_RECALIBRATION")
        self.assertEqual(r["core_as_of"],"2026-09-25")
        self.assertEqual(r["core_age_calendar_days"],32)
        self.assertEqual(r["pair_price_as_of"],"2026-10-26")
        self.assertEqual(r["pair_macro_baseline_as_of"],"2026-09-25")
        self.assertTrue(r["pair_macro_baseline_matches_core"])
        self.assertFalse(r["core_matches_pair_price_day"])
        self.assertEqual(set(r["currency_source_coverage"]),set(G8))
        for c in G8:
            self.assertEqual(set(r["currency_source_coverage"][c]),{"inflation","labour"})
            for dim in ("inflation","labour"):
                source=r["currency_source_coverage"][c][dim]
                self.assertEqual(source["series_id"],
                                 self.heat["currencies"][c][dim]["series_id"])
                self.assertFalse(source["approved_as_core_weight"])

    def test_no_automatic_score_or_pair_promotion_even_if_date_manually_edited(self):
        r=self.check()
        for key in ("daily_core_scoring_and_rank_rebuild_certified",
                    "eligible_to_promote_new_macro_scores",
                    "eligible_to_republish_28_pair_thesis",
                    "historical_gdp_research_is_eligible_for_live_model",
                    "core_growth_dimension_rebuilt_by_daily_macro_pipeline"):
            self.assertIs(r[key],False)
        fake_core=copy.deepcopy(self.core);fake_core["asOf"]="2026-10-27"
        fake_pair=copy.deepcopy(self.pairs)
        fake_pair["macro_baseline_asof"]="2026-10-27"
        q=self.check(core=fake_core,pairs=fake_pair)
        self.assertTrue(q["core_same_day_as_check"])
        self.assertFalse(q["eligible_to_promote_new_macro_scores"])
        self.assertEqual(q["status"],"BLOCKED_UNCERTIFIED_CORE_RECALIBRATION")

    def test_all_24_frozen_scores_and_cycles_are_immutable_without_rebase(self):
        receipt=self.check()
        self.assertTrue(receipt["frozen_24_scores_and_8_cycles_match_historical_source"])
        self.assertTrue(receipt["historical_score_match_does_not_certify_freshness"])
        for c in G8:
            for key in ("growth", "labour", "inflation", "cycle"):
                core=copy.deepcopy(self.core)
                core["macro"][c][key] = (
                    "GOLDILOCKS" if core["macro"][c][key] != "GOLDILOCKS"
                    else "STAGFLATION"
                ) if key == "cycle" else core["macro"][c][key] + 0.001
                with self.subTest(ccy=c, pillar=key):
                    with self.assertRaisesRegex(
                        ValueError, "FROZEN_CORE_MACRO_SCORE_VECTOR_CHANGED"
                    ):
                        self.check(core=core)

    def test_rome_local_date_drives_automatic_daily_audit(self):
        # UTC is still the previous day at 00:10 in Rome: no UTC date drift.
        rome_midnight=datetime(2026, 10, 30, 0, 10,
                               tzinfo=ZoneInfo("Europe/Rome"))
        with patch("validation.macro.check_core_daily_bridge_readiness_v1.datetime") as clock:
            clock.now.return_value=rome_midnight
            receipt=run()
        self.assertEqual(receipt["checked_as_of"], "2026-10-30")
        self.assertEqual(receipt["core_age_calendar_days"], 35)
        self.assertFalse(receipt["eligible_to_promote_new_macro_scores"])

    def test_changed_macro_baseline_is_not_silently_reconciled(self):
        x=copy.deepcopy(self.pairs);x["macro_baseline_asof"]="2026-10-15"
        r=self.check(pairs=x)
        self.assertEqual(r["status"],"BROKEN_PAIR_MACRO_BASELINE_CONTRACT")
        self.assertIs(r["pair_macro_baseline_matches_core"],False)
        self.assertFalse(r["eligible_to_republish_28_pair_thesis"])

    def test_reject_future_publication_observations_and_corrupted_inputs(self):
        core=copy.deepcopy(self.core);core["asOf"]="2026-10-28"
        with self.assertRaises(ValueError):self.check(core=core)
        h=copy.deepcopy(self.heat)
        h["currencies"]["NZD"]["inflation"]["as_of"]="2026-11"
        with self.assertRaises(ValueError):self.check(heat=h)
        h["currencies"]["NZD"]["inflation"]["as_of"]="2026-13"
        with self.assertRaises(ValueError):self.check(heat=h)
        p=copy.deepcopy(self.pairs);p["price_audit"]["status"]="FAIL"
        with self.assertRaises(ValueError):self.check(pairs=p)
        p=copy.deepcopy(self.pairs);p["price_asof"]="2026-10-28"
        with self.assertRaises(ValueError):self.check(pairs=p)
        s=copy.deepcopy(self.series);s.pop("EUR")
        with self.assertRaises(ValueError):self.check(series=s)

    def test_official_month_as_of_is_observation_not_unverified_release_time(self):
        r=self.check()
        self.assertTrue(r["source_observation_as_of_is_not_release_timestamp"])
        self.assertTrue(r["all_observation_dates_not_future"])
        self.assertEqual(r["currency_source_coverage"]["NZD"]["labour"]["observation_as_of"],
                         self.heat["currencies"]["NZD"]["labour"]["as_of"])
        self.assertEqual(r["currency_source_coverage"]["AUD"]["inflation"]["observation_frequency"],"Q")
        self.assertTrue(r["audit_only_no_data_written"])

    def test_read_only_run_and_source_refresh_separation(self):
        files=("D","MACRO_THERMOMETER_DATA","MACRO_SERIES","PAIR_SETUP_OPERATIONAL_VIEW")
        before={k:(ROOTS/(k+".json")).read_bytes() for k in files}
        r=run(as_of="2026-10-27")
        after={k:(ROOTS/(k+".json")).read_bytes() for k in files}
        self.assertEqual(before,after)
        self.assertFalse(r["daily_core_scoring_and_rank_rebuild_certified"])
        wf=(ROOT/".github/workflows/macro-persistent-daily-v1.yml").read_text(encoding="utf-8")
        self.assertIn("'live_data/sections/MACRO_SERIES.json'",wf)
        self.assertIn("'live_data/sections/MACRO_THERMOMETER_DATA.json'",wf)
        # The daily source pipeline does not authorize writing D.
        self.assertNotIn("git add -- live_data/sections/D.json",wf)
        self.assertNotIn("--section D",wf)
        gdp=(ROOT/"validation/macro/v2_g8_gdp_unified_web_research_v1.py").read_text(encoding="utf-8")
        self.assertIn('"safe_to_update_live_macro_D":False',gdp)

if __name__=="__main__":unittest.main()
