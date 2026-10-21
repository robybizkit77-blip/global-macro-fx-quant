#!/usr/bin/env python3
"""Fail-closed official NZD Rates publication eligibility, with reviewed evidence.

A future NZD snapshot needs both the source registry to advance explicitly and
two independently recorded RBNZ B2 same-basis evidence files to agree. Merely
changing rates JSON (or only updating a registry date) cannot publish it.
No network calls, refresh, source promotion or model effects.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "validation/RATES_SOURCE_ADAPTERS_V1_2026-10-05.json"
FIRST = "validation/fixtures/rbnz_b2_official_table_2026-10-19_review_required.json"
SECOND = "validation/fixtures/rbnz_b2_independent_source_review_2026-10-19.json"
OFFICIAL_PAGE = "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates"
MANUAL_QUALITY = "FULL_CURRENT_OFFICIAL_MANUAL_VERIFIED"
MANUAL_FRESHNESS = "CURRENT_OFFICIAL_SAME_BASIS_MANUAL_VERIFIED"


def require(condition, why):
    if not condition:
        raise ValueError("NZD_RATES_REVIEWED_REGISTRY_FAIL_CLOSED: " + why)


def eq(x, y):
    return type(x) in (int, float) and type(y) in (int, float) and (
        math.isfinite(x) and math.isfinite(y) and abs(x-y) < 1e-9
    )


def review_file(root: Path, relative: str) -> dict:
    require(isinstance(relative, str) and relative.startswith("validation/fixtures/") and
            re.fullmatch(r"validation/fixtures/[a-zA-Z0-9_.-]+\.json", relative),
            "review evidence must be in an explicit local fixtures path")
    return json.loads((root / relative).read_text(encoding="utf-8"))


def validate(rates: dict, registry: dict, *, root: Path = ROOT) -> dict:
    require(set(rates) >= {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"},
            "canonical G8 Rates coverage missing")
    require(registry.get("policy", {}).get("official_source_required") is True and
            registry["policy"].get("same_basis_required") is True and
            registry["policy"].get("no_market_indication_fallback") is True,
            "official same-basis / no-estimate policy relaxed")
    meta = registry["currencies"]["NZD"]
    row = rates["NZD"]
    require(meta.get("adapter_status") == "OPERATIONAL_MANUAL_OFFICIAL_VERIFIED__RUNNER_ACCESS_BLOCKED",
            "NZD manual RBNZ-only source policy changed")
    day = meta.get("current_snapshot")
    try:
        valid_date = isinstance(day, str) and date.fromisoformat(day).isoformat() == day
    except (ValueError, TypeError):
        valid_date = False
    require(valid_date and row.get("date") == day, "snapshot date differs from approved registry")
    y2, y10 = meta.get("current_2Y"), meta.get("current_10Y")
    require(eq(row.get("2Y"), y2) and eq(row.get("10Y"), y10),
            "2Y/10Y differ from reviewed registry")
    require(row.get("quality") == MANUAL_QUALITY and
            row.get("freshness_status") == MANUAL_FRESHNESS,
            "manual official source certification missing")
    require("Reserve Bank of New Zealand" in row.get("source", "") and
            "B2" in row.get("source", "") and day in row.get("source", "") and
            "reviewed" in row.get("source", "").lower(),
            "current source lacks official reviewed B2 lineage")
    require(eq(row.get("curve_bp"), round((y10-y2)*100, 1)), "NZD curve not same-day")
    for tenor, history in (("2Y", "history2"), ("10Y", "history10")):
        matching = [x for x in row.get("tenors", []) if x.get("tenor") == tenor]
        require(len(matching) == 1 and matching[0].get("date") == day and
                eq(matching[0].get("value"), row[tenor]),
                tenor+" tenor not reconciled to snapshot")
        h = row.get(history) or {}
        ds, values = h.get("dates"), h.get("values")
        require(isinstance(ds, list) and isinstance(values, list) and len(ds) == len(values) and len(ds) > 1 and
                ds == sorted(set(ds)) and ds[-1] == day and eq(values[-1], row[tenor]) and
                h.get("last_date") == day and eq(h.get("last_value"), row[tenor]),
                tenor+" history tail not reconciled")
        week = row.get("weekly"+tenor[:-1]+"_validation") or {}
        require(week.get("end_date") == day and eq(week.get("end_value"), row[tenor]) and
                "Reserve Bank of New Zealand" in week.get("source", ""),
                tenor+" weekly validation not reconciled")
    paths = (meta.get("first_review_evidence"), meta.get("independent_review_evidence"))
    require(paths[0] and paths[1] and paths[0] != paths[1],
            "two distinct explicitly approved review artifacts required")
    first, second = (review_file(root, p) for p in paths)
    require(first.get("schema") == "GMFQ_RBNZ_B2_OFFICIAL_HTML_TABLE_EVIDENCE_V1" and
            first.get("usable_for_automatic_promotion") is False and
            second.get("status") == "SOURCE_TABLE_CROSS_CHECKED_STAGING_ONLY" and
            second.get("live_data_promotion_allowed") is False and
            second.get("review_type") == "INDEPENDENT_WEB_PAGE_READ_NOT_MACHINE_FETCHED_IN_GITHUB",
            "first/second human review status contract missing")
    require(first.get("source_url") == second.get("source_url") == OFFICIAL_PAGE and
            "government bond closing yields" in first.get("basis", "").lower() and
            "government bond closing yields" in second.get("basis", "").lower(),
            "independent reviewers disagree on official RBNZ B2 basis")
    a, b = first.get("observations"), second.get("source_rows")
    require(isinstance(a, list) and len(a) >= 3 and a == b,
            "independent review observations do not match")
    dates = [x.get("date") for x in a]
    require(dates == sorted(set(dates)) and dates[-1] == day and
            all(set(x) == {"date","2Y","10Y"} for x in a),
            "latest approved RBNZ source row is not current/unique")
    require(eq(a[-1]["2Y"], y2) and eq(a[-1]["10Y"], y10),
            "approved independent source values differ from published Rates")
    ref = meta.get("manual_approval_reference")
    require(isinstance(ref, str) and
            re.fullmatch(r"https://github\.com/robybizkit77-blip/global-macro-fx-quant/pull/[1-9][0-9]*", ref),
            "explicit manual review reference missing")
    require(meta.get("automatic_promotion_allowed") is False,
            "manual approval cannot be substituted with automatic promotion")
    return {
        "status": "PASS",
        "currency": "NZD",
        "as_of": day,
        "2Y": y2, "10Y": y10,
        "basis": "RBNZ_B2_OFFICIAL_GOVERNMENT_CLOSE",
        "review_reference": ref,
        "source_access": "MANUAL_VERIFIED_RUNNER_BLOCKED",
        "automatic_promotion_allowed": False,
    }


def main():
    obj = json.loads((ROOT / "live_data/sections/NATIVE_RATES_DATA.json").read_text())
    reg = json.loads(REGISTRY.read_text())
    print("NZD_RATES_REVIEWED_SNAPSHOT_PASS", json.dumps(validate(obj, reg), sort_keys=True))


if __name__ == "__main__":
    main()
