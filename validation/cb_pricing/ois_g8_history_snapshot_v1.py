#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIEW_PATH = ROOT / "live_data/sections/OIS_OPERATIONAL_VIEW.json"
HISTORY_PATH = ROOT / "validation/cb_pricing/history/OIS_G8_SNAPSHOTS_V1.jsonl"
CCYS = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
HORIZONS = ("3m", "6m", "12m")
OFFICIAL_METHOD_ID = "OFFICIAL_CERTIFIED_V1"


def _method_id(row: dict) -> str:
    if row.get("operational_status") == "GREEN_OFFICIAL":
        return OFFICIAL_METHOD_ID
    return row.get("method_id") or "UNKNOWN_ESTIMATED_METHOD"


def _payload(currency: str, row: dict) -> dict:
    horizons = row.get("horizons") or {}
    return {
        "currency": currency,
        "operational_status": row.get("operational_status"),
        "quality": row.get("quality"),
        "confidence": row.get("confidence"),
        "official_status": row.get("official_status"),
        "input_mode": row.get("input_mode"),
        "method_id": _method_id(row),
        "source_as_of": row.get("as_of"),
        "source": row.get("source"),
        "policy_rate": row.get("policy_rate"),
        "direction_vs_policy": row.get("direction_vs_policy"),
        "backtest_eligible_as_official": row.get("backtest_eligible_as_official"),
        "horizons": {
            h: {
                "rate": (horizons.get(h) or {}).get("rate"),
                "policy_delta_bp": (horizons.get(h) or {}).get("policy_delta_bp"),
            }
            for h in HORIZONS
        },
    }


def _fingerprint(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def make_record(currency: str, row: dict, captured_at_utc: str) -> dict:
    payload = _payload(currency, row)
    return {
        "schema": "GMFQ_OIS_G8_SNAPSHOT_V1",
        "captured_at_utc": captured_at_utc,
        **payload,
        "fingerprint": _fingerprint(payload),
    }


def append_snapshots(view: dict, captured_at_utc: str, path: Path) -> dict:
    currencies = view.get("currencies") or {}
    missing = [c for c in CCYS if c not in currencies]
    if missing:
        raise SystemExit(f"missing G8 currencies in operational view: {missing}")

    for c in CCYS:
        status = (currencies[c] or {}).get("operational_status")
        if status not in {"GREEN_OFFICIAL", "GREEN_ESTIMATED"}:
            raise SystemExit(f"{c}: unsupported operational status {status!r}")

    history = load_history(path)
    latest_fp: dict[str, str | None] = {}
    for rec in history:
        latest_fp[rec.get("currency")] = rec.get("fingerprint")

    appended: list[dict] = []
    for c in CCYS:
        rec = make_record(c, currencies[c], captured_at_utc)
        if latest_fp.get(c) == rec["fingerprint"]:
            continue
        appended.append(rec)

    if appended:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for rec in appended:
                fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

    return {
        "status": "PASS",
        "g8_total": 8,
        "appended": len(appended),
        "currencies": [x["currency"] for x in appended],
        "history_path": str(path),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--view", default=str(VIEW_PATH))
    ap.add_argument("--history", default=str(HISTORY_PATH))
    ap.add_argument("--captured-at-utc")
    args = ap.parse_args()

    captured = args.captured_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    view = json.loads(Path(args.view).read_text(encoding="utf-8"))
    if view.get("status") != "GREEN_8_OF_8":
        raise SystemExit(f"operational OIS view is not GREEN_8_OF_8: {view.get('status')}")
    result = append_snapshots(view, captured, Path(args.history))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
