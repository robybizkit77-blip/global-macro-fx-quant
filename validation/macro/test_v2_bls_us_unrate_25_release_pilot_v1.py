#!/usr/bin/env python3
"""Defensive checks for the first real 25-observation BLS Macro V2 pilot."""
from __future__ import annotations

import copy
import unittest

from validation.macro.v2_bls_us_unrate_25_release_pilot_v1 import (
    read_fixture, run, validate_manifest,
)
from validation.macro.v2_shadow_intensity_v1 import build_shadow_intensity


class BLS25PilotTests(unittest.TestCase):
    def test_historical_real_first_release_window_and_no_live_score(self):
        m=read_fixture()
        validate_manifest(m)
        self.assertEqual(len(m["vintages"]),25)
        r=run()
        self.assertEqual(r["source_id"],"LNS14000000")
        self.assertEqual(r["fred_alias"],"UNRATE")
        self.assertEqual(r["last_reference_period"],"2025-09")
        self.assertEqual(r["historical_cutoff"],"2025-11-20T13:30:00Z")
        self.assertEqual(r["training_releases"],24)
        self.assertEqual(r["current_first_release"],4.4)
        self.assertAlmostEqual(r["training_median"],4.1)
        self.assertAlmostEqual(r["training_mad"],0.1)
        self.assertAlmostEqual(r["unemployment_robust_z_clipped"],2.02347227842978)
        self.assertAlmostEqual(r["labour_tightness_intensity_not_currency_strength"],
                               -2.02347227842978)
        self.assertTrue(r["october_2025_release_gap"])
        self.assertTrue(r["not_a_current_2026_macro_score"])
        self.assertIsNone(r["currency_strength_score"])
        for k in ("archive_release_bytes_hashed","independent_full_pit_certified",
                  "eligible_for_live_macro","eligible_for_backtest",
                  "safe_to_publish_new_D","safe_to_update_pair_theses","writes_live_data"):
            self.assertIs(r[k],False,k)

    def test_just_before_delayed_september_release_must_fail_not_look_ahead(self):
        m=read_fixture()
        m["as_of"]="2025-11-20T13:29:59Z"
        with self.assertRaisesRegex(ValueError,"historical 20 November"):
            validate_manifest(m)
        # Raw shadow evaluator must also refuse to leak late release,
        # because only 24 prior first releases are available at cutoff.
        with self.assertRaises(ValueError):
            build_shadow_intensity(m)

    def test_october_shutdown_cannot_be_filled_with_fred_or_interpolation(self):
        m=read_fixture()
        m["vintages"].append({
            "observation_period":"2025-10",
            "released_at":"2025-12-16T08:30:00-05:00",
            "value":4.5,"kind":"FIRST",
            "evidence_ref":"https://www.bls.gov/news.release/archives/empsit_12162025.htm",
        })
        with self.assertRaisesRegex(ValueError,"exactly 25"):
            validate_manifest(m)

    def test_value_corruption_fails_pin_or_reconciling_five_older_releases(self):
        for period in ("2024-02","2025-09","2023-11"):
            m=read_fixture()
            row=next(r for r in m["vintages"] if r["observation_period"]==period)
            row["value"]=float('nan') if period=="2023-11" else 8.9
            if period=="2023-11":
                with self.assertRaises(ValueError):validate_manifest(m)
            elif period=="2024-02":
                with self.assertRaisesRegex(ValueError,"first-five"):validate_manifest(m)
            else:
                with self.assertRaisesRegex(ValueError,"delayed September"):validate_manifest(m)

    def test_archive_identity_and_release_hour_fail_closed(self):
        for change,reason in (
            (lambda m:m["source"].update(source_id="UNRATE"),"source identity"),
            (lambda m:m.update(canonical_alias="NOT_UNRATE"),"identity/cadence"),
            (lambda m:m["vintages"][10].update(released_at="2024-08-02T09:30:00-04:00"),
             "08:30"),
            (lambda m:m["vintages"][9].update(released_at="2024-07-05T08:30:00-05:00"),
             "offset"),
            (lambda m:m["vintages"][13].update(evidence_ref="https://example.com/fake"),
             "archived HTML evidence"),
            (lambda m:m["vintages"][14].update(kind="REVISION"),
             "headline value/first-release"),
            (lambda m:m.update(complete_revision_vintage_history_certified=True),
             "cannot promote"),
            (lambda m:m.update(source_evidence_is_independently_certified=True),
             "cannot promote"),
            (lambda m:m.update(eligible_for_current_2026_macro_scoring=True),
             "cannot promote"),
        ):
            with self.subTest(reason=reason):
                m=read_fixture()
                change(m)
                with self.assertRaisesRegex(ValueError,reason):
                    validate_manifest(m)

    def test_missing_period_rejected_despite_full_number_of_rows(self):
        m=read_fixture()
        m["vintages"][8]["observation_period"]="2024-06"
        with self.assertRaisesRegex(ValueError,"missing or reordered"):
            validate_manifest(m)

    def test_no_external_files_modified_by_pure_replay(self):
        m=read_fixture()
        orig=copy.deepcopy(m)
        self.assertEqual(run(m),run(m))
        self.assertEqual(m,orig)

    def test_cutoff_2026_cannot_promote_historical_sample(self):
        m=read_fixture()
        m["as_of"]="2026-10-23T12:00:00Z"
        with self.assertRaisesRegex(ValueError,"historical 20 November"):
            validate_manifest(m)
        # Actual research evaluator also rejects 2025-09 as too stale.
        with self.assertRaisesRegex(ValueError,"staleness"):
            build_shadow_intensity(m)


if __name__=="__main__":
    unittest.main()
