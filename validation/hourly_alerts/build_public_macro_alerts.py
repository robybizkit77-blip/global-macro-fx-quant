#!/usr/bin/env python3
"""Publish a deliberately small, fail-closed public view of certified alerts.

This is a presentation adapter.  It never changes canonical data, upgrades an
estimated input, or turns an empty hourly run into a news item.  The gh-pages
copy is the history store; only event ids that passed the existing receipt and
outbox checks may be appended to it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "GMFQ_PUBLIC_MACRO_MARKET_ALERTS_V1"
MAX_HISTORY = 100
PAIR_BY_CCY = {
    "USD": ("EURUSD", "USDJPY"), "EUR": ("EURUSD", "EURGBP"),
    "GBP": ("GBPUSD", "EURGBP"), "JPY": ("USDJPY", "EURJPY"),
    "CHF": ("USDCHF", "EURCHF"), "CAD": ("USDCAD", "EURCAD"),
    "AUD": ("AUDUSD", "EURAUD"), "NZD": ("NZDUSD", "EURNZD"),
}


def load(path: Path | None) -> Any:
    if not path or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def event_item(receipt: dict[str, Any], outbox: dict[str, Any]) -> dict[str, Any] | None:
    macro = receipt.get("lanes", {}).get("macro", {})
    event = macro.get("event") if isinstance(macro, dict) else None
    if (outbox.get("kind") != "SIGNIFICANT" or not isinstance(event, dict)
            or macro.get("alert_eligible") is not True):
        return None
    event_id = event.get("event_id")
    source = event.get("source", {})
    if not isinstance(event_id, str) or not isinstance(source, dict):
        return None
    ccy = event.get("currency")
    if not isinstance(ccy, str) or not isinstance(event.get("release_timestamp_utc"), str):
        return None
    if not all(isinstance(event.get(x), (int, float)) and not isinstance(event.get(x), bool)
               for x in ("actual", "consensus", "previous")):
        return None
    pairs = PAIR_BY_CCY.get(ccy, ())
    return {
        "event_id": event_id,
        "observed_at_utc": event["release_timestamp_utc"],
        "as_of_utc": event.get("as_of_utc"),
        "currency": ccy,
        "indicator": event.get("indicator"),
        "period": event.get("period"),
        "actual": event["actual"], "consensus": event["consensus"],
        "previous": event["previous"], "revisions": event.get("revisions", []),
        "source": {"authority": source.get("authority"), "release_url": source.get("release_url"),
                   "consensus_provider": source.get("consensus_provider"),
                   "consensus_as_of_utc": source.get("consensus_as_of_utc")},
        "related_pairs": list(pairs),
        "certification": "CERTIFIED_MACRO_TO_OIS_2Y_FX_AUDIT",
    }


def build(receipt: Any, outbox: Any, previous: Any) -> dict[str, Any]:
    generated = receipt.get("generated_at_utc") if isinstance(receipt, dict) else None
    current = event_item(receipt, outbox) if isinstance(outbox, dict) else None
    old = previous.get("history", []) if isinstance(previous, dict) else []
    old = old if isinstance(old, list) else []
    history, seen = [], set()
    for row in ([current] if current else []) + old:
        if not isinstance(row, dict) or not isinstance(row.get("event_id"), str) or row["event_id"] in seen:
            continue
        seen.add(row["event_id"]); history.append(row)
    history = history[:MAX_HISTORY]
    reason = None
    if not current:
        reason = (outbox.get("withheld_reason") if isinstance(outbox, dict) else None) or \
            "Nessun evento macro certificato, fresco e non duplicato nell'ultima verifica."
    return {
        "schema": SCHEMA, "generated_at_utc": generated,
        "as_of_evaluation_date": receipt.get("as_of_evaluation_date") if isinstance(receipt, dict) else None,
        "state": "ACTIVE" if current else "WITHHELD",
        "withheld_reason": reason,
        "today": [current] if current else [],
        "history": history,
        "policy": {"fail_closed": True, "today_limit": 5, "empty_feed_creates_no_event": True,
                   "deduplicate_by": "event_id", "canonical_engine_modified": False},
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--outbox", type=Path, required=True)
    p.add_argument("--previous", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = build(load(a.receipt), load(a.outbox), load(a.previous))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"state": result["state"], "today": len(result["today"]), "history": len(result["history"])}))


if __name__ == "__main__":
    main()
