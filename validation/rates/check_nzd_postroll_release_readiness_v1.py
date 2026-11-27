#!/usr/bin/env python3
"""Read-only release preflight for the reconciled RBNZ B2 post-roll segment.
Never writes native rates, merges pre/post-roll histories or authorizes promotion.
"""
from __future__ import annotations
import argparse
import json
import math
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "site/fx-quant-v2/nzd-rbnz-b2-reconciled-research.json"
NATIVE = ROOT / "live_data/sections/NATIVE_RATES_DATA.json"
SCHEMA = "GMFQ_NZD_RBNZ_B2_RECONCILED_RESEARCH_V1"

def require(ok, message):
    if not ok:
        raise ValueError("NZD_POSTROLL_PREFLIGHT: " + message)

def day(s):
    d = date.fromisoformat(s)
    require(d.isoformat() == s, "noncanonical date")
    return d

def build(research, native, asof):
    require(research.get("schema") == SCHEMA and
            research.get("status") == "RBNZ_B2_HTML_XLSX_AGREE_POSTROLL_RESEARCH_ONLY",
            "reconciled official B2 receipt required")
    for key in ("eligible_for_core", "eligible_for_fx_pair_engine",
                "eligible_for_backtests", "eligible_for_automatic_promotion"):
        require(research.get(key) is False, "protected research-only policy changed")
    require(research.get("research_only") is True and research.get("no_interpolation") is True,
            "research provenance required")
    require(research.get("source_url") == "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates" and
            research.get("xlsx_url") == "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close.xlsx",
            "official source identity changed")
    for k in ("html_sha256", "xlsx_sha256"):
        require(bool(re.fullmatch(r"[0-9a-f]{64}", str(research.get(k, "")))), "source hash absent")
    roll = day(research["benchmark_roll_date"])
    pub = day(research["publication_date"])
    end = day(research["last_observation_date"])
    require(roll.isoformat() == "2026-10-30" and
            research.get("benchmark_2Y") == "April 2029" and
            research.get("benchmark_10Y") == "April 2037",
            "benchmark identity changed: independent review required")
    require(roll <= end <= pub <= asof, "future or inconsistent source date")
    rows = research["observations"]
    require(isinstance(rows, list) and len(rows) >= 6, "insufficient post-roll observations")
    days = [day(r["date"]) for r in rows]
    require(days == sorted(set(days)) and days[0] == roll and days[-1] == end and
            all(d.weekday() < 5 for d in days), "invalid post-roll chronology")
    for r in rows:
        require(all(type(r.get(k)) in (float, int) and math.isfinite(r[k]) and -5 < r[k] < 25
                    for k in ("2Y", "10Y")), "invalid paired yield")
    matched = research["html_xlsx_matched_dates"]
    require(isinstance(matched, list) and len(set(matched)) >= 6 and
            all(day(d) in days for d in matched) and end.isoformat() in matched,
            "latest edition lacks paired HTML/XLSX evidence")
    cutoff = end - timedelta(days=7)
    references = [r for r, d in zip(rows, days) if d <= cutoff]
    require(bool(references), "weekly reference would cross benchmark roll")
    ref, last = references[-1], rows[-1]
    base = day(native["NZD"]["date"])
    changes = {k: round((last[k] - ref[k]) * 100, 1) for k in ("2Y", "10Y")}
    age = (asof - end).days
    return {"schema": "GMFQ_NZD_POSTROLL_RELEASE_READINESS_V1",
            "status": "READY_FOR_INDEPENDENT_RELEASE_REVIEW" if base < end and age <= 5 else "RETAINED_OR_STALE_REVIEW_ONLY",
            "canonical_as_of": base.isoformat(), "candidate_as_of": end.isoformat(),
            "publication_date": pub.isoformat(), "age_calendar_days": age,
            "benchmark_roll_date": roll.isoformat(), "post_roll_rows": len(rows),
            "matched_html_xlsx_rows": len(set(matched)), "latest": last,
            "weekly_cutoff": cutoff.isoformat(), "weekly_reference": ref,
            "weekly_change_bp": changes,
            "curve_bp": round((last["10Y"] - last["2Y"]) * 100, 1),
            "cross_roll_change_allowed": False, "writes_live_data": False,
            "eligible_for_automatic_promotion": False, "eligible_for_core": False,
            "independent_release_review_required": True}

def isolated_candidate(research, native, asof):
    """Construct a separate release candidate. Never replace canonical history."""
    receipt = build(research, native, asof)
    require(receipt["status"] == "READY_FOR_INDEPENDENT_RELEASE_REVIEW",
            "candidate is not newer and current")
    rows = research["observations"]
    last, ref = rows[-1], receipt["weekly_reference"]
    return {
        "schema": "GMFQ_NZD_POSTROLL_ISOLATED_RELEASE_CANDIDATE_V1",
        "currency": "NZD", "date": last["date"],
        "source": research["source"], "source_url": research["source_url"],
        "publication_date": research["publication_date"],
        "source_sha256": {"html": research["html_sha256"], "xlsx": research["xlsx_sha256"]},
        "benchmark_roll_date": research["benchmark_roll_date"],
        "benchmark_2Y": research["benchmark_2Y"], "benchmark_10Y": research["benchmark_10Y"],
        "2Y": last["2Y"], "10Y": last["10Y"], "curve_bp": receipt["curve_bp"],
        "history2": {"dates": [r["date"] for r in rows], "values": [r["2Y"] for r in rows],
                     "last_date": last["date"], "last_value": last["2Y"]},
        "history10": {"dates": [r["date"] for r in rows], "values": [r["10Y"] for r in rows],
                      "last_date": last["date"], "last_value": last["10Y"]},
        "weekly_reference": ref, "weekly_change_bp": receipt["weekly_change_bp"],
        "canonical_base_date": native["NZD"]["date"],
        "prior_canonical_history_retained_untouched": True,
        "cross_roll_change_allowed": False, "first_release_pit_certified": False,
        "writes_live_data": False, "eligible_for_automatic_promotion": False,
        "eligible_for_core": False, "eligible_for_backtests": False,
        "independent_release_review_required": True,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", type=date.fromisoformat, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--candidate-output", type=Path)
    a = p.parse_args()
    require(a.output.resolve().is_relative_to(Path("/tmp")), "output must be temporary")
    research, native = json.loads(RESEARCH.read_text()), json.loads(NATIVE.read_text())
    report = build(research, native, a.as_of)
    if a.candidate_output:
        require(a.candidate_output.resolve().is_relative_to(Path("/tmp")), "candidate output must be temporary")
        candidate = isolated_candidate(research, native, a.as_of)
        a.candidate_output.write_text(json.dumps(candidate, indent=2) + "\n")
        print("NZD_POSTROLL_ISOLATED_CANDIDATE", json.dumps({"date": candidate["date"],
              "rows": len(candidate["history2"]["dates"]), "weekly_change_bp": candidate["weekly_change_bp"],
              "writes_live_data": False, "cross_roll_change_allowed": False}, sort_keys=True))
    a.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))

if __name__ == "__main__":
    main()
