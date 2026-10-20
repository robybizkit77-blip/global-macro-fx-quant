#!/usr/bin/env python3
"""Fail-closed G8 Growth first-release provenance and metric-definition gate.

This is an input audit, NEVER an FX Macro score builder. Sparse official
publisher attestations constrain latest-period dates/values, NOT historical
vintage replay, source snapshots, initial-release weights or dynamic FX labels.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from validation.macro.rebase_readiness_v1 import (
    ROOT, FX, PATHS, g8_coverage, period_key,
)
from validation.macro.latest_release_pit_ledger_v1 import build_ledger

SCHEMA = "GMFQ_G8_GROWTH_FIRST_RELEASE_ATTESTATIONS_V1"
RECEIPT = "GMFQ_G8_GROWTH_PIT_READINESS_V1"
ATTESTATIONS = ROOT / "validation/macro/GROWTH_FIRST_RELEASE_OFFICIAL_WEB_ATTESTATIONS_2026-10-20.json"
ALLOWED_AUTHORITIES = {
    "AUD": ("abs.gov.au", "Australian Bureau of Statistics"),
    "NZD": ("stats.govt.nz", "Stats NZ"),
}


def require(condition, reason):
    if not condition:
        raise ValueError("GROWTH_PIT_EVIDENCE_INVALID: "+reason)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def period(raw, frequency):
    key = period_key(raw, frequency)
    require(frequency == "M" or key[5:] in ("03", "06", "09", "12"),
            f"unrecognized quarter {raw!r}")
    return key


def validate_series(row, today):
    ident = row.get("id")
    dates, values = row.get("dates"), row.get("values")
    require(isinstance(ident, str) and ident.strip(), "Growth series missing id")
    require(isinstance(dates, list) and isinstance(values, list) and
            len(dates) >= 2 and len(dates) == len(values),
            ident+": incomplete growth history")
    require(all(number(v) for v in values), ident+": nonfinite observation")
    declared = row.get("frequency")
    require(declared in (None, "", "M", "Q"), ident+": unsupported frequency")
    frequency = declared or "M"
    normalized = [period(x, frequency) for x in dates]
    require(normalized == sorted(set(normalized)), ident+": unsorted/duplicate periods")
    require(normalized[-1] <= today.strftime("%Y-%m"), ident+": future Growth observation")
    require(number(row.get("last_value")) and
            row["last_value"] == values[-1], ident+": last value mismatch")
    require(period(row.get("last_date"), frequency) == normalized[-1],
            ident+": last_date inconsistent with history")
    unit = row.get("unit")
    return {
        "currency": None,
        "id": ident, "name": row.get("label"),
        "frequency": frequency, "frequency_declared": declared in ("M", "Q"),
        "unit": unit or None,
        "unit_declared": bool(unit),
        "source_file_label": row.get("source_file") or None,
        "latest_period": normalized[-1],
        "latest_date_stored": dates[-1],
        "latest_value": values[-1],
        "history_length": len(dates),
    }


def normalize_release_date(s, now):
    require(isinstance(s, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) is not None,
            "missing/invalid first-release date")
    d = date.fromisoformat(s)
    require(d <= now, "future release date")
    return d


def verify_attestation(entry, row, today):
    c, ident = entry.get("currency"), entry.get("series_id")
    require(c == row["currency"] and ident == row["id"],
            "series/currency attestation identity drift")
    require(entry.get("observation_period") == row["latest_period"],
            ident+": attestation not for latest observation")
    require(entry.get("units") == row["unit"] and row["unit_declared"],
            ident+": metric unit not locked")
    definition = entry.get("metric_definition")
    require(isinstance(definition, str) and len(definition.strip()) >= 30,
            ident+": missing precise official metric definition")
    require(number(entry.get("first_release_value")) and
            math.isclose(entry["first_release_value"], row["latest_value"],
                         abs_tol=1e-8, rel_tol=0.0),
            ident+": OFFICIAL_FIRST_RELEASE_VALUE_DISAGREES_WITH_CANONICAL")
    released = normalize_release_date(entry.get("release_date"), today)
    require(released >= date.fromisoformat(row["latest_period"]+"-01"),
            ident+": purported release predates reference period")
    authority = ALLOWED_AUTHORITIES.get(c)
    require(authority is not None and entry.get("publisher") == authority[1],
            ident+": unsupported/unverified official publisher")
    url = entry.get("official_source_url")
    require(isinstance(url, str), ident+": official release URL missing")
    parsed = urlsplit(url)
    require(parsed.scheme == "https" and parsed.hostname and
            (parsed.hostname == authority[0] or parsed.hostname.endswith("."+authority[0])) and
            not parsed.username and not parsed.password and
            not parsed.fragment, ident+": official URL publisher mismatch")
    require(entry.get("provenance_level") ==
            "OFFICIAL_WEB_PAGE_DATE_VALUE_VERIFIED_NO_ARCHIVED_BYTES",
            ident+": unsupported evidence grade")
    require(entry.get("source_artifact_sha256") is None,
            ident+": do not claim unchecked source artifact hash")
    timestamp = entry.get("release_timestamp_local")
    utc_time = None
    if timestamp is not None:
        require(isinstance(timestamp, str), ident+": invalid timestamp")
        dt = datetime.fromisoformat(timestamp)
        require(dt.tzinfo is not None and dt.utcoffset() is not None,
                ident+": naive clock cannot certify UTC availability")
        require(dt.date() == released, ident+": clock and release date disagree")
        require(dt.astimezone(timezone.utc).date() <= today,
                ident+": future timestamp")
        utc_time = dt.astimezone(timezone.utc).isoformat()
    note = entry.get("source_locator")
    require(isinstance(note, str) and len(note) >= 40,
            ident+": source locator missing")
    alt = entry.get("comparison_must_not_use")
    if c == "NZD":
        require(alt == {
            "metric": "GDP four-quarter annual average growth",
            "value": 1.7,
            "reason": "Stats NZ reports a distinct average-annual measure; 1.7 is not the same-quarter YoY metric"
        }, "NZD YoY/annual-average distinction missing")
        require("SAME quarter" in definition,
                "NZD YoY reference quarter definition missing")
        require(alt["value"] != entry["first_release_value"],
                "NZD annual-average silently substituted for YoY")
    elif alt is not None:
        require(False, ident+": unexpected alternative indicator metric")
    return {
        "status": "OFFICIAL_LATEST_VALUE_DATE_MATCH_WEB_ONLY",
        "release_date": released.isoformat(),
        "release_instant_utc": utc_time,
        "intraday_time_documented": utc_time is not None,
        "official_metric_definition": definition,
        "official_source_url": url,
        "source_locator": note,
        "separate_metric_not_to_conflate": alt,
        "source_artifact_sha256": None,
        "full_historical_PIT_vintage": False,
        "structural_score_certifiable": False,
    }


def build(root, now, attestations=None, feeds=None, core_ledger=None):
    feeds = feeds or {
        key: json.loads((root / path).read_text(encoding="utf-8"))
        for key, path in PATHS.items()
    }
    require(g8_coverage(*(feeds[k] for k in PATHS), now)["source_lineage"] == "PASS",
            "G8 inflation/labour lineage not certified")
    raw = attestations if attestations is not None else json.loads(
        (root / "validation/macro/GROWTH_FIRST_RELEASE_OFFICIAL_WEB_ATTESTATIONS_2026-10-20.json").read_text(encoding="utf-8"))
    require(raw.get("schema") == SCHEMA and
            raw.get("scope") ==
            "LATEST_GROWTH_OBSERVATIONS_OFFICIAL_WEB_EVIDENCE_NOT_FULL_HISTORICAL_PIT" and
            raw.get("attestation_does_not_certify_historical_vintage") is True and
            raw.get("attestation_does_not_recalculate_macro_scores") is True,
            "unsupported release attestation registry semantics")
    review_date = normalize_release_date(raw.get("review_as_of"), now)
    require(review_date >= date.fromisoformat(feeds["model"]["asOf"]),
            "review predates canonical baseline")
    items = raw.get("attestations")
    require(isinstance(items, list), "missing attestation records")
    mapped = {}
    for item in items:
        require(isinstance(item, dict) and isinstance(item.get("series_id"), str),
                "invalid attestation row")
        ident = item["series_id"]
        require(ident not in mapped, "duplicate official Growth attestation")
        mapped[ident] = item

    counters = {
        "official_latest_value_date_match": 0,
        "no_first_release_evidence": 0,
        "missing_frequency_declared": 0,
        "missing_unit_declared": 0,
        "archival_first_release_vintage_certified": 0,
    }
    source = feeds["series"]
    rows = {}
    unitless = []
    freq_missing = []
    for c in FX:
        candidates = [r for r in source[c] if r.get("category") == "Crescita"]
        require(len(candidates) >= 1, c+": no Growth inputs")
        for src in candidates:
            row = validate_series(src, now)
            ident = row["id"]
            require(ident not in rows, ident+": Growth id duplicated")
            row["currency"] = c
            if not row["unit_declared"]:
                counters["missing_unit_declared"] += 1
                unitless.append(ident)
            if not row["frequency_declared"]:
                counters["missing_frequency_declared"] += 1
                freq_missing.append(ident)
            if ident in mapped:
                require(row["frequency_declared"],
                        ident+": frequency not declared; cannot certify official release")
                attestation = verify_attestation(mapped[ident], row, now)
                counters["official_latest_value_date_match"] += 1
            else:
                attestation = {
                    "status": "WITHHELD_NO_PERIOD_EXACT_OFFICIAL_FIRST_RELEASE_EVIDENCE",
                    "release_date": None, "release_instant_utc": None,
                    "official_source_url": None,
                    "full_historical_PIT_vintage": False,
                    "structural_score_certifiable": False,
                }
                counters["no_first_release_evidence"] += 1
            rows[ident] = {**row, "official_release": attestation}
    require(len(rows) == 21 and sum(x["currency"] == c for x in rows.values()) >= 1
            for c in FX, "21 G8 Growth contract broken")
    require(set(mapped).issubset(rows), "attestation for nonexistent/deleted Growth source")
    core_ledger = core_ledger or build_ledger(root, now)
    require(core_ledger.get("source_lineage") == "PASS" and
            core_ledger.get("observations_checked") == 16,
            "core G8 release ledger not available")
    core_missing = sorted(k for k, v in core_ledger["observations"].items()
                          if v["release"]["status"] == "WITHHELD_EXACT_PERIOD_EVIDENCE")
    return {
        "schema": RECEIPT, "as_of": now.isoformat(),
        "source_lineage": "PASS",
        "historical_macro_baseline_as_of": feeds["model"]["asOf"],
        "growth_country_count": 8, "growth_series_count": len(rows),
        "declared_missing_frequency_ids": sorted(freq_missing),
        "declared_missing_unit_ids": sorted(unitless),
        "counts": counters,
        "unresolved_core_latest_release_targets": core_missing,
        "unresolved_core_latest_release_target_count": len(core_missing),
        "safe_to_refresh_growth_score": False,
        "safe_to_refresh_qualitative_macro_labels": False,
        "safe_to_publish_D": False,
        "historical_value_vintages_certified": False,
        "official_web_evidence_not_source_snapshot": True,
        "note": (
            "Comparing official first-release source value and exact indicator definition "
            "for latest period alone cannot establish historical first-release vintage "
            "or structural Growth weights. Never compare New Zealand same-quarter YoY "
            "with Stats NZ four-quarter annual-average growth."),
        "growth": rows,
        "blockers": [
            "19 remaining latest Growth series need period-specific official release value, date and metric identity evidence",
            "4 US Growth sources have no declared frequency or unit in canonical metadata",
            "No full growth historical first-release archive or release timestamps per period",
            "No versioned 3-pillar FX score weights or qualitative directional-label promotion contract",
        ],
    }


def markdown(r):
    lines = [
        "## Macro Growth G8 — fonte ufficiale e verifica PIT",
        "",
        f"**Baseline D:** {r['historical_macro_baseline_as_of']} · "
        f"**Serie crescita:** {r['growth_series_count']} · "
        f"**Uscite ufficiali ultimo periodo verificate:** "
        f"{r['counts']['official_latest_value_date_match']}/21",
        "",
        "| Valuta | Serie | Ultimo periodo | Valore | Evidenza ufficiale |",
        "|---|---|---|---:|---|",
    ]
    for item in r["growth"].values():
        v = item["official_release"]
        lines.append(f"| {item['currency']} | {item['name']} | {item['latest_period']} "
                     f"| {item['latest_value']} | {v['status']} |")
    lines += [
        "",
        "**Date/valori ufficiali verificati non equivalgono a una storia PIT completa.**",
        "Nessun nuovo Growth score, giudizio Macro o bias FX generato.",
        "",
        f"**Release core inflazione/lavoro ancora senza prova esatta:** "
        f"{', '.join(r['unresolved_core_latest_release_targets']) or 'nessuno'}",
        "",
        f"**Metadati da normalizzare:** "
        f"{r['counts']['missing_frequency_declared']} frequenze, "
        f"{r['counts']['missing_unit_declared']} unità.",
        "",
        "**Attenzione alle definizioni:** il +2,6% YoY NZD è diverso dal "
        "+1,7% medio annuo: entrambe sono metriche ufficiali del PIL, "
        "ma non intercambiabili.",
        "",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=ROOT)
    p.add_argument("--asof", default=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat())
    p.add_argument("--out", type=Path)
    p.add_argument("--markdown", type=Path)
    args = p.parse_args()
    result = build(args.repo_root, date.fromisoformat(args.asof))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n",
                            encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(result), encoding="utf-8")
    print(json.dumps({
        "source_lineage": result["source_lineage"],
        "growth_series_count": result["growth_series_count"],
        "counts": result["counts"],
        "unresolved_core_latest_release_target_count":
            result["unresolved_core_latest_release_target_count"],
        "safe_to_publish_D": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
