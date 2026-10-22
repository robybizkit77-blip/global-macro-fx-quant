#!/usr/bin/env python3
"""Offline StatCan transport regression: never treat an error page as official CSV."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parent / "sources" / "cad_statcan_core.py"
spec = importlib.util.spec_from_file_location("cad_statcan_transport_under_test", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class Response:
    def __init__(self, content, content_type="application/zip"):
        self.content = content
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.content


def archive(name="18100004.csv", data=b"REF_DATE,VALUE\n2026-09,100\n"):
    result = io.BytesIO()
    with zipfile.ZipFile(result, mode="w") as z:
        z.writestr(name, data)
    return result.getvalue()


class StatCanTransportTests(unittest.TestCase):
    def test_valid_official_pid_archive(self):
        payload = archive(data=b"REF_DATE,VALUE\n2026-09,100\n")
        with patch.object(module.urllib.request, "urlopen", return_value=Response(payload)) as fetch:
            result = module.download_csv("18100004")
        self.assertEqual(result, "REF_DATE,VALUE\n2026-09,100\n")
        self.assertEqual(fetch.call_count, 1)

    def test_html_200_then_real_zip_bounded_retry(self):
        official = archive()
        with patch.object(module.urllib.request, "urlopen", side_effect=[
            Response(b"<html>temporary challenge</html>", "text/html"),
            Response(official),
        ]) as fetch, patch.object(module.time, "sleep") as sleep:
            result = module.download_csv("18100004")
        self.assertTrue(result.startswith("REF_DATE,VALUE"))
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(sleep.call_count, 1)

    def test_only_html_is_unavailable_and_not_a_candidate(self):
        with patch.object(module.urllib.request, "urlopen",
                          return_value=Response(b"<html>blocked</html>", "text/html")) as fetch, \
             patch.object(module.time, "sleep"):
            with self.assertRaisesRegex(module.StatCanTransportUnavailable, "ZIP signature absent"):
                module.download_csv("18100004")
        self.assertEqual(fetch.call_count, module.MAX_DOWNLOAD_ATTEMPTS)

    def test_corrupt_zip_is_unavailable_but_mismatched_pid_is_hard_failure(self):
        with patch.object(module.urllib.request, "urlopen",
                          return_value=Response(b"PK\x03\x04BROKEN")), \
             patch.object(module.time, "sleep"):
            with self.assertRaises(module.StatCanTransportUnavailable):
                module.download_csv("18100004")
        with patch.object(module.urllib.request, "urlopen",
                          return_value=Response(archive(name="14100287.csv"))) as fetch:
            with self.assertRaisesRegex(ValueError, "expected table CSV"):
                module.download_csv("18100004")
        self.assertEqual(fetch.call_count, 1, "wrong table must never be retried or accepted")

    def test_http_outage_exhausts_only_bounded_attempts(self):
        fail = urllib.error.HTTPError("https://www150.statcan.gc.ca/", 503,
                                      "Service Unavailable", None, None)
        with patch.object(module.urllib.request, "urlopen", side_effect=fail) as fetch, \
             patch.object(module.time, "sleep"):
            with self.assertRaises(module.StatCanTransportUnavailable):
                module.download_csv("18100004")
        self.assertEqual(fetch.call_count, module.MAX_DOWNLOAD_ATTEMPTS)

    def test_cli_exit_75_has_no_candidate_and_cannot_hide_other_errors(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "candidate.json"
            audit = Path(td) / "audit.json"
            argv = ["cad_statcan_core.py", "--dimension", "inflation",
                    "--output", str(output), "--audit-output", str(audit)]
            with patch.object(sys, "argv", argv), \
                 patch.object(module, "build_live_candidate",
                              side_effect=module.StatCanTransportUnavailable("offline fixture")), \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(module.main(), 75)
            self.assertIn("CAD_STATCAN_TRANSPORT_WITHHELD", stderr.getvalue())
            self.assertFalse(output.exists())
            self.assertFalse(audit.exists())
            with patch.object(sys, "argv", argv), \
                 patch.object(module, "build_live_candidate",
                              side_effect=ValueError("schema mismatch")):
                with self.assertRaisesRegex(ValueError, "schema mismatch"):
                    module.main()
            self.assertFalse(output.exists())
            self.assertFalse(audit.exists())


if __name__ == "__main__":
    unittest.main()
