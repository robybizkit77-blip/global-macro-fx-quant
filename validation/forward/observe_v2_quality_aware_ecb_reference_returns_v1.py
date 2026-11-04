#!/usr/bin/env python3
"""Observe strictly matured ECB reference movements for the separate Quality-Aware cohort.

No historical T0 reconstruction, executable prices, directional signal, costs,
PnL or validated model edge. This journal must never be merged with legacy V2.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.forward.capture_v2_quality_aware_prospective_v1 import (
    ROOT, JOURNAL as SNAPSHOTS, SCHEMA as SNAP_SCHEMA, verify_journal
)
from validation.forward.capture_v2_research_prospective_evidence_v1 import (
    sha, canonical
)
from validation.forward.observe_official_ecb_reference_outcomes_v1 import (
    SOURCE_URL, FX_PATH, source_map, cross, HORIZONS
)
from validation.forward.observe_v2_research_ecb_reference_returns_v1 import (
    read_jsonl
)

OUTCOMES = ROOT / "validation/forward/reference_observations/V2_QUALITY_AWARE_ECB_REFERENCE_RETURNS_V1.jsonl"
SCHEMA = "GMFQ_V2_QUALITY_AWARE_ECB_REFERENCE_RETURNS_V1"
RECEIPT_SCHEMA = "GMFQ_V2_QUALITY_AWARE_ECB_OBSERVER_RECEIPT_V1"
ROME = ZoneInfo("Europe/Rome")
ANCHOR_LAYER = "ECB_DAILY_REFERENCE_NOT_EXECUTABLE_SPOT"
REFERENCE_LAYER = "OFFICIAL_ECB_DAILY_REFERENCE_NOT_EXECUTION_PRICE"


def require(ok, message):
    if not ok:
        raise ValueError("QUALITY_AWARE_REFERENCE_OBSERVER_REJECTED: " + message)


def verify_prior(items):
    seen = set()
    for item in items:
        require(isinstance(item, dict)
                and item.get("schema") == SCHEMA
                and item.get("reference_return_sha256") == sha({
                    k: v for k, v in item.items() if k != "reference_return_sha256"
                }), "missing or altered prior outcome seal")
        key = (item.get("quality_snapshot_id"), item.get("pair"), item.get("horizon"))
        require(key not in seen, "duplicate Quality-Aware outcome")
        require(item.get("reference_source") == SOURCE_URL
                and item.get("reference_layer") == REFERENCE_LAYER
                and item.get("source_day_original_issuer_bytes_verifiable") is False
                and item.get("trade_direction") is None
                and item.get("trade_gross_return") is None
                and item.get("trade_cost_bps") is None
                and item.get("trade_net_return") is None
                and item.get("trade_PnL") is None
                and item.get("model_alpha_claim") is False
                and item.get("predictive_accuracy") is None
                and item.get("quality_aware_signal_computed") is False,
                "prior result incorrectly promoted to trading performance")
        seen.add(key)
    return seen


def compute(frozen, fx, now, prior=()):
    require(isinstance(now, datetime) and now.tzinfo is not None
            and now.utcoffset() is not None, "timezone-aware observation clock required")
    require(isinstance(frozen, list) and isinstance(prior, (tuple, list)),
            "expected immutable journal collections")
    current = now.astimezone(timezone.utc)
    local = current.astimezone(ROME)
    latest_allowed = local.date() if local.hour >= 19 else local.date()-timedelta(days=1)
    history = source_map(fx)
    verify_journal(frozen)
    previous = verify_prior(prior)
    known_snapshots = {s["snapshot_id"] for s in frozen}
    require(len(known_snapshots) == len(frozen), "duplicate capture identity")
    require(all(key[0] in known_snapshots for key in previous),
            "prior reference orphaned from registered Quality-Aware cohort")
    additions = []
    waiting = {"not_matured": 0, "no_later_official_fixing": 0,
               "fixing_gap": 0, "already_recorded": 0, "new": 0}
    for snap in frozen:
        require(snap["schema"] == SNAP_SCHEMA
                and snap.get("V2_numeric_model_computed") is False
                and snap.get("V2_FX_signal_computed") is False
                and snap.get("future_outcomes_observed_at_capture") is False
                and snap.get("can_feed_preregistered_H1") is False,
                "source snapshot improperly promoted")
        captured = datetime.fromisoformat(snap["capture_at_utc"].replace("Z", "+00:00"))
        require(captured.utcoffset() is not None and captured <= current,
                "future or naive original snapshot time")
        t0 = captured.astimezone(ROME).date()
        require(snap["local_date_rome"] == t0.isoformat()
                and snap["official_ecb_t0_date"] == t0.isoformat(),
                "original source/capture date mismatch")
        first = history.get(t0)
        require(first is not None, "original ECB T0 missing in verified source")
        anchors = snap["observed_t0_ref"]
        require(len(anchors) == 28, "incomplete G8 cross panel")
        for pair, anchor in sorted(anchors.items()):
            require(pair.count("/") == 1 and anchor["date"] == t0.isoformat()
                    and anchor["layer"] == ANCHOR_LAYER
                    and anchor["source"] == FX_PATH.relative_to(ROOT).as_posix()
                    and anchor["trade_execution_price"] is False,
                    "invalid non-executable ECB T0 anchor")
            a, b = pair.split("/")
            rate0 = cross(first, a, b)
            require(rate0 is not None and math.isclose(rate0, anchor["rate"],
                    rel_tol=1e-9, abs_tol=1e-10),
                    "ECB fixing changed since frozen T0; quarantine entire panel")
            for horizon, days in HORIZONS.items():
                key = (snap["snapshot_id"], pair, horizon)
                if key in previous:
                    waiting["already_recorded"] += 1
                    continue
                due = captured + timedelta(days=days)
                if due > current:
                    waiting["not_matured"] += 1
                    continue
                due_date = due.astimezone(ROME).date()
                later = [day for day in history if due_date < day <= latest_allowed]
                if not later:
                    waiting["no_later_official_fixing"] += 1
                    continue
                end_date = min(later)
                gap = (end_date - due_date).days
                if gap > 4:
                    waiting["fixing_gap"] += 1
                    continue
                end = cross(history[end_date], a, b)
                if end is None:
                    waiting["fixing_gap"] += 1
                    continue
                record = {
                    "schema": SCHEMA,
                    "quality_snapshot_id": snap["snapshot_id"],
                    "origin_snapshot_sha256": snap["snapshot_sha256"],
                    "capture_at_utc": snap["capture_at_utc"],
                    "original_economic_asof": snap["economic_checked_as_of"],
                    "pair": pair,
                    "horizon": horizon,
                    "horizon_calendar_days": days,
                    "t0_source_date": t0.isoformat(),
                    "t0_ECB_nonexecutable_rate": rate0,
                    "maturity_date": due_date.isoformat(),
                    "first_observed_ecb_date_strictly_after_maturity": end_date.isoformat(),
                    "days_after_maturity": gap,
                    "observed_ECB_nonexecutable_rate": end,
                    "observed_reference_return_pct": round(100*(end/rate0-1), 8),
                    "reference_source": SOURCE_URL,
                    "reference_layer": REFERENCE_LAYER,
                    "source_day_original_issuer_bytes_verifiable": False,
                    "trade_direction": None,
                    "trade_gross_return": None,
                    "trade_cost_bps": None,
                    "trade_net_return": None,
                    "trade_PnL": None,
                    "predictive_accuracy": None,
                    "model_alpha_claim": False,
                    "quality_aware_signal_computed": False
                }
                record["reference_return_sha256"] = sha(record)
                additions.append(record)
                waiting["new"] += 1
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "QUALITY_AWARE_FEATURE_OUTCOME_PANEL_ONLY_NOT_PREDICTIVE_VALIDATION",
        "observed_at_utc": current.isoformat().replace("+00:00", "Z"),
        "source_last_observed_ecb_fixing": fx["last_as_of"],
        "frozen_capture_dates": len(frozen),
        "new_matured_reference_rows": len(additions),
        "horizons": list(HORIZONS),
        "twenty_eight_pairs_are_not_independent_trials": True,
        "no_actual_pnl_or_trade_claim": True,
        "no_H1_or_original_V2_model_claim": True,
        "new_rows": additions,
        "waiting": waiting,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--receipt", required=True, type=Path)
    p.add_argument("--append-journal", action="store_true")
    args = p.parse_args()
    require(args.receipt.resolve().is_relative_to(Path("/tmp")),
            "audit receipt must remain in /tmp")
    now = datetime.now(timezone.utc)
    fx = json.loads(FX_PATH.read_text(encoding="utf-8"))
    result = compute(read_jsonl(SNAPSHOTS), fx, now, read_jsonl(OUTCOMES))
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    if args.append_journal and result["new_rows"]:
        OUTCOMES.parent.mkdir(parents=True, exist_ok=True)
        with OUTCOMES.open("ab") as f:
            for item in result["new_rows"]:
                f.write(canonical(item))
    print(json.dumps({k: v for k, v in result.items() if k != "new_rows"},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
