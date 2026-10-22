#!/usr/bin/env python3
"""Deterministic, network-free negative tests for CHF SNB read-only capture."""
import json
import unittest
from datetime import datetime, timezone, timedelta
from validation.macro.capture_chf_labour_snb_vintage_v1 import (
    LABEL, URL, MAX_BYTES, parse_source, record_capture,
)


def raw_series(values=None, label=LABEL):
    values = values if values is not None else [
        {"date": "2026-08", "value": 3.13682671641221},
        {"date": "2026-09", "value": 3.1249882357461},
    ]
    return json.dumps({"timeseries": [{"header": [
        {"dim": "Overview", "dimItem": label}], "values": values}]}).encode()


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.t0 = datetime(2026, 10, 22, 11, 30, tzinfo=timezone.utc)
        self.t1 = self.t0 + timedelta(seconds=2)

    def record(self, raw=None, response_url=URL, expected_period=None):
        return record_capture(raw if raw is not None else raw_series(),
                              {"date": "Thu, 22 Oct 2026 11:30:01 GMT", "etag": '"abc"'},
                              self.t0, self.t1, response_url,
                              expected_period=expected_period)

    def test_pinned_series_readonly_capture_not_first_release(self):
        row = self.record(expected_period="2026-09")
        self.assertEqual(row["latest_value"], 3.1249882357461)
        self.assertEqual(row["observation_count"], 2)
        self.assertEqual(row["latest_period"], "2026-09")
        self.assertEqual(len(row["raw_payload_sha256"]), 64)
        self.assertEqual(row["retrieval_started_utc"], "2026-10-22T11:30:00+00:00")
        self.assertIsNone(row["first_release_instant_utc"])
        self.assertFalse(row["first_release_exact_value_certified"])
        self.assertFalse(row["historical_vintages_certified"])
        self.assertFalse(row["safe_to_publish_new_D"])
        self.assertFalse(row["live_data_written"])

    def test_wrong_exact_source_identity_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "ambiguous seasonally adjusted"):
            self.record(raw_series(label="Jobless rate - Not seasonally adjusted"))

    def test_duplicated_series_identity_fails_closed(self):
        doc = json.loads(raw_series())
        doc["timeseries"].append(doc["timeseries"][0])
        with self.assertRaisesRegex(ValueError, "ambiguous seasonally adjusted"):
            self.record(json.dumps(doc).encode())

    def test_duplicate_month_even_equal_value_fails_closed(self):
        vals = [{"date": "2026-09", "value": 3.1}] * 2
        with self.assertRaisesRegex(ValueError, "duplicate month"):
            self.record(raw_series(vals))

    def test_invalid_period_or_value_fails_closed(self):
        for x in (float("nan"), "3.1", True, None):
            with self.subTest(value=repr(x)), self.assertRaisesRegex(ValueError, "invalid numeric"):
                self.record(raw_series([{"date": "2026-09", "value": x}]))
        with self.assertRaisesRegex(ValueError, "invalid monthly period"):
            self.record(raw_series([{"date": "2026-13", "value": 3.1}]))

    def test_wrong_latest_period_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "differs from explicit"):
            self.record(expected_period="2026-10")

    def test_redirect_to_untrusted_host_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unexpected final source URL"):
            self.record(response_url="https://data.snb.ch.evil.example/api/cube/amarbma/data/json/en")
        with self.assertRaisesRegex(ValueError, "unexpected final source URL"):
            self.record(response_url="https://data.snb.ch/api/cube/other/data/json/en")

    def test_bad_clock_or_payload_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid retrieval UTC clock"):
            record_capture(raw_series(), {}, self.t1, self.t0, URL)
        with self.assertRaisesRegex(ValueError, "missing or oversized"):
            self.record(b"")
        with self.assertRaisesRegex(ValueError, "missing or oversized"):
            self.record(b"x" * (MAX_BYTES + 1))

    def test_json_shape_rejected(self):
        for raw in (b"{}", b"[]", b"null"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_source(raw)


if __name__ == "__main__":
    unittest.main()
