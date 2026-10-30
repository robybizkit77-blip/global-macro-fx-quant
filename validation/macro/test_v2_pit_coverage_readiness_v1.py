#!/usr/bin/env python3
"""Deterministic fail-closed checks for 24-slot Macro V2 evidence readiness."""
from __future__ import annotations

import copy
import json
import unittest
from datetime import date

from validation.macro.v2_pit_coverage_readiness_v1 import (
    BLS_FILE, CORE_FILE, CORE_CURRENT_FILE, CORE_CURRENT_FROM, GBP_FILE, GROWTH_FILE, REGISTRY, SERIES,
    THERMOMETER, ROOT, inspect, markdown, read, run,
)


def fixture():
    return {
        "registry": read(ROOT, REGISTRY),
        "therm": read(ROOT, THERMOMETER),
        "series": read(ROOT, SERIES),
        "core": read(ROOT, CORE_CURRENT_FILE if date(2026, 10, 30) >= CORE_CURRENT_FROM else CORE_FILE),
        "growth": read(ROOT, GROWTH_FILE),
        "gbp": read(ROOT, GBP_FILE),
        "bls": read(ROOT, BLS_FILE),
    }


class ReadinessTests(unittest.TestCase):
    ASOF = date(2026, 10, 30)

    def report(self, modified=None):
        inputs = fixture()
        if modified is not None:
            modified(inputs)
        return inspect(inputs, as_of=self.ASOF)

    def test_observed_24_pillars_not_misrepresented_as_pit(self):
        receipt = self.report()
        x = receipt["summary"]
        self.assertEqual(x["observed_pillar_slots"], 24)
        self.assertEqual(x["registered_core_series"], 16)
        self.assertEqual(x["growth_currencies_with_observations"], 8)
        current_core = sum(
            a["observation_period"][:7] ==
            fixture()["therm"]["currencies"][a["key"].split(".")[0]][a["key"].split(".")[1]]["as_of"][:7]
            for a in fixture()["core"]["attestations"]
        )
        self.assertEqual(x["latest_core_official_web_anchors"], current_core)
        self.assertEqual(x["historical_core_official_web_anchors"], 8 - current_core)
        self.assertEqual(x["latest_core_official_web_anchors"] +
                         x["historical_core_official_web_anchors"], 8)
        self.assertEqual(x["latest_growth_official_web_anchors"], 2)
        self.assertEqual(x["first_release_pilot_rows_unmapped_to_canonical"], 5)
        self.assertEqual(x["gbp_ons_rolling_month_evidence_only"], 3)
        self.assertEqual(x["certified_full_first_release_histories"], 0)
        self.assertEqual(x["eligible_live_macro_pillars"], 0)
        self.assertEqual(len(receipt["rows"]), 24)
        self.assertEqual(sum(bool(r["latest_anchor"]) for r in receipt["rows"]),
                         current_core + 2)
        for row in receipt["rows"]:
            self.assertGreater(row["observed_history_points_max"], 11)
            self.assertFalse(row["full_historical_pit_for_scoring"])
            self.assertFalse(row["eligible_for_shadow_intensity_training"])
            self.assertFalse(row["eligible_for_live_scoring"])
            self.assertFalse(row["complete_canonical_first_release_history_certified"])
            self.assertGreater(len(row["blocking_requirements"]), 2)
        for k in ("scores_computed", "model_parameters_fitted",
                  "safe_to_publish_new_D", "safe_to_update_pair_theses",
                  "writes_live_data"):
            self.assertIs(receipt[k], False)

    def test_cadence_preserved_and_growth_not_auto_selected(self):
        rows = {(r["currency"], r["pillar"]): r for r in self.report()["rows"]}
        self.assertEqual(rows["NZD", "inflation"]["frequency"], "Q")
        self.assertEqual(rows["NZD", "inflation"]["training_first_release_minimum"], 13)
        self.assertEqual(rows["AUD", "inflation"]["training_first_release_minimum"], 13)
        self.assertEqual(rows["USD", "labour"]["frequency"], "M")
        self.assertEqual(rows["USD", "labour"]["training_first_release_minimum"], 25)
        self.assertEqual(rows["USD", "labour"]["source_id"], "UNRATE")
        self.assertIsNone(rows["USD", "growth"]["source_id"])
        self.assertIsNone(rows["NZD", "growth"]["frequency"])
        self.assertEqual(rows["GBP", "labour"]["source_id"], "MGSX")
        self.assertEqual(rows["EUR", "inflation"]["source_transport"], "INTERMEDIARY_TRANSPORT")
        self.assertEqual(rows["NZD", "labour"]["source_transport"], "SECONDARY_MIRROR")

    def test_fingerprinted_bls_pilot_not_relabelled_as_unrate(self):
        self.assertRaisesRegex(
            ValueError, "mapping needs separate review",
            self.report, lambda p: p["registry"]["series"]["USD.labour"].update(
                series_id="LNS14000000"
            ),
        )

    def test_single_latest_core_official_value_must_match_observed(self):
        self.assertRaisesRegex(
            ValueError, "Core attestation value/period mismatch",
            self.report, lambda p: p["core"]["attestations"][0].update(
                published_value=999.0
            ),
        )

    def test_duplicate_core_latest_attestation_is_rejected(self):
        def mutation(p):
            p["core"]["attestations"].append(
                copy.deepcopy(p["core"]["attestations"][0])
            )
        self.assertRaisesRegex(ValueError, "duplicate or unknown", self.report, mutation)

    def test_future_core_attestation_period_is_rejected(self):
        self.assertRaisesRegex(
            ValueError, "Core attestation after current canonical period",
            self.report, lambda p: p["core"]["attestations"][0].update(
                observation_period="2026-12"
            ),
        )

    def test_jpy_september_current_release_is_date_only_not_training_pit(self):
        r = self.report()
        rows = {(x["currency"], x["pillar"]): x for x in r["rows"]}
        jpy = rows["JPY", "labour"]
        anchor = next(a for a in fixture()["core"]["attestations"]
                      if a["key"] == "JPY.labour")
        self.assertEqual(anchor["observation_period"], "2026-09")
        self.assertEqual(anchor["published_value"], 2.4)
        self.assertEqual(anchor["release_date"], "2026-10-30")
        self.assertEqual(jpy["latest_anchor"]["period"], "2026-09")
        self.assertEqual(jpy["latest_anchor"]["released_on"], "2026-10-30")
        self.assertFalse(jpy["latest_anchor"]["utc_release_time_verified"])
        self.assertTrue(jpy["latest_anchor_only"])
        self.assertFalse(jpy["eligible_for_live_scoring"])
        self.assertNotIn("JPY.labour", r["summary"]["historical_core_source_keys"])

    def test_stale_core_attestation_cannot_be_reissued_after_cutoff(self):
        def mutation(p):
            old = next(a for a in p["core"]["attestations"]
                       if a["key"] == "JPY.labour")
            old["release_date"] = "2026-11-01"
        self.assertRaisesRegex(
            ValueError, "Core publication outside observation/as-of chronology",
            self.report, mutation
        )

    def test_latest_release_cannot_exist_after_audit_cutoff(self):
        self.assertRaisesRegex(
            ValueError, "Core publication outside",
            self.report, lambda p: p["core"]["attestations"][0].update(
                release_date="2026-11-01"
            ),
        )

    def test_growth_attested_value_needs_exact_native_series(self):
        self.assertRaisesRegex(
            ValueError, "Growth latest anchor",
            self.report, lambda p: p["growth"]["attestations"][0].update(
                first_release_value=4.0
            ),
        )

    def test_growth_units_drift_is_rejected(self):
        self.assertRaisesRegex(
            ValueError, "Growth latest anchor",
            self.report, lambda p: p["growth"]["attestations"][0].update(
                units="percentage yoy instead of qoq"
            ),
        )

    def test_missing_live_core_history_is_not_automatically_padded(self):
        self.assertRaisesRegex(
            ValueError, "registry/observed history",
            self.report, lambda p: p["therm"]["currencies"]["CAD"]["labour"][
                "history"
            ].pop(),
        )

    def test_intermediary_transport_not_upgraded_to_official_direct(self):
        r = self.report()
        eur = next(x for x in r["rows"]
                   if x["currency"] == "EUR" and x["pillar"] == "labour")
        self.assertEqual(eur["source_transport"],
                         "CERTIFIED_OFFICIAL_TRANSPORT_REQUIRED")
        self.assertFalse(eur["eligible_for_shadow_intensity_training"])

    def test_bls_missing_or_duplicate_first_releases_are_rejected(self):
        self.assertRaisesRegex(
            ValueError, "five distinct",
            self.report, lambda p: p["bls"]["vintages"][1].update(
                observation_period=p["bls"]["vintages"][0]["observation_period"]
            ),
        )

    def test_rolling_ons_windows_not_assumed_to_have_utc_release_hours(self):
        self.assertRaisesRegex(
            ValueError, "not a complete release archive",
            self.report, lambda p: p["gbp"].update(
                released_at_timestamps_utc=["2026-10-20T06:00:00Z"]
            ),
        )

    def test_web_attestation_cannot_mark_full_pit_certified(self):
        self.assertRaisesRegex(
            ValueError, "cannot promote historical PIT",
            self.report, lambda p: p["core"].update(
                historical_full_PIT_vintage_certified=True
            ),
        )

    def test_consistent_receipts_and_documented_report(self):
        r = run(as_of=self.ASOF)
        self.assertEqual(r, self.report())
        m = markdown(r)
        self.assertIn("**0/24** certified full first-release histories", m)
        self.assertIn("| NZD | inflation | Q |", m)
        self.assertIn("| USD | growth | unselected |", m)
        self.assertEqual(r["as_of"], "2026-10-30")


if __name__ == "__main__":
    unittest.main()
