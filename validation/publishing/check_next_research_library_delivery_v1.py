#!/usr/bin/env python3
"""Research Library: latest *committed* approved HTML and actual public HTTP.

Read-only. A correctly dated report in ChatGPT Library is not a GitHub commit;
a commit is not a public website. Validate eight canonical report categories,
retain only latest actual editions, then optionally compare exact HTTP bytes.
Do not treat freshness of publication as freshness of underlying market data.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from validation.publishing.verify_pages_http_delivery_v1 import BASE_URL, verify

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path("site/fx-quant-v2/next/reports")
BLOCKED = re.compile(r"(?:^|_)(?:PROVA|TEST|BOZZA|DRAFT|BACKUP|ANTEPRIMA|PREVIEW|LEGACY|OLD|DATI_PARZIALI)(?:_|\.|$)", re.I)
PREFIXES = {
    "daily": ("Briefing_Forex_Commodities_",),
    "macro": ("Weekly_Global_Macro_Report_",),
    "bank": ("Weekly_Bank_FX_Report_",),
    "cb": ("Weekly_CB_Sentiment_Report_",),
    "ois": ("Weekly_CB_Pricing_G8_", "Weekly_Central_Bank_Pricing_G8_"),
    "cot": ("COT_FX_G8_",),
    "cross": ("Weekly_Global_Macro_Strength_Cross_Asset_",),
    "pairs": ("Weekly_FX_Pair_Selection_",),
}
MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
          "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def parse_date(name: str) -> str | None:
    match = re.search(r"(?:^|_)(20\d{2}-\d{2}-\d{2})(?:_|\.|$)", name)
    if match:
        day = match.group(1)
    else:
        cot = re.match(r"COT_FX_G8_(\d{2})_([A-Z]{3})_(20\d{2})_", name, re.I)
        if not cot or cot.group(2).upper() not in MONTHS:
            return None
        day = f"{cot.group(3)}-{MONTHS[cot.group(2).upper()]:02d}-{cot.group(1)}"
    try:
        if datetime.strptime(day, "%Y-%m-%d").strftime("%Y-%m-%d") != day:
            return None
    except ValueError:
        return None
    return day


def report_type(name: str) -> str | None:
    return next((key for key, stems in PREFIXES.items()
                 if any(name.startswith(stem) for stem in stems)), None)


def revision_score(name: str) -> int:
    versions = [int(n) for n in re.findall(r"(?:^|_)v(\d+)(?:_|\.|$)", name, re.I)]
    return max(versions, default=0) * 100 + int(bool(re.search(
        r"DEFINITIV|CORRETT|FINAL|APPROVAT", name, re.I)))


def latest(root: Path = ROOT, today: str | None = None) -> dict:
    today = today or datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    directory = root / DIRECTORY
    if not directory.is_dir():
        raise ValueError("RESEARCH_LIBRARY_SOURCE_DIR_MISSING")
    chosen = {}
    for file in directory.glob("*.html"):
        name = file.name
        if BLOCKED.search(name):
            continue
        typ, date = report_type(name), parse_date(name)
        if typ is None or date is None or date > today:
            continue
        data = file.read_bytes()
        if (len(data) < 1000 or not re.search(rb"<(?:!doctype\s+html|html)\b", data[:500], re.I)
                or b"</html>" not in data.lower()[-1000:]):
            raise ValueError(f"INVALID_FINAL_HTML:{name}")
        candidate = {"type": typ, "reference_date": date, "filename": name,
                     "relative_path": (DIRECTORY / name).as_posix(), "bytes": len(data)}
        previous = chosen.get(typ)
        if previous is None or (date, revision_score(name), name) > (
                previous["reference_date"], revision_score(previous["filename"]),
                previous["filename"]):
            chosen[typ] = candidate
    missing = sorted(set(PREFIXES) - set(chosen))
    if missing:
        raise ValueError("RESEARCH_LIBRARY_CATEGORIES_MISSING:" + ",".join(missing))
    return {"status": "SOURCE_FINAL_HTML_VALIDATED",
            "canonical_categories": len(PREFIXES),
            "latest": [chosen[key] for key in sorted(chosen)],
            "latest_daily": chosen["daily"]["reference_date"],
            "reference_today_rome": today, "source_is_not_http_proof": True}


def run(root: Path = ROOT, *, http: bool = False, today: str | None = None,
        budget_seconds: float = 180.0) -> dict:
    report = latest(root, today)
    if http:
        paths = tuple(item["relative_path"] for item in report["latest"])
        proof = verify(root, BASE_URL, paths, budget_seconds=budget_seconds,
                       interval_seconds=8, timeout_seconds=15)
        report["http"] = proof
        report["status"] = ("LATEST_8_PUBLIC_HTTP_EXACT_PASS" if proof["status"] == "PASS"
                            else "LATEST_8_PUBLIC_HTTP_NOT_VERIFIED")
    else:
        report["http"] = None
    report["market_source_freshness_certified"] = False
    report["automatic_chatgpt_to_github_transfer_certified"] = False
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--http", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("/tmp/research-library-public-proof.json"))
    parser.add_argument("--budget-seconds", type=float, default=180)
    args = parser.parse_args()
    report = run(http=args.http, budget_seconds=args.budget_seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("NEXT_RESEARCH_LIBRARY_DELIVERY", json.dumps(report, ensure_ascii=False), flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("### Next Research Library — delivery receipts\n")
            f.write("- " + report["status"] + "\n")
            f.write("- Latest daily committed: " + report["latest_daily"] + "\n")
            for item in report["latest"]:
                f.write("- " + item["type"] + ": " + item["reference_date"] +
                        " · " + item["filename"] + "\n")
            f.write("- Source dates are editorial references, not verified economic data vintages.\n")
            f.write("- HTML in ChatGPT Library is separate from GitHub; no auto-ingestion inferred.\n")
    if args.http:
        return 0 if report["http"]["status"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
