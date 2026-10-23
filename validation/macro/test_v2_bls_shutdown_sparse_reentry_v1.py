#!/usr/bin/env python3
"""Adversarial November/December 2025 BLS missing October CPS tests."""
from __future__ import annotations

import copy
import unittest

from validation.macro.v2_bls_shutdown_sparse_reentry_v1 import (
    load_evidence, read_fixture, replay, validate_evidence,
)
from validation.macro.v2_shadow_intensity_v1 import build_shadow_intensity


class BLS2025GapTests(unittest.TestCase):
    def test_missing_october_documented_not_imputed(self):
        r=replay(at="2026-01-09T13:30:00Z")
        self.assertEqual(r["schema"],"GMFQ_MACRO_V2_BLS_U3_SPARSE_RELEASE_REENTRY_V1")
        self.assertTrue(r["missing_2025_10_CPS_reference_period"])
        self.assertFalse(r["missing_2025_10_observation_imputed"])
        self.assertFalse(r["missing_2025_10_first_release_invented"])
        self.assertFalse(r["official_web_source_bytes_hashed"])
        self.assertFalse(r["full_historical_pit_independently_certified"])
        self.assertTrue(r["calendar_month_momentum_after_gap_is_withheld"])
        self.assertEqual(r["first_release_periods_available"],27)
        self.assertEqual(r["reentered_first_releases"],2)
        self.assertEqual([x["reference_period"] for x in r["historical_reentry_snapshots"]],
                         ["2025-11","2025-12"])
        self.assertEqual([x["u3_first_release_percent"] for x in r["historical_reentry_snapshots"]],
                         [4.6,4.4])
        self.assertEqual([x["calendar_observation_holes_since_previous_first_release"]
                          for x in r["historical_reentry_snapshots"]],[1,0])
        self.assertEqual(r["historical_reentry_snapshots"][0]["gap_reference_period"],"2025-10")
        self.assertIsNone(r["historical_reentry_snapshots"][1]["gap_reference_period"])
        for s in r["historical_reentry_snapshots"]:
            self.assertEqual(s["training_first_releases"],24)
            self.assertIsNone(s["velocity_per_month"])
            self.assertIsNone(s["acceleration_per_month_squared"])
            self.assertIsNone(s["turning_point_per_month"])
            self.assertTrue(s["not_a_momentum_signal"])
            self.assertTrue(s["not_a_current_macro_score"])
            self.assertTrue(-3 <= s["labour_tightness_descriptive_only"] <= 3)
            self.assertFalse(s["eligible_for_live_scoring"])
            self.assertFalse(s["eligible_for_backtest"])
        self.assertFalse(r["historical_reentry_snapshots"][0][
            "successive_reference_month_change_comparable"])
        self.assertTrue(r["historical_reentry_snapshots"][1][
            "successive_reference_month_change_comparable"])
        self.assertIsNone(r["2026_macro_strength"])
        self.assertIsNone(r["2026_forex_signal"])
        for k in ("safe_to_publish_new_D","safe_to_update_pair_theses",
                  "eligible_for_live_scoring","eligible_for_backtest","writes_live_data"):
            self.assertFalse(r[k])

    def test_cutoff_at_exact_release_second_no_lookahead(self):
        dates=[
            ("2025-12-16T13:29:59Z",0,25),
            ("2025-12-16T13:30:00Z",1,26),
            ("2026-01-09T13:29:59Z",1,26),
            ("2026-01-09T13:30:00Z",2,27),
        ]
        for at,releases,count in dates:
            with self.subTest(at=at):
                r=replay(at=at)
                self.assertEqual(r["reentered_first_releases"],releases)
                self.assertEqual(r["first_release_periods_available"],count)
        self.assertNotEqual(replay(at=dates[0][0])["method_fingerprint_sha256"],
                            replay(at=dates[1][0])["method_fingerprint_sha256"])

    def test_strict_monthly_normalizer_still_rejects_observation_gap(self):
        m=read_fixture()
        e=load_evidence()
        m["vintages"] += e["resumed_first_releases"]
        m["as_of"]="2026-01-09T13:30:00Z"
        with self.assertRaisesRegex(ValueError,"missing observation interval"):
            build_shadow_intensity(m)

    def test_explicit_october_zero_or_interpolated_first_is_forbidden(self):
        cases=[
            lambda e:e["missing_observations"][0].update(published_value=4.5),
            lambda e:e["missing_observations"][0].update(reported_first_release="2025-11-05"),
            lambda e:e["missing_observations"][0].update(permitted_imputation=True),
            lambda e:e["missing_observations"][0].update(permitted_backfill=True),
            lambda e:e["missing_observations"][0].update(continue_monthly_derivative_across_gap=True),
            lambda e:e["missing_observations"].clear(),
        ]
        for alter in cases:
            with self.subTest(case=repr(alter)):
                e=load_evidence()
                alter(e)
                with self.assertRaises(ValueError):validate_evidence(e,read_fixture())

    def test_absent_month_cannot_be_inserted_among_first_releases(self):
        e=load_evidence()
        e["resumed_first_releases"].insert(0,{
            "observation_period":"2025-10",
            "released_at":"2025-11-10T08:30:00-05:00",
            "value":4.5,"kind":"FIRST",
            "evidence_ref":"https://www.bls.gov/news.release/archives/empsit_11102025.htm",
        })
        with self.assertRaisesRegex(ValueError,"two checked resumed"):
            validate_evidence(e,read_fixture())

    def test_source_dates_values_and_dst_are_pinned(self):
        variants=[
            lambda x:x["resumed_first_releases"][0].update(value=4.4),
            lambda x:x["resumed_first_releases"][1].update(value=4.6),
            lambda x:x["resumed_first_releases"][0].update(
                released_at="2025-12-16T08:30:00-04:00"),
            lambda x:x["resumed_first_releases"][1].update(
                evidence_ref="https://example.com/not-official"),
            lambda x:x["resumed_first_releases"][0].update(kind="REVISION"),
            lambda x:x["resumed_first_releases"].reverse(),
        ]
        for variant in variants:
            with self.subTest(variant=repr(variant)):
                data=load_evidence()
                variant(data)
                with self.assertRaises(ValueError):validate_evidence(data,read_fixture())

    def test_historical_only_rejects_2026_live_asof(self):
        for at in ("2026-10-23T12:00:00Z","2026-01-10T00:00:01Z"):
            with self.subTest(at=at):
                with self.assertRaisesRegex(ValueError,"historical shadow cutoff"):
                    replay(at=at)

    def test_approval_or_trading_fraud_rejected(self):
        changes=[
            lambda e:e.update(complete_revision_vintage_history_certified=True),
            lambda e:e.update(source_evidence_independently_hashed=True),
            lambda e:e["methodological_policy"].update(safe_to_publish_new_D=True),
            lambda e:e["methodological_policy"].update(safe_to_update_pair_theses=True),
            lambda e:e["methodological_policy"].update(permitted_live_macro_score=True),
            lambda e:e["methodological_policy"].update(permitted_backtest=True),
            lambda e:e["methodological_policy"].update(writes_live_data=True),
            lambda e:e["methodological_policy"].update(monthly_velocity=0.0),
        ]
        for alter in changes:
            with self.subTest(alter=repr(alter)):
                e=load_evidence()
                alter(e)
                with self.assertRaises(ValueError):validate_evidence(e,read_fixture())

    def test_pure_and_reproducible(self):
        e=load_evidence()
        before=copy.deepcopy(e)
        a=replay(at="2026-01-09T13:30:00Z",evidence=e)
        b=replay(at="2026-01-09T13:30:00Z",evidence=e)
        self.assertEqual(a,b)
        self.assertEqual(e,before)


if __name__=="__main__":
    unittest.main()
