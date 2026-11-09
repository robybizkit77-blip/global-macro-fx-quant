"""V9 deterministic regression tests: source-observed is never certified consensus."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from validation.macro import freeze_exact_metric_forecasts_v9 as v9
from validation.macro.g8_metric_issuer_contract_v8 import enumerate_secondary_candidates
from validation.macro.freeze_pre_release_consensus_v1 import digest

ROOT = Path(__file__).resolve().parents[2]
CALENDAR = json.loads((ROOT / "live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json").read_text())
BEFORE = datetime(2026, 11, 9, 16, 0, tzinfo=timezone.utc)
AFTER = datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc)
FEED_TIME = "2026-11-09T15:40:00Z"


def feed(rows, at=FEED_TIME):
    return {
        "schema": "GMFQ_MACRO_CONSENSUS_SECONDARY_V1",
        "provider": v9.PROVIDER,
        "provider_endpoint": v9.ENDPOINT,
        "provider_field": "forecast",
        "generated_at_utc": at,
        "rules": {
            "metric_candidates_not_frozen_and_never_promoted": True,
            "actual_not_used_as_pre_release_consensus": True,
        },
        "metric_candidates_research_v8":
            enumerate_secondary_candidates(CALENDAR, rows, now=BEFORE),
    }


def source_rows():
    return [
        {"currency": "USD", "date": "2026-11-10",
         "event": "CPI m/m", "consensus": "0.3%"},
        {"currency": "USD", "date": "2026-11-10",
         "event": "CPI y/y", "consensus": "3.5%"},
        {"currency": "USD", "date": "2026-11-10",
         "event": "Core CPI m/m", "consensus": "0.2%"},
        {"currency": "USD", "date": "2026-11-10",
         "event": "Core CPI y/y", "consensus": "2.9%"},
        {"currency": "GBP", "date": "2026-11-12",
         "event": "Prelim GDP q/q", "consensus": "0.7%"},
        {"currency": "CHF", "date": "2026-11-16",
         "event": "Swiss GDP q/q", "consensus": "0.2%"},
    ]


class FirstSeenV9(unittest.TestCase):
    def test_each_cpi_series_is_separate_and_no_surprises(self):
        rows, receipt = v9.freeze(CALENDAR, feed(source_rows()), [], BEFORE)
        self.assertEqual(len(rows), 6)
        self.assertEqual(receipt["new_metrics_observed_before_release"], 6)
        ids = {r["metric_id"] for r in rows}
        self.assertEqual(len(ids), 6)
        self.assertTrue({"US_CPI_U_HEADLINE_MOM_SA", "US_CPI_U_HEADLINE_YOY_NSA",
                         "US_CPI_U_CORE_MOM_SA", "US_CPI_U_CORE_YOY_NSA"} <= ids)
        self.assertTrue(all(r["actual"] is None and r["surprise"] is None and
                            r["FX_signal"] is None and
                            r["eligible_for_macro_surprise"] is False and
                            r["eligible_for_live_model"] is False for r in rows))
        self.assertTrue(receipt["not_survey_consensus_certified"])
        self.assertTrue(receipt["existing_usd_cad_forecast_ledger_untouched"])
        v9.validate_existing(rows)

    def test_same_metric_second_forecast_does_not_overwrite_first(self):
        initial, _ = v9.freeze(CALENDAR, feed(source_rows()), [], BEFORE)
        altered = source_rows()
        altered[0]["consensus"] = "0.9%"
        second, receipt = v9.freeze(
            CALENDAR, feed(altered, "2026-11-09T15:59:00Z"),
            initial, datetime(2026, 11, 9, 16, 1, tzinfo=timezone.utc))
        self.assertEqual(second, initial)
        self.assertEqual(receipt["new_metrics_observed_before_release"], 0)
        self.assertEqual(second[0]["previous_record_sha256"], "GENESIS")

    def test_no_capture_after_official_release_or_feed_generated_after_it(self):
        rows, receipt = v9.freeze(CALENDAR, feed(source_rows()),
                                  [], AFTER)
        self.assertEqual({r["currency"] for r in rows}, {"GBP", "CHF"})
        self.assertEqual(receipt["skipped"]["NO_VERIFIED_PRE_RELEASE_RUNNER_OBSERVATION"], 4)
        future_feed = feed(source_rows(), "2026-11-10T13:31:00Z")
        later = datetime(2026, 11, 10, 13, 32, tzinfo=timezone.utc)
        rows, _ = v9.freeze(CALENDAR, future_feed, [], later)
        self.assertTrue(all(r["currency"] != "USD" for r in rows))

    def test_wrong_unit_or_wrong_metric_id_fails_closed(self):
        x = feed(source_rows())
        x["metric_candidates_research_v8"][0]["unit"] = "PCT_YOY_NSA"
        rows, receipt = v9.freeze(CALENDAR, x, [], BEFORE)
        self.assertEqual(len(rows), 5)
        self.assertEqual(receipt["skipped"]["SERIES_IDENTITY_OR_V8_GUARDS_MISMATCH"], 1)

    def test_source_label_must_match_registered_exact_metric(self):
        x = feed(source_rows())
        x["metric_candidates_research_v8"][0]["provider_event"] = "CPI"
        rows, receipt = v9.freeze(CALENDAR, x, [], BEFORE)
        self.assertEqual(len(rows), 5)
        self.assertEqual(receipt["skipped"]["SERIES_IDENTITY_OR_V8_GUARDS_MISMATCH"], 1)

    def test_malformed_and_non_percent_forecast_rejected(self):
        x = feed(source_rows())
        x["metric_candidates_research_v8"][0]["forecast"] = "0.3"
        x["metric_candidates_research_v8"][1]["forecast"] = "not available"
        rows, receipt = v9.freeze(CALENDAR, x, [], BEFORE)
        self.assertEqual(len(rows), 4)
        self.assertEqual(receipt["skipped"]["PROVIDER_FORECAST_MISSING_OR_UNIT_UNPROVEN"], 2)

    def test_duplicated_metric_is_not_chosen_by_order(self):
        x = feed(source_rows())
        x["metric_candidates_research_v8"].append(
            copy.deepcopy(x["metric_candidates_research_v8"][0]))
        rows, receipt = v9.freeze(CALENDAR, x, [], BEFORE)
        self.assertEqual(len(rows), 5)
        self.assertEqual(receipt["skipped"]["DUPLICATE_METRIC_PROVIDER_CANDIDATES"], 2)

    def test_clock_and_provider_not_fabricated(self):
        with self.assertRaisesRegex(ValueError, "generated after capture"):
            v9.freeze(CALENDAR, feed(source_rows()),
                      [], datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc))
        x = feed(source_rows())
        x["provider_endpoint"] = "https://not-the-issuer.invalid"
        with self.assertRaisesRegex(ValueError, "source"):
            v9.freeze(CALENDAR, x, [], BEFORE)

    def test_tamper_detection_value_and_chain(self):
        rows, _ = v9.freeze(CALENDAR, feed(source_rows()), [], BEFORE)
        changed = copy.deepcopy(rows)
        changed[0]["forecast_value_percent"] = 50.
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            v9.validate_existing(changed)
        changed = copy.deepcopy(rows)
        changed[1]["previous_record_sha256"] = "GENESIS"
        changed[1]["record_sha256"] = digest({
            k: v for k, v in changed[1].items() if k != "record_sha256"})
        with self.assertRaisesRegex(ValueError, "chain mismatch"):
            v9.validate_existing(changed)

    def test_run_writes_separate_ledger_and_does_not_modify_existing_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            seed, src, out = [p / name for name in
                              ("official.json", "feed.json", "first_seen.jsonl")]
            seed.write_text(json.dumps(CALENDAR))
            src.write_text(json.dumps(feed(source_rows())))
            first = v9.run(seed, src, out, captured_at=BEFORE)
            self.assertEqual(first["new_metrics_observed_before_release"], 6)
            raw = out.read_bytes()
            second = v9.run(seed, src, out, captured_at=BEFORE)
            self.assertEqual(second["new_metrics_observed_before_release"], 0)
            self.assertEqual(out.read_bytes(), raw)
            original = ROOT / "validation/macro/MACRO_PRE_RELEASE_CONSENSUS_LEDGER_V1.jsonl"
            self.assertEqual(len(original.read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
