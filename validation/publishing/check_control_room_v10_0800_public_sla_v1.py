#!/usr/bin/env python3
"""Read-only v10 08:00 receipt: root runtime, market mirrors AND preview assets.

Runs after the independently triggered Control Room market publisher. A PASS
requires same-day source readiness and HTTP 200/exact SHA-256 of the complete
tracked v10 delivery surface by 08:00 Rome. It does not claim browser rendering,
nor does it alter the site, rank, OOS model, Beta or Forward.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from check_pages_0800_delivery_sla_v1 import evaluate
from check_pages_morning_readiness_v1 import in_morning_window, evaluate as source_evaluate
from verify_pages_http_delivery_v1 import BASE_URL, FILES as DASHBOARD_FILES, verify
from verify_control_room_market_delivery_v1 import FILES as MARKET_FILES

PREVIEW_FILES = (
    "site/control-room-preview/index.html",
    "site/control-room-preview/home-navigation-v10.js",
    "site/control-room-preview/ois-pricing-estimates-v1.js",
)
V10_FILES = tuple(dict.fromkeys((*DASHBOARD_FILES, *MARKET_FILES, *PREVIEW_FILES)))


def run(now: dt.datetime, root: Path, base_url: str, *, auditor=verify) -> dict:
    if not in_morning_window(now):
        receipt = evaluate({"morning_gate_required": False}, None, now, expected_files=V10_FILES)
        receipt["schema"] = "GMFQ_CONTROL_ROOM_V10_0800_PUBLIC_SLA_V1"
        receipt["scope"] = "V10_NOT_IN_MORNING_WINDOW"
        return receipt

    try:
        source = source_evaluate(now)
    except Exception as exc:
        source = {
            "schema": "GMFQ_PAGES_MORNING_SOURCE_GATE_V1",
            "morning_gate_required": True,
            "status": "BLOCK_SOURCE_AUDIT_EXCEPTION",
            "critical_daily_problems": [type(exc).__name__],
        }
    try:
        public = auditor(root, base_url, V10_FILES,
                         budget_seconds=0, interval_seconds=0, timeout_seconds=3.0)
    except (OSError, ValueError, TimeoutError) as exc:
        public = {"status": "FAIL", "error": type(exc).__name__ + ": " + str(exc)[:160]}
    receipt = evaluate(source, public, dt.datetime.now(dt.timezone.utc),
                       expected_files=V10_FILES)
    receipt["schema"] = "GMFQ_CONTROL_ROOM_V10_0800_PUBLIC_SLA_V1"
    receipt["scope"] = "PUBLIC_DASHBOARD_MARKET_MIRRORS_AND_V10_PREVIEW_EXACT_SHA256"
    receipt["expected_file_count"] = len(V10_FILES)
    receipt["public_proof"] = public
    receipt["source_readiness"] = source
    receipt["browser_render_certified"] = False
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--output", default="/tmp/control-room-v10-0800-public-sla.json")
    args = parser.parse_args()
    receipt = run(dt.datetime.now(dt.timezone.utc), args.root, args.base_url)
    Path(args.output).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("CONTROL_ROOM_V10_0800_PUBLIC_SLA", json.dumps({
        k: receipt.get(k) for k in (
            "status", "source_checked_at_rome", "public_verified_at_rome",
            "source_pass", "public_exact_bytes_pass", "verified_file_count", "expected_file_count")
    }, sort_keys=True), flush=True)
    return 0  # Evidence only; do not block successful source recovery.


if __name__ == "__main__":
    raise SystemExit(main())
