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


def validate_conflict_lineage(feed: dict, history: list[dict],
                              existing_events: list[dict]) -> dict:
    """Cross-check three independent receipts: immutable bar, event and live.

    A valid event_id by itself is NOT evidence that the current displayed
    tentative quote is the quote referenced by that event. Equally, a
    syntactically valid quarantined quote is NOT evidence that the original
    signed history was preserved. Neither can be silently reclassified.
    """
    archived = {record_key(row): row for row in history}
    events = {}
    for event in existing_events:
        original, incoming = (event["original_immutable_quote"],
                              event["conflicting_source_quote"])
        validate_row(original)
        validate_row(incoming)
        key = record_key(original)
        require(key in archived and
                quote_fingerprint(archived[key]) == quote_fingerprint(original),
                "quarantine original missing or diverges from immutable first quote")
        require(event == conflict_event(original, incoming),
                "quarantine event ID/payload integrity mismatch")
        require(event["event_id"] not in events, "duplicate journal event identity")
        events[event["event_id"]] = event

    checked = []
    for ccy in ("USD", "EUR", "CHF"):
        entry = ((feed.get("currencies") or {}).get(ccy) or {})
        flagged = entry.get("source_conflict_status") == STATUS
        keys = entry.get("source_conflict_keys")
        if not flagged:
            require(entry.get("source_conflict_status") is None
                    and keys is None,
                    ccy + ": unmanaged quarantine metadata")
            # One may collect newly timestamp-verified quotes with prior
            # historical conflicts; the old events remain append-only.
            require(entry.get("status") != "LIVE_SECONDARY_CONFLICT_QUARANTINED",
                    ccy + ": quarantined status without evidence")
            continue
        require(entry.get("status") == "LIVE_SECONDARY_CONFLICT_QUARANTINED"
                and isinstance(keys, list) and len(keys) > 0,
                ccy + ": quarantine status without matched horizon keys")
        visited = set()
        for k in keys:
            require(isinstance(k, dict) and
                    set(k) == {"contract", "observation_date", "horizon", "event_id"}
                    and k["horizon"] in ("3m", "6m", "12m")
                    and isinstance(k["event_id"], str) and
                    k["event_id"] in events,
                    ccy + ": nonexistent or malformed quarantine key")
            h = k["horizon"]
            require(h not in visited, ccy + ": same horizon quarantined twice")
            visited.add(h)
            event = events[k["event_id"]]
            incoming = event["conflicting_source_quote"]
            require(event["key"] == [ccy, k["contract"], k["observation_date"]]
                    and incoming["observed_under_horizon"] == h,
                    ccy + ": quarantine event does not describe claimed contract")
            q = ((entry.get("horizons") or {}).get(h) or {})
            require(
                q.get("contract") == incoming["contract"] and
                q.get("symbol") == incoming["symbol"] and
                q.get("expiration") == incoming["expiration"] and
                q.get("quote_as_of") == incoming["observation_date"] and
                type(q.get("rate")) in (int, float) and
                type(q.get("futures_price")) in (int, float) and
                q["rate"] == incoming["implied_rate"] and
                q["futures_price"] == incoming["futures_price"] and
                q.get("quote_timestamp_verified") is False and
                q.get("quote_timestamp_source") ==
                    "QUARANTINED_SAME_CONTRACT_SAME_DAY",
                ccy + "/" + h + ": displayed tentative quote not identical to signed event")
            checked.append((ccy, h, k["event_id"]))
        for h, q in (entry.get("horizons") or {}).items():
            if q.get("quote_timestamp_source") == "QUARANTINED_SAME_CONTRACT_SAME_DAY":
                require(h in visited and q.get("quote_timestamp_verified") is False,
                        ccy + ": quarantined raw quote without independently verified event")
    return {"journal_events_validated": len(events),
            "current_quarantine_horizons_verified": len(checked)}


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
    # A previously quarantined feed can be replayed by either OIS writer.
    # Do not let a forged/stale event_id or a mutated tentative quote bypass
    # the per-contract archive merely because candidates() skips it.
    existing_lineage = validate_conflict_lineage(feed, archived, prior)
    # On the first encounter, reconcile generates fresh events and updates the
    # feed in memory. Recheck the combined ledger BEFORE any persistent write.
    all_lineage = validate_conflict_lineage(clean, archived, prior + events)
    receipt["quarantine_evidence"] = all_lineage
    receipt["previous_events_checked"] = existing_lineage["journal_events_validated"]
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
