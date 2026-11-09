"""V10 offline contract tests: four actuals, one BLS source, no false surprise."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

from validation.macro import capture_us_cpi_exact_actuals_v10 as v10
from validation.macro import preflight_us_cpi_official_actual_v8 as bls
from validation.macro.test_g8_metric_issuer_readiness_v8 import mock_bls
from validation.macro.freeze_exact_metric_forecasts_v9 import LEDGER as V9_LEDGER, read_rows
from validation.macro.freeze_pre_release_consensus_v1 import digest

BEFORE = datetime(2026, 11, 9, 17, 30, tzinfo=timezone.utc)
AFTER = datetime(2026, 11, 10, 13, 34, tzinfo=timezone.utc)
SEEN = AFTER + timedelta(seconds=17)
RAW = mock_bls("October", "Tuesday, November 10, 2026",
               hmo="increased 0.4", hyo="increased 3.4",
               cmo="rose 0.3", cyo="rose 2.7")
ISSUER = (bls.SOURCE, "www.bls.gov")


def sample_fetch(url, host):
    assert (url, host) == ISSUER
    return RAW, url


class BLSActualV10Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forecasts = read_rows(V9_LEDGER)
        assert len(cls.forecasts) >= 3

    def test_pre_release_never_fetches_future_actual(self):
        calls = []
        def prohibited(*args):
            calls.append(args)
            raise AssertionError("No future BLS page fetch allowed")
        rows, receipt = v10.capture(self.forecasts, [], BEFORE, prohibited)
        self.assertEqual(rows, [])
        self.assertEqual(receipt["source_status"], "BEFORE_RELEASE_NO_HTTP")
        self.assertEqual(receipt["certified_consensus_surprises"], 0)
        self.assertEqual(calls, [])

    def test_four_exact_metrics_one_source_one_snapshot_two_v9_links(self):
        rows, receipt = v10.capture(
            self.forecasts, [], AFTER, sample_fetch, observed_clock=lambda: SEEN)
        self.assertEqual(len(rows), 4)
        self.assertEqual(receipt["new_metrics_archived"], 4)
        self.assertEqual({r["metric_id"] for r in rows}, set(bls.KEYS))
        self.assertEqual({r["observed_at_utc"] for r in rows},
                         {"2026-11-10T13:34:17Z"})
        self.assertEqual(len({r["source_html_sha256"] for r in rows}), 1)
        result = {r["metric_id"]: r for r in rows}
        self.assertEqual(result["US_CPI_U_HEADLINE_MOM_SA"]["actual_percent"], 0.4)
        self.assertEqual(result["US_CPI_U_CORE_MOM_SA"]["actual_percent"], 0.3)
        self.assertEqual(result["US_CPI_U_HEADLINE_YOY_NSA"]["actual_percent"], 3.4)
        self.assertEqual(result["US_CPI_U_CORE_YOY_NSA"]["actual_percent"], 2.7)
        self.assertEqual(result["US_CPI_U_HEADLINE_MOM_SA"]
                         ["actual_minus_v9_provider_observation_pp"], 0.1)
        self.assertEqual(result["US_CPI_U_CORE_MOM_SA"]
                         ["actual_minus_v9_provider_observation_pp"], 0.1)
        self.assertIsNone(result["US_CPI_U_HEADLINE_YOY_NSA"]
                          ["actual_minus_v9_provider_observation_pp"])
        self.assertIsNone(result["US_CPI_U_CORE_YOY_NSA"]
                          ["actual_minus_v9_provider_observation_pp"])
        self.assertEqual(receipt["provider_observation_links"], 2)
        self.assertTrue(all(r["delta_is_certified_macro_surprise"] is False and
                            r["eligible_for_Core_Beta_Forward"] is False and
                            r["eligible_for_rates_or_fx_causality"] is False and
                            r["FX_signal"] is None for r in rows))
        v10.validate_actual_log(rows, self.forecasts)

    def test_old_september_page_not_promoted_to_october(self):
        old = mock_bls("September", "Wednesday, October 14, 2026")
        rows, receipt = v10.capture(
            self.forecasts, [], AFTER,
            fetch=lambda url, host: (old, url),
            observed_clock=lambda: SEEN)
        self.assertEqual(rows, [])
        self.assertEqual(receipt["source_status"],
                         "ISSUER_NOT_AVAILABLE_OR_EXACT_RELEASE_NOT_PARSABLE")

    def test_realistic_issuer_repeats_annual_core_in_later_section(self):
        # Actual Sept 2026 release repeats the 12-month core rate in its
        # later 'All items less food and energy' explanation, independently
        # of the introductory annual core line.
        repeated = RAW.replace(
            b"</body>",
            b" <h3>Table A. Percent changes in CPI</h3>"
            b"<p>All items | 0.4 | 3.4</p>"
            b"<h3>All items less food and energy</h3>"
            b"The index for all items less food and energy rose 2.7 percent "
            b"over the past 12 months. </body>")
        got = bls.parse(raw=repeated)["metric_actual_pct"]
        self.assertEqual(got["US_CPI_U_CORE_YOY_NSA"], 2.7)

    def test_conflicting_duplicate_annual_core_inside_intro_fails_closed(self):
        duplicate = RAW.replace(
            b"over the year.",
            b"over the year. The all items less food and energy index "
            b"rose 3.1 percent over the year.", 1)
        with self.assertRaises(bls.Pending):
            bls.parse(raw=duplicate)

    def test_idempotent_no_fetch_once_four_actuals_archived(self):
        first, _ = v10.capture(
            self.forecasts, [], AFTER, sample_fetch, observed_clock=lambda: SEEN)
        def prohibited(*args):
            raise AssertionError("Already archived: HTTP must never run")
        second, receipt = v10.capture(
            self.forecasts, first, AFTER + timedelta(hours=1), prohibited)
        self.assertEqual(second, first)
        self.assertEqual(receipt["source_status"], "FOUR_METRICS_ALREADY_ARCHIVED_NO_HTTP")

    def test_incorrect_official_final_url_or_source_failure_fails_closed(self):
        for fetch in (
            lambda u,h: (RAW, "https://example.com/news.release/cpi.htm"),
            lambda u,h: (_ for _ in ()).throw(OSError("BLS unavailable")),
            lambda u,h: (b"out of date",u),
        ):
            rows, receipt = v10.capture(
                self.forecasts, [], AFTER, fetch, observed_clock=lambda: SEEN)
            self.assertEqual(rows, [])
            self.assertEqual(receipt["new_metrics_archived"], 0)

    def test_no_http_after_first_observation_window(self):
        def fail(*args):
            raise AssertionError("No late fetch allowed")
        rows, receipt = v10.capture(
            self.forecasts, [], AFTER + timedelta(days=8), fail)
        self.assertEqual(rows, [])
        self.assertEqual(receipt["source_status"], "OUTSIDE_OBSERVATION_WINDOW_NO_HTTP")

    def test_capture_clock_after_successful_http(self):
        for clock in (AFTER - timedelta(seconds=1), datetime(2026,11,10,13,36),
                      AFTER + timedelta(days=8)):
            with self.subTest(clock=str(clock)), self.assertRaises(ValueError):
                v10.capture(self.forecasts, [], AFTER, sample_fetch,
                            observed_clock=lambda clock=clock: clock)

    def test_records_cannot_rewrite_actual_forecast_or_status(self):
        rows, _ = v10.capture(
            self.forecasts, [], AFTER, sample_fetch, observed_clock=lambda: SEEN)
        for edit in (
            lambda d: d[0].update(actual_percent=11),
            lambda d: d[0].update(delta_is_certified_macro_surprise=True),
            lambda d: d[0].update(v9_provider_observation_percent=99),
            lambda d: d[0].update(source_url="https://foo.example.com"),
            lambda d: d[1].update(previous_record_sha256="GENESIS"),
            lambda d: d.pop(),
        ):
            tampered = copy.deepcopy(rows)
            edit(tampered)
            with self.subTest(edit=str(edit)), self.assertRaises(ValueError):
                v10.validate_actual_log(tampered, self.forecasts)

    def test_even_rehashed_false_pit_is_rejected(self):
        rows, _ = v10.capture(
            self.forecasts, [], AFTER, sample_fetch, observed_clock=lambda: SEEN)
        wrong = copy.deepcopy(rows)
        wrong[0]["publisher_first_publication_PIT_verified"] = True
        previous = "GENESIS"
        for item in wrong:
            item["previous_record_sha256"] = previous
            item["record_sha256"] = digest({
                k:v for k,v in item.items() if k != "record_sha256"})
            previous = item["record_sha256"]
        with self.assertRaisesRegex(ValueError, "false surprise/causality"):
            v10.validate_actual_log(wrong, self.forecasts)

    def test_no_actual_without_v9_forecast_still_records_official_actual(self):
        rows, receipt = v10.capture(
            [], [], AFTER, sample_fetch, observed_clock=lambda: SEEN)
        self.assertEqual(len(rows), 4)
        self.assertEqual(receipt["provider_observation_links"], 0)
        self.assertTrue(all(x["v9_provider_observation_sha256"] is None and
                            x["actual_minus_v9_provider_observation_pp"] is None
                            for x in rows))
        v10.validate_actual_log(rows, [])

    def test_run_writes_only_new_research_ledger_and_existing_legacy_files_unchanged(self):
        old_v9 = V9_LEDGER.read_bytes()
        old_legacy = (
            v10.ROOT / "validation/macro/MACRO_PRE_RELEASE_CONSENSUS_LEDGER_V1.jsonl"
        ).read_bytes()
        old_legacy_actual = (
            v10.ROOT / "validation/macro/MACRO_OFFICIAL_ACTUAL_FIRST_SEEN_V1.jsonl"
        ).read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            actual_path = Path(folder) / "actuals.jsonl"
            receipt = v10.run(V9_LEDGER, actual_path, now=AFTER,
                              fetch=sample_fetch, observed_clock=lambda:SEEN)
            self.assertEqual(receipt["new_metrics_archived"], 4)
            bytes_first = actual_path.read_bytes()
            again = v10.run(V9_LEDGER, actual_path, now=AFTER,
                            fetch=sample_fetch, observed_clock=lambda:SEEN)
            self.assertEqual(again["new_metrics_archived"], 0)
            self.assertEqual(actual_path.read_bytes(), bytes_first)
        self.assertEqual(V9_LEDGER.read_bytes(), old_v9)
        self.assertEqual((v10.ROOT /
            "validation/macro/MACRO_PRE_RELEASE_CONSENSUS_LEDGER_V1.jsonl").read_bytes(),
            old_legacy)
        self.assertEqual((v10.ROOT /
            "validation/macro/MACRO_OFFICIAL_ACTUAL_FIRST_SEEN_V1.jsonl").read_bytes(),
            old_legacy_actual)


if __name__ == "__main__":
    unittest.main()
