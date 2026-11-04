"""Adversarial V2 shadow research publication, including blocked strict GDP/CPI/UR axes."""
from __future__ import annotations
import copy
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from validation.macro.v2_domestic_candidate_explicit_formula_v1 import run_source_readiness
from validation.macro.v2_g8_observed_feature_bridge_v1 import run as observed_run
from validation.macro.publish_fxv2_domestic_shadow_baseline_v1 import (
    partial_from_strict_source,run,publish
)

ROOT=Path(__file__).resolve().parents[2]
ASOF=date(2026,11,4)
CORE=("live_data/sections/D.json",
      "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
      "live_data/sections/OIS_OPERATIONAL_VIEW.json")

class ShadowBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observed=observed_run(as_of=ASOF.isoformat())
        cls.readiness=run_source_readiness(as_of=ASOF.isoformat())
        cls.original={path:(ROOT/path).read_bytes() for path in CORE}
    def test_partial_strict_source_coverage_does_not_invent_z(self):
        x=run(ASOF)
        y=run(ASOF)
        self.assertEqual(x,y)
        self.assertEqual(x["schema"],"GMFQ_FXV2_MACRO_SHADOW_FORMULA_RESEARCH_V1")
        self.assertEqual(x["status"],"PARTIAL_SHADOW_SOURCE_GAPS_RESEARCH_ONLY")
        self.assertEqual(len(x["countries"]),8)
        self.assertGreater(x["summary"]["countries_blocked_activity"],0)
        self.assertLess(x["summary"]["countries_with_calculable_activity"],8)
        self.assertEqual(x["summary"]["fx_directional_signals_generated"],0)
        self.assertFalse(x["eligible_for_fx_core"])
        self.assertFalse(x["eligible_for_forward"])
        self.assertFalse(x["eligible_for_backtests"])
        self.assertEqual(x["original_frozen_legacy_D_asof"],"2026-09-25")
        self.assertEqual(x["formula_version"],"v2_domestic_activity_2026_10_27_FIXED_50_50")
        self.assertTrue(all(v["fx_policy_or_return_signal"] is None for v in x["countries"].values()))
        self.assertTrue(any(v["activity_z_research"] is None for v in x["countries"].values()))
        with TemporaryDirectory() as tmp:
            target=Path(tmp)/"macro.json"
            self.assertTrue(publish(x,target))
            raw=target.read_bytes()
            self.assertFalse(publish(x,target),"No synthetic source-timestamp refresh")
            self.assertEqual(target.read_bytes(),raw)
    def test_available_activity_always_equals_registered_50_50(self):
        x=partial_from_strict_source(self.observed,self.readiness,ASOF)
        for c,v in x["countries"].items():
            axes=v["source_axes"]
            self.assertEqual(set(axes),{"growth","labour","inflation"})
            self.assertFalse(v["official_first_publication_PIT_replay_complete"])
            self.assertTrue(all(d["is_estimate"] is False for d in axes.values()))
            if v["activity_z_research"] is not None:
                self.assertAlmostEqual(v["activity_z_research"],
                   (v["growth_z_research"]+v["labour_tightness_z_research"])*.5,9)
                self.assertIn(v["stable_for_continuous_growth_weight_25_to_75_pct"],(True,False))
                self.assertEqual(set(v["hypothetical_independent_axis_z_revision_stability"]),{"10","25","50"})
            else:
                self.assertTrue(v["growth_z_research"] is None or v["labour_tightness_z_research"] is None)
                self.assertIsNone(v["stable_for_continuous_growth_weight_25_to_75_pct"])
                self.assertIsNone(v["hypothetical_independent_axis_z_revision_stability"])
    def test_adversarial_core_provenance_and_source_status(self):
        for change in [
           lambda d:d.update(safe_to_publish_new_D=True),
           lambda d:d.update(safe_to_update_pair_theses=True),
           lambda d:d["inflation_labour"]["CAD.labour"].update(research_robust_z=float("nan")),
           lambda d:d["inflation_labour"]["USD.inflation"].update(eligible_for_macro_score=True),
           lambda d:d["growth_quarterly_gdp_initial_web_research_features"]["EUR"].update(currency="GBP"),
        ]:
            corrupt=copy.deepcopy(self.observed);change(corrupt)
            with self.subTest(change=change),self.assertRaises(ValueError):
                partial_from_strict_source(corrupt,self.readiness,ASOF)
        r=copy.deepcopy(self.readiness)
        r["eligible_to_recompute_28_pairs"]=True
        with self.assertRaises(ValueError):
            partial_from_strict_source(self.observed,r,ASOF)
    @classmethod
    def tearDownClass(cls):
        assert all((ROOT/path).read_bytes()==raw for path,raw in cls.original.items()),\
            "Core D / 28 pairs / OIS must remain unchanged"

if __name__=="__main__":
    unittest.main()
