#!/usr/bin/env python3
"""PIT-aware Macro V2 feature prototype. Shadow/research-only: NEVER build scores."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone, date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "GMFQ_MACRO_V2_PIT_FEATURE_INPUT_V1"
FX = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}
PILLARS = {"growth", "labour", "inflation"}
TRANSPORT = {"OFFICIAL_DIRECT", "CERTIFIED_OFFICIAL_TRANSPORT", "SYNTHETIC_FIXTURE"}
FREQ = {"M": 12, "Q": 4}


def require(ok, detail):
    if not ok:
        raise ValueError("MACRO_V2_PIT_REJECTED: " + detail)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def timestamp(value):
    require(isinstance(value, str), "timestamp must be an offset-aware ISO string")
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("MACRO_V2_PIT_REJECTED: invalid timestamp") from exc
    require(ts.tzinfo is not None and ts.utcoffset() is not None,
            "offset-aware release timestamp required")
    return ts.astimezone(timezone.utc)


def period_index(raw, freq):
    require(freq in FREQ, "unsupported or missing frequency")
    require(isinstance(raw, str), "observation period must be a string")
    if freq == "M":
        m = re.fullmatch(r"(\d{4})-(\d{2})", raw)
        require(m is not None, "monthly period must be YYYY-MM")
        year, month = map(int, m.groups())
        require(1 <= month <= 12, "invalid calendar month")
        return year * 12 + month - 1
    m = re.fullmatch(r"(\d{4})Q([1-4])", raw)
    require(m is not None, "quarterly period must be YYYYQn")
    year, quarter = map(int, m.groups())
    return year * 4 + quarter - 1


def period_start(raw, freq):
    idx = period_index(raw, freq)
    if freq == "M":
        return date(idx // 12, idx % 12 + 1, 1)
    return date(idx // 4, (idx % 4) * 3 + 1, 1)


def asof_index(ts, freq):
    return ts.year * FREQ[freq] + ((ts.month - 1) if freq == "M"
                                    else (ts.month - 1) // 3)


def sign(value):
    return "UP" if value > 0 else "DOWN" if value < 0 else "FLAT"


def build_features(manifest):
    """Select actual known vintages as of a specific clock time; never infer release dates.

    A supplied evidence_ref is a declaration, NOT independent official verification.
    All derived numerical values are RAW units; neither FX polarity nor weight nor
    normalisation is inferred. Output cannot enter D.json or pair model.
    """
    require(isinstance(manifest, dict) and manifest.get("schema") == SCHEMA,
            "unknown input contract")
    c, pillar, freq = (manifest.get("currency"), manifest.get("pillar"),
                       manifest.get("frequency"))
    require(c in FX and pillar in PILLARS and freq in FREQ,
            "G8 currency / pillar / frequency contract")
    series_id, unit = manifest.get("series_id"), manifest.get("unit")
    require(isinstance(series_id, str) and bool(series_id.strip()) and
            isinstance(unit, str) and bool(unit.strip()), "series identity and unit required")
    source = manifest.get("source")
    require(isinstance(source, dict), "source declaration required")
    require(source.get("transport") in TRANSPORT, "unverified or secondary transport")
    require(all(isinstance(source.get(k), str) and source[k].strip()
                for k in ("authority", "source_id")), "source identity missing")
    cutoff = timestamp(manifest.get("as_of"))
    lag = manifest.get("max_lag_periods")
    require(type(lag) is int and 0 <= lag <= 6, "explicit bounded staleness rule required")
    events = manifest.get("vintages")
    require(isinstance(events, list) and bool(events), "dated source vintages required")
    grouped = defaultdict(list)
    for event in events:
        require(isinstance(event, dict), "vintage must be a record")
        period = event.get("observation_period")
        idx = period_index(period, freq)
        when = timestamp(event.get("released_at"))
        require(when.date() >= period_start(period, freq),
                "release timestamp precedes its observation period")
        require(number(event.get("value")), "finite observation required")
        require(event.get("kind") in ("FIRST", "REVISION"), "vintage kind required")
        require(isinstance(event.get("evidence_ref"), str) and
                bool(event["evidence_ref"].strip()), "evidence reference required")
        grouped[(idx, period)].append((when, event))
    selected = []
    for (idx, period), records in grouped.items():
        records.sort(key=lambda x: x[0])
        require(sum(e["kind"] == "FIRST" for _, e in records) == 1,
                "exactly one first release required per period")
        require(records[0][1]["kind"] == "FIRST", "revision before first release")
        require(len({when for when, _ in records}) == len(records),
                "duplicate release timestamp for one observation")
        candidates = [(when, e) for when, e in records if when <= cutoff]
        if candidates:
            when, e = candidates[-1]
            selected.append({"idx": idx, "period": period, "value": e["value"],
                             "released_at": when.isoformat(), "kind": e["kind"],
                             "evidence_ref": e["evidence_ref"]})
    selected.sort(key=lambda x: x["idx"])
    require(len(selected) >= 4, "four point-in-time released observations required")
    tail = selected[-4:]
    require(all(tail[i+1]["idx"] - tail[i]["idx"] == 1 for i in range(3)),
            "missing observation interval in latest four periods")
    require(0 <= asof_index(cutoff, freq) - tail[-1]["idx"] <= lag,
            "latest observation outside explicit staleness tolerance")
    values = [float(x["value"]) for x in tail]
    velocity, prev_velocity = values[-1] - values[-2], values[-2] - values[-3]
    acceleration = velocity - prev_velocity
    turning = ("DOWN_TO_UP" if prev_velocity < 0 < velocity else
               "UP_TO_DOWN" if prev_velocity > 0 > velocity else "NONE")
    digest = hashlib.sha256(json.dumps({
        "schema": SCHEMA, "as_of": cutoff.isoformat(), "source": source,
        "currency": c, "pillar": pillar, "series_id": series_id,
        "frequency": freq, "unit": unit, "selected": selected,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema": "GMFQ_MACRO_V2_SHADOW_FEATURE_RECEIPT_V1",
        "status": "SHADOW_FEATURES_COMPUTED_PROVENANCE_NOT_INDEPENDENTLY_VERIFIED",
        "currency": c, "pillar": pillar, "series_id": series_id,
        "as_of": cutoff.isoformat(), "frequency": freq, "unit": unit,
        "source_transport_claim": source["transport"],
        "source_evidence_is_independently_certified": False,
        "selected_observations": len(selected),
        "latest_period": tail[-1]["period"],
        "latest_release_timestamp": tail[-1]["released_at"],
        "latest_vintage_kind": tail[-1]["kind"],
        "latest_evidence_ref": tail[-1]["evidence_ref"],
        "level": values[-1], "direction": sign(velocity),
        "velocity_per_period": velocity, "acceleration_per_period_squared": acceleration,
        "turning_point": turning,
        "note": ("Raw series dynamics only. No standardised score, FX strength, "
                 "inflation desirability, cross-series aggregation or backtest claim."),
        "feature_fingerprint_sha256": digest,
        "numeric_pillar_score": None, "economic_cycle": None,
        "ready_for_scoring": False, "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False, "writes_live_data": False,
    }


def audit_current_inventory(root=ROOT):
    """Read source availability only; a macro runtime value is not a PIT release log."""
    series = json.loads((root / "live_data/sections/MACRO_SERIES.json").read_text())
    registry = json.loads((root / "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json").read_text())
    require(set(series) == FX, "G8 source series coverage changed")
    require(len(registry.get("series", {})) == 16, "core registry must contain 16 series")
    coverage = {}
    for ccy in sorted(FX):
        growth = [r for r in series[ccy] if r.get("category") == "Crescita"]
        require(growth, ccy + ": no Growth inventory")
        dimensions = {}
        for dim in ("inflation", "labour"):
            entry = registry["series"].get(ccy + "." + dim)
            require(isinstance(entry, dict), ccy + "." + dim + ": registry missing")
            dimensions[dim] = {
                "adapter_status": entry.get("source_adapter_status"),
                "historical_replay_certified": entry.get("historical_replay_certified") is True,
                "transport": entry.get("transport_class"),
                "score_pit_release_log_certified": False,
            }
        coverage[ccy] = {
            "growth_observation_series": len(growth),
            "growth_score_pit_release_log_certified": False,
            "core_series": dimensions,
        }
    return {
        "schema": "GMFQ_MACRO_V2_SOURCE_INVENTORY_V1",
        "status": "OBSERVATION_SERIES_PRESENT_SCORE_PIT_VINTAGES_UNCERTIFIED",
        "currency_count": len(FX),
        "growth_observation_series_total": sum(x["growth_observation_series"] for x in coverage.values()),
        "inflation_labour_registered": len(registry["series"]),
        "currency_coverage": coverage,
        "interpretation": ("Registry historical replay certification does not by itself "
                           "establish per-period first releases/revisions and full "
                           "source-to-score point-in-time suitability."),
        "model_version": "V2_SHADOW_FEATURE_PROTOTYPE_ONLY",
        "ready_for_live_feature_replay": False,
        "ready_for_scoring": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "writes_live_data": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path,
                        help="Optional audit receipt in an external CI artifact directory")
    args = parser.parse_args()
    receipt = audit_current_inventory()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: receipt[k] for k in (
        "status", "currency_count", "growth_observation_series_total",
        "inflation_labour_registered", "ready_for_scoring", "safe_to_publish_new_D",
    )}))


if __name__ == "__main__":
    main()
