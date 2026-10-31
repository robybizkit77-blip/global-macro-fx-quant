#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIEW_PATH = ROOT / "live_data/sections/OIS_OPERATIONAL_VIEW.json"
HISTORY_PATH = ROOT / "validation/cb_pricing/history/OIS_ESTIMATED_SNAPSHOTS_V1.jsonl"
ESTIMATED = ("USD", "EUR", "CHF", "NZD")
HORIZONS = ("3m", "6m", "12m")
LEGACY_METHOD_ID = "NATIVE_CB_ESTIMATED_V1"


def method_id(row: dict) -> str:
    # All snapshots written before method_id existed were produced by the
    # original NATIVE_CB estimated builder. Preserve that lineage explicitly.
    return row.get("method_id") or LEGACY_METHOD_ID


def _canonical_payload(currency: str, row: dict) -> dict:
    return {
        "currency": currency,
        "method_id": method_id(row),
        "source_as_of": row.get("as_of"),
        "source": row.get("source"),
        "confidence": row.get("confidence"),
        "horizons": {
            h: {
                "rate": ((row.get("horizons") or {}).get(h) or {}).get("rate"),
                "policy_delta_bp": ((row.get("horizons") or {}).get(h) or {}).get("policy_delta_bp"),
            }
            for h in HORIZONS
        },
    }


def fingerprint(currency: str, row: dict) -> str:
    payload = _canonical_payload(currency, row)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_history(path: Path = HISTORY_PATH) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def make_record(currency: str, row: dict, captured_at_utc: str) -> dict:
    payload = _canonical_payload(currency, row)
    return {
        "schema": "GMFQ_OIS_ESTIMATED_SNAPSHOT_V1",
        "captured_at_utc": captured_at_utc,
        **payload,
        "fingerprint": fingerprint(currency, row),
    }


def append_changed_snapshots(view: dict, captured_at_utc: str, path: Path = HISTORY_PATH) -> dict:
    history = load_history(path)
    latest = {}
    for rec in history:
        latest[rec["currency"]] = rec
    appended = []
    for currency in ESTIMATED:
        row = (view.get("currencies") or {}).get(currency) or {}
        if row.get("source_conflict_status") == (
                "UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT"):
            # Indicative levels may remain visible, but no new estimated
            # snapshot/repricing reference can be derived from disputed bars.
            continue
        if row.get("operational_status") == "WITHHELD":
            continue  # No observation: do not append stale or synthetic history.
        if row.get("operational_status") != "GREEN_ESTIMATED":
            raise SystemExit(f"{currency}: expected GREEN_ESTIMATED")
        rec = make_record(currency, row, captured_at_utc)
        prev = latest.get(currency)
        prev_fp = None if prev is None else prev.get("fingerprint")
        # Historical fingerprints did not include method_id. Reconstruct only
        # for same-method legacy rows; a method transition must append a new row.
        if prev is not None and method_id(prev) != rec["method_id"]:
            prev_fp = None
        elif prev_fp is None and prev is not None:
            prev_fp = fingerprint(currency, {
                "method_id": method_id(prev),
                "as_of": prev.get("source_as_of"),
                "source": prev.get("source"),
                "confidence": prev.get("confidence"),
                "horizons": prev.get("horizons") or {},
            })
        if prev_fp == rec["fingerprint"]:
            continue
        appended.append(rec)
    if appended:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for rec in appended:
                fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    return {"status": "PASS", "appended": len(appended), "currencies": [x["currency"] for x in appended]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--captured-at-utc")
    p.add_argument("--view", default=str(VIEW_PATH))
    p.add_argument("--history", default=str(HISTORY_PATH))
    args = p.parse_args()
    captured = args.captured_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    view = json.loads(Path(args.view).read_text(encoding="utf-8"))
    result = append_changed_snapshots(view, captured, Path(args.history))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
