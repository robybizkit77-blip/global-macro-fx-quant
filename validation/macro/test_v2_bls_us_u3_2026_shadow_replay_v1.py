#!/usr/bin/env python3
"""Nine original 2026 BLS U-3 releases: adversarial cutoff, gap and FX gates."""
from __future__ import annotations

import copy
import unittest

from validation.macro.v2_bls_us_u3_2026_shadow_replay_v1 import (
    EXPECTED, evidence, replay, validate, read_fixture, load_evidence
)
from validation.macro.v2_shadow_intensity_v1 import build_shadow_intensity


class BLS2026FirstReleaseTests(unittest.TestCase):
    ASOF="2026-10-23T12:00:00Z"

    def test_nine_original_releases_current_observation_and_no_fx_score(self):
        x=replay(at=self.ASOF)
        self.assertEqual(x["releases_2026_visible_at_cutoff"],9)
        self.assertEqual(x["first_release_rows_visible_at_cutoff"],36)
        self.assertEqual(x["original_2026_annual_first_release_count_verified"],9)
        self.assertEqual(x["latest_reference_period"],"2026-09")
        self.assertEqual(x["latest_rate_first_release_percent"],4.2)
        self.assertEqual(x["latest_released_at"],"2026-10-02T12:30:00+00:00")
        self.assertAlmostEqual(x["latest_research_descriptive_labour_intensity"],0)
        self.assertTrue(x["asof_contains_latest_released_2026_09"])
        self.assertTrue(x["has_2025_10_missing_CPS_observation"])
        self.assertIsNone(x["October_2025_cps_value"])
        self.assertFalse(x["consecutive_month_normalizer_eligible"])
        self.assertIsNone(x["calendar_month_velocity_through_gap"])
        self.assertIsNone(x["calendar_month_acceleration_through_gap"])
        self.assertFalse(x["source_evidence_archive_bytes_hashed"])
        self.assertFalse(x["independent_complete_revision_chain_certified"])
        self.assertTrue(x["no_new_macro_or_currency_score"])
        self.assertIsNone(x["currency_strength_score"])
        self.assertIsNone(x["FX_signal"])
        for k in ("eligible_for_current_macro_scoring","eligible_for_backtest",
                  "safe_to_publish_new_D","safe_to_update_pair_theses","writes_live_data"):
            self.assertFalse(x[k],k)
        rows=x["nine_first_release_snapshots"]
        self.assertEqual([v["reference_period"] for v in rows],
                         [x[0] for x in EXPECTED])
        self.assertEqual([v["u3_first_release_percent"] for v in rows],
                         [4.3,4.4,4.3,4.3,4.3,4.2,4.1,4.1,4.2])
        for row in rows:
            self.assertEqual(row["training_first_releases"],24)
            self.assertIsNone(row["velocity_per_month"])
            self.assertIsNone(row["acceleration_per_month_squared"])
            self.assertIsNone(row["turning_point_per_month"])
            self.assertTrue(row["not_a_momentum_signal"])
            self.assertTrue(row["not_a_current_macro_score"])
            self.assertFalse(row["eligible_for_live_scoring"])

    def test_all_nine_cutoffs_one_second_early_and_at_release(self):
        from validation.macro.v2_shadow_features_v1 import timestamp
        from datetime import timedelta
        for i,(month,release,rate,_) in enumerate(EXPECTED):
            actual=timestamp(release)
            before=(actual-timedelta(seconds=1)).isoformat()
            at=actual.isoformat()
            with self.subTest(month=month):
                b=replay(at=before)
                a=replay(at=at)
                self.assertEqual(b["releases_2026_visible_at_cutoff"],i)
                self.assertEqual(a["releases_2026_visible_at_cutoff"],i+1)
                self.assertEqual(a["latest_reference_period"],month)
                self.assertEqual(a["latest_rate_first_release_percent"],rate)
                self.assertNotEqual(b["method_fingerprint_sha256"],
                                    a["method_fingerprint_sha256"])

    def test_sparse_index_is_zero_for_september_not_a_currency_signal(self):
        x=replay(at=self.ASOF)
        latest=x["nine_first_release_snapshots"][-1]
        self.assertEqual(latest["reference_period"],"2026-09")
        self.assertEqual(latest["training_last_period"],"2026-08")
        self.assertEqual(latest["training_median"],4.2)
        self.assertAlmostEqual(latest["training_mad"],0.1)
        self.assertAlmostEqual(latest["sparse_event_robust_z_clipped"],0.0)
        self.assertEqual(latest["labour_tightness_descriptive_only"],0.0)
        self.assertFalse(x["eligible_for_backtest"])

    def test_regular_consecutive_monthly_model_still_fails_missing_october(self):
        m=read_fixture();g=load_evidence();e=evidence()
        m["vintages"]+=g["resumed_first_releases"]+e["first_release_values"]
        m["as_of"]=self.ASOF
        with self.assertRaisesRegex(ValueError,"rolling training window"):
            build_shadow_intensity(m)

    def test_any_mutated_first_rate_or_date_is_rejected(self):
        variants=[
          lambda e:e["first_release_values"][0].update(value=4.0),
          lambda e:e["first_release_values"][8].update(value=4.3),
          lambda e:e["first_release_values"][4].update(
              released_at="2026-06-05T08:30:00-05:00"),
          lambda e:e["first_release_values"][2].update(
              released_at="2026-04-04T08:30:00-04:00"),
          lambda e:e["first_release_values"][1].update(
              evidence_ref="https://example.org/not-bls.html"),
          lambda e:e["first_release_values"][0].update(kind="REVISION"),
          lambda e:e["first_release_values"].reverse(),
          lambda e:e["first_release_values"].append(
              copy.deepcopy(e["first_release_values"][-1])),
        ]
        for alter in variants:
            with self.subTest(case=str(alter)):
                e=evidence();alter(e)
                with self.assertRaises(ValueError):
                    validate(e,read_fixture(),load_evidence())

    def test_october_2025_and_future_october_2026_cannot_be_imputed(self):
        for modify in (
          lambda e:e.update(structural_missing_cps_period="2025-11"),
          lambda e:e["governance"].update(previous_2025_10_cps_hole_imputed=True),
          lambda e:e["governance"].update(strict_monthly_macro_v2_still_fails_gap=False),
          lambda e:e["governance"].update(monthly_velocity_through_missing_period=0.0),
          lambda e:e.update(next_release_not_yet_published_at_asof=None),
          lambda e:e["first_release_values"][0].update(observation_period="2025-10"),
        ):
            with self.subTest(case=str(modify)):
                e=evidence();modify(e)
                with self.assertRaises(ValueError):
                    validate(e,read_fixture(),load_evidence())

    def test_unsupported_live_promotions_are_rejected(self):
        for edit in (
          lambda x:x["governance"].update(live_data_promotion_allowed=True),
          lambda x:x["governance"].update(allow_pair_mutation=True),
          lambda x:x["governance"].update(allow_backtest=True),
          lambda x:x["governance"].update(safe_to_publish_new_D=True),
          lambda x:x["governance"].update(force_no_forex_strength=False),
          lambda x:x.update(evidence_independently_hashed=True),
          lambda x:x.update(full_vintage_revision_chain_certified=True),
        ):
            with self.subTest(case=str(edit)):
                e=evidence();edit(e)
                with self.assertRaises(ValueError):
                    validate(e,read_fixture(),load_evidence())

    def test_never_claim_data_after_official_september_2026(self):
        with self.assertRaisesRegex(ValueError,"no verified evidence"):
            replay(at="2026-11-06T13:30:00Z")
        x=replay(at="2026-10-23T12:00:00Z")
        self.assertEqual(x["latest_reference_period"],"2026-09")

    def test_pure_deterministic_at_same_cutoff_and_unmodified_inputs(self):
        e=evidence();original=copy.deepcopy(e)
        a=replay(at=self.ASOF,record=e)
        b=replay(at=self.ASOF,record=e)
        self.assertEqual(a,b)
        self.assertEqual(e,original)


if __name__=="__main__":
    unittest.main()
