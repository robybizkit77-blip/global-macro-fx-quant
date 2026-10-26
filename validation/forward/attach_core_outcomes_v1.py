#!/usr/bin/env python3
"""Append separately supplied forward outcomes; never treat input as certified.

The source file is caller-supplied and its prices/costs have NOT been audited.
No synthetic returns, lookahead timestamps, nonfinite values or duplicated
(snapshot,horizon) entries can be recorded. No source or trading model mutated.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ROOT / "validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl"
OUTCOMES = ROOT / "validation/forward/outcomes/CORE_DECISION_OUTCOMES_V1.jsonl"
HORIZONS = {"1D": 1, "3D": 3, "1W": 7, "2W": 14, "1M": 30, "3M": 90}


def canonical(x):
    return (json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def aware_instant(value):
    if not isinstance(value, str):
        raise ValueError("explicit ISO timestamp required")
    try:
        x = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if x.tzinfo is None or x.utcoffset() is None:
        raise ValueError("timezone-naive outcome timestamp")
    return x.astimezone(dt.timezone.utc)


def number(value, name, *, nonnegative=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"numeric finite {name} required")
    if nonnegative and value < 0:
        raise ValueError(f"negative {name}")
    return float(value)


def evaluate(decisions, supplied, existing_keys, as_of):
    """Validate entire batch before any append. Time comparisons use UTC."""
    if not isinstance(as_of, dt.date) or isinstance(as_of, dt.datetime):
        raise ValueError("ISO as-of date required")
    if not isinstance(decisions, dict) or not isinstance(supplied, list):
        raise ValueError("malformed decision/supplied records")
    additions, seen_batch = [], set()
    end_of_day = dt.datetime.combine(as_of, dt.time.max, tzinfo=dt.timezone.utc)
    for x in supplied:
        if not isinstance(x, dict):
            raise ValueError("malformed outcome row")
        key = (x.get("snapshot_id"), x.get("horizon"))
        if key in seen_batch:
            raise ValueError("duplicate snapshot/horizon in supplied batch")
        seen_batch.add(key)
        if not isinstance(key[0], str) or key[0] not in decisions or key[1] not in HORIZONS:
            raise ValueError("unknown snapshot/horizon")
        snap = decisions[key[0]]
        if snap.get("snapshot_id") != key[0]:
            raise ValueError("snapshot identity mismatch")
        cutoff = aware_instant(snap.get("decision_cutoff"))
        available = aware_instant(x.get("available_at"))
        if available <= cutoff:
            raise ValueError("outcome price predates or coincides with decision")
        if available > end_of_day:
            raise ValueError("outcome price not available as of requested evaluation date")
        if not isinstance(x.get("source_id"), str) or not x["source_id"].strip():
            raise ValueError("missing verifiable source reference")
        gross = number(x.get("gross_return"), "gross_return")
        costs = number(x.get("cost_bps"), "cost_bps", nonnegative=True)
        # Require 24 hours/7*24h etc after the actual decision *instant*,
        # not merely after midnight on the calendar date.
        maturity = cutoff + dt.timedelta(days=HORIZONS[key[1]])
        if as_of < maturity.date():
            continue
        if available < maturity:
            raise ValueError("outcome source predates the full target horizon")
        if key in existing_keys:
            continue
        row = {
            "schema_version": "GMFQ_CORE_FORWARD_OUTCOME_V1.0.0",
            "snapshot_id": key[0],
            "horizon": key[1],
            "gross_return": gross,
            "cost_bps": costs,
            "net_return": gross - costs / 10000,
            "source_id": x["source_id"],
            "available_at": available.isoformat().replace("+00:00", "Z"),
            "price_input_provenance": "CALLER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED",
            "performance_certified": False,
        }
        row["outcome_sha256"] = sha(row)
        additions.append(row)
    return additions


def _read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(t) for t in path.read_text(encoding="utf-8").splitlines() if t.strip()]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", required=True, help="UTC evaluation day YYYY-MM-DD")
    p.add_argument("--price-input", required=True, help="JSONL with externally checked outcomes")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    as_of = dt.date.fromisoformat(a.as_of)
    if not DECISIONS.exists():
        raise SystemExit("no decision snapshots to attach")
    rows = _read_jsonl(DECISIONS)
    ids = [x.get("snapshot_id") for x in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate decision snapshot IDs")
    decisions = {row["snapshot_id"]: row for row in rows}
    supplied = _read_jsonl(Path(a.price_input))
    current = _read_jsonl(OUTCOMES)
    keys = [(x.get("snapshot_id"), x.get("horizon")) for x in current]
    if len(set(keys)) != len(keys):
        raise SystemExit("duplicate existing forward outcomes")
    additions = evaluate(decisions, supplied, set(keys), as_of)
    if additions and not a.dry_run:
        OUTCOMES.parent.mkdir(parents=True, exist_ok=True)
        with OUTCOMES.open("ab") as f:
            for row in additions:
                f.write(canonical(row))
    print(json.dumps({
        "status": "RESEARCH_ONLY_UNVERIFIED_PRICE_INPUT",
        "appended": 0 if a.dry_run else len(additions),
        "candidate_rows": len(additions),
        "dry_run": a.dry_run,
        "decision_rows_untouched": True,
        "join_key": "snapshot_id",
        "performance_certified": False,
        "no_model_effect": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
