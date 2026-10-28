"""Adversarial unit tests for non-executable official FX reference comparisons."""
import copy
from datetime import datetime, timezone
import json
import unittest
from zoneinfo import ZoneInfo
from validation.forward import observe_official_ecb_reference_outcomes_v1 as m


def at(value):
    return datetime.fromisoformat(value.replace("Z","+00:00"))


class ReferenceOutcomesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = json.loads(m.FX_PATH.read_text(encoding="utf-8"))
        cls.fx_rows = m.source_map(cls.fx)

    def sample(self, *, pair="EUR/USD", source_date="2026-10-02",
               cutoff="2026-10-02T18:30:00Z"):
        base, quote = pair.split("/")
        date = datetime.fromisoformat(source_date).date()
        rate = m.cross(self.fx_rows[date], base, quote)
        t0 = {
            "layer": "ECB_DAILY_REFERENCE_NOT_EXECUTABLE_SPOT",
            "state": "OBSERVED_AT_CAPTURE", "rate": rate, "pair": pair,
            "source_date": source_date, "unit": quote+"_PER_"+base,
            "source_id": "live_data/sections/ECB_G8_PRICE_HISTORY.json",
            "source_sha256": "a"*64, "intra_day_traded_price": False,
            "official_publication_instant_independently_verified": False,
            "basis": "ECB_EUR_BASE_CROSS_AFTER_1900_ROME_REPOSITORY_OBSERVATION"
        }
        snap = {
            "snapshot_id": "b"*64 if pair=="EUR/USD" else "c"*64,
            "pair": pair, "capture_class": "FROZEN_CORE_BASELINE_OBSERVATION",
            "schema_version": "GMFQ_CORE_FORWARD_DECISION_LOGGER_V1.1.0",
            "decision_cutoff": cutoff,
            "core_baseline_as_of": "2026-09-25",
            "core_recomputed_at_capture": False,
            "current_macro_score_certified": False,
            "price_anchor_is_executable": False,
            "t0_fx_reference": t0, "inputs": {"ecb_reference": t0},
            "source_provenance": {"ecb_reference":{
                "source_id":t0["source_id"],"sha256":t0["source_sha256"]}},
        }
        snap["snapshot_sha256"]=m.digest(snap)
        return snap

    def observe(self, snaps=None, *, now="2026-10-26T20:15:00Z",fx=None,prior=()):
        return m.compute([self.sample()] if snaps is None else snaps,
                         self.fx if fx is None else fx,at(now),prior)

    def test_october_weekend_next_official_fixing_and_six_horizons(self):
        a=self.observe()
        by={r["horizon"]:r for r in a["new_rows"]}
        self.assertEqual(set(by),set(m.HORIZONS)-{"1M","3M"})
        one=by["1D"]
        self.assertEqual(one["t0_fixing_date"],"2026-10-02")
        self.assertEqual(one["target_due_date"],"2026-10-03")
        self.assertEqual(one["observed_reference_date"],"2026-10-05")
        self.assertEqual(one["gap_after_due_days"],2)
        self.assertAlmostEqual(one["observed_reference_change_pips"],-21,places=3)
        self.assertAlmostEqual(one["observed_reference_return_pct"],
                               (1.1204/1.1225-1)*100,places=6)
        self.assertIsNone(one["trade_cost_bps"])
        self.assertIsNone(one["trade_net_return"])
        self.assertIsNone(one["trade_gross_return"])
        self.assertFalse(one["model_out_of_sample_performance_certified"])

    def test_all_observations_are_not_certified_trade_returns(self):
        for row in self.observe()["new_rows"]:
            self.assertEqual(row["schema"],m.SCHEMA)
            self.assertFalse(row["recomputed_core_signal"])
            self.assertIsNone(row["trade_pnl"])
            self.assertFalse(row["source_vintage_time_for_historical_fixing_verified"])

    def test_no_october_2026_return_before_date_matures(self):
        a=self.observe(now="2026-10-03T12:00:00Z")
        self.assertEqual(a["new_reference_observations"],0)
        self.assertGreater(a["blocked_and_waiting"]["waiting"],0)

    def test_one_day_fixing_not_available_until_evening(self):
        fx=copy.deepcopy(self.fx)
        fx["rows"]=fx["rows"][:]
        # The current source is only observed through Oct 23; test as-of Oct 5.
        at_1830=self.observe(now="2026-10-05T16:30:00Z",fx=fx)
        at_2115=self.observe(now="2026-10-05T19:15:00Z",fx=fx)
        self.assertEqual(at_1830["new_reference_observations"],0)
        self.assertEqual(at_2115["new_reference_observations"],1)

    def test_future_cutoff_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"cutoff in the future"):
            self.observe(now="2026-10-01T20:15:00Z")

    def test_legacy_oct14_smoke_not_promoted(self):
        legacy={"snapshot_id":"d"*64,"pair":"EUR/USD",
                "schema_version":"GMFQ_CORE_FORWARD_DECISION_LOGGER_V1.0.0"}
        a=self.observe([legacy])
        self.assertEqual(a["new_reference_observations"],0)
        self.assertEqual(a["blocked_and_waiting"]["no_t0"],1)

    def test_tampered_snapshot_hash_rejected(self):
        a=self.sample();a["t0_fx_reference"]["rate"]=0.25
        with self.assertRaisesRegex(ValueError,"corrupted prospective snapshot"):
            self.observe([a])

    def test_revisions_to_t0_ecb_history_fail_closed(self):
        fx=copy.deepcopy(self.fx)
        next(x for x in fx["rows"] if x["Date"]=="2026-10-02")["USD"]+=.002
        with self.assertRaisesRegex(ValueError,"historical ECB T0 fixing revised"):
            self.observe(fx=fx)

    def test_source_relabelled_as_executable_rejected(self):
        a=self.sample();a["price_anchor_is_executable"]=True
        a["snapshot_sha256"]=m.digest({k:v for k,v in a.items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,"incorrectly promoted"):
            self.observe([a])

    def test_source_hash_provenance_must_match(self):
        a=self.sample()
        a["source_provenance"]["ecb_reference"]["sha256"]="f"*64
        a["snapshot_sha256"]=m.digest({k:v for k,v in a.items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,"checksum provenance mismatch"):
            self.observe([a])

    def test_no_fake_data_if_official_source_missing(self):
        fx=copy.deepcopy(self.fx)
        fx["source_url"]="https://fake-ecb.example/"
        with self.assertRaisesRegex(ValueError,"only existing official ECB"):
            self.observe(fx=fx)

    def test_duplicate_fx_date_fails(self):
        fx=copy.deepcopy(self.fx)
        idx=next(i for i,x in enumerate(fx["rows"]) if x["Date"]=="2026-10-02")
        fx["rows"].insert(idx,fx["rows"][idx].copy())
        with self.assertRaisesRegex(ValueError,"duplicate/unordered"):
            self.observe(fx=fx)

    def test_jpy_pip_units(self):
        a=self.observe([self.sample(pair="EUR/JPY")])
        rows={x["horizon"]:x for x in a["new_rows"]}
        self.assertEqual(rows["1D"]["quote_unit"],"JPY_PER_EUR")
        self.assertAlmostEqual(rows["1D"]["observed_reference_change_pips"],
          (m.cross(self.fx_rows[datetime(2026,10,5).date()],"EUR","JPY") -
           m.cross(self.fx_rows[datetime(2026,10,2).date()],"EUR","JPY"))/0.01,places=5)

    def test_archive_append_idempotent(self):
        first=self.observe()
        after=self.observe(prior=first["new_rows"])
        self.assertEqual(after["new_reference_observations"],0)
        self.assertEqual(after["new_rows"],[])

    def test_corrupt_archive_hash_rejected(self):
        prior=self.observe()["new_rows"]
        prior[0]["observed_reference_return_pct"]=500
        with self.assertRaisesRegex(ValueError,"archived reference comparison hash"):
            self.observe(prior=prior)

    def test_invalid_archive_duplicate_rejected(self):
        prior=self.observe()["new_rows"]
        with self.assertRaisesRegex(ValueError,"duplicate or unknown archived"):
            self.observe(prior=prior+[copy.deepcopy(prior[0])])

    def test_missing_cross_cannot_be_made_up(self):
        fx=copy.deepcopy(self.fx)
        # The target date's currency is missing: do not select a later fixing.
        next(x for x in fx["rows"] if x["Date"]=="2026-10-05").pop("GBP")
        fx["last_as_of"]=fx["rows"][-1]["Date"]
        snap=self.sample(pair="EUR/GBP")
        a=self.observe([snap],fx=fx,now="2026-10-05T19:15:00Z")
        self.assertEqual(a["new_reference_observations"],0)
        self.assertEqual(a["blocked_and_waiting"]["source_gap"],1)

    def test_no_timezone_naive_eval(self):
        with self.assertRaisesRegex(ValueError,"timezone"):
            m.compute([self.sample()],self.fx,datetime(2026,10,26,20,15))


    def test_real_2026_10_26_t0_has_28_1d_ecb_reference_returns_on_oct28(self):
        # Prospective T0 was actually captured on 26 Oct. This test is
        # reference-only, not trading performance or a reconstructed signal.
        snapshots=[x for x in m.rows(m.DECISIONS)
                   if x.get("capture_class")=="FROZEN_CORE_BASELINE_OBSERVATION"
                   and str(x.get("decision_cutoff","")).startswith("2026-10-26")]
        self.assertEqual(len(snapshots),28)
        result=self.observe(snaps=snapshots,now="2026-10-28T20:40:00Z")
        self.assertEqual(result["new_reference_observations"],28)
        self.assertEqual({r["horizon"] for r in result["new_rows"]},{"1D"})
        self.assertEqual({r["observed_reference_date"] for r in result["new_rows"]},
                         {"2026-10-28"})
        self.assertTrue(all(r["trade_pnl"] is None and r["trade_net_return"] is None
                            and not r["model_out_of_sample_performance_certified"]
                            for r in result["new_rows"]))
        second=self.observe(snaps=snapshots,now="2026-10-28T20:40:00Z",
                            prior=result["new_rows"])
        self.assertEqual(second["new_reference_observations"],0)

    def test_observer_recovery_reuses_existing_hourly_without_new_cron(self):
        workflow=(m.ROOT/".github/workflows/forward-ecb-reference-outcomes-v1.yml"
                  ).read_text(encoding="utf-8")
        self.assertEqual(workflow.count("cron: '15 19 * * 1-5'"),1)
        self.assertEqual(workflow.count("cron: '15 20 * * 1-5'"),1)
        self.assertIn("workflows: ['Hourly Certified Alert Readiness V1']",workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'",workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'",workflow)
        self.assertIn("github.event.workflow_run.event == 'schedule'",workflow)
        self.assertIn("github.event_name == 'push' && github.ref == 'refs/heads/main'",workflow)
        self.assertIn("now.weekday()<5 and now.hour>=21",workflow)
        self.assertIn("REFERENCE_ONLY_NOT_TRADE_PERFORMANCE",workflow)
        self.assertIn("--append-journal",workflow)


if __name__=="__main__":
    unittest.main()
