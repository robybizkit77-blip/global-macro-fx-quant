#!/usr/bin/env python3
"""Future-only, research-only HY risk filter shadow capture. Never changes FX Core."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "validation/quant/HY_FX_RISK_FORWARD_PREREGISTERED_V1.json"
SNAPSHOTS = ROOT / "validation/quant/prospective/HY_FX_RISK_FROZEN_SNAPSHOTS_V1.jsonl"
OUTCOMES = ROOT / "validation/quant/prospective/HY_FX_RISK_FUTURE_ECB_OUTCOMES_V1.jsonl"
FX = ROOT / "live_data/sections/ECB_G8_PRICE_HISTORY.json"
ROME = ZoneInfo("Europe/Rome")
PAIRS = {"AUDJPY": ("AUD", "JPY"), "NZDJPY": ("NZD", "JPY"),
         "AUDCHF": ("AUD", "CHF"), "AUDUSD": ("AUD", "USD")}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def seal(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical({**record, "record_sha256": seal(record)}) + "\n")


def check_policy():
    obj = json.loads(POLICY.read_text(encoding="utf-8"))
    assert obj["schema"] == "GMFQ_HY_FX_RISK_FORWARD_PREREGISTRATION_V1"
    assert obj["earliest_eligible_capture_rome"] == "2026-11-10"
    assert obj["primary_pair"] == "AUDJPY"
    assert obj["time"]["hy_threshold_bp"] == 10
    assert obj["signal"]["primary_direction"] == "Long-only, no short or automatic reverse"
    assert obj["eligible_for_live_engine"] is False
    assert obj["eligible_for_trading"] is False
    return obj, hashlib.sha256(POLICY.read_bytes()).hexdigest()


def can_capture(now, policy):
    local = now.astimezone(ROME)
    time_ok = (20, 30) <= (local.hour, local.minute) <= (21, 5)
    return (local.weekday() < 5 and
            local.date().isoformat() >= policy["earliest_eligible_capture_rome"] and
            time_ok)


def source_text(url):
    req = Request(url, headers={"User-Agent": "GlobalMacroFXQuant-HYForwardResearch/1.0"})
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")


def fred_csv(text, col):
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or col not in reader.fieldnames:
        raise ValueError("Missing FRED field: " + col)
    date_col = "observation_date" if "observation_date" in reader.fieldnames else "DATE"
    if date_col not in reader.fieldnames:
        raise ValueError("Missing FRED observation date")
    rows = []
    for row in reader:
        try:
            value = float(row[col])
        except (ValueError, TypeError):
            continue
        date = row[date_col]
        if len(date) != 10 or not math.isfinite(value):
            continue
        rows.append((date, value))
    return sorted(rows)


def fx_cross(row, pair):
    base, quote = PAIRS[pair]
    return float(row[quote]) / float(row[base])


def build_snapshot(now, policy_sha, fx_rows, hy, vix):
    local_date = now.astimezone(ROME).date().isoformat()
    base = {
        "schema": "GMFQ_HY_FX_FORWARD_SNAPSHOT_V1",
        "capture_rome_date": local_date,
        "captured_at_utc": now.isoformat().replace("+00:00", "Z"),
        "policy_sha256": policy_sha,
        "status": "ABSTAIN",
        "reason": None,
        "source": {"ECB_history_latest": fx_rows[-1]["Date"] if fx_rows else None},
        "pairs": {},
    }
    if len(fx_rows) < 21 or fx_rows[-1]["Date"] != local_date:
        base["reason"] = "NO_SAME_DAY_ECB_FIXING"
        return base
    earlier = [item for item in hy if item[0] < local_date]
    if len(earlier) < 7:
        base["reason"] = "INSUFFICIENT_HY_HISTORY"
        return base
    hy_now, hy_before = earlier[-2], earlier[-7]
    age = (datetime.fromisoformat(local_date) - datetime.fromisoformat(hy_now[0])).days
    if age > 8:
        base["reason"] = "STALE_HY_OBSERVATION"
        return base
    hy_bp = round(100 * (hy_now[1] - hy_before[1]), 2)
    stress = hy_bp >= 10.0
    vix_prior = [item for item in vix if item[0] < local_date]
    vix_latest = vix_prior[-1] if vix_prior else None
    base["source"].update({
        "hy_observation_date": hy_now[0],
        "hy_five_observations_before": hy_before[0],
        "hy_value_pct": hy_now[1],
        "hy_prior_value_pct": hy_before[1],
        "hy_delta_5_bp": hy_bp,
        "vix_observation_date": vix_latest[0] if vix_latest else None,
        "vix_value": vix_latest[1] if vix_latest else None,
        "ecb_momentum_reference_date": fx_rows[-21]["Date"],
    })
    for pair in PAIRS:
        current_price = fx_cross(fx_rows[-1], pair)
        old_price = fx_cross(fx_rows[-21], pair)
        long_signal = int(current_price > old_price)
        base["pairs"][pair] = {
            "cross_t0": current_price, "cross_tminus20": old_price,
            "momentum20_long": long_signal,
            "hy_filtered_long": 0 if stress else long_signal,
        }
    base["status"] = "ELIGIBLE"
    base["reason"] = None
    return base


def mature_outcomes(now, fx_rows, snapshots, outcomes):
    today = now.astimezone(ROME).date().isoformat()
    existing = {r["capture_rome_date"] for r in outcomes}
    for snap in snapshots:
        t0 = snap["capture_rome_date"]
        if snap["status"] != "ELIGIBLE" or t0 in existing:
            continue
        later = [r for r in fx_rows if r["Date"] > t0 and r["Date"] <= today]
        if len(later) < 2:
            continue
        entry, exit_row = later[:2]
        rets = {
            pair: 100.0 * math.log(fx_cross(exit_row, pair) / fx_cross(entry, pair))
            for pair in PAIRS
        }
        append(OUTCOMES, {
            "schema": "GMFQ_HY_FX_FORWARD_REFERENCE_OUTCOME_V1",
            "capture_rome_date": t0,
            "observed_at_utc": now.isoformat().replace("+00:00", "Z"),
            "entry_ecb_fixing_date": entry["Date"],
            "exit_ecb_fixing_date": exit_row["Date"],
            "reference_log_return_pct": rets,
            "snapshot_sha256": snap["record_sha256"],
            "note": "Reference fixing outcome, not an executable FX trade/PnL",
        })
        existing.add(t0)


def capture():
    policy, sha = check_policy()
    now = datetime.now(timezone.utc)
    if not can_capture(now, policy):
        print("SKIP: outside strict future-only Rome capture window")
        return
    snaps = read_jsonl(SNAPSHOTS)
    outcomes = read_jsonl(OUTCOMES)
    if any(row["policy_sha256"] != sha for row in snaps):
        raise RuntimeError("Frozen research policy has changed; refusing to append")
    local_date = now.astimezone(ROME).date().isoformat()
    if any(row["capture_rome_date"] == local_date for row in snaps):
        print("IDEMPOTENT: today's snapshot already exists")
    else:
        fx_rows = json.loads(FX.read_text(encoding="utf-8"))["rows"]
        try:
            hy = fred_csv(source_text(policy["sources"]["hy_source_url"]), "BAMLH0A0HYM2")
            vix = fred_csv(source_text(policy["sources"]["vix_source_url"]), "VIXCLS")
            snap = build_snapshot(now, sha, fx_rows, hy, vix)
        except (OSError, ValueError, KeyError, TimeoutError) as exc:
            snap = {
                "schema": "GMFQ_HY_FX_FORWARD_SNAPSHOT_V1",
                "capture_rome_date": local_date,
                "captured_at_utc": now.isoformat().replace("+00:00", "Z"),
                "policy_sha256": sha,
                "status": "ABSTAIN",
                "reason": "SOURCE_ERROR_" + type(exc).__name__,
                "source": {}, "pairs": {},
            }
        append(SNAPSHOTS, snap)
        snaps.append({**snap, "record_sha256": seal(snap)})
        print("SNAPSHOT", local_date, snap["status"], snap.get("reason"))
    fx_rows = json.loads(FX.read_text(encoding="utf-8"))["rows"]
    mature_outcomes(now, fx_rows, snaps, outcomes)
    print("RESEARCH_ONLY: no FX Core, dashboard, or trading changes")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true", help="Append future-only research observation during real Rome window")
    args = parser.parse_args()
    policy, sha = check_policy()
    print("HY_FX_FORWARD_PROTOCOL_OK", policy["schema"], sha)
    if args.capture:
        capture()


if __name__ == "__main__":
    main()
