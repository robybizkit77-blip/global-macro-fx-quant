#!/usr/bin/env python3
"""Offline fail-closed tests for official BLS transient HTTP transport failures."""
from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from validation.sources import us_bls_core_macro as bls
from validation import macro_adapter_pit_handoff as handoff


def http_error(status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(bls.API_URL, status, "simulated", {}, None)


class BlsTransportQuarantineTests(unittest.TestCase):
    def test_503_retries_only_three_times_then_raises_distinct_transport_error(self):
        with mock.patch.object(bls.urllib.request, "urlopen", side_effect=http_error(503)) as opener, \
                mock.patch.object(bls.time, "sleep") as sleep:
            with self.assertRaisesRegex(bls.BlsTransportUnavailable, "HTTP 503 after 3 attempts"):
                bls.fetch_payload(2024, 2026)
        self.assertEqual(opener.call_count, 3)
        self.assertEqual(sleep.call_args_list, [mock.call(1), mock.call(2)])

    def test_second_attempt_with_genuine_json_response(self):
        payload = {"status": "REQUEST_SUCCEEDED", "Results": {"series": []}}
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        with mock.patch.object(bls.urllib.request, "urlopen", side_effect=[http_error(503), response]) as opener, \
                mock.patch.object(bls.time, "sleep") as sleep:
            self.assertEqual(bls.fetch_payload(2024, 2026), payload)
        self.assertEqual(opener.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_401_authentication_failure_does_not_get_quarantined(self):
        with mock.patch.object(bls.urllib.request, "urlopen", side_effect=http_error(401)) as opener, \
                mock.patch.object(bls.time, "sleep") as sleep:
            with self.assertRaises(urllib.error.HTTPError):
                bls.fetch_payload(2024, 2026)
        self.assertEqual(opener.call_count, 1)
        sleep.assert_not_called()

    def test_bad_bls_payload_remains_fatal_parser_error(self):
        with self.assertRaises(ValueError):
            bls.parse_series({"status": "REQUEST_FAILED", "message": ["bad series"]}, bls.LABOUR_BLS_SERIES)

    def test_bls_main_emits_no_candidate_or_audit_when_transport_unavailable(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(bls, "fetch_payload", side_effect=bls.BlsTransportUnavailable("simulated")), \
                mock.patch("sys.argv", ["us_bls_core_macro.py", "--output-dir", d]):
            self.assertEqual(bls.main(), 76)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_handoff_only_quarantines_registered_usd_bls_exit_76(self):
        entry = {"authority": "U.S. Bureau of Labor Statistics"}
        route = {"adapter": "validation/sources/us_bls_core_macro.py", "transport": "OFFICIAL_DIRECT"}
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(handoff, "registered_target", return_value=(entry, route, "US_CPIAUCSL_history_value")), \
                mock.patch.object(handoff, "run_adapter", side_effect=subprocess.CalledProcessError(76, ["bls"])), \
                mock.patch("sys.argv", ["macro_adapter_pit_handoff.py", "--currency", "USD", "--dimension", "inflation", "--output", f"{d}/candidate.json", "--audit-output", f"{d}/audit.json"]):
            self.assertEqual(handoff.main(), 76)
            self.assertFalse((Path(d) / "candidate.json").exists())
            self.assertFalse((Path(d) / "audit.json").exists())

    def test_handoff_does_not_hide_non_bls_pit_or_transport_failure(self):
        entry = {"authority": "U.S. Bureau of Labor Statistics"}
        other_route = {"adapter": "validation/sources/not-the-certified-bls.py", "transport": "OFFICIAL_DIRECT"}
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(handoff, "registered_target", return_value=(entry, other_route, "US_CPIAUCSL_history_value")), \
                mock.patch.object(handoff, "run_adapter", side_effect=subprocess.CalledProcessError(76, ["other"])), \
                mock.patch("sys.argv", ["macro_adapter_pit_handoff.py", "--currency", "USD", "--dimension", "inflation", "--output", f"{d}/candidate.json", "--audit-output", f"{d}/audit.json"]):
            with self.assertRaises(subprocess.CalledProcessError):
                handoff.main()


if __name__ == "__main__":
    unittest.main()
