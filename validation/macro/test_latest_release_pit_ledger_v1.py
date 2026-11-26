#!/usr/bin/env python3
"""PIT-date evidence negative tests from pinned official G8 source records."""
import copy
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.latest_release_pit_ledger_v1 import (
    ROOT, WEB_EVIDENCE_FILE, WEB_EVIDENCE_SUPPLEMENT_GLOB,
    build_ledger, collect_candidates, resolved_time, iso_day,
)

TODAY = datetime.now(ZoneInfo('Europe/Rome')).date()


class LatestReleaseLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.anchors = collect_candidates(ROOT / "validation/macro")

    def run_receipt(self, records=None):
        return build_ledger(ROOT, TODAY, self.anchors if records is None else records)

    def assert_pinned_release(self, key, period, day, timestamp=None, *, value=None, web=False):
        """Exercise an archived release independently of the moving live month."""
        pinned = [
            row for row in self.anchors.get((key, period), [])
            if row["date"] == day
            and resolved_time(row) == timestamp
            and (value is None or row["value"] == value)
            and (not web or row["source_kind"] == "OFFICIAL_WEB_RELEASE_UNHASHED")
        ]
        self.assertTrue(pinned, (key, period, day, timestamp))

        # Isolate the archived bucket for this series. A valid newer anchor
        # may exist, but it cannot hide a leak from the archived bucket.
        records = {target: rows for target, rows in self.anchors.items() if target[0] != key}
        records[(key, period)] = pinned
        observed = self.run_receipt(records)["observations"][key]
        release = observed["release"]
        if observed["current_observation_period"][:7] == period:
            self.assertEqual(release["status"], "FULL_RELEASE_INSTANT" if timestamp else "DATE_ONLY")
            self.assertEqual(release["first_release_date"], day)
            self.assertEqual(release["first_release_timestamp_utc"], timestamp)
            self.assertEqual(release["date_only_not_eligible_for_intraday_PIT"], timestamp is None)
            if web:
                self.assertTrue(release["latest_web_release_unhashed"])
        else:
            self.assertTrue(release["status"].startswith("WITHHELD"), (key, release))
            self.assertIsNone(release["first_release_date"], key)
            self.assertIsNone(release["first_release_timestamp_utc"], key)
            self.assertFalse(release["evidence_paths"], key)
        self.assertFalse(release["historical_backtest_safe_for_all_periods"], key)

    def synthetic_current_eur_date_only(self):
        """Test-only current-period evidence, never committed as an official release.

        The live EUR release period advances each month; mutating a pinned
        September 2026 anchor must not be mistaken for testing today's source.
        The ledger still must reject future, pre-period, conflicting values and
        duplicate first-release dates for the CURRENT source period.
        """
        live = self.run_receipt()["observations"]["EUR.inflation"]
        period = live["current_observation_period"][:7]
        row = {
            "date": TODAY.isoformat(),
            "value": live["latest_transformed_observation"],
            "source_path": "TEST_ONLY/synthetic_current_eur_date_only",
            "source_kind": "TEST_NEGATIVE_CONTROL_NOT_OFFICIAL",
            "official_reference": None,
            "source_sha256": None,
            "release_time_utc": None,
            "release_time_jst": None,
        }
        records = copy.deepcopy(self.anchors)
        records[("EUR.inflation", period)] = [row]
        return records, period

    def test_us_cpi_missing_annual_base_never_redates_release_evidence(self):
        row = self.run_receipt()["observations"]["USD.inflation"]
        raw_period = row["latest_raw_source_period"]
        transformed_period = row["current_observation_period"][:7]
        if row["documented_annual_base_gap"]:
            self.assertGreater(raw_period, transformed_period)
            records = {target: rows for target, rows in self.anchors.items()
                       if target[0] != "USD.inflation"}
            records[("USD.inflation", raw_period)] = [{
                "date": TODAY.isoformat(),
                "value": row["latest_transformed_observation"],
                "source_path": "TEST_ONLY/raw_period_must_not_certify_older_yoy",
                "source_kind": "TEST_NEGATIVE_CONTROL_NOT_OFFICIAL",
                "official_reference": None,
                "source_sha256": None,
                "release_time_utc": None,
                "release_time_jst": None,
            }]
            isolated = self.run_receipt(records)["observations"]["USD.inflation"]
            self.assertEqual(isolated["current_observation_period"][:7], transformed_period)
            self.assertTrue(isolated["release"]["status"].startswith("WITHHELD"))
            self.assertIsNone(isolated["release"]["first_release_date"])
        else:
            self.assertEqual(raw_period, transformed_period)

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
            elif release["status"] == "DATE_ONLY":
                self.assertIsNotNone(release["first_release_date"], key)
                self.assertIsNone(release["first_release_timestamp_utc"], key)
                self.assertTrue(release["date_only_not_eligible_for_intraday_PIT"], key)
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
        self.assertFalse(out["safe_to_promote_macro_labels"])
        self.assertFalse(out["safe_to_publish_new_D"])
        self.assertFalse(out["historical_vintage_series_available"])

    def test_official_web_anchors_remain_specific_to_their_reference_period(self):
        examples = (
            ("USD.inflation", "2026-09", "2026-10-14", "2026-10-14T12:30:00+00:00", None),
            ("AUD.labour", "2026-09", "2026-10-15", "2026-10-15T00:30:00+00:00", None),
            ("AUD.labour", "2026-10", "2026-11-19", "2026-11-19T00:30:00+00:00", 4.9),
            ("CAD.labour", "2026-09", "2026-10-09", None, 6.5),
            ("CAD.labour", "2026-10", "2026-11-06", "2026-11-06T13:30:00+00:00", 6.7),
            ("GBP.labour", "2026-09", "2026-11-17", "2026-11-17T07:00:00+00:00", 4.6),
            ("GBP.inflation", "2026-10", "2026-11-18", "2026-11-18T07:00:00+00:00", 3.6),
            ("AUD.inflation", "2026-09", "2026-10-28", "2026-10-28T00:30:00+00:00", 3.9),
            ("EUR.inflation", "2026-10", "2026-11-04", None, 4.0),
            ("EUR.labour", "2026-09", "2026-10-30", None, 6.5),
            ("JPY.inflation", "2026-09", "2026-10-23", None, 2.1),
            ("JPY.inflation", "2026-10", "2026-11-20", None, 2.3),
            ("NZD.labour", "2026-09", "2026-11-04", "2026-11-03T21:45:00+00:00", 5.7),
            ("USD.labour", "2026-10", "2026-11-06", "2026-11-06T13:30:00+00:00", 4.1),
            ("CAD.inflation", "2026-09", "2026-10-19", None, None),
            ("CAD.inflation", "2026-10", "2026-11-16", "2026-11-16T13:30:00+00:00",
             (170.4 / 165.3 - 1) * 100),
            ("JPY.labour", "2026-09", "2026-10-30", None, 2.4),
            ("CHF.inflation", "2026-10", "2026-11-03", None, 1.5),
        )
        for key, period, day, timestamp, value in examples:
            with self.subTest(key=key):
                self.assert_pinned_release(key, period, day, timestamp, value=value, web=True)

    def test_later_supplement_cannot_replace_an_official_release_period(self):
        pattern = WEB_EVIDENCE_SUPPLEMENT_GLOB
        original = pattern.replace("*", "2026-11-17")
        content = (ROOT / "validation/macro" / original).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / original).write_text(content, encoding="utf-8")
            (directory / pattern.replace("*", "2026-11-18")).write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "supplement would replace"):
                collect_candidates(directory)

    def test_jpy_august_archive_is_not_reissued_as_latest_first_release(self):
        self.assert_pinned_release("JPY.labour", "2026-08", "2026-10-02", value=2.5, web=True)

    def test_gbp_august_first_release_remains_date_only(self):
        self.assert_pinned_release("GBP.labour", "2026-08", "2026-10-20", value=4.7, web=True)

    def test_date_only_is_never_intraday_eligible(self):
        # The pinned 2-Oct date belongs to a HISTORICAL EUR observation.
        # If the live source has advanced, it must not be stamped current.
        previous = self.anchors.get(("EUR.inflation", "2026-09"), [])
        self.assertTrue(any(r["date"] == "2026-10-02" for r in previous))
        records, _period = self.synthetic_current_eur_date_only()
        eur = self.run_receipt(records)["observations"]["EUR.inflation"]["release"]
        self.assertEqual(eur["status"], "DATE_ONLY")
        self.assertEqual(eur["first_release_date"], TODAY.isoformat())
        self.assertIsNone(eur["first_release_timestamp_utc"])
        self.assertFalse(eur["release_clock_verified"])
        self.assertTrue(eur["date_only_not_eligible_for_intraday_PIT"])
        self.assertFalse(eur["historical_backtest_safe_for_all_periods"])

    def test_chf_archival_utc_instant_is_properly_converted(self):
        self.assert_pinned_release(
            "CHF.inflation", "2026-09", "2026-10-01", "2026-10-01T06:30:00+00:00",
        )

    def test_jpy_release_jst_crosses_previous_utc_day(self):
        self.assert_pinned_release(
            "JPY.inflation", "2026-08", "2026-09-18", "2026-09-17T23:30:00+00:00",
        )

    def test_september_uk_nz_headline_cpi_has_publisher_date_only_proof(self):
        from validation.macro.latest_release_pit_ledger_v1 import source_web_attestations
        evidence = source_web_attestations(ROOT / "validation/macro")
        by_period = {(row["key"], row["observation_period"]): row
                     for row in evidence["attestations"]}
        expected = (
            ("GBP.inflation", "2026-10-21", 3.5, "Office for National Statistics"),
            ("NZD.inflation", "2026-10-22", 3.7, "Stats NZ"),
        )
        out = self.run_receipt()
        for key, release_day, value, publisher in expected:
            with self.subTest(key=key):
                row = by_period[(key, "2026-09")]
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
        if rec["current_observation_period"][:7] == "2026-10":
            self.assertAlmostEqual(rec["latest_transformed_observation"], 3.09398862381848)
            self.assertEqual(rec["release"]["status"], "WITHHELD_EXACT_PERIOD_EVIDENCE")
            self.assertIsNone(rec["release"]["first_release_date"])
            self.assertFalse(rec["release"]["historical_backtest_safe_for_all_periods"])

    def test_chf_observed_capture_is_not_first_release(self):
        from validation.macro.latest_release_pit_ledger_v1 import observed_chf_labour_capture
        exact = 3.09398862381848
        captured = observed_chf_labour_capture(ROOT, "2026-10", exact, date(2026, 11, 25))
        self.assertEqual(captured["observed_at_utc"], "2026-11-23T21:26:47.345331+00:00")
        self.assertFalse(captured["first_release_exact_value_certified"])
        self.assertFalse(captured["eligible_for_historical_first_release_backtest"])
        self.assertFalse(captured["source_bytes_reverified"])
        self.assertIsNone(observed_chf_labour_capture(ROOT, "2026-10", exact, date(2026, 11, 22)))
        self.assertIsNone(observed_chf_labour_capture(ROOT, "2026-10", 3.1, date(2026, 11, 25)))
        row = self.run_receipt()["observations"]["CHF.labour"]
        if row["current_observation_period"][:7] == "2026-10":
            self.assertEqual(row["release"]["observed_exact_value_capture"], captured)
            self.assertEqual(row["release"]["status"], "WITHHELD_EXACT_PERIOD_EVIDENCE")
            self.assertIsNone(row["release"]["first_release_timestamp_utc"])

    def test_chf_observed_capture_rejects_false_first_release_claim(self):
        from validation.macro.latest_release_pit_ledger_v1 import observed_chf_labour_capture
        name = "20261123_0900--20261123_0900.json"
        row = json.loads((ROOT / "research/chf-labour-snb-vintages" / name).read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "research/chf-labour-snb-vintages"
            directory.mkdir(parents=True)
            row["source_capture"]["first_release_exact_value_certified"] = True
            (directory / name).write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError, "invalid CHF observed-edition provenance"):
                observed_chf_labour_capture(root, "2026-10", 3.09398862381848, date(2026, 11, 25))

    def test_chf_fso_attestation_is_inflation_only_and_rejects_spoofed_hosts(self):
        from validation.macro.latest_release_pit_ledger_v1 import source_web_attestations
        filename = "CORE_G8_OFFICIAL_RELEASE_WEB_SUPPLEMENT_2026-11-25.json"
        original = json.loads((ROOT / "validation/macro" / filename).read_text())
        for key, url, error in (
            ("CHF.inflation", "https://bfs.admin.ch.evil.example/cpi", "unsupported source publisher URL"),
            ("CHF.labour", "https://www.bfs.admin.ch/en/newnsb/UA8hylpLYO6i", "unknown/duplicate official source key"),
            ("CHF.inflation", "https://www.seco.admin.ch/example", "unsupported source publisher URL"),
        ):
            with self.subTest(key=key, url=url), tempfile.TemporaryDirectory() as tmp:
                data = copy.deepcopy(original)
                data["attestations"][0].update(key=key, url=url)
                (Path(tmp) / filename).write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, error):
                    source_web_attestations(Path(tmp), filename)

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
        data, period = self.synthetic_current_eur_date_only()
        data[("EUR.inflation", period)][0]["date"] = (TODAY + timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "future official release metadata"):
            self.run_receipt(data)

    def test_same_period_wrong_value_fails_closed(self):
        data, period = self.synthetic_current_eur_date_only()
        data[("EUR.inflation", period)][0]["value"] = 99.5
        with self.assertRaisesRegex(ValueError, "conflicting current-period pinned official value"):
            self.run_receipt(data)

    def test_inconsistent_same_period_official_dates_fail_closed(self):
        data, period = self.synthetic_current_eur_date_only()
        first_day = date.fromisoformat(period + "-01")
        if TODAY <= first_day:
            self.skipTest("Only one permissible release day inside the live reference period")
        row = copy.deepcopy(data[("EUR.inflation", period)][0])
        row["date"] = first_day.isoformat()
        data[("EUR.inflation", period)].append(row)
        with self.assertRaisesRegex(ValueError, "incompatible official first-release"):
            self.run_receipt(data)

    def test_pre_observation_release_date_fails_closed(self):
        data, period = self.synthetic_current_eur_date_only()
        for row in data[("EUR.inflation", period)]:
            row["date"] = (date.fromisoformat(period + "-01") - timedelta(days=1)).isoformat()
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
