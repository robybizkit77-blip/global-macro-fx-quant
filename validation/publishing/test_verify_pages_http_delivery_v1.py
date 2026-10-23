#!/usr/bin/env python3
"""Local HTTP regression: public stale bytes must retry, never pass prematurely."""
from __future__ import annotations

import json
import pathlib
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from verify_pages_http_delivery_v1 import FILES, verify


def case(delayed: bool) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        for idx, name in enumerate(FILES):
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(f"source-{idx}".encode())
        requests = {"n": 0}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests["n"] += 1
                name = self.path.lstrip("/")
                if name not in FILES:
                    self.send_error(404)
                    return
                # One outdated CDN reply, then the verified bytes; or a
                # permanently outdated endpoint if delayed=False.
                outdated = name == FILES[0] and (requests["n"] == 1 if delayed else True)
                payload = b"old-cdn-copy" if outdated else (root / name).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                pass

        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            return verify(
                root,
                f"http://127.0.0.1:{srv.server_address[1]}/",
                FILES,
                budget_seconds=1.0 if delayed else 0.0,
                interval_seconds=0.01,
                timeout_seconds=0.5,
            )
        finally:
            srv.shutdown()
            srv.server_close()
            thread.join(timeout=3)


def main():
    # VIX must stay in the public HTTP proof after future refactors.
    assert "live_data/sections/D.json" in FILES
    assert "live_data/sections/MACRO_THERMOMETER_DATA.json" in FILES
    assert "live_data/sections/NEWS_PULSE_OPERATIONAL.json" in FILES
    assert "live_data/sections/CALENDAR_OPERATIONAL_VIEW.json" in FILES
    assert "payload/part-00.txt" in FILES
    assert "live_data/sections/V247_COT_STORIES.json" in FILES
    assert "live_data/sections/RATES_AUDIT_METADATA.json" in FILES
    assert "live_data/sections/OIS_DATA.json" in FILES
    assert "live_data/manifest.v2.json" in FILES
    assert "live_data/sections/NATIVE_CB_DATA.json" in FILES
    assert "live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json" in FILES
    assert "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json" in FILES
    assert "live_data/sections/OIS_SOURCE_READINESS_VIEW.json" in FILES
    assert "dashboard/risk-operational-v1.js" in FILES
    assert "dashboard/editorial-freshness-guard-v1.js" in FILES
    assert "live_data/sections/ESTIMATED_RESIDUAL_GAPS.json" in FILES
    success = case(True)
    assert success["status"] == "PASS", success
    assert success["attempts"] >= 2, success
    assert all(x["http_200_and_sha256_match"] for x in success["checks"])
    failure = case(False)
    assert failure["status"] == "FAIL", failure
    assert failure["attempts"] == 1
    assert failure["conclusion"] == "DELIVERY_NOT_CONVERGED"
    assert failure["checks"][0]["public_sha256"] != failure["checks"][0]["expected_sha256"]
    print("PAGES_PUBLIC_HTTP_BOUNDED_CONVERGENCE_V1_PASS", json.dumps({
        "eventual_consistency_attempts": success["attempts"],
        "permanent_failure": failure["conclusion"],
    }))


if __name__ == "__main__":
    main()
