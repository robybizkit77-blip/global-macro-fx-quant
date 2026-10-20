#!/usr/bin/env python3
"""Read-only release-time availability ledger for each live G8 Macro core input.

Data observation periods are NOT release dates. Evidence is accepted only when
it ties an exact observation period AND numerical value to an official dated
release artifact in existing repository strict-PIT materialization. Where a
release hour is missing, a DATE is retained but no intraday permission is given.
No score, structural label, D.json or pair is written or refreshed.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.rebase_readiness_v1 import ROOT, FX, PATHS, DIMS, g8_coverage, period_key

SCHEMA = "GMFQ_MACRO_PIT_RELEASE_LEDGER_V1"
ANCHOR_GLOB = "*_historical_anchor_*.json"
EVIDENCE_GLOB = "*_strict_pit_evidence_*.json"
RECEIPT_GLOB = "*_strict_pit_receipt_*.json"


def require(flag, why):
    if not flag:
        raise ValueError("MACRO_PIT_RELEASE_LEDGER_REJECTED: " + why)


def iso_day(s, label):
    require(isinstance(s, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) is not None,
            f"{label} invalid release date")
    return date.fromisoformat(s)


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def anchor_row(entry, path, series_key, kind):
    """Return an explicitly anchored period; no inferred dates or website scraping."""
    require(isinstance(entry, dict) and "release_date" in entry,
            f"{path} {series_key}: unsupported release anchor")
    value = entry.get("value", entry.get("rate", entry.get("yoy")))
    require(finite(value), f"{path}: missing numerical anchor")
    source = entry.get("official_reference")
    if source is not None:
        require(isinstance(source, str) and source.startswith("https://"),
                f"{path}: malformed official link")
    hashval = entry.get("source_sha256")
    if hashval is not None:
        require(isinstance(hashval, str) and re.fullmatch(r"[a-f0-9]{64}", hashval) is not None,
                f"{path}: malformed source sha")
    return {
        "date": entry["release_date"], "value": value, "source_path": path,
        "source_kind": kind, "official_reference": source,
        "source_sha256": hashval, "release_time_utc": entry.get("release_time_utc"),
        "release_time_jst": entry.get("release_time_jst"),
    }


def collect_candidates(core_dir):
    candidates = {}
    def add(target, period, row):
        candidates.setdefault((target, period), []).append(row)
    for path in sorted(core_dir.glob(ANCHOR_GLOB)):
        item = json.loads(path.read_text(encoding="utf-8"))
        require(item.get("schema") == "GMFQ_MACRO_HISTORICAL_BOOTSTRAP_ANCHOR_V1",
                f"{path.name} unexpected historical anchor schema")
        t = item.get("target") or {}
        key = str(t.get("currency")) + "." + str(t.get("dimension"))
        require(key.split(".")[0] in FX and key.split(".")[-1] in DIMS,
                f"{path.name} unknown target")
        for stage in ("previous", "current"):
            obj = item.get(stage) or {}
            require("observation_date" in obj and "release_date" in obj,
                    f"{path.name} missing anchored release")
            add(key, obj["observation_date"],
                anchor_row(obj, path.relative_to(ROOT).as_posix(), key,
                           "PINNED_OFFICIAL_BOOTSTRAP_"+stage.upper()))
    for glob, kind in ((EVIDENCE_GLOB, "STRICT_DIRECT_ARCHIVAL_EVIDENCE"),
                       (RECEIPT_GLOB, "STRICT_DIRECT_ARCHIVAL_RECEIPT")):
        for path in sorted(core_dir.glob(glob)):
            item = json.loads(path.read_text(encoding="utf-8"))
            key = item.get("target")
            if isinstance(key, dict):
                key = str(key.get("currency")) + "." + str(key.get("dimension"))
            require(isinstance(key, str) and key.split(".")[0] in FX and
                    key.split(".")[-1] in DIMS, f"{path.name} unknown strict PIT target")
            if kind.endswith("EVIDENCE"):
                require(item.get("status") == "PASS" and
                        item.get("evidence_class") == "STRICT_DIRECT_ARCHIVAL_PIT",
                        f"{path.name} missing archived PIT verdict")
            else:
                require(item.get("verdict") in (
                    "STRICT_DIRECT_ARCHIVAL_PIT_CERTIFIABLE",
                    "STRICT_DIRECT_ARCHIVAL_PIT_PASS"),
                    f"{path.name} missing strict PIT receipt verdict")
            for field in ("anchors", "anchor_checks", "anchors_verified"):
                mapping = item.get(field) or {}
                require(isinstance(mapping, dict), f"{path.name} malformed {field}")
                for period, row in mapping.items():
                    if not isinstance(row, dict) or "release_date" not in row:
                        continue
                    add(key, period, anchor_row(row, path.relative_to(ROOT).as_posix(),
                                                key, kind+"_"+field.upper()))
    return candidates


def resolved_time(item):
    if item.get("release_time_utc") and item.get("release_time_jst"):
        raise ValueError("MACRO_PIT_RELEASE_LEDGER_REJECTED: conflicting time zones")
    if item.get("release_time_utc"):
        stamp = item["release_time_utc"]
        try:
            tt = time.fromisoformat(stamp)
        except (ValueError, TypeError) as exc:
            raise ValueError("MACRO_PIT_RELEASE_LEDGER_REJECTED: invalid UTC clock") from exc
        require(tt.tzinfo is None, "UTC clock must omit offset")
        return datetime.combine(iso_day(item["date"], "official"), tt,
                                tzinfo=timezone.utc).isoformat()
    if item.get("release_time_jst"):
        stamp = item["release_time_jst"]
        try:
            tt = time.fromisoformat(stamp)
        except (ValueError, TypeError) as exc:
            raise ValueError("MACRO_PIT_RELEASE_LEDGER_REJECTED: invalid JST clock") from exc
        require(tt.tzinfo is None, "JST clock must omit offset")
        return datetime.combine(iso_day(item["date"], "official"), tt,
                                tzinfo=ZoneInfo("Asia/Tokyo")).astimezone(timezone.utc).isoformat()
    return None


def build_ledger(root, today, items=None):
    data = {key: json.loads((root / path).read_text(encoding="utf-8"))
            for key, path in PATHS.items()}
    g = g8_coverage(*(data[k] for k in PATHS), today)
    require(g["source_lineage"] == "PASS" and
            g["structural_rebase"] == "BLOCKED_SCORE_CONTRACT" and
            g["safe_to_publish_D"] is False,
            "unexpected source-to-engine state")
    model, series, heat, registry = (data[k] for k in
                                    ("model", "series", "heat", "registry"))
    candidates = collect_candidates(root / "validation/macro") if items is None else items
    results = {}
    counts = {"FULL_RELEASE_INSTANT": 0, "DATE_ONLY": 0,
              "WITHHELD_EXACT_PERIOD_EVIDENCE": 0}
    for c in FX:
        for dim in DIMS:
            key = c+"."+dim
            source = registry["series"][key]
            histid = (source.get("historical_replay_evidence") or {}).get("macro_series_id") or \
                     source["series_id"]+"_history_value"
            row = [r for r in series[c] if r.get("id") == histid]
            require(len(row) == 1 and len(row[0].get("dates") or []) >= 2,
                    key+": missing canonical PIT series")
            actual = heat["currencies"][c][dim]
            period = period_key(row[0]["dates"][-1], source["frequency"])
            require(period == period_key(actual["as_of"], source["frequency"]),
                    key+": canonical source and heatmap observation differ")
            raw = []
            # Exact calendar period only. Previous-month anchor cannot certify
            # the latest month even if it is for the same series.
            for (label, observed_period), bucket in candidates.items():
                if label != key or period_key(observed_period, source["frequency"]) != period:
                    continue
                raw += bucket
            match = []
            for r in raw:
                pub = iso_day(r["date"], key)
                require(pub <= today, key+": future official release metadata")
                require(pub >= date.fromisoformat(period+"-01"),
                        key+": publication before reference month")
                if math.isclose(r["value"], actual["latest_value"],
                                rel_tol=0.0, abs_tol=1e-8):
                    match.append(r)
            require(not raw or match,
                    key+": anchored period matches but published value conflicts with latest")
            if match:
                require(len({v["date"] for v in match}) == 1,
                        key+": incompatible official first-release dates")
                clock = {resolved_time(v) for v in match if resolved_time(v) is not None}
                require(len(clock) <= 1, key+": conflicting documented release timestamps")
                timestamp = next(iter(clock)) if clock else None
                status = "FULL_RELEASE_INSTANT" if timestamp else "DATE_ONLY"
                # A signed source hash is not mandatory if official reference
                # path+verdict exists; preserve that evidence distinction.
                lines = sorted({r["source_path"] for r in match})
                result = {
                    "status": status,
                    "first_release_date": match[0]["date"],
                    "first_release_timestamp_utc": timestamp,
                    "release_clock_verified": bool(timestamp),
                    "date_only_not_eligible_for_intraday_PIT": timestamp is None,
                    "evidence_paths": lines,
                    "official_references": sorted({r["official_reference"] for r in match
                                                   if r["official_reference"]}),
                    "pinned_source_hashes": sorted({r["source_sha256"] for r in match
                                                    if r["source_sha256"]}),
                    "source_history_values_are_not_first_release_vintages": True,
                    "historical_backtest_safe_for_all_periods": False,
                }
            else:
                status = "WITHHELD_EXACT_PERIOD_EVIDENCE"
                result = {
                    "status": status, "first_release_date": None,
                    "first_release_timestamp_utc": None,
                    "release_clock_verified": False,
                    "date_only_not_eligible_for_intraday_PIT": True,
                    "evidence_paths": [], "official_references": [],
                    "pinned_source_hashes": [],
                    "source_history_values_are_not_first_release_vintages": True,
                    "historical_backtest_safe_for_all_periods": False,
                }
            counts[status] += 1
            results[key] = {
                "currency": c, "dimension": dim,
                "frequency": source["frequency"],
                "series_id": source["series_id"], "canonical_series_id": histid,
                "current_observation_period": actual["as_of"],
                "latest_transformed_observation": actual["latest_value"],
                "release": result,
            }
    require(len(results) == 16 and sum(counts.values()) == 16,
            "G8 latest PIT source count incomplete")
    return {
        "schema": SCHEMA, "as_of": today.isoformat(),
        "model_baseline_as_of": model["asOf"],
        "source_lineage": "PASS",
        "observations_checked": 16, "counts": counts,
        "release_ledger_scope": "LATEST_OBSERVATION_ONLY",
        "release_dates_not_inferred_from_calendar": True,
        "safe_to_promote_macro_labels": False,
        "safe_to_publish_new_D": False,
        "historical_vintage_series_available": False,
        "note": ("Pinned official release dates are not equal to observation periods. "
                 "Sparse anchor examples do not establish a complete PIT archive. "
                 "Only two-source-clock proofs can support exact timestamps."),
        "observations": results,
    }


def render(ledger):
    lines = [
        "## PIT Macro G8 — disponibilità dell'ultima osservazione",
        "",
        f"Baseline Macro {ledger['model_baseline_as_of']} · "
        f"Copertura: **{ledger['observations_checked']}/16** input ispezionati",
        "",
        "| Valuta | Dato | Periodo osservato | Prima uscita verificabile | Qualità ora |",
        "|---|---|---|---|---|",
    ]
    for target, record in ledger["observations"].items():
        r = record["release"]
        lines.append(f"| {record['currency']} | {record['dimension']} | "
                     f"{record['current_observation_period']} | "
                     f"{r['first_release_date'] or 'WITHHELD'} | {r['status']} |")
    lines += ["", "**Bilancio:** " + " · ".join(f"{k}: {v}" for k, v in ledger["counts"].items()),
              "", "**NON è una nuova baseline Macro.** Nessuna data o valore vengono "
              "stimati dai calendari. Le fonti senza ora non possono certificare "
              "decisioni intraday; gli anchor disponibili non certificano automaticamente "
              "tutta la serie storica.", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=ROOT)
    p.add_argument("--asof", default=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat())
    p.add_argument("--out", type=Path)
    p.add_argument("--markdown", type=Path)
    a = p.parse_args()
    report = build_ledger(a.repo_root, date.fromisoformat(a.asof))
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    if a.markdown:
        a.markdown.parent.mkdir(parents=True, exist_ok=True)
        a.markdown.write_text(render(report), encoding="utf-8")
    print(json.dumps({"source_lineage": report["source_lineage"],
                      "observations_checked": report["observations_checked"],
                      "counts": report["counts"],
                      "safe_to_promote_macro_labels": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
