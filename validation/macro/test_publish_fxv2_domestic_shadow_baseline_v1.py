"""Shadow V2 Formula publication: deterministic, adversarial, never Core signals."""
from __future__ import annotations
import copy
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    run as candidate_run,run_source_readiness
)
from validation.macro.publish_fxv2_domestic_shadow_baseline_v1 import build,publish

ROOT=Path(__file__).resolve().parents[2]
ASOF=date(2026,11,4)
class ShadowBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate=candidate_run(as_of=ASOF.isoformat())
        cls.readiness=run_source_readiness(as_of=ASOF.isoformat())
        cls.original=json.dumps({
            x:(ROOT/x).read_bytes().hex()[:96] for x in (
               "live_data/sections/D.json",
               "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
               "live_data/sections/OIS_OPERATIONAL_VIEW.json")
        },sort_keys=True)
    def test_reproducible_and_source_quality(self):
        x=build(self.candidate,self.readiness,ASOF)
        y=build(self.candidate,self.readiness,ASOF)
        self.assertEqual(x,y)
        self.assertEqual(x["schema"],"GMFQ_FXV2_MACRO_SHADOW_FORMULA_RESEARCH_V1")
        self.assertEqual(len(x["countries"]),8)
        self.assertEqual(x["summary"]["fx_directional_signals_generated"],0)
        self.assertFalse(x["eligible_for_fx_core"])
        self.assertFalse(x["eligible_for_forward"])
        self.assertFalse(x["eligible_for_backtests"])
        self.assertEqual(x["original_frozen_legacy_D_asof"],"2026-09-25")
        self.assertTrue(all(v["fx_policy_or_return_signal"] is None for v in x["countries"].values()))
        self.assertEqual(x["formula_version"],"v2_domestic_activity_2026_10_27_FIXED_50_50")
        with TemporaryDirectory() as td:
            path=Path(td)/"shadow.json"
            self.assertTrue(publish(x,path))
            original=path.read_bytes()
            self.assertFalse(publish(x,path),"unchanged economic sources must not synthetic-refresh")
            self.assertEqual(path.read_bytes(),original)
    def test_arithmetic_sensitivity_and_estimate_grade(self):
        x=build(self.candidate,self.readiness,ASOF)
        for c,row in x["countries"].items():
            self.assertAlmostEqual(row["activity_z_research"],
              (row["growth_z_research"]+row["labour_tightness_z_research"])*.5,9)
            self.assertEqual(row["official_first_publication_PIT_replay_complete"],False)
            self.assertEqual(set(row["hypothetical_independent_axis_z_revision_stability"]),{"10","25","50"})
            self.assertEqual(set(row["source_axes"]),{"growth","labour","inflation"})
        self.assertTrue(any(v["source_axes"][a]["is_estimate"] for v in x["countries"].values() for a in ("labour","inflation")))
    def test_adversarial_no_fake_rebase(self):
        for corrupt in [
           lambda d:d.update(safe_to_publish_D=True),
           lambda d:d.update(safe_to_update_pair_theses=True),
           lambda d:d["summary"].update(FX_scores_produced=1),
           lambda d:d["summary"].update(axes=23),
           lambda d:d["countries"]["EUR"].update(domestic_activity_candidate_z=2.9),
           lambda d:d["countries"]["CHF"]["source_quality_details"]["growth"].update(quality=None),
           lambda d:d["countries"]["GBP"]["continuous_weight_sensitivity_RESEARCH_ONLY"].update(growth_weight_interval_inclusive=[.5,.5]),
        ]:
            d=copy.deepcopy(self.candidate);corrupt(d)
            with self.subTest(corrupt=corrupt),self.assertRaises(ValueError):build(d,self.readiness,ASOF)
        r=copy.deepcopy(self.readiness)
        r["eligible_to_recompute_28_pairs"]=True
        with self.assertRaises(ValueError):build(self.candidate,r,ASOF)
        with self.assertRaises(ValueError):build(self.candidate,self.readiness,date(2026,10,1))
    @classmethod
    def tearDownClass(cls):
        current=json.dumps({
            x:(ROOT/x).read_bytes().hex()[:96] for x in (
               "live_data/sections/D.json",
               "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
               "live_data/sections/OIS_OPERATIONAL_VIEW.json")
        },sort_keys=True)
        assert current==cls.original,"canonical macro/rates/FX files modified"
if __name__=="__main__":
    unittest.main()
