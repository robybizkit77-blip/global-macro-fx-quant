#!/usr/bin/env python3
"""Fail-closed, bounded public HTTP delivery verification for GitHub Pages.

GitHub may accept a gh-pages commit before its CDN serves the new bytes.
A single stale HTTP 200 is not proof of permanent deployment failure. Require
every exact file digest to converge within one shared time budget. Never call a
stale response a success. Emit evidence even on failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE_URL = "https://robybizkit77-blip.github.io/global-macro-fx-quant/"
FILES = (
    "live_data/sections/OIS_DATA.json",
    "live_data/sections/OIS_OPERATIONAL_VIEW.json",
    "dashboard/ois-operational-monitor-v1.js",
    "dashboard/cbdesk-operational-v1.js",
    # Assert exact public VIX source and loaded runtime payload, not only OIS/JS.
    "live_data/sections/D.json",
    "live_data/sections/MACRO_THERMOMETER_DATA.json",
    # Canonical source and thermometer must converge as separate exact-byte files.
    "live_data/sections/MACRO_SERIES.json",
    # Home Market Pulse: exact public bytes, not just network HTTP 200.
    "live_data/sections/NEWS_PULSE_OPERATIONAL.json",
    "live_data/sections/CALENDAR_OPERATIONAL_VIEW.json",
    # Every shipped runtime segment is required: a single stale part can
    # break FX pairs, the research monitor or the Home while part-00 looks OK.
    "index.html",
    *(f"payload/part-{i:02d}.txt" for i in range(16)),
    "dashboard/pairs-operational-v1.js",
    "dashboard/forwarddesk-operational-v1.js",
    "dashboard/currencies-operational-v1.js",
    "dashboard/macro-operational-v1.js",
    "dashboard/ratesdesk-operational-v1.js",
    # Keep the public derived COT story and manifest in exact-byte lockstep
    # with the runtime payload. A stale standalone file fails the release.
    "live_data/sections/V247_COT_STORIES.json",
    "live_data/sections/RATES_AUDIT_METADATA.json",
    "live_data/manifest.v2.json",
    # Previously missing/obsolete standalone reference feeds must converge too.
    "live_data/sections/NATIVE_CB_DATA.json",
    "live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json",
    "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json",
    # Source-to-UI exact-byte parity for RBNZ B2 context, never auto-promote
    # into the official NZD rate/OIS data source.
    "live_data/sections/NZD_B2_GOVT_WEB_REVIEW_CONTEXT.json",
    "live_data/sections/OIS_SOURCE_READINESS_VIEW.json",
    # Risk UI & fail-closed freshness must be delivered, not only risk data.
    "dashboard/risk-operational-v1.js",
    "dashboard/editorial-freshness-guard-v1.js",
    # Brent's secondary futures proxy is a separate displayed Risk input.
    "live_data/sections/ESTIMATED_RESIDUAL_GAPS.json",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(
    root: pathlib.Path,
    base_url: str,
    names: tuple[str, ...],
    *,
    budget_seconds: float,
    interval_seconds: float,
    timeout_seconds: float = 12.0,
) -> dict:
    if budget_seconds < 0 or interval_seconds < 0 or timeout_seconds <= 0:
        raise ValueError("invalid verification timings")
    if not base_url.endswith("/"):
        raise ValueError("base URL must end with /")
    expected = {name: sha256((root / name).read_bytes()) for name in names}
    observed: dict[str, dict] = {}
    deadline = time.monotonic() + budget_seconds
    attempt = 0
    while True:
        attempt += 1
        for name in names:
            error = None
            actual_hash = None
            status = None
            try:
                req = urllib.request.Request(
                    base_url + name,
                    headers={"User-Agent": "GMFQ-Pages-Delivery-Audit/2.0",
                             "Cache-Control": "no-cache", "Pragma": "no-cache"},
                )
                with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                    status = response.status
                    actual_hash = sha256(response.read())
                if status != 200 or actual_hash != expected[name]:
                    error = f"HTTP {status}; public content differs from validated main"
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                error = f"{type(exc).__name__}: {str(exc)[:120]}"
            observed[name] = {
                "path": name,
                "http_200_and_sha256_match": error is None,
                "http_status": status,
                "expected_sha256": expected[name],
                "public_sha256": actual_hash,
                "error": error,
            }
        all_match = all(observed[name]["http_200_and_sha256_match"] for name in names)
        if all_match or time.monotonic() >= deadline:
            break
        if attempt == 1 or attempt % 6 == 0:
            pending = [name for name in names if not observed[name]["http_200_and_sha256_match"]]
            print(f"PAGES_CDN_WAIT attempt={attempt} pending={pending}", flush=True)
        time.sleep(min(interval_seconds, max(0.0, deadline - time.monotonic())))
    return {
        "status": "PASS" if all_match else "FAIL",
        "basis": "PUBLIC_HTTP_200_EXACT_SHA256",
        "checks": [observed[name] for name in names],
        "attempts": attempt,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "max_wait_seconds": budget_seconds,
        "conclusion": "ALL_PUBLIC_FILES_MATCH" if all_match else "DELIVERY_NOT_CONVERGED",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default=BASE_URL)
    p.add_argument("--root", default=".")
    p.add_argument("--output", default="/tmp/pages-public-http-proof.json")
    p.add_argument("--budget-seconds", type=float, default=480.0)
    p.add_argument("--interval-seconds", type=float, default=10.0)
    args = p.parse_args()
    report = verify(
        pathlib.Path(args.root), args.base_url, FILES,
        budget_seconds=args.budget_seconds,
        interval_seconds=args.interval_seconds,
    )
    pathlib.Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print("PAGES_PUBLIC_HTTP_PROOF", json.dumps(report, sort_keys=True), flush=True)
    if report["status"] != "PASS":
        raise SystemExit("Public Pages content did not converge to validated main within budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
