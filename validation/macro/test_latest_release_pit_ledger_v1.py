#!/usr/bin/env python3
"""PIT-date evidence negative tests from pinned official G8 source records."""
import copy
import json
import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from validation.macro.latest_release_pit_ledger_v1 import (
    ROOT, WEB_EVIDENCE_FILE, build_ledger, collect_candidates, resolved_time, iso_day,
)

TODAY = datetime.now(ZoneInfo('Europe/Rome')).date()


class LatestReleaseLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.anchors = collect_candidates(ROOT / "validation/macro")

    def run_receipt(self, records=None):
        return build_ledger(ROOT, TODAY, self.anchors if records is None else records)

    def test_strict_latest_period_evidence_and_withheld(self):
        out = self.run_receipt()
        self.assertEqual(out["source_lineage"], "PASS")
        self.assertEqual(out["observations_checked"], 16)
        self.assertEqual(sum(out["counts"].values()), 16)
        # The live canonical period advances independently of archival release
        # attestations. Never require a stale August release to prove September.
        for key, record in out["observations"].items():
            release = record["release"]
            if release["status"] == "FULL_RELEASE_INSTANT":
                self.assertIsNotNone(release["first_release_date"], key)
                self.assertIsNotNone(release["first_release_timestamp_utc"], key)
                self.assertTrue(release["release_clock_verified"], key)
        withheld = [key for key, record in out["observations"].items()
                    if record["release"]["status"].startswith("WITHHELD")]
        self.assertEqual(out["unresolved_targets"], sorted(withheld))
        self.assertEqual(
            len(withheld), out["counts"]["WITHHELD_EXACT_PERIOD_EVIDENCE"]
            + out["counts"]["WITHHELD_OFFICIAL_SOURCE_VALUE_CONFLICT"])
        self.assertEqual(sum(out["counts"].values()), 16)
        for key in withheld:
            row = out["observations"][key]["release"]
            self.assertIsNone(row["first_release_date"], key)
            self.assertIsNone(row["first_release_timestamp_utc"], key)
            self.assertFalse(row["historical_backtest_safe_for_all_periods"], key)
        self.assertGreater(out["counts"]["DATE_ONLY"], 0)
        self.assertFalse(out["safe_to_promote_macro_labels"])
        self.assertFalse(out["safe_to_publish_new_D"])
        self.assertFalse(out["historical_vintage_series_available"])

    def test_new_latest_official_web_anchors_are_current_period_specific(self):
        out = self.run_receipt()
        usd = out["observations"]["USD.inflation"]
        self.assertEqual(usd["current_observation_period"], "2026-09")
        self.assertEqual(usd["release"]["first_release_date"], "2026-10-14")
        self.assertEqual(usd["release"]["first_release_timestamp_utc"],
                         "2026-10-14T12:30:00+00:00")
        self.assertTrue(usd["release"]["latest_web_release_unhashed"])
        self.assertEqual(out["observations"]["CAD.labour"]["release"]["first_release_date"],
                         "2026-10-09")
        self.assertEqual(out["observations"]["AUD.labour"]["release"]["first_release_timestamp_utc"],
                         "2026-10-15T00:30:00+00:00")
        self.assertEqual(out["observations"]["CAD.inflation"]["release"]["first_release_date"],
                         "2026-10-19")
        # The 2 October release documents AUGUST unemployment only. The
        # canonical e-Stat series has advanced to September: a previous-month
        # anchor cannot certify the latest period (nor its intraday clock).
        august = self.anchors.get(("JPY.labour", "2026-08"), [])
        self.assertTrue(any(r["date"] == "2026-10-02" and r["value"] == 2.5
                            for r in august))
        jpy = out["observations"]["JPY.labour"]
        self.assertEqual(jpy["current_observation_period"][:7], "2026-09")
        self.assertEqual(jpy["latest_transformed_observation"], 2.4)
        self.assertEqual(jpy["release"]["first_release_date"], "2026-10-30")
        self.assertEqual(jpy["release"]["status"], "DATE_ONLY")
        self.assertIsNone(jpy["release"]["first_release_timestamp_utc"])
        self.assertFalse(jpy["release"]["historical_backtest_safe_for_all_periods"])

    def test_jpy_august_archive_is_not_reissued_as_september_first_release(self):
        current = self.run_receipt()["observations"]["JPY.labour"]
        self.assertEqual(current["release"]["first_release_date"], "2026-10-30")
        self.assertEqual(current["release"]["status"], "DATE_ONLY")
        self.assertEqual(current["latest_transformed_observation"], 2.4)
        august = self.anchors.get(("JPY.labour", "2026-08"), [])
        self.assertTrue(any(r["date"] == "2026-10-02" and r["value"] == 2.5
                            for r in august))
        forged = copy.deepcopy(self.anchors)
        archived = next(r for r in forged[("JPY.labour", "2026-08")]
                        if r["date"] == "2026-10-02" and r["value"] == 2.5)
        forged[("JPY.labour", "2026-09")] = [copy.deepcopy(archived)]
        with self.assertRaisesRegex(ValueError,
                                    "conflicting current-period pinned official value"):
            self.run_receipt(forged)

    def test_gbp_two_period_first_release_corrected_without_promoting_macro_score(self):
        r = self.run_receipt()["observations"]["GBP.labour"]
        self.assertEqual(r["current_observation_period"], "2026-08-01")
        self.assertEqual(r["latest_transformed_observation"], 4.7)
        self.assertEqual(r["release"]["first_release_date"], "2026-10-20")
        self.assertEqual(r["release"]["status"], "DATE_ONLY")
        self.assertTrue(r["release"]["date_only_not_eligible_for_intraday_PIT"])
        self.assertFalse(r["release"]["historical_backtest_safe_for_all_periods"])

    def test_date_only_is_never_intraday_eligible(self):
        out = self.run_receipt()
        eur = out["observations"]["EUR.inflation"]["release"]
        self.assertEqual(eur["first_release_date"], "2026-10-02")
        self.assertIsNone(eur["first_release_timestamp_utc"])
        self.assertTrue(eur["date_only_not_eligible_for_intraday_PIT"])

    def test_chf_archival_utc_instant_is_properly_converted(self):
        chf = self.run_receipt()["observations"]["CHF.inflation"]["release"]
        self.assertEqual(chf["status"], "FULL_RELEASE_INSTANT")
        self.assertEqual(chf["first_release_timestamp_utc"], "2026-10-01T06:30:00+00:00")

    def test_jpy_release_jst_crosses_previous_utc_day(self):
        # Preserve the original, immutable August 2026 Tokyo release evidence.
        # The production series may now show a later month; August's official
        # timestamp cannot be reused as September's first-release timestamp.
        august_records = self.anchors[("JPY.inflation", "2026-08")]
        self.assertTrue(any(resolved_time(record) == "2026-09-17T23:30:00+00:00"
                            for record in august_records))
        live = self.run_receipt()["observations"]["JPY.inflation"]
        if live["current_observation_period"][:7] == "2026-08":
            self.assertEqual(live["release"]["status"], "FULL_RELEASE_INSTANT")
            self.assertEqual(live["release"]["first_release_timestamp_utc"],
                             "2026-09-17T23:30:00+00:00")
        elif live["current_observation_period"][:7] == "2026-09":
            self.assertEqual(live["release"]["status"], "WITHHELD_EXACT_PERIOD_EVIDENCE")
            self.assertIsNone(live["release"]["first_release_date"])
            self.assertIsNone(live["release"]["first_release_timestamp_utc"])
            self.assertFalse(live["release"]["historical_backtest_safe_for_all_periods"])

    def test_september_uk_nz_headline_cpi_has_publisher_date_only_proof(self):
        from validation.macro.latest_release_pit_ledger_v1 import source_web_attestations
        evidence = source_web_attestations(ROOT / "validation/macro")
        by_key = {row["key"]: row for row in evidence["attestations"]}
        expected = (
            ("GBP.inflation", "2026-10-21", 3.5, "Office for National Statistics"),
            ("NZD.inflation", "2026-10-22", 3.7, "Stats NZ"),
        )
        out = self.run_receipt()
        for key, release_day, value, publisher in expected:
            with self.subTest(key=key):
                row = by_key[key]
                self.assertEqual(row["observation_period"], "2026-09")
                self.assertEqual(row["release_date"], release_day)
                self.assertEqual(row["published_value"], value)
                self.assertEqual(row["raw_series_value"], value)
                self.assertEqual(row["transform"], "reported_yoy_rate")
                self.assertEqual(row["publisher"], publisher)
                self.assertIsNone(row["release_timestamp_local"])
                # Once later official releases arrive, September's immutable
                # attestation stays in the archive but no longer proves the
                # current period. Do not redate stale evidence.
                rec = out["observations"][key]
                if rec["current_observation_period"][:7] == "2026-09":
                    self.assertEqual(rec["release"]["status"], "DATE_ONLY")
                    self.assertEqual(rec["release"]["first_release_date"], release_day)
                    self.assertIsNone(rec["release"]["first_release_timestamp_utc"])
                    self.assertFalse(rec["release"]["historical_backtest_safe_for_all_periods"])

    def test_swiss_rounded_seco_press_release_cannot_certify_exact_snb_value(self):
        out = self.run_receipt()
        rec = out["observations"]["CHF.labour"]
        if rec["current_observation_period"][:7] == "2026-09":
            # Official SECO September headline is rounded to 3.1%; the
            # canonical SNB portal stores a much more precise figure.
            # Do not infer the exact official initial-release value from 3.1.
            self.assertAlmostEqual(rec["latest_transformed_observation"], 3.1249882357461)
            self.assertEqual(rec["release"]["status"], "WITHHELD_EXACT_PERIOD_EVIDENCE")
            self.assertIsNone(rec["release"]["first_release_date"])
            self.assertFalse(rec["release"]["historical_backtest_safe_for_all_periods"])

    def test_nzd_official_source_url_cannot_use_spoofed_hostname(self):
        from validation.macro.latest_release_pit_ledger_v1 import source_web_attestations
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            d = json.loads((ROOT / "validation/macro" / WEB_EVIDENCE_FILE).read_text())
            nz = next(r for r in d["attestations"] if r["key"] == "NZD.inflation")
            nz["url"] = "https://stats.govt.nz.evil.example/news/cpi"
            (Path(temp) / WEB_EVIDENCE_FILE).write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError, "unsupported source publisher URL"):
                source_web_attestations(Path(temp))

    def test_future_release_in_evidence_fails_closed(self):
        data = copy.deepcopy(self.anchors)
        row = data[("EUR.inflation", "2026-09")][0]
        row["date"] = (TODAY + timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "future official release metadata"):
            self.run_receipt(data)

    def test_same_period_wrong_value_fails_closed(self):
        data = copy.deepcopy(self.anchors)
        row = data[("EUR.inflation", "2026-09")][0]
        row["value"] = 99.5
        # The other anchored sources for the same period still agree; test
        # that a single inconsistent official source cannot be silently used.
        with self.assertRaisesRegex(ValueError, "conflicting current-period pinned official value"):
            self.run_receipt(data)

    def test_inconsistent_same_period_official_dates_fail_closed(self):
        data = copy.deepcopy(self.anchors)
        row = copy.deepcopy(data[("EUR.inflation", "2026-09")][0])
        row["date"] = "2026-10-03"
        data[("EUR.inflation", "2026-09")].append(row)
        with self.assertRaisesRegex(ValueError, "incompatible official first-release"):
            self.run_receipt(data)

    def test_pre_observation_release_date_fails_closed(self):
        data = copy.deepcopy(self.anchors)
        for row in data[("EUR.inflation", "2026-09")]:
            row["date"] = "2026-08-29"
        with self.assertRaisesRegex(ValueError, "publication before reference month"):
            self.run_receipt(data)


    def test_web_source_does_not_accept_official_domain_spoofing(self):
        from validation.macro.latest_release_pit_ledger_v1 import source_web_attestations
        import json, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            original = json.loads((ROOT / "validation/macro/CORE_G8_OFFICIAL_RELEASE_WEB_ATTESTATIONS_2026-10-20.json").read_text())
            original["attestations"][0]["url"] = "https://bls.gov.evil.example/release"
            (directory / WEB_EVIDENCE_FILE).write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError, "unsupported source publisher URL"):
                source_web_attestations(directory)

    def test_yoy_calculation_cannot_be_rounded_to_headline(self):
        from validation.macro.latest_release_pit_ledger_v1 import source_web_attestations
        import json, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            original = json.loads((ROOT / "validation/macro/CORE_G8_OFFICIAL_RELEASE_WEB_ATTESTATIONS_2026-10-20.json").read_text())
            original["attestations"][0]["published_value"] = 3.7
            (directory / WEB_EVIDENCE_FILE).write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError, "official index-to-YoY formula mismatch"):
                source_web_attestations(directory)

    def test_official_source_conflict_cannot_be_silently_resolved(self):
        from validation.macro.latest_release_pit_ledger_v1 import source_web_attestations
        import json, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            original = json.loads((ROOT / "validation/macro/CORE_G8_OFFICIAL_RELEASE_WEB_ATTESTATIONS_2026-10-20.json").read_text())
            original["attestations"] = [r for r in original["attestations"] if r["key"] != "GBP.labour"]
            original["contradictions"].append({
                "key":"GBP.labour","observation_period":"2026-08",
                "release_date":"2026-10-20",
                "canonical_value":4.7,"official_first_release_value":4.7,
                "url":"https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/employmentintheuk/october2026",
                "note":"Deliberately forged duplicate equal source conflict that should not pass source evidence"
            })
            (directory / WEB_EVIDENCE_FILE).write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError, "source contradiction must be real"):
                source_web_attestations(directory)

    def test_missing_release_time_does_not_become_midnight(self):
        rec = {"date": "2026-10-02", "release_time_utc": None, "release_time_jst": None}
        self.assertIsNone(resolved_time(rec))

    def test_utc_clock_and_jst_clock_simultaneously_rejected(self):
        rec = {"date": "2026-10-02", "release_time_utc": "06:00",
               "release_time_jst": "09:00"}
        with self.assertRaisesRegex(ValueError, "conflicting time zones"):
            resolved_time(rec)

    def test_malformed_date_rejected(self):
        with self.assertRaises(ValueError):
            iso_day("2026-13-01", "test")


if __name__ == "__main__":
    unittest.main()
