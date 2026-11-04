#!/usr/bin/env python3
"""Read-only morning HTTP proof for the published FX Quant V2 website.

This verifies public GitHub Pages bytes against approved main, and never
certifies economic release freshness, OIS market accuracy, or trading signals.
The check cannot retroactively prove publication before 08:00 if run late.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site/fx-quant-v2"
URL = "https://robybizkit77-blip.github.io/global-macro-fx-quant/site/fx-quant-v2/"
FILES = (
    "index.html", "valute.html", "coppie.html", "tassi.html", "ois.html",
    "macro.html", "banche.html", "cot.html", "cross-asset.html",
    "liquidita-credito.html", "calendario-news.html", "research.html",
    "assets/site-nav.js", "assets/site-nav.css",
    "ois-pricing-snapshot.json", "cross-asset-live-data.json",
)
CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}
TENORS = ("3m", "6m", "12m")


def evaluate(now: dt.datetime, rows: list[dict], *, expected=FILES) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware evaluation time required")
    local = now.astimezone(ROME)
    deadline = dt.datetime.combine(local.date(), dt.time(8), tzinfo=ROME)
    paths = [r.get("path") for r in rows]
    delivered = bool(
        len(rows) == len(expected) and len(set(paths)) == len(expected)
        and set(paths) == set(expected)
        and all(r.get("status") == "MATCH" and r.get("http") == 200
                and isinstance(r.get("expected_sha256"), str)
                and len(r["expected_sha256"]) == 64
                and r.get("public_sha256") == r["expected_sha256"]
                for r in rows)
    )
    if local.weekday() > 4:
        status = "NOT_WEEKDAY"
    elif not delivered:
        status = "FAIL_PUBLIC_FILES_NOT_MATCHED"
    elif local > deadline:
        status = "VERIFIED_AFTER_0800_ON_TIME_UNPROVEN"
    else:
        status = "PASS_12_PAGES_PUBLIC_BY_0800"
    return {
        "schema": "GMFQ_FXV2_MORNING_PUBLIC_PROOF_V1",
        "date_rome": local.date().isoformat(),
        "verified_at_rome": local.isoformat(timespec="seconds"),
        "deadline_rome": deadline.isoformat(timespec="seconds"),
        "status": status,
        "on_time_proven": status == "PASS_12_PAGES_PUBLIC_BY_0800",
        "public_files_verified": sum(r.get("status") == "MATCH" for r in rows),
        "expected_file_count": len(expected),
        "all_exact_public_bytes_match": delivered,
        "critical_coverage": {"pages": 12, "files": len(expected)},
        "source_scope": "FXV2_PUBLIC_HTML_AND_STATIC_ASSETS_ONLY",
        "economic_data_freshness_certified": False,
        "ois_market_accuracy_certified": False,
        "legacy_v10_untouched": True,
        "note": "Late verification does not prove when files first became available. Source-level as-of dates and instrument quality require separate review.",
        "files": rows,
    }


def check_snapshot() -> None:
    data = json.loads((SITE / "ois-pricing-snapshot.json").read_text(encoding="utf-8"))
    if data.get("schema") != "GMFQ_FXV2_PRICING_SNAPSHOT_V1":
        raise ValueError("OIS snapshot schema drift")
    currencies = data.get("currencies", {})
    if set(currencies) != CURRENCIES:
        raise ValueError("G8 pricing coverage missing currencies")
    for c, row in currencies.items():
        horizons = row.get("horizons", {})
        if any(not isinstance(horizons.get(t, {}).get("rate"), (float, int))
               or not -5 <= horizons[t]["rate"] <= 30 for t in TENORS):
            raise ValueError(f"Invalid indicative pricing horizon for {c}")
        if c == "GBP" and row.get("kind") != "OIS":
            raise ValueError("OIS GBP provenance lost")
        if c != "GBP" and row.get("kind") == "OIS":
            raise ValueError(f"Futures/estimate {c} incorrectly labelled OIS")


def fetch_one(path: str, *, attempts: int = 3) -> dict:
    data = (SITE / path).read_bytes()
    expected = hashlib.sha256(data).hexdigest()
    last_error = ""
    public_hash = None
    http = None
    for retry in range(attempts):
        try:
            req = Request(URL + path + "?fxv2_proof=" + str(int(time.time())),
                          headers={"Cache-Control": "no-cache", "User-Agent": "FXV2-Morning-Public-Proof/1"})
            with urlopen(req, timeout=9) as response:
                http = response.status
                public_hash = hashlib.sha256(response.read()).hexdigest()
            if http == 200 and public_hash == expected:
                return {"path": path, "http": http, "status": "MATCH",
                        "expected_sha256": expected, "public_sha256": public_hash}
            last_error = "bytes differ from approved main"
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
            http = getattr(exc, "code", None)
        if retry < attempts - 1:
            time.sleep(3)
    return {"path": path, "http": http, "status": "MISMATCH_OR_UNAVAILABLE",
            "expected_sha256": expected, "public_sha256": public_hash,
            "error": last_error[:250]}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    args = p.parse_args()
    check_snapshot()
    rows = [fetch_one(name) for name in FILES]
    report = evaluate(dt.datetime.now(dt.timezone.utc), rows)
    report["run_trigger"] = os.environ.get("GITHUB_EVENT_NAME", "manual")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("FXV2_MORNING_PUBLIC_PROOF", json.dumps({k: v for k, v in report.items() if k != "files"}))
    for row in rows:
        if row["status"] != "MATCH":
            print("PUBLIC_MISMATCH", row["path"], row.get("error", ""))
    return 0 if report["on_time_proven"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
