"""Prospective-only V2 quality-aware contract tests, synthetic clocks never persisted."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone, time, date
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
        # Choose a synthetic weekday on/after both the registered first day
        # and the actual test clock. This still cannot write a real snapshot.
        day=max(date(2026,11,2),datetime.now(ZoneInfo("Europe/Rome")).date())
        while day.weekday()>=5:
            day+=timedelta(days=1)
        cls.day=day.isoformat()
        cls.cut=datetime.combine(day,time(19,31),
                                 tzinfo=ZoneInfo("Europe/Rome"))
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
        cls.rates = copy.deepcopy(LegacyFixture.rates)
        cls.ois = copy.deepcopy(LegacyFixture.ois)
        cls.banks = copy.deepcopy(LegacyFixture.cb)
        cls.nzd_proxy = json.loads((qa.ROOT/qa.SOURCE_PATHS["nzd_proxy"]).read_text())
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
            "rates":copy.deepcopy(self.rates),
            "ois":copy.deepcopy(self.ois),
            "banks":copy.deepcopy(self.banks),
            "nzd_proxy":copy.deepcopy(self.nzd_proxy),
            "hashes":copy.deepcopy(self.hashes),
        }
        inputs.update(kwargs)
        return qa.make(self.cut,self.now,**inputs)

    def test_g8_24_economic_slots_28_genuine_reference_shapes_and_no_H1(self):
        snap=self.make()
        self.assertEqual(snap["schema"],qa.SCHEMA)
        self.assertEqual(snap["local_date_rome"],self.day)
        self.assertEqual(len(snap["observed_t0_ref"]),28)
        self.assertEqual(len(snap["economic_observations"]),8)
        self.assertEqual(len(snap["market_context"]["countries"]),8)
        self.assertEqual(len(snap["market_context"]["pairs"]),28)
        self.assertEqual(snap["market_context"]["summary"]["FX_scores"],0)
        self.assertTrue(snap["market_context"]["no_2y_yield_spread_as_trading_signal"])
        self.assertEqual(snap["market_context"]["summary"]["official_6m"],4)
        self.assertEqual(snap["market_context"]["summary"]["estimated_or_proxy_6m"],4)
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
        self.assertEqual(qa.validate_snapshot(snap),self.day)
        if "EUR.labour" in self.ordinal["zero_mad_components"]:
            euro=snap["economic_observations"]["EUR"]
            self.assertIsNone(euro["labour"]["research_robust_z"])
            self.assertEqual(euro["zero_mad_context"]["labour"][
                "ordinal_relation"],self.ordinal["zero_mad_components"][
                    "EUR.labour"]["ordinal_relation"])
            self.assertIsNone(euro["zero_mad_context"]["labour"][
                "numeric_replacement_z"])

    def test_resigned_noncomparable_6m_or_unmatched_2y_cannot_become_fx_signal(self):
        valid=self.make()
        original=valid["market_context"]
        self.assertEqual(original["summary"]["estimated_or_proxy_6m"],4)
        self.assertEqual(original["countries"]["NZD"]["six_month_source_tier"],
                         "NZD_BANK_BILL_BASIS_PROXY_NOT_OIS")
        for c in ("NZD","CHF","EUR","USD"):
            self.assertFalse(original["countries"][c]["six_month_is_official_ois_only"])
        for pair,info in original["pairs"].items():
            self.assertIsNone(info["6m_cross_market_policy_spread_bp"])
            self.assertIsNone(info["FX_signal"])
            if not info["2y_same_official_observation_day"]:
                self.assertIsNone(info["2y_sovereign_spread_bp_DESCRIPTIVE_ONLY"])
        forged=copy.deepcopy(valid)
        forged["market_context"]["countries"]["NZD"]["six_month_is_official_ois_only"]=True
        forged["market_context_sha256"]=qa.sha(forged["market_context"])
        forged["snapshot_sha256"]=qa.sha({k:v for k,v in forged.items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError, "false official"):
            qa.validate_snapshot(forged)
        forged=copy.deepcopy(valid)
        pair=next(k for k,v in forged["market_context"]["pairs"].items()
                  if not v["2y_same_official_observation_day"])
        forged["market_context"]["pairs"][pair]["2y_sovereign_spread_bp_DESCRIPTIVE_ONLY"]=12.5
        forged["market_context_sha256"]=qa.sha(forged["market_context"])
        forged["snapshot_sha256"]=qa.sha({k:v for k,v in forged.items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError, "mismatched-date"):
            qa.validate_snapshot(forged)

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

    def test_resigned_nontriangular_ecb_cross_is_rejected(self):
        original=self.make()
        forged=copy.deepcopy(original)
        # Choose a cross not involving the EUR reference legs, because an
        # independent non-EUR cross has to equal the quotient of two EUR legs.
        pair=next(p for p in forged["observed_t0_ref"]
                  if "EUR" not in p.split("/"))
        forged["observed_t0_ref"][pair]["rate"] *= 1.01
        forged["snapshot_sha256"]=qa.sha({
            k:v for k,v in forged.items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,
                                    "seven-leg triangle"):
            qa.validate_snapshot(forged)
        # The valid original must remain acceptable.
        self.assertEqual(qa.validate_snapshot(original),self.day)

    def test_resigned_random_snapshot_id_cannot_claim_source_provenance(self):
        original=self.make()
        forged=copy.deepcopy(original)
        forged["snapshot_id"]="f"*64
        forged["snapshot_sha256"]=qa.sha({
            k:v for k,v in forged.items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,
                                    "snapshot identity does not bind"):
            qa.validate_snapshot(forged)
        forged=copy.deepcopy(original)
        forged["source_file_sha256"]["ecb"]="0"*64
        forged["snapshot_sha256"]=qa.sha({
            k:v for k,v in forged.items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,
                                    "snapshot identity does not bind"):
            qa.validate_snapshot(forged)

    def test_no_backfill_before_nov2_wrong_times_and_blocked_pricing(self):
        for cut in (datetime.fromisoformat("2026-10-30T19:31:00+01:00"),
                    datetime.fromisoformat("2026-10-31T20:31:00+01:00"),
                    datetime.fromisoformat("2026-11-01T20:31:00+01:00"),
                    datetime.fromisoformat("2026-11-02T18:31:00+01:00")):
            with self.subTest(cut=cut),self.assertRaises(ValueError):
                qa.make(cut,cut+timedelta(seconds=3),
                        fx=self.fx,pair_setup=self.pair,core=self.core,
                        observed=self.observed,ordinal=self.ordinal,
                        rates=self.rates,ois=self.ois,banks=self.banks,
                        nzd_proxy=self.nzd_proxy,hashes=self.hashes)
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

    def test_full_future_command_with_isolated_synthetic_disk_inputs(self):
        # Exercise the entire attempt -> official admission -> economic bridge
        # -> ordinal quality -> source-digest -> make -> append path on a
        # SYNTHETIC future date in an ISOLATED temporary repository.
        import hashlib
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            fixtures={
                "ecb":self.fx,"pair_setup":self.pair,"legacy_core":self.core,
                "macro_series":{"SYNTHETIC_ONLY":True},
                "macro_thermometer":{"SYNTHETIC_ONLY":True},
                "macro_registry":{"SYNTHETIC_ONLY":True},
                "rates":self.rates,"ois":self.ois,
                "banks":self.banks,"nzd_proxy":self.nzd_proxy,
            }
            for key,relative in qa.SOURCE_PATHS.items():
                target=root/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(json.dumps(fixtures[key])+"\n",
                                  encoding="utf-8")
            target=root/"research"/"future-only.jsonl"
            digest=lambda rel: hashlib.sha256((root/rel).read_bytes()).hexdigest()
            with patch.object(qa,"ROOT",root), \
                 patch.object(qa,"file_sha",side_effect=digest), \
                 patch.object(qa,"economic_run",return_value=self.observed) as econ, \
                 patch.object(qa,"ordinal_build",return_value=self.ordinal) as ordinal:
                out=qa.attempt(cutoff=self.cut,now=self.now,path=target)
                self.assertEqual(out["status"],
                                 "QUALITY_AWARE_PROSPECTIVE_SNAPSHOT_APPEND_OK")
                self.assertEqual(out["economic_dimension_slots"],24)
                self.assertEqual(out["market_economies"],8)
                self.assertEqual(out["market_pairs"],28)
                self.assertFalse(out["forward_H1_eligible"])
                econ.assert_called_once_with(as_of=self.day)
                ordinal.assert_called_once()
                snapshot=json.loads(target.read_text())
                self.assertEqual(qa.validate_snapshot(snapshot),self.day)
                self.assertEqual(snapshot["source_file_sha256"],
                                 {k:digest(p) for k,p in qa.SOURCE_PATHS.items()})
                orig=target.read_bytes()
                second=qa.attempt(cutoff=self.cut+timedelta(minutes=15),
                                  now=self.now+timedelta(minutes=15),path=target)
                self.assertEqual(second["status"],
                                 "EXISTING_QUALITY_AWARE_DATE_FROZEN_NO_OVERWRITE")
                self.assertEqual(orig,target.read_bytes())
                # Different target, but no same-day official ECB: no fake
                # observation can bypass the existing canonical market gate.
                stale=copy.deepcopy(self.fx)
                stale["last_as_of"]="2026-10-30"
                (root/qa.SOURCE_PATHS["ecb"]).write_text(json.dumps(stale)+"\n")
                out=qa.attempt(cutoff=self.cut,now=self.now,
                               path=root/"research"/"blocked.jsonl")
                self.assertEqual(out["status"],
                                 "BLOCKED_NO_OFFICIAL_SAME_DAY_ECB_T0")
                self.assertFalse((root/"research"/"blocked.jsonl").exists())

    def test_1930_missing_source_recovers_at_2030_without_duplicate_or_fake_T0(self):
        """Full synthetic disk path: late ECB/Pair -> retry -> durable proof -> no rewrite.

        Tests two independent delayed inputs without changing any live source or
        preregistered outcome. No synthetic row is committed to the real journal.
        """
        import hashlib
        from unittest.mock import patch
        from validation.forward.certify_quality_aware_persisted_v1 import audit

        for missing in ("ecb", "pair_setup"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                fixtures = {
                    "ecb": copy.deepcopy(self.fx),
                    "pair_setup": copy.deepcopy(self.pair),
                    "legacy_core": copy.deepcopy(self.core),
                    "macro_series": {"SYNTHETIC_ONLY": True},
                    "macro_thermometer": {"SYNTHETIC_ONLY": True},
                    "macro_registry": {"SYNTHETIC_ONLY": True},
                    "rates": copy.deepcopy(self.rates),
                    "ois": copy.deepcopy(self.ois),
                    "banks": copy.deepcopy(self.banks),
                    "nzd_proxy": copy.deepcopy(self.nzd_proxy),
                }
                if missing == "ecb":
                    fixtures["ecb"]["last_as_of"] = "2026-10-30"
                    fixtures["ecb"]["rows"] = [
                        row for row in fixtures["ecb"]["rows"]
                        if row["Date"] < self.day
                    ]
                    fixtures["ecb"]["row_count"] = len(fixtures["ecb"]["rows"])
                else:
                    fixtures["pair_setup"]["price_asof"] = "2026-10-30"

                for key, relative in qa.SOURCE_PATHS.items():
                    source = root / relative
                    source.parent.mkdir(parents=True, exist_ok=True)
                    source.write_text(json.dumps(fixtures[key]) + "\n", encoding="utf-8")

                journal = root / "isolated" / "quality.jsonl"
                file_digest = lambda rel: hashlib.sha256(
                    (root / rel).read_bytes()
                ).hexdigest()
                with patch.object(qa, "ROOT", root), \
                     patch.object(qa, "file_sha", side_effect=file_digest), \
                     patch.object(qa, "economic_run", return_value=self.observed) as econ, \
                     patch.object(qa, "ordinal_build", return_value=self.ordinal) as ordinal:
                    first = qa.attempt(cutoff=self.cut, now=self.now, path=journal)
                    self.assertEqual(first["status"], "BLOCKED_NO_OFFICIAL_SAME_DAY_ECB_T0")
                    self.assertEqual(first["appended"], 0)
                    self.assertFalse(journal.exists())
                    econ.assert_not_called()
                    ordinal.assert_not_called()

                    # The official source arrives after the primary run, not
                    # a fabricated or backdated first snapshot.
                    updated = "ecb" if missing == "ecb" else "pair_setup"
                    source = root / qa.SOURCE_PATHS[updated]
                    real = self.fx if missing == "ecb" else self.pair
                    source.write_text(json.dumps(real) + "\n", encoding="utf-8")

                    backup_time = self.cut + timedelta(hours=1)
                    backup_now = self.now + timedelta(hours=1)
                    second = qa.attempt(
                        cutoff=backup_time, now=backup_now, path=journal
                    )
                    self.assertEqual(
                        second["status"], "QUALITY_AWARE_PROSPECTIVE_SNAPSHOT_APPEND_OK"
                    )
                    self.assertEqual(second["appended"], 1)
                    econ.assert_called_once_with(as_of=self.day)
                    ordinal.assert_called_once()
                    frozen = journal.read_bytes()
                    row = json.loads(frozen)
                    self.assertEqual(qa.validate_snapshot(row), self.day)
                    self.assertEqual(row["official_ecb_t0_date"], self.day)
                    self.assertEqual(len(row["observed_t0_ref"]), 28)
                    self.assertEqual(row["numeric_z_imputation_count"], 0)

                    proof = audit(
                        now=backup_now, admitted=True,
                        core_persisted=True, path=journal
                    )
                    self.assertEqual(
                        proof["status"],
                        "QUALITY_AWARE_DURABLE_RESEARCH_COHORT_CERTIFIED"
                    )
                    self.assertTrue(proof["source_controlled_journal_verified"])
                    self.assertFalse(proof["can_validate_H1_or_FX_predictive_skill"])

                    replay = qa.attempt(
                        cutoff=backup_time + timedelta(minutes=30),
                        now=backup_now + timedelta(minutes=30), path=journal
                    )
                    self.assertEqual(
                        replay["status"],
                        "EXISTING_QUALITY_AWARE_DATE_FROZEN_NO_OVERWRITE"
                    )
                    self.assertEqual(replay["appended"], 0)
                    self.assertEqual(journal.read_bytes(), frozen)
                    econ.assert_called_once_with(as_of=self.day)

    def test_workflow_separate_provenance_and_no_extra_schedules(self):
        path=qa.ROOT/".github/workflows/forward-frozen-core-prospective-daily-v1.yml"
        text=path.read_text(encoding="utf-8")
        for utc in ("17","18","19"):
            self.assertEqual(text.count("cron: '30 "+utc+" * * 1-5'"),1)
        self.assertIn("id: v2_quality",text)
        self.assertIn("NOT_BEFORE_FUTURE_QUALITY_AWARE_COHORT",text)
        self.assertIn("QUALITY_AWARE_PROSPECTIVE_SNAPSHOT_APPEND_OK",text)
        self.assertIn("QUALITY_AWARE_PROSPECTIVE_CAPTURE_MISSING_AFTER_CORE_PERSISTENCE",text)
        self.assertIn("V2_RESEARCH_CAPTURE_FAILED_AFTER_LEGACY_PERSISTENCE",text)
        self.assertLess(
            text.index("name: Append immutable daily 28-pair frozen-Core observation only"),
            text.index("name: Freeze separate quality-aware V2 research features"))
        self.assertLess(
            text.index("name: Freeze separate quality-aware V2 research features"),
            text.index("name: Commit new prospective observation only"))
        self.assertLess(
            text.index("name: Commit new prospective observation only"),
            text.index("name: Certify future quality-aware observational journal only after Core persistence"))
        self.assertIn("git add validation/forward/candidate_shadow_snapshots/V2_QUALITY_AWARE_PROSPECTIVE_SNAPSHOTS_V1.jsonl",text)
        self.assertEqual(text.count("git push origin HEAD:main"),1)
        self.assertNotIn("cancel-in-progress: true",text)

    def test_independent_v2_certifications_run_after_successful_persistence(self):
        # Regression for a real GitHub Actions "implicit success()" trap:
        # a failing quality gate must not suppress the next original-V2
        # diagnosis, but failed git push must NEVER be called persisted.
        path=qa.ROOT/".github/workflows/forward-frozen-core-prospective-daily-v1.yml"
        workflow=path.read_text(encoding="utf-8")
        start=workflow.index(
            "      - name: Commit new prospective observation only, no forced push")
        quality=workflow.index(
            "      - name: Certify future quality-aware observational journal only after Core persistence")
        original=workflow.index(
            "      - name: Certify V2 research capture separately after primary Core commit")
        commit_step=workflow[start:quality]
        quality_step=workflow[quality:original]
        original_step=workflow[original:]
        self.assertIn("id: commit_snapshot",commit_step)
        self.assertIn("git push origin HEAD:main",commit_step)
        self.assertIn("steps.commit_snapshot.outcome == 'success'",quality_step)
        self.assertIn("steps.commit_snapshot.outcome == 'success'",original_step)
        self.assertIn("always()",original_step.split("run: |",1)[0])
        self.assertIn("V2_RESEARCH_CAPTURE_FAILED_AFTER_LEGACY_PERSISTENCE",
                      original_step)
        self.assertIn("QUALITY_AWARE_PROSPECTIVE_CAPTURE_MISSING_AFTER_CORE_PERSISTENCE",
                      quality_step)
        self.assertNotIn("continue-on-error: true",quality_step)
        self.assertNotIn("continue-on-error: true",original_step)
        # A real error remains a RED run; never silently approve a model.
        self.assertIn("exit 1",quality_step)
        self.assertIn("exit 1",original_step)
        self.assertEqual(workflow.count("git push origin HEAD:main"),1)

    def test_cli_cannot_write_future_snapshot_today(self):
        today=datetime.now(ZoneInfo("Europe/Rome"))
        # Only enforce the early-date test on current 2026-10-30 CI window.
        if today.date().isoformat() <= "2026-11-01":
            previous=qa.JOURNAL.read_bytes() if qa.JOURNAL.exists() else None
            with self.assertRaisesRegex(
                ValueError,"only real observed evening weekday captures|"
                           "first legitimate local capture"
            ):
                qa.attempt(cutoff=today,now=today)
            after=qa.JOURNAL.read_bytes() if qa.JOURNAL.exists() else None
            self.assertEqual(previous,after)
        self.assertTrue(qa.NO_HISTORICAL_BACKFILL)


if __name__=="__main__":
    unittest.main()
