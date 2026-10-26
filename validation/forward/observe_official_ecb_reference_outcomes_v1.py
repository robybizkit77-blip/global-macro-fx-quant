#!/usr/bin/env python3
"""Read-only ECB daily reference *comparison* of REAL prospective Core snapshots.

This is NOT realized P&L, execution-price performance, or a new Core signal.
No public endpoint is scraped. Uses already-stored ECB reference observations.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
FX_PATH = ROOT / "live_data/sections/ECB_G8_PRICE_HISTORY.json"
DECISIONS = ROOT / "validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl"
REFERENCE_LOG = ROOT / "validation/forward/reference_observations/ECB_REFERENCE_COMPARISONS_V1.jsonl"
SOURCE_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
HORIZONS = {"1D": 1, "3D": 3, "1W": 7, "2W": 14, "1M": 30, "3M": 90}
ROME = ZoneInfo("Europe/Rome")
SCHEMA = "GMFQ_FORWARD_ECB_REFERENCE_COMPARISON_V1"


def canonical(record):
    return (json.dumps(record, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def digest(record):
    return hashlib.sha256(canonical(record)).hexdigest()


def stamp(value):
    if not isinstance(value, str):
        raise ValueError("missing ISO timestamp")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid ISO timestamp") from exc
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return d.astimezone(timezone.utc)


def rows(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def finite_price(value):
    return (type(value) in (int, float) and math.isfinite(value) and value > 0)


def source_map(source):
    if (not isinstance(source, dict) or source.get("schema") != "GMFQ_ECB_G8_PRICE_HISTORY_V1"
            or source.get("status") != "CURRENT_OFFICIAL_HISTORY"
            or source.get("source_url") != SOURCE_URL
            or source.get("base") != "EUR"):
        raise ValueError("only existing official ECB history accepted")
    items = source.get("rows")
    if not isinstance(items, list) or not items:
        raise ValueError("ECB historical series absent")
    out, previous = {}, None
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("malformed ECB row")
        raw = item.get("Date")
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d").date()
            if parsed.isoformat() != raw:
                raise ValueError("non-canonical")
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid ECB fixing date") from exc
        if previous is not None and parsed <= previous:
            raise ValueError("duplicate/unordered ECB observations")
        previous = parsed
        if item.get("EUR") not in (1, 1.0):
            raise ValueError("ECB EUR base is not 1")
        for key, val in item.items():
            if key != "Date" and not finite_price(val):
                raise ValueError("invalid/zero/NaN ECB fixing rate")
        out[parsed] = item
    if source.get("last_as_of") != previous.isoformat():
        raise ValueError("ECB as-of does not match last observed row")
    return out


def cross(row, base, quote):
    if row is None:
        return None
    b = row.get(base)
    q = row.get(quote)
    if not finite_price(b) or not finite_price(q):
        return None
    return float(q) / float(b)


def eligible_decision(snap, fx_rows):
    if snap.get("capture_class") != "FROZEN_CORE_BASELINE_OBSERVATION":
        return None  # Old October 14 smoke is historical, never promoted.
    if snap.get("schema_version") != "GMFQ_CORE_FORWARD_DECISION_LOGGER_V1.1.0":
        raise ValueError("unknown prospective snapshot schema")
    stored_sha = snap.get("snapshot_sha256")
    body = {k:v for k,v in snap.items() if k != "snapshot_sha256"}
    if stored_sha != digest(body):
        raise ValueError("corrupted prospective snapshot hash")
    cutoff = stamp(snap.get("decision_cutoff"))
    event_day = cutoff.astimezone(ROME).date()
    if (snap.get("core_recomputed_at_capture") is not False
            or snap.get("current_macro_score_certified") is not False
            or snap.get("price_anchor_is_executable") is not False):
        raise ValueError("frozen Core source is incorrectly promoted")
    if snap.get("core_baseline_as_of") != "2026-09-25":
        raise ValueError("unexpected frozen Core baseline vintage")
    pair = snap.get("pair")
    if not isinstance(pair, str) or pair.count("/") != 1:
        raise ValueError("invalid forward pair")
    base, quote = pair.split("/")
    if len(base) != 3 or len(quote) != 3 or base == quote:
        raise ValueError("invalid pair currency identifiers")
    t0 = snap.get("t0_fx_reference")
    if not isinstance(t0, dict) or t0.get("state") != "OBSERVED_AT_CAPTURE":
        return None  # Validly WITHHELD price has no reference-return denominator.
    if (t0.get("pair") != pair or t0.get("source_date") != event_day.isoformat()
            or t0.get("source_id") != "live_data/sections/ECB_G8_PRICE_HISTORY.json"
            or t0.get("intra_day_traded_price") is not False
            or t0.get("official_publication_instant_independently_verified") is not False
            or t0.get("layer") != "ECB_DAILY_REFERENCE_NOT_EXECUTABLE_SPOT"):
        raise ValueError("invalid point-in-time reference price provenance")
    if not finite_price(t0.get("rate")):
        raise ValueError("invalid T0 ECB anchor")
    inp = snap.get("inputs")
    if not isinstance(inp, dict) or inp.get("ecb_reference") != t0:
        raise ValueError("T0 reference differs from saved input")
    prov = snap.get("source_provenance", {}).get("ecb_reference", {})
    if (prov.get("source_id") != t0["source_id"]
            or prov.get("sha256") != t0.get("source_sha256")):
        raise ValueError("original source checksum provenance mismatch")
    initial = cross(fx_rows.get(event_day), base, quote)
    if initial is None:
        raise ValueError("historical T0 fixing not in ECB source history")
    if not math.isclose(initial, t0["rate"], rel_tol=1e-9, abs_tol=1e-10):
        raise ValueError("historical ECB T0 fixing revised; manual audit required")
    return cutoff, event_day, pair, base, quote, initial


def compute(decisions, fx, now, prior=()):
    """Produce only matured, uniquely comparable ECB *reference* observations."""
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("as-of instant must have timezone")
    instant = now.astimezone(timezone.utc)
    locale = instant.astimezone(ROME)
    fx_rows = source_map(fx)
    if not isinstance(decisions, list) or not isinstance(prior, (tuple, list)):
        raise ValueError("invalid input ledgers")

    # To use today's official date, require a local evening as-of instant.
    latest_allowed = locale.date()
    if locale.hour < 19:
        latest_allowed = latest_allowed - timedelta(days=1)

    previous = set()
    for item in prior:
        if not isinstance(item, dict):
            raise ValueError("corrupt reference comparison journal")
        key = (item.get("snapshot_id"), item.get("horizon"))
        if key in previous or item.get("schema") != SCHEMA:
            raise ValueError("duplicate or unknown archived reference comparison")
        if item.get("observation_sha256") != digest(
                {k:v for k,v in item.items() if k != "observation_sha256"}):
            raise ValueError("archived reference comparison hash mismatch")
        previous.add(key)

    additions = []
    blockers = {"no_t0":0, "waiting":0, "source_gap":0, "matured":0}
    seen = set()
    for snap in decisions:
        if not isinstance(snap, dict):
            raise ValueError("malformed decision entry")
        sid = snap.get("snapshot_id")
        if not isinstance(sid, str) or sid in seen:
            raise ValueError("duplicated/bad decision snapshot IDs")
        seen.add(sid)
        valid = eligible_decision(snap, fx_rows)
        if valid is None:
            blockers["no_t0"] += 1
            continue
        cutoff, day, pair, base, quote, start = valid
        if cutoff > instant:
            raise ValueError("prospective cutoff in the future")
        for horizon, duration in HORIZONS.items():
            key = (sid, horizon)
            if key in previous:
                continue
            maturity = cutoff + timedelta(days=duration)
            if instant < maturity:
                blockers["waiting"] += 1
                continue
            target = maturity.astimezone(ROME).date()
            candidates = [d for d in fx_rows if target <= d <= latest_allowed]
            if not candidates:
                blockers["waiting"] += 1
                continue
            observed_on = min(candidates)
            # A holiday/weekend may move the next fixing, but never interpolate
            # across a material market data gap.
            if (observed_on - target).days > 4:
                blockers["source_gap"] += 1
                continue
            end = cross(fx_rows[observed_on], base, quote)
            if end is None:
                blockers["source_gap"] += 1
                continue
            pip = 0.01 if quote == "JPY" else 0.0001
            rec = {
                "schema": SCHEMA,
                "capture_class": "FROZEN_CORE_BASELINE_OBSERVATION",
                "snapshot_id": sid,
                "pair": pair, "horizon": horizon,
                "horizon_calendar_days": duration,
                "decision_cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
                "t0_fixing_date": day.isoformat(), "t0_ecb_rate": start,
                "target_due_date": target.isoformat(),
                "observed_reference_date": observed_on.isoformat(),
                "observed_ecb_rate": end,
                "gap_after_due_days": (observed_on - target).days,
                "quote_unit": f"{quote}_PER_{base}",
                "observed_reference_return_pct": round((end/start-1)*100, 7),
                "observed_reference_change_pips": round((end-start)/pip, 5),
                "reference_source": SOURCE_URL,
                "reference_source_type": "OFFICIAL_ECB_DAILY_NON_EXECUTABLE_FIXING",
                "trade_gross_return": None,
                "trade_cost_bps": None,
                "trade_net_return": None,
                "trade_pnl": None,
                "model_out_of_sample_performance_certified": False,
                "recomputed_core_signal": False,
                "event_causality": "NOT_ESTABLISHED",
                "source_vintage_time_for_historical_fixing_verified": False,
            }
            rec["observation_sha256"] = digest(rec)
            additions.append(rec)
            blockers["matured"] += 1
    return {
        "schema": "GMFQ_FORWARD_ECB_REFERENCE_AUDIT_RECEIPT_V1",
        "status": "REFERENCE_ONLY_NOT_TRADE_PERFORMANCE",
        "evaluated_at_utc": instant.isoformat().replace("+00:00", "Z"),
        "new_reference_observations": len(additions),
        "source_fx_last_as_of": fx.get("last_as_of"),
        "blocked_and_waiting": blockers,
        "no_fake_costs": True,
        "no_model_effect": True,
        "no_trading_pnl_claims": True,
        "new_rows": additions,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--append-journal", action="store_true")
    args = parser.parse_args()
    if not args.receipt.resolve().is_relative_to(Path("/tmp")):
        parser.error("QA receipt must be under /tmp")
    now = datetime.now(timezone.utc)
    data = compute(rows(DECISIONS), json.loads(FX_PATH.read_text(encoding="utf-8")),
                   now, rows(REFERENCE_LOG))
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(data, indent=2, sort_keys=True)+"\n",
                            encoding="utf-8")
    if args.append_journal and data["new_rows"]:
        REFERENCE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with REFERENCE_LOG.open("ab") as journal:
            for item in data["new_rows"]:
                journal.write(canonical(item))
    print(json.dumps({k:v for k,v in data.items() if k != "new_rows"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
