#!/usr/bin/env python3
"""Fail-open for source outages, fail-closed for invalid provenance.

Produce a read-only chronological receipt: a workflow can succeed and retain
a dated quote without ever implying a new observed market price. No Core writes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "site/fx-quant-v2/chf-nzd-benchmark-research.json"
ROME = ZoneInfo("Europe/Rome")
KEYS = {"CHF": ("paired_date", ("2Y", "10Y")),
        "NZD": ("latest_date", ("latest_2Y", "latest_10Y"))}


def demand(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError("FXV2_SOURCE_FRESHNESS_REJECTED: " + message)


def summarize(before: dict, after: dict, today: dt.date,
              official_html: bool, authorized_vendor: bool) -> dict:
    demand(isinstance(before, dict) and isinstance(after, dict) and
           before.get("schema") == after.get("schema") ==
           "GMFQ_FXV2_CHF_NZD_BENCHMARK_RESEARCH_V1",
           "research source schema changed")
    for name in ("eligible_for_core", "eligible_for_fx_pair_engine",
                 "eligible_for_backtests"):
        demand(after.get(name) is False, "protected FX/Backtest scope changed")
    demand(after.get("canonical_government_rates_untouched") is True,
           "canonical-rate immutability lost")
    demand(not (official_html and authorized_vendor),
           "two competing NZD source reads cannot coexist")
    rows = {}
    for c, (datekey, rates) in KEYS.items():
        current = after.get(c)
        older = before.get(c)
        demand(isinstance(current, dict) and isinstance(older, dict),
               c + " source record missing")
        day = dt.date.fromisoformat(current[datekey])
        prior = dt.date.fromisoformat(older[datekey])
        demand(day <= today and day >= prior,
               c + " future observation or source rollback")
        values = [current[k] for k in rates]
        demand(all(isinstance(x, (int, float)) and not isinstance(x, bool)
                   and -5 <= x <= 25 for x in values), c + " malformed rates")
        changed = day > prior or any(current[k] != older[k] for k in rates)
        if day > prior:
            label = "NEW_OBSERVATION_DATE"
        elif changed:
            label = "REVISED_SAME_DATE_OBSERVATION"
        else:
            label = "RETAINED_PREVIOUS_DATED_OBSERVATION"
        rows[c] = {
            "source_as_of": day.isoformat(),
            "previous_source_as_of": prior.isoformat(),
            "source_calendar_age_days": (today - day).days,
            "observations_changed": changed,
            "capture_result": label,
            "quality": "RESEARCH_NOT_CANONICAL",
            "eligible_for_core": False,
        }
    if official_html:
        source_status = "RBNZ_OFFICIAL_HTML_RESEARCH_READ"
    elif authorized_vendor:
        source_status = "AUTHORIZED_RBNZ_REDISTRIBUTION_RESEARCH_READ"
    else:
        source_status = "NO_NEW_RBNZ_SOURCE_ACCEPTED_DATED_RESEARCH_RETAINED"
    return {
        "schema": "GMFQ_FXV2_CHF_NZD_DAILY_SOURCE_FRESHNESS_RECEIPT_V1",
        "check_date_rome": today.isoformat(),
        "CHF": rows["CHF"], "NZD": rows["NZD"],
        "NZD_source_access": source_status,
        "accepted_new_chf_date": rows["CHF"]["capture_result"] == "NEW_OBSERVATION_DATE",
        "accepted_new_nzd_date": rows["NZD"]["capture_result"] == "NEW_OBSERVATION_DATE",
        "workflow_success_does_not_certify_new_observations": True,
        "canonical_G8_rates_modified": False,
        "FX_pair_signals_modified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--official-html-file", type=Path)
    parser.add_argument("--vendor-file", type=Path)
    args = parser.parse_args()
    rel = RESEARCH.relative_to(ROOT).as_posix()
    before = json.loads(subprocess.check_output(
        ["git", "show", "HEAD:" + rel], cwd=ROOT, text=True))
    after = json.loads(RESEARCH.read_text(encoding="utf-8"))
    report = summarize(
        before, after, dt.datetime.now(ROME).date(),
        bool(args.official_html_file and args.official_html_file.is_file()),
        bool(args.vendor_file and args.vendor_file.is_file()))
    if args.output:
        demand(args.output.resolve().is_relative_to(Path("/tmp")),
               "receipt may only be written to temporary evidence")
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as f:
            f.write("\n### FX Quant V2 — verified CHF/NZD source dates\n")
            for c in KEYS:
                row=report[c]
                f.write("- " + c + ": **" + row["capture_result"] +
                        "**, source **" + row["source_as_of"] +
                        "** (" + str(row["source_calendar_age_days"]) +
                        " calendar days old). Research only.\n")
            f.write("- NZD source access: **" + report["NZD_source_access"] + "**.\n")
            f.write("- PASS proves read-only integrity, **not** quote freshness.\n")
    print("FXV2_CHF_NZD_SOURCE_FRESHNESS", json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
