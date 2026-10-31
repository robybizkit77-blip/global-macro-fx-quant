#!/usr/bin/env python3
"""Quarantine conflicting *secondary* futures bars without rewriting their first print.

A second quote for the same (currency, listed contract, observation date)
is not automatically a corrected close. Keep both validated pieces of evidence
in a separate append-only diagnostic file; do not derive repricing from them.
Other unaffected contracts remain eligible for the existing strict writer.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from ois_same_contract_history_v1 import (
    HISTORY, SOURCE, append_verified, candidates, load_history,
    quote_fingerprint, record_key, require, validate_row,
)

CONFLICTS = HISTORY.with_name("OIS_SAME_CONTRACT_CONFLICTS_V1.jsonl")
SCHEMA = "GMFQ_OIS_SAME_CONTRACT_SECONDARY_CONFLICT_V1"
STATUS = "UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT"


def digest(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def conflict_event(original: dict, incoming: dict) -> dict:
    validate_row(original)
    validate_row(incoming)
    require(record_key(original) == record_key(incoming),
            "conflict must have identical listed-contract/day identity")
    require(quote_fingerprint(original) != quote_fingerprint(incoming),
            "identical source print is not a conflict")
    identity = {
        "key": list(record_key(original)),
        "original_fingerprint": list(quote_fingerprint(original)),
        "incoming_fingerprint": list(quote_fingerprint(incoming)),
    }
    return {
        "schema": SCHEMA,
        "event_id": digest(identity),
        "status": STATUS,
        "key": list(record_key(original)),
        "original_immutable_quote": copy.deepcopy(original),
        "conflicting_source_quote": copy.deepcopy(incoming),
        "resolution": None,
        "eligible_for_ois_level": False,
        "eligible_for_repricing": False,
        "eligible_for_model_or_H1": False,
    }


def read_conflicts(path: Path = CONFLICTS) -> list[dict]:
    if not path.is_file():
        return []
    seen = set()
    events = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        event = json.loads(line)
        require(isinstance(event, dict) and set(event) == {
            "schema", "event_id", "status", "key",
            "original_immutable_quote", "conflicting_source_quote",
            "resolution", "eligible_for_ois_level", "eligible_for_repricing",
            "eligible_for_model_or_H1",
        }, "invalid quarantine event fields")
        require(event["schema"] == SCHEMA and event["status"] == STATUS
                and event["resolution"] is None
                and event["eligible_for_ois_level"] is False
                and event["eligible_for_repricing"] is False
                and event["eligible_for_model_or_H1"] is False,
                "quarantine evidence improperly promoted")
        reconstructed = conflict_event(event["original_immutable_quote"],
                                       event["conflicting_source_quote"])
        require(event == reconstructed, "quarantine event integrity mismatch")
        require(event["event_id"] not in seen,
                f"duplicate quarantine identity line {number}")
        seen.add(event["event_id"])
        events.append(event)
    return events


def reconcile(feed: dict, history: list[dict],
              existing_events: list[dict]) -> tuple[dict, list[dict], dict]:
    # candidates() validates quotes and issuer/non-OIS governance before comparison.
    eligible, excluded = candidates(feed)
    known = {record_key(row): row for row in history}
    seen = {row["event_id"] for row in existing_events}
    updated = copy.deepcopy(feed)
    conflicts = []
    quarantined = {}
    for row in eligible:
        archived = known.get(record_key(row))
        if archived is None or quote_fingerprint(archived) == quote_fingerprint(row):
            continue
        event = conflict_event(archived, row)
        if event["event_id"] not in seen:
            conflicts.append(event)
            seen.add(event["event_id"])
        currency = row["currency"]
        horizon = row["observed_under_horizon"]
        quarantined.setdefault(currency, []).append({
            "contract": row["contract"], "observation_date": row["observation_date"],
            "horizon": horizon, "event_id": event["event_id"],
        })
        raw = updated["currencies"][currency]["horizons"][horizon]
        require(raw.get("contract") == row["contract"]
                and raw.get("quote_as_of") == row["observation_date"],
                "cannot quarantine a different horizon source")
        # The raw rate is retained as research evidence but is no longer
        # timestamp-certified for operational/policy repricing.
        raw["quote_timestamp_verified"] = False
        raw["quote_timestamp_source"] = "QUARANTINED_SAME_CONTRACT_SAME_DAY"
    for currency, keys in quarantined.items():
        entry = updated["currencies"][currency]
        entry["status"] = "LIVE_SECONDARY_CONFLICT_QUARANTINED"
        entry["source_conflict_status"] = STATUS
        entry["source_conflict_keys"] = keys
        entry["freshness_status"] = "SOURCE_CONFLICT_NOT_CERTIFIED"
        entry["note"] = (entry.get("note") or "") + (
            " Same listed contract and quote day had conflicting source values; "
            "first observed version retained, later version quarantined. "
            "No policy-level, OIS or daily repricing inference."
        )
    receipt = {
        "status": ("PARTIAL_SOURCE_CONFLICT_QUARANTINED"
                   if quarantined else "PASS_NO_SAME_DAY_SOURCE_CONFLICT"),
        "conflict_currencies": sorted(quarantined),
        "conflict_keys": quarantined,
        "new_quarantine_events": len(conflicts),
        "unaffected_eligible_contracts": len(eligible) - sum(map(len, quarantined.values())),
        "preexisting_source_exclusions": excluded,
        "official_ois_promoted": False,
        "market_repricing_from_conflicts": False,
    }
    return updated, conflicts, receipt


def apply(*, source: Path = SOURCE, history: Path = HISTORY,
          quarantine: Path = CONFLICTS, write: bool = False) -> dict:
    feed = json.loads(source.read_text(encoding="utf-8"))
    archived = load_history(history)
    prior = read_conflicts(quarantine)
    clean, events, receipt = reconcile(feed, archived, prior)
    # Assert only valid, non-conflicted sources reach the immutable bar writer.
    # This must succeed before any mutations to the runner worktree.
    append_verified(clean, history, write=False)
    if write:
        # Quarantine first, then mark operational quote feed; either failure
        # aborts subsequent steps/push, leaving main unchanged.
        if events:
            quarantine.parent.mkdir(parents=True, exist_ok=True)
            with quarantine.open("a", encoding="utf-8") as out:
                for event in events:
                    out.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        if clean != feed:
            source.write_text(json.dumps(clean, ensure_ascii=False, sort_keys=True,
                                         indent=2) + "\n", encoding="utf-8")
        require(len(read_conflicts(quarantine)) == len(prior) + len(events),
                "quarantine post-append integrity failure")
    receipt["feed_degraded_currencies"] = receipt["conflict_currencies"]
    receipt["written"] = len(events) if write else 0
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quotes", type=Path, default=SOURCE)
    parser.add_argument("--history", type=Path, default=HISTORY)
    parser.add_argument("--quarantine", type=Path, default=CONFLICTS)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = apply(source=args.quotes, history=args.history,
                   quarantine=args.quarantine, write=args.write)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
