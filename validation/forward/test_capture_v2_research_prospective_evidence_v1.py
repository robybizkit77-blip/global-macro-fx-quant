"""Prospective V2 feature freeze: same-day real-clock gate and synthetic tests.

The Oct-27 exercise uses currently archived data to test pure code ONLY; it
must NEVER write a retroactive live snapshot into the forward research journal.
"""
import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo
from pathlib import Path

from validation.forward import capture_v2_research_prospective_evidence_v1 as cap
from validation.macro.v2_domestic_candidate_explicit_formula_v1 import run as domestic


class V2ProspectiveResearchCapture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Run the CI on any day, even after the real ECB and pair archives
        # advance beyond 2026-10-27. These are ONLY synthetic test inputs.
        # No synthetic date or price is ever written to the real journal.
        today=datetime.now(ZoneInfo("Europe/Rome")).date()
        while today.weekday()>=5:
            today-=timedelta(days=1)
        cls.day=today.isoformat()
        cls.cut=datetime.combine(today,time(19,31),tzinfo=ZoneInfo("Europe/Rome"))
        cls.now=cls.cut+timedelta(seconds=9)
        cls.fx=copy.deepcopy(cap.read_live("ECB_G8_PRICE_HISTORY"))
        cls.pairs=copy.deepcopy(cap.read_live("PAIR_SETUP_OPERATIONAL_VIEW"))
        cls.legacy=cap.read_live("D")
        cls.cb=cap.read_live("NATIVE_CB_DATA")
        cls.ois=cap.read_live("OIS_OPERATIONAL_VIEW")
        cls.rates=cap.read_live("NATIVE_RATES_DATA")
        # Use the archived last quote ONLY as a test-only surrogate for the
        # test civil day. This cannot certify today's real ECB publication.
        if cls.fx["last_as_of"]!=cls.day:
            cls.fx["rows"]=[r for r in cls.fx["rows"] if r["Date"]<cls.day]
            if not cls.fx["rows"]:
                raise ValueError("no prior ECB quote for an isolated test")
            synthetic=copy.deepcopy(cls.fx["rows"][-1])
            synthetic["Date"]=cls.day
            cls.fx["rows"].append(synthetic)
            cls.fx["last_as_of"]=cls.day
            cls.fx["row_count"]=len(cls.fx["rows"])
        cls.pairs["price_asof"]=cls.day
        for k in ("as_of","overlay_asof","history_asof"):
            cls.pairs["price_audit"][k]=cls.day
        cls.candidate=domestic(as_of=cls.day)
        cls.hashes={
            "ecb":cap.file_sha("live_data/sections/ECB_G8_PRICE_HISTORY.json"),
            "pair_setup":cap.file_sha("live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json"),
            "legacy_core":cap.file_sha("live_data/sections/D.json"),
            "native_cb":cap.file_sha("live_data/sections/NATIVE_CB_DATA.json"),
            "ois_view":cap.file_sha("live_data/sections/OIS_OPERATIONAL_VIEW.json"),
            "native_rates":cap.file_sha("live_data/sections/NATIVE_RATES_DATA.json"),
            "candidate":cap.sha(cls.candidate)
        }

    def build(self, **kwargs):
        params={
            "fx":copy.deepcopy(self.fx),"pair_setup":copy.deepcopy(self.pairs),
            "legacy":copy.deepcopy(self.legacy),
            "candidate":copy.deepcopy(self.candidate),
            "banks":copy.deepcopy(self.cb),
            "ois":copy.deepcopy(self.ois),
            "rates":copy.deepcopy(self.rates),
            "source_hashes":copy.deepcopy(self.hashes),
        }
        params.update(kwargs)
        return cap.make(self.cut,self.now,**params)

    def test_complete_28_t0_and_separate_eight_country_frozen_features(self):
        x=self.build()
        self.assertEqual(x["schema"],cap.SCHEMA)
        self.assertEqual(x["local_date_rome"],self.day)
        self.assertEqual(x["economic_checked_as_of"],self.day)
        self.assertEqual(x["official_ecb_t0_date"],self.day)
        self.assertEqual(len(x["observed_t0_ref"]),28)
        self.assertEqual(len(x["domestic_v2_features"]),8)
        self.assertEqual(len(x["old_core_pair_context_UNCHANGED"]),28)
        for pair,p in x["observed_t0_ref"].items():
            self.assertEqual(p["layer"],"ECB_DAILY_REFERENCE_NOT_EXECUTABLE_SPOT")
            self.assertFalse(p["trade_execution_price"])
            a,b=pair.split("/")
            self.assertAlmostEqual(p["rate"],self.fx["rows"][-1][b]/self.fx["rows"][-1][a])
        for c,row in x["domestic_v2_features"].items():
            self.assertIsNone(row["FX_signal"])
            self.assertIsNone(row["trade_entry"])
            self.assertTrue(row["cb_CAN_not_calibrated"])
            self.assertEqual(
                row["weight_invariant_class_only"],
                self.candidate["countries"][c][
                    "continuous_weight_sensitivity_RESEARCH_ONLY"][
                        "weight_invariant_domestic_class_RESEARCH_ONLY"])
        for flag in (
            "historical_issuer_PIT_backtest_certified",
            "future_outcomes_observed_at_capture",
            "executable_t0_prices_certified",
            "V2_currency_FX_strength_calibrated",
            "V2_pair_directional_predictions",
            "FX_COT_OIS_causality_calibrated",
            "allowed_for_beta_hedge_performance",
            "eligible_for_real_trading_or_sizing",
            "core_D_recalculated","pair_rankings_recalculated"
        ):
            self.assertFalse(x[flag])
        self.assertEqual(x["snapshot_sha256"],
            cap.sha({k:v for k,v in x.items() if k!="snapshot_sha256"}))

    def test_never_backfill_or_accept_timestamp_more_than_five_minutes(self):
        invalid=[
            (self.cut,self.now+timedelta(minutes=6)),
            (self.cut,self.cut-timedelta(seconds=1)),
            (self.cut.replace(tzinfo=None),self.now),
            (self.cut,self.now.replace(tzinfo=None)),
            (datetime.fromisoformat("2026-10-27T18:30:00+01:00"),
             datetime.fromisoformat("2026-10-27T18:30:09+01:00")),
            (datetime.fromisoformat("2026-11-01T20:30:00+01:00"),
             datetime.fromisoformat("2026-11-01T20:30:09+01:00"))
        ]
        for at, now in invalid:
            with self.subTest(at=at,now=now),self.assertRaises(ValueError):
                cap.cutoff_valid(at,now)

    def test_not_a_forward_prediction_and_guard_v2_quality(self):
        changed=copy.deepcopy(self.candidate)
        changed["economic_as_of"]=(self.cut.date()+timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):
            self.build(candidate=changed,source_hashes={
                **self.hashes,"candidate":cap.sha(changed)})
        changed=copy.deepcopy(self.candidate)
        changed["countries"]["USD"]["FX_strength_candidate"]=1.0
        with self.assertRaises(ValueError):
            self.build(candidate=changed,source_hashes={
                **self.hashes,"candidate":cap.sha(changed)})
        changed=copy.deepcopy(self.ois)
        changed["currencies"]["CHF"]["operational_status"]="GREEN_OFFICIAL"
        with self.assertRaises(ValueError):
            self.build(ois=changed)
        changed=copy.deepcopy(self.hashes)
        changed["candidate"]="0"*64
        with self.assertRaises(ValueError):
            self.build(source_hashes=changed)

    def test_stale_or_noncurrent_t0_and_modified_sources_are_rejected(self):
        changed=copy.deepcopy(self.fx)
        changed["last_as_of"]=(self.cut.date()-timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):
            self.build(fx=changed)
        changed=copy.deepcopy(self.pairs)
        changed["price_asof"]=(self.cut.date()-timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):
            self.build(pair_setup=changed)
        changed=copy.deepcopy(self.legacy)
        changed["asOf"]=self.day
        with self.assertRaises(ValueError):
            self.build(legacy=changed)

    def test_idempotency_and_no_future_return_archive_mutation(self):
        x=self.build()
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"research"/"V2.jsonl"
            self.assertEqual(cap.append(x,path=path,dry_run=True),
                             "VALID_FIRST_DAY_DRY_RUN_NO_WRITE")
            self.assertFalse(path.exists())
            self.assertEqual(cap.append(x,path=path),
                             "PROSPECTIVE_SHADOW_RESEARCH_SNAPSHOT_APPEND_OK")
            before=path.read_bytes()
            self.assertEqual(cap.append(x,path=path),
                             "EXISTING_DATE_ALREADY_FROZEN_NO_OVERWRITE")
            self.assertEqual(before,path.read_bytes())
            tampered=copy.deepcopy(x)
            tampered["observed_t0_ref"]["EUR/USD"]["rate"]*=2
            with self.assertRaises(ValueError):
                cap.append(tampered,path=path)
            changed=json.loads(before.decode("utf-8"))
            changed["domestic_v2_features"]["USD"]["FX_signal"]="LONG"
            path.write_bytes(cap.canonical(changed))
            with self.assertRaises(ValueError):
                cap.append(x,path=path)

    def test_existing_cadence_keeps_core_primary_but_never_false_green_v2(self):
        workflow=(cap.ROOT/".github/workflows/forward-frozen-core-prospective-daily-v1.yml").read_text(encoding="utf-8")
        # Only existing Rome 19:30/20:30 DST union, never a new cron.
        self.assertEqual(workflow.count("cron: '30 17 * * 1-5'"),1)
        self.assertEqual(workflow.count("cron: '30 18 * * 1-5'"),1)
        self.assertEqual(workflow.count("cron: '30 19 * * 1-5'"),1)
        core_pos=workflow.index("name: Append immutable daily 28-pair frozen-Core observation only")
        v2_pos=workflow.index("name: Freeze independent V2 research features beside today's ECB T0")
        persist_pos=workflow.index("name: Commit new prospective observation only, no forced push")
        check_pos=workflow.index("name: Certify V2 research capture separately after primary Core commit")
        self.assertLess(core_pos,v2_pos)
        self.assertLess(v2_pos,persist_pos)
        self.assertLess(persist_pos,check_pos)
        self.assertIn("id: v2_shadow",workflow)
        self.assertIn("V2_SHADOW_STATUS: ${{ steps.v2_shadow.outputs.status }}",workflow)
        self.assertIn("V2_RESEARCH_CAPTURE_FAILED_AFTER_LEGACY_PERSISTENCE",workflow)
        self.assertIn("V2_RESEARCH_SOURCE_FAILURE",workflow)
        self.assertIn("V2_RESEARCH_RECEIPT_INVALID",workflow)
        self.assertIn("EXISTING_DATE_ALREADY_FROZEN_NO_OVERWRITE",workflow)
        self.assertIn("PROSPECTIVE_SHADOW_RESEARCH_SNAPSHOT_APPEND_OK",workflow)
        # An admitted run that lacks a V2 record MUST exit with a failing
        # status. This occurs only after the older Core has already persisted.
        self.assertIn("exit 1",workflow[check_pos:])
        self.assertIn("git push origin HEAD:main",workflow[persist_pos:check_pos])

    def test_no_runtime_output_or_historical_snapshots_written(self):
        paths=[
            cap.ROOT/"live_data/sections/D.json",
            cap.ROOT/"live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
            cap.ROOT/"validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl",
        ]
        previous={str(p):p.read_bytes() for p in paths}
        x=self.build()
        self.assertIsNotNone(x["snapshot_id"])
        self.assertEqual(previous,{str(p):p.read_bytes() for p in paths})


if __name__=="__main__":
    unittest.main()
