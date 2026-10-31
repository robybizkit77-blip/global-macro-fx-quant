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
import subprocess
from pathlib import Path

from check_pages_0800_delivery_sla_v1 import evaluate
from check_pages_morning_readiness_v1 import in_morning_window, evaluate as source_evaluate
from verify_pages_http_delivery_v1 import BASE_URL, FILES as DASHBOARD_FILES, verify
from verify_control_room_market_delivery_v1 import FILES as MARKET_FILES
from verify_control_room_v10_preview_parts_v1 import (
    PARTS as PREVIEW_PART_FILES,
    verify_parts,
)

PREVIEW_FILES = (
    "site/control-room-preview/index.html",
    "site/control-room-preview/home-navigation-v10.js",
    "site/control-room-preview/ois-pricing-estimates-v1.js",
)
V10_MAIN_FILES = tuple(dict.fromkeys((*DASHBOARD_FILES, *MARKET_FILES, *PREVIEW_FILES)))
V10_FILES = (*V10_MAIN_FILES, *PREVIEW_PART_FILES)


def run(now: dt.datetime, root: Path, base_url: str, *,
        auditor=verify, part_auditor=verify_parts, clock=None) -> dict:
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
        primary = auditor(root, base_url, V10_MAIN_FILES,
                          budget_seconds=0, interval_seconds=0,
                          timeout_seconds=3.0)
    except (OSError, ValueError, TimeoutError) as exc:
        primary = {"status": "FAIL", "error": type(exc).__name__ + ": " + str(exc)[:160]}
    try:
        parts = part_auditor(root, base_url)
    except (OSError, ValueError, TimeoutError, subprocess.CalledProcessError) as exc:
        parts = {"status": "FAIL", "error": type(exc).__name__ + ": " + str(exc)[:160]}
    # Both independent sources are mandatory: main owns the runtime + three
    # preview assets; 32 original design segments exist ONLY on gh-pages.
    # Exact public HTTP must match both, not merely the loader.
    main_rows = primary.get("checks") if isinstance(primary.get("checks"), list) else []
    part_rows = parts.get("checks") if isinstance(parts.get("checks"), list) else []
    complete = (primary.get("status") == "PASS"
                and parts.get("status") == "PASS"
                and len(main_rows) == len(V10_MAIN_FILES)
                and len(part_rows) == len(PREVIEW_PART_FILES))
    proof_clocks = [
        dt.datetime.fromisoformat(x["verified_at_utc"].replace("Z", "+00:00"))
        for x in (primary, parts)
        if isinstance(x.get("verified_at_utc"), str)
    ]
    finished = max(proof_clocks) if len(proof_clocks) == 2 else None
    public = {
        "status": "PASS" if complete else "FAIL",
        "basis": "PUBLIC_HTTP_200_EXACT_SHA256",
        "conclusion": "ALL_PUBLIC_FILES_MATCH" if complete else "PREVIEW_OR_MAIN_NOT_VERIFIED",
        "checks": main_rows + part_rows,
        "verified_at_utc": finished.isoformat() if finished else None,
        "main": {"status": primary.get("status"), "file_count": len(main_rows)},
        "preview_parts": {
            "status": parts.get("status"), "file_count": len(part_rows),
            "basis": "PINNED_ORIGINAL_GIT_BLOB_AND_PUBLIC_HTTP",
            "source_error": parts.get("error"),
        },
    }
    observed = clock() if clock is not None else dt.datetime.now(dt.timezone.utc)
    receipt = evaluate(source, public, observed, expected_files=V10_FILES)
    receipt["schema"] = "GMFQ_CONTROL_ROOM_V10_0800_PUBLIC_SLA_V1"
    receipt["scope"] = "PUBLIC_DASHBOARD_MARKET_MIRRORS_AND_V10_PREVIEW_EXACT_SHA256"
    receipt["expected_file_count"] = len(V10_FILES)
    receipt["public_proof"] = public
    receipt["preview_parts_delivery_verified"] = bool(complete and parts.get("status") == "PASS")
    receipt["preview_parts_expected"] = len(PREVIEW_PART_FILES)
    receipt["preview_parts_verified"] = parts.get("verified_count", 0)
    receipt["source_readiness"] = source
    receipt["browser_render_certified"] = False
    receipt["delivery_timestamp_basis"] = "OBSERVED_HTTP_TIMESTAMP_ONLY_NOT_FIRST_CDN_AVAILABILITY"
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
