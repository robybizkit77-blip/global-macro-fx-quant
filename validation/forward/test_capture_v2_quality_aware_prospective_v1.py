"""Prospective-only V2 quality-aware contract tests, synthetic clocks never persisted."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone, time
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from validation.forward import capture_v2_quality_aware_prospective_v1 as qa
from validation.forward.test_capture_v2_research_prospective_evidence_v1 import (
    V2ProspectiveResearchCapture as LegacyFixture
)
from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    run as observed_run,
)
from validation.macro.v2_zero_mad_ordinal_quality_v1 import (
    build as ordinal_build, SOURCE as SERIES, REGISTRY
)


class QualityAwareProspectiveCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This is a synthetic future clock solely for pure-code testing.
        # There is NO V2 quality journal written by this fixture.
        LegacyFixture.setUpClass()
        cls.day = "2026-11-02"
        cls.cut = datetime.fromisoformat("2026-11-02T19:31:00+01:00")
        cls.now = cls.cut + timedelta(seconds=7)
        cls.fx = copy.deepcopy(LegacyFixture.fx)
        original = [r for r in cls.fx["rows"] if r["Date"] < cls.day]
        if not original:
            raise AssertionError("no original ECB history before synthetic 2026-11-02")
        source = copy.deepcopy(original[-1])
        source["Date"] = cls.day
        cls.fx["rows"] = original + [source]
        cls.fx["last_as_of"] = cls.day
        cls.fx["row_count"] = len(cls.fx["rows"])
        cls.pair = copy.deepcopy(LegacyFixture.pairs)
        cls.pair["price_asof"] = cls.day
        for key in ("as_of","overlay_asof","history_asof"):
            cls.pair["price_audit"][key] = cls.day
        cls.core = copy.deepcopy(LegacyFixture.legacy)
        cls.observed = observed_run(as_of=cls.day)
        series = json.loads(SERIES.read_text(encoding="utf-8"))
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.ordinal = ordinal_build(
            cls.observed,series,registry,today=cls.cut.date()
        )
        cls.hashes = {k:"a"*64 for k in qa.SOURCE_PATHS}

    def make(self, **kwargs):
        inputs={
            "fx":copy.deepcopy(self.fx),
            "pair_setup":copy.deepcopy(self.pair),
            "core":copy.deepcopy(self.core),
            "observed":copy.deepcopy(self.observed),
            "ordinal":copy.deepcopy(self.ordinal),
            "hashes":copy.deepcopy(self.hashes),
        }
        inputs.update(kwargs)
        return qa.make(self.cut,self.now,**inputs)

    def test_g8_24_economic_slots_28_genuine_reference_shapes_and_no_H1(self):
        snap=self.make()
        self.assertEqual(snap["schema"],qa.SCHEMA)
        self.assertEqual(snap["local_date_rome"],"2026-11-02")
        self.assertEqual(len(snap["observed_t0_ref"]),28)
        self.assertEqual(len(snap["economic_observations"]),8)
        self.assertEqual(
            sum(len([c["inflation"],c["labour"],c["growth"]])
                for c in snap["economic_observations"].values()),24)
        self.assertEqual(snap["zero_mad_source_count"],
                         len(self.ordinal["zero_mad_components"]))
        self.assertEqual(snap["strict_robust_z_missing_count"],
                         sum(v["research_robust_z"] is None
                             for v in self.observed["inflation_labour"].values()))
        self.assertFalse(snap["can_feed_preregistered_H1"])
        self.assertFalse(snap["V2_numeric_model_computed"])
        self.assertFalse(snap["historical_issuer_PIT_certified"])
        self.assertFalse(snap["eligible_for_beta_forward_trading"])
        self.assertEqual(snap["numeric_z_imputation_count"],0)
        self.assertEqual(qa.validate_snapshot(snap),"2026-11-02")
        if "EUR.labour" in self.ordinal["zero_mad_components"]:
            euro=snap["economic_observations"]["EUR"]
            self.assertIsNone(euro["labour"]["research_robust_z"])
            self.assertEqual(euro["zero_mad_context"]["labour"][
                "ordinal_relation"],"ABOVE_ALL_PRIOR")
            self.assertIsNone(euro["zero_mad_context"]["labour"][
                "numeric_replacement_z"])

    def test_frozen_snapshot_no_future_outcomes_and_no_price_execution(self):
        snap=self.make()
        self.assertTrue(all(p["trade_execution_price"] is False
                            for p in snap["observed_t0_ref"].values()))
        self.assertTrue(all(c["trade_entry"] is None and c["FX_signal"] is None
                            for c in snap["economic_observations"].values()))
        bad=copy.deepcopy(snap)
        bad["can_feed_preregistered_H1"]=True
        bad["snapshot_sha256"]=qa.sha({k:v for k,v in bad.items()
                                      if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,"research-only"):
            qa.validate_snapshot(bad)

    def test_no_backfill_before_nov2_wrong_times_and_blocked_pricing(self):
        for cut in (datetime.fromisoformat("2026-10-30T19:31:00+01:00"),
                    datetime.fromisoformat("2026-10-31T20:31:00+01:00"),
                    datetime.fromisoformat("2026-11-01T20:31:00+01:00"),
                    datetime.fromisoformat("2026-11-02T18:31:00+01:00")):
            with self.subTest(cut=cut),self.assertRaises(ValueError):
                qa.make(cut,cut+timedelta(seconds=3),
                        fx=self.fx,pair_setup=self.pair,core=self.core,
                        observed=self.observed,ordinal=self.ordinal,
                        hashes=self.hashes)
        stale=copy.deepcopy(self.fx)
        stale["last_as_of"]="2026-10-30"
        with self.assertRaisesRegex(ValueError,"official same-day"):
            self.make(fx=stale)
        corrupted=copy.deepcopy(self.pair)
        corrupted["price_audit"]["returns_complete"]=False
        with self.assertRaisesRegex(ValueError,"official same-day"):
            self.make(pair_setup=corrupted)

    def test_ordinal_quality_source_mismatch_missing_slot_and_fake_numeric_score(self):
        altered=copy.deepcopy(self.ordinal)
        altered["can_feed_preregistered_H1"]=True
        with self.assertRaisesRegex(ValueError,"ordinal"):
            self.make(ordinal=altered)
        altered=copy.deepcopy(self.ordinal)
        altered["zero_mad_components"]={}
        altered["zero_mad_component_count"]=0
        with self.assertRaisesRegex(ValueError,"completeness"):
            self.make(ordinal=altered)
        observed=copy.deepcopy(self.observed)
        observed["inflation_labour"].pop("EUR.labour")
        with self.assertRaisesRegex(ValueError,"completeness"):
            self.make(observed=observed)
        row=self.make()
        bad=copy.deepcopy(row)
        bad["economic_observations"]["EUR"]["labour"][
            "eligible_for_macro_score"]=True
        bad["snapshot_sha256"]=qa.sha({k:v for k,v in bad.items()
                                      if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,"promoted"):
            qa.validate_snapshot(bad)

    def test_append_only_no_overwrites_no_tamper_and_real_journals_untouched(self):
        protect=[
            qa.ROOT/"live_data/sections/D.json",
            qa.ROOT/"live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
            qa.ROOT/"validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl",
            qa.ROOT/"validation/forward/candidate_shadow_snapshots/V2_MACRO_EVIDENCE_SNAPSHOTS_V1.jsonl",
        ]
        before={str(p):p.read_bytes() for p in protect}
        snap=self.make()
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"qa.jsonl"
            self.assertEqual(qa.append(snap,path=target,dry_run=True),
                             "VALID_QUALITY_AWARE_PROSPECTIVE_DRY_RUN_NO_WRITE")
            self.assertFalse(target.exists())
            self.assertEqual(qa.append(snap,path=target),
                             "QUALITY_AWARE_PROSPECTIVE_SNAPSHOT_APPEND_OK")
            original=target.read_bytes()
            self.assertEqual(qa.append(snap,path=target),
                             "EXISTING_QUALITY_AWARE_DATE_FROZEN_NO_OVERWRITE")
            self.assertEqual(target.read_bytes(),original)
            with self.assertRaisesRegex(ValueError,"integrity"):
                qa.append({**snap,"local_date_rome":"2026-11-03"},path=target)
            duplicate=json.loads(original)
            with target.open("ab") as out:
                out.write(qa.canonical(duplicate))
            with self.assertRaisesRegex(ValueError,"duplicate"):
                qa.append(snap,path=target)
        self.assertEqual(before,{str(p):p.read_bytes() for p in protect})

    def test_cli_cannot_write_future_snapshot_today(self):
        today=datetime.now(ZoneInfo("Europe/Rome"))
        # Only enforce the early-date test on current 2026-10-30 CI window.
        if today.date().isoformat() <= "2026-11-01":
            with self.assertRaisesRegex(ValueError,"first legitimate"):
                qa.attempt(cutoff=today,now=today)
        self.assertTrue(qa.NO_HISTORICAL_BACKFILL)
        self.assertFalse(qa.JOURNAL.exists())


if __name__=="__main__":
    unittest.main()
