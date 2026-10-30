"""Synthetic H1 tests only: never write reconstructed history to the real journals."""
import copy
from datetime import datetime, timezone
from pathlib import Path
import unittest

from validation.forward import evaluate_v2_h1_2y_repricing_readonly_v1 as h1
from validation.forward import capture_v2_research_prospective_evidence_v1 as cap
from validation.forward.test_audit_v2_prospective_cohort_independence_v1 import (
    test_freeze as frozen_fixture, test_return as outcome_fixture
)


class H1RepricingTests(unittest.TestCase):
    def snap(self, day, clock):
        s = frozen_fixture(day, clock)
        for ccy, f in s["domestic_v2_features"].items():
            f["two_year_instrument_identity"] = "issuer/series-"+ccy+" | 2Y"
            f["bond_date"] = day
            f["two_year_observed_yield_pct"] = {"EUR": 3.0, "USD": 4.0}.get(ccy, 2.0)
        s["snapshot_sha256"] = cap.sha({
            k:v for k,v in s.items() if k != "snapshot_sha256"})
        return s

    def sample(self):
        prior = self.snap("2026-10-29", "2026-10-29T20:08:00Z")
        current = self.snap("2026-10-30", "2026-10-30T20:08:00Z")
        current["domestic_v2_features"]["USD"]["two_year_observed_yield_pct"] = 4.03
        # A lower contemporaneous EUR/USD means momentum forecasts DOWN.
        current["observed_t0_ref"]["USD/EUR"]["rate"] = (
            prior["observed_t0_ref"]["USD/EUR"]["rate"] * .995)
        current["snapshot_sha256"] = cap.sha({
            k:v for k,v in current.items() if k != "snapshot_sha256"})
        outcome = outcome_fixture(current, "USD/EUR", "1W", "2026-11-09")
        now = datetime(2026,11,10,20,15,tzinfo=timezone.utc)
        return prior, current, outcome, now

    def test_old_oct28_is_not_retroactively_scored(self):
        x = self.snap("2026-10-28", "2026-10-28T20:08:00Z")
        o = h1.inspect([x], [], datetime(2026,10,29,6,0,tzinfo=timezone.utc))
        self.assertEqual(o["eligible_H1_capture_dates"],0)
        self.assertEqual(o["status"],"INSUFFICIENT_VALID_PIT_COHORT")
        self.assertEqual(o["mean_paired_accuracy_difference_descriptive"],None)

    def test_valid_post_registered_one_week_pair_and_paired_baseline(self):
        prev, curr, out, now = self.sample()
        result = h1.inspect([prev,curr],[out],now)
        self.assertEqual(result["eligible_H1_capture_dates"],2)
        # The first date has no preceding business-day frozen T0.
        self.assertEqual(result["possible_H1_pairs"],56)
        self.assertEqual(result["reason_counts"]["missing_prior_T0"],28)
        self.assertEqual(result["reason_counts"]["evaluated"],1)
        self.assertEqual(result["paired_evaluable_dates"],1)
        self.assertEqual(result["mean_paired_accuracy_difference_descriptive"],1.0)
        self.assertEqual(result["block_confidence_intervals_95"],None)
        self.assertTrue(result["reference_only_not_trade_pnl"])

    def test_not_matured_yet_and_missing_future_dont_fabricate(self):
        prev,curr,out,now = self.sample()
        early = h1.inspect([prev,curr],[], datetime(2026,11,2,20,0,tzinfo=timezone.utc))
        self.assertGreater(early["reason_counts"]["not_matured"],0)
        self.assertEqual(early["reason_counts"]["evaluated"],0)
        late = h1.inspect([prev,curr],[],now)
        self.assertGreater(late["reason_counts"]["missing_future_fixing"],0)
        self.assertEqual(late["paired_evaluable_dates"],0)

    def test_source_staleness_identity_and_unchanged_quote_date_block(self):
        prev,curr,out,now = self.sample()
        for change,reason in (
            ({"two_year_instrument_identity":None},"noncomparable_source"),
            ({"two_year_instrument_identity":"different issuer | 2Y"},"noncomparable_source"),
            ({"bond_date":"2026-10-21"},"stale_rate"),
            ({"bond_date":"2026-10-29"},"unchanged_bond_date"),
            ({"two_year_observed_yield_pct":None},"missing_rate"),
        ):
            with self.subTest(change=change):
                bad=copy.deepcopy(curr)
                bad["domestic_v2_features"]["USD"].update(change)
                bad["snapshot_sha256"]=cap.sha({
                    k:v for k,v in bad.items() if k!="snapshot_sha256"})
                result=h1.inspect([prev,bad],[],now)
                self.assertGreater(result["reason_counts"][reason],0)
                self.assertEqual(result["reason_counts"]["evaluated"],0)

    def test_future_2y_source_date_rejected_even_when_snapshot_hash_valid(self):
        prev,curr,out,now=self.sample()
        curr["domestic_v2_features"]["USD"]["bond_date"]="2026-11-02"
        curr["snapshot_sha256"]=cap.sha({
            k:v for k,v in curr.items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,"future dated 2Y"):
            h1.inspect([prev,curr],[],now)

    def test_snapshot_or_outcome_forgery_rejected(self):
        prev,curr,out,now=self.sample()
        forged=copy.deepcopy(out)
        forged["observed_reference_return_pct"]=99
        with self.assertRaises(ValueError):
            h1.inspect([prev,curr],[forged],now)
        with self.assertRaises(ValueError):
            h1.inspect([prev,curr],[out,out],now)
        changed=copy.deepcopy(curr)
        changed["observed_t0_ref"]["USD/EUR"]["rate"]=1234
        with self.assertRaises(ValueError):
            h1.inspect([prev,changed],[out],now)

    def test_source_fingerprint_uses_issuer_curve_label_and_no_source_date(self):
        def rate(d):
            return {"USD":{"source":"US Treasury · Daily Par Curve · "+d,
                    "history2":{"label":"Treasury 2Y"},
                    "2Y":4.5, "tenors":[{"tenor":"2Y","value":4.5,"date":d}]}}
        x=cap.two_year_instrument_identity(rate("2026-10-28"),"USD",4.5)
        y=cap.two_year_instrument_identity(rate("2026-10-29"),"USD",4.5)
        self.assertEqual(x,y)
        self.assertIn("Treasury 2Y",x)
        self.assertIsNone(cap.two_year_instrument_identity({},"USD",4.5))

    def test_2y_operational_readiness_is_separate_from_H1_and_source_dated(self):
        def entry(day, value, quality="FULL_CURRENT_OFFICIAL"):
            return {
                "date":day, "2Y":value, "quality":quality,
                "source":"Official issuer · constant 2Y definition · "+day,
                "history2":{"label":"2Y instrument"},
                "tenors":[{"tenor":"2Y","date":day,"value":value}],
            }
        live={
            "USD":entry("2026-10-27",4.5),
            "JPY":entry("2026-10-28",1.3),
            # Negative yields are valid sovereign yields.
            "CHF":entry("2026-10-28",-0.15),
            # Fresh-looking quality labels do NOT override source age.
            "GBP":entry("2026-10-26",4.3),
            "AUD":entry("2026-10-21",5.0),
            "NZD":entry("2026-11-02",3.8),
            "EUR":entry("2026-10-28",2.9),
        }
        live["EUR"]["history2"].pop("label")
        out=h1.operational_2y_readiness(
            live,datetime(2026,10,29,7,0,tzinfo=timezone.utc))
        states={k:v["state"] for k,v in out["currency_status"].items()}
        self.assertEqual(states["USD"],"POTENTIALLY_FRESH_NOT_YET_H1_ELIGIBLE")
        self.assertEqual(states["JPY"],"POTENTIALLY_FRESH_NOT_YET_H1_ELIGIBLE")
        self.assertEqual(states["CHF"],"POTENTIALLY_FRESH_NOT_YET_H1_ELIGIBLE")
        self.assertEqual(states["GBP"],"STALE_FOR_H1")
        self.assertEqual(states["AUD"],"STALE_FOR_H1")
        self.assertEqual(states["NZD"],"FUTURE_SOURCE_REJECTED")
        self.assertEqual(states["EUR"],"MISSING_COMPARABLE_2Y_IDENTITY")
        self.assertEqual(states["CAD"],"MISSING_RATE")
        self.assertEqual(out["potential_pairs_upper_bound_not_scored"],3)
        self.assertTrue(out["does_not_certify_H1_pair_or_outcome"])
        self.assertTrue(out["no_rates_or_forward_journal_mutation"])

    def test_no_mutation_of_original_ledgers(self):
        paths=[cap.JOURNAL,h1.obs.OUTCOMES]
        before={str(p):p.read_bytes() if p.is_file() else None for p in paths}
        prev,curr,out,now=self.sample()
        h1.inspect([prev,curr],[out],now)
        after={str(p):p.read_bytes() if p.is_file() else None for p in paths}
        self.assertEqual(before,after)


    def test_preflight_is_rates_only_and_blocks_stale_prior_and_unchanged_date(self):
        prior = self.snap("2026-10-29", "2026-10-29T20:08:00Z")
        for ccy, feature in prior["domestic_v2_features"].items():
            feature["two_year_instrument_identity"] = (
                "issuer/series-" + ccy + " | 2Y label | 2Y")
        prior["domestic_v2_features"]["AUD"]["bond_date"] = "2026-10-21"
        prior["domestic_v2_features"]["CHF"]["bond_date"] = "2026-09-30"
        prior["domestic_v2_features"]["NZD"]["bond_date"] = "2026-10-16"
        prior["snapshot_sha256"] = cap.sha({
            k: v for k, v in prior.items() if k != "snapshot_sha256"})
        def row(ccy, date_str):
            v = prior["domestic_v2_features"][ccy]["two_year_observed_yield_pct"]
            return {"date": date_str, "2Y": v + 0.01,
                    "source": "issuer/series-" + ccy + " · " + date_str,
                    "history2": {"label": "2Y label"},
                    "tenors": [{"tenor": "2Y", "date": date_str, "value": v + 0.01}]}
        live = {
            ccy: row(ccy, "2026-10-30" if ccy in ("USD", "JPY", "AUD")
                     else "2026-10-29")
            for ccy in cap.G8
        }
        live["CHF"] = row("CHF", "2026-09-30")
        live["NZD"] = row("NZD", "2026-10-16")
        result = h1.preflight_previous_frozen_rates_only(
            [prior], live, datetime(2026, 10, 30, 11, 46, tzinfo=timezone.utc))
        self.assertEqual(result["denominator_potential_pairs"], 28)
        self.assertEqual(result["potential_rate_comparable_pairs"], ["USD/JPY"])
        self.assertEqual(result["pair_count_upper_bound"], 1)
        self.assertEqual(result["currency_rate_comparability"]["AUD"], "stale_rate")
        self.assertEqual(result["currency_rate_comparability"]["EUR"], "unchanged_bond_date")
        self.assertEqual(result["currency_rate_comparability"]["CHF"], "stale_rate")
        self.assertEqual(sum(result["other_pairs_by_primary_rate_blocker"].values()), 27)
        self.assertTrue(result["rates_only_not_frozen_t0"])
        self.assertTrue(result["no_predictions_or_outcomes"])
        self.assertFalse(result["mutates_forward_journals"])

    def test_preflight_missing_prior_and_weekend_fail_closed(self):
        now = datetime(2026, 10, 30, 11, 0, tzinfo=timezone.utc)
        empty = h1.preflight_previous_frozen_rates_only([], {}, now)
        self.assertEqual(empty["status"], "MISSING_PREVIOUS_BUSINESS_DAY_FREEZE")
        self.assertEqual(empty["pair_count_upper_bound"], 0)
        weekend = h1.preflight_previous_frozen_rates_only(
            [], {}, datetime(2026, 10, 31, 11, 0, tzinfo=timezone.utc))
        self.assertEqual(weekend["status"], "WEEKEND_NO_SAME_DAY_FORWARD_CAPTURE")
        self.assertEqual(weekend["pair_count_upper_bound"], 0)


if __name__=="__main__":
    unittest.main()
