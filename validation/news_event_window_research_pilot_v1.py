#!/usr/bin/env python3
"""Read-only EUR/USD event-window bridge from the existing bounded BI5 probe.

This bridge does not fetch ticks, confirm source usage rights, or certify
that a scheduled publication instant was the moment news reached the market.
It never modifies live_data or any model/backtest/score.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
import re

from validation.macro.v2_dukascopy_bi5_hour_probe_v1 import source_clock

SCHEMA = "GMFQ_NEWS_EURUSD_EVENT_WINDOW_RESEARCH_V1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
WINDOW = timedelta(minutes=2)
TARGET = timedelta(minutes=5)


def _instant(value):
    if not isinstance(value, str):
        raise ValueError("explicit offset-aware ISO event/quote timestamp required")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timezone-naive timestamps are not permitted")
    return stamp.astimezone(timezone.utc)


def _number(value):
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("nonfinite or nonnumeric price")
    return float(value)


def _quote(value, *, hour):
    if not isinstance(value, dict):
        raise ValueError("missing timestamped bid/ask quote")
    ts = _instant(value.get("observed_at_utc"))
    bid = _number(value.get("bid"))
    ask = _number(value.get("ask"))
    mid = _number(value.get("mid"))
    if not (0.5 < bid <= ask < 2.5):
        raise ValueError("invalid EURUSD quote or crossed market")
    if not (hour <= ts < hour + timedelta(hours=1)):
        raise ValueError("quote falls outside the hashed BI5 source hour")
    if abs(mid - (bid + ask) / 2) > 0.00000011:
        raise ValueError("quote mid is inconsistent with bid/ask")
    return {"at_utc": ts, "bid": bid, "ask": ask, "mid": mid}


def _base(reason, status):
    return {
        "schema": SCHEMA,
        "status": status,
        "reason": reason,
        "market": "EURUSD",
        "intraday_fx_descriptive_window": False,
        "independently_verified_release_instant": False,
        "source_usage_rights_independently_verified": False,
        "intraday_ois": "NOT_AVAILABLE",
        "intraday_government_2y": "NOT_AVAILABLE",
        "cross_asset_event_confirmation": "NOT_AVAILABLE",
        "market_reaction": "NOT_CERTIFIED",
        "causal_attribution": "NOT_ESTABLISHED",
        "eligible_for_score": False,
        "eligible_for_backtest": False,
        "safe_to_publish_live_data": False,
        "safe_to_update_pair_theses": False,
        "writes_live_data": False,
    }


def audit(probe, event):
    """Assess a caller-supplied probe, never an automatic production feed.

    'event' must identify an independently linkable official calendar source;
    it is *not* considered proof of the actual first-news/trading timestamp.
    """
    if not isinstance(probe, dict) or not isinstance(event, dict):
        return _base("No probe/event receipt", "MISSING_SOURCE")
    receipt = probe.get("transport_receipt")
    if not isinstance(receipt, dict) or probe.get("source_bytes_externally_retrieved") is not True:
        return _base("No externally acquired transport receipt", "NO_EXTERNAL_TRANSPORT_RECEIPT")
    try:
        url = probe["source_url"]
        hour, _ = source_clock(url)  # Canonical EURUSD-only URL, zero-based month.
        if receipt.get("effective_url") != url or receipt.get("http_status") != 200:
            raise ValueError("transport URL or HTTP status inconsistent")
        if receipt.get("content_length") != probe.get("source_bytes_n") or (
            type(probe.get("source_bytes_n")) is not int or
            not 0 < probe["source_bytes_n"] <= 10_000_000
        ):
            raise ValueError("source byte count not attested")
        if not isinstance(probe.get("source_sha256"), str) or not HEX64.fullmatch(probe["source_sha256"]):
            raise ValueError("missing content SHA-256")
        if type(probe.get("tick_count")) is not int or probe["tick_count"] <= 0:
            raise ValueError("missing decoded ticks")
        if not isinstance(event.get("official_event_source_url"), str) or not (
            event["official_event_source_url"].startswith("https://www.bls.gov/")
        ):
            raise ValueError("missing official BLS event source")
        release = _instant(event.get("scheduled_release_utc"))
        if release != _instant(probe.get("release_at")):
            raise ValueError("event and probe target timestamps do not match")
        if not hour <= release < hour + timedelta(hours=1):
            raise ValueError("event outside the source BI5 hour")
        pre = _quote(probe.get("pre_0825_new_york"), hour=hour)
        post = _quote(probe.get("post_0835_new_york"), hour=hour)
        if not (pre["at_utc"] < release < post["at_utc"]):
            raise ValueError("market quotes are not on opposite sides of release")
        if abs(pre["at_utc"] - (release - TARGET)) > WINDOW:
            raise ValueError("pre-event quote outside target tolerance")
        if abs(post["at_utc"] - (release + TARGET)) > WINDOW:
            raise ValueError("post-event quote outside target tolerance")
        delta = round((post["mid"] - pre["mid"]) * 10000, 3)
        reported = _number(probe.get("mid_move_pips"))
        if abs(delta - reported) > 0.003:
            raise ValueError("reported pip delta disagrees with auditable quotes")
    except (KeyError, TypeError, ValueError) as exc:
        return _base(str(exc), "INVALID_OR_INCOMPLETE_PROBE")

    out = _base(
        "Observed bid/ask difference around an official scheduled time; "
        "source licence and actual first-disclosure time are not certified.",
        "DESCRIPTIVE_FX_WINDOW_RIGHTS_UNVERIFIED",
    )
    out.update({
        "intraday_fx_descriptive_window": True,
        "scheduled_release_utc": release.isoformat(),
        "official_event_source_url": event["official_event_source_url"],
        "source_url": url,
        "source_sha256": probe["source_sha256"],
        "source_byte_count": probe["source_bytes_n"],
        "source_tick_count": probe["tick_count"],
        "pre_quote_utc": pre["at_utc"].isoformat(),
        "post_quote_utc": post["at_utc"].isoformat(),
        "pre_mid": pre["mid"],
        "post_mid": post["mid"],
        "delta_pips": delta,
        "quote_selection": "ORIGINAL_BI5_PROBE_RECEIPT_NOT_INDEPENDENTLY_REDECODED",
        "comparability": "SAME_SPOT_FX_PAIR_SAME_SOURCE_HOUR",
    })
    return out


def main():
    """Convert an existing audit receipt into a research-only local JSON record."""
    import argparse
    import json
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", type=Path, required=True)
    ap.add_argument("--release-utc", required=True)
    ap.add_argument("--official-event-url", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if not args.out.resolve().is_relative_to(Path("/tmp")):
        ap.error("research-only output must remain under /tmp")
    probe = json.loads(args.probe.read_text(encoding="utf-8"))
    result = audit(probe, {
        "scheduled_release_utc": args.release_utc,
        "official_event_source_url": args.official_event_url,
    })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    if not result["intraday_fx_descriptive_window"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
