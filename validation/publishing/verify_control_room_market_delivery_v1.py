#!/usr/bin/env python3
"""Fail closed on all five Control Room v10 Market Data public mirrors.

First require exact bytes on gh-pages, then bounded public HTTP 200+SHA256
convergence. This is publication-only QA, not source validation or a trading
signal. The Dashboard publisher separately owns the other nine feed mirrors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from verify_pages_http_delivery_v1 import BASE_URL, verify

FILES = (
    "live_data/sections/NATIVE_RATES_DATA.json",
    "live_data/sections/V250_COT_CHART_DATA.json",
    "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
    "live_data/sections/ECB_G8_PRICE_HISTORY.json",
    "live_data/sections/DXY_SYNTHETIC_ECB.json",
)


def branch_parity(root: Path, reader=None) -> dict:
    root = Path(root)
    if reader is None:
        def reader(path):
            return subprocess.check_output(
                ["git", "show", "origin/gh-pages:" + path],
                cwd=root,
            )
    entries = []
    for path in FILES:
        canonical = (root / path).read_bytes()
        try:
            published = reader(path)
            error = None
        except (OSError, subprocess.CalledProcessError) as exc:
            published, error = None, str(exc)[:200]
        expected = hashlib.sha256(canonical).hexdigest()
        actual = hashlib.sha256(published).hexdigest() if published is not None else None
        entries.append({
            "path": path,
            "match": published is not None and actual == expected,
            "canonical_sha256": expected,
            "gh_pages_sha256": actual,
            "error": error,
        })
    return {
        "status": "PASS" if all(row["match"] for row in entries) else "FAIL",
        "basis": "MAIN_VS_GH_PAGES_EXACT_SHA256",
        "checks": entries,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--base-url", default=BASE_URL)
    p.add_argument("--budget-seconds", type=float, default=180)
    p.add_argument("--interval-seconds", type=float, default=8)
    p.add_argument("--output", type=Path, default=Path("/tmp/control-room-market-public-proof.json"))
    args = p.parse_args()
    branch = branch_parity(args.root)
    public = None
    if branch["status"] == "PASS":
        public = verify(args.root, args.base_url, FILES,
                        budget_seconds=args.budget_seconds,
                        interval_seconds=args.interval_seconds)
    result = {
        "status": "PASS" if branch["status"] == "PASS" and public is not None and public["status"] == "PASS" else "FAIL",
        "scope": "CONTROL_ROOM_V10_FIVE_MARKET_FEEDS_ONLY",
        "branch": branch,
        "public_http": public,
        "core_model_mutated": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CONTROL_ROOM_MARKET_PUBLICATION_PROOF", json.dumps({
        "status": result["status"], "branch": branch["status"],
        "http": None if public is None else public["status"],
        "checked": len(FILES), "output": str(args.output),
    }, sort_keys=True), flush=True)
    if result["status"] != "PASS":
        raise SystemExit("Market feed mirror/HTTP content differs from canonical main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
