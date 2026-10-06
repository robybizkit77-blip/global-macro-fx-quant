#!/usr/bin/env python3
"""Build a canonical G8 FX history from official ECB euro reference rates.

Read-only validator: downloads ECB historical reference rates, freezes a requested
window, creates the canonical EUR-base matrix and verifies the 28 G8 crosses
against the frozen 2026-09-30 OOS anchors. It never writes live_data.
"""
from __future__ import annotations

import argparse
import json
import math
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ECB_HIST_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
NON_EUR = tuple(c for c in CURRENCIES if c != "EUR")

CANONICAL_PAIRS = (
    "AUD/CAD", "AUD/CHF", "AUD/JPY", "AUD/NZD", "AUD/USD",
    "CAD/CHF", "CAD/JPY", "CHF/JPY",
    "EUR/AUD", "EUR/CAD", "EUR/CHF", "EUR/GBP", "EUR/JPY", "EUR/NZD", "EUR/USD",
    "GBP/AUD", "GBP/CAD", "GBP/CHF", "GBP/JPY", "GBP/NZD", "GBP/USD",
    "NZD/CAD", "NZD/CHF", "NZD/JPY", "NZD/USD",
    "USD/CAD", "USD/CHF", "USD/JPY",
)

# Frozen OOS T0 V3 anchors captured from the production baseline on 2026-10-01.
FROZEN_2026_09_30_ROW = {
    "EUR": 1.0,
    "USD": 1.1355,
    "GBP": 0.85463,
    "JPY": 178.27,
    "CHF": 0.9478,
    "CAD": 1.6105,
    "AUD": 1.6297,
    "NZD": 2.0115,
}
FROZEN_PAIR_ANCHORS = {
    "AUD/CAD": 0.9882186905565442,
    "AUD/CHF": 0.5815794317972633,
    "AUD/JPY": 109.3882309627539,
    "AUD/NZD": 1.2342762471620543,
    "AUD/USD": 0.6967540038043811,
    "CAD/CHF": 0.5885128841974542,
    "CAD/JPY": 110.69233157404533,
    "CHF/JPY": 188.08820426250264,
    "EUR/AUD": 1.6297,
    "EUR/CAD": 1.6105,
    "EUR/CHF": 0.9478,
    "EUR/GBP": 0.85463,
    "EUR/JPY": 178.27,
    "EUR/NZD": 2.0115,
    "EUR/USD": 1.1355,
    "GBP/AUD": 1.9069070825971473,
    "GBP/CAD": 1.8844412201771528,
    "GBP/CHF": 1.109017937587026,
    "GBP/JPY": 208.59319237564796,
    "GBP/NZD": 2.3536501175947486,
    "GBP/USD": 1.328645144682494,
    "NZD/CAD": 0.8006462838677605,
    "NZD/CHF": 0.47119065374098934,
    "NZD/JPY": 88.62540392741737,
    "NZD/USD": 0.5645041014168531,
    "USD/CAD": 1.4183179216204316,
    "USD/CHF": 0.834698370761779,
    "USD/JPY": 156.99691765741966,
}


def fetch_xml(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "GMFQ-ECB-History-Validator/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    if not data or b"currency=" not in data:
        raise RuntimeError("ECB historical response is empty or malformed")
    return data


def parse_rows(xml_bytes: bytes, start: str, end: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    rows: list[dict] = []
    for node in root.iter():
        obs_date = node.attrib.get("time")
        if not obs_date or obs_date < start or obs_date > end:
            continue
        vals = {"EUR": 1.0}
        for child in list(node):
            ccy = child.attrib.get("currency")
            rate = child.attrib.get("rate")
            if ccy in NON_EUR and rate is not None:
                vals[ccy] = float(rate)
        if all(c in vals for c in CURRENCIES):
            row = {"Date": obs_date}
            row.update({c: vals[c] for c in CURRENCIES})
            rows.append(row)
    rows.sort(key=lambda r: r["Date"])
    return rows


def cross(row: dict, pair: str) -> float:
    base, quote = pair.split("/")
    return float(row[quote]) / float(row[base])


def pair_snapshot(row: dict) -> dict[str, float]:
    return {p: cross(row, p) for p in CANONICAL_PAIRS}


def max_triangle_error(row: dict) -> float:
    vals = {c: float(row[c]) for c in CURRENCIES}
    worst = 0.0
    for a in CURRENCIES:
        for b in CURRENCIES:
            if b == a:
                continue
            for c in CURRENCIES:
                if c in (a, b):
                    continue
                ab = vals[b] / vals[a]
                bc = vals[c] / vals[b]
                ac = vals[c] / vals[a]
                worst = max(worst, abs(ab * bc - ac))
    return worst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default="2018-01-01")
    ap.add_argument("--end-date", default="2026-09-30")
    ap.add_argument("--source-url", default=ECB_HIST_URL)
    ap.add_argument("--output", required=True)
    ap.add_argument("--summary", required=True)
    args = ap.parse_args()

    # Validate ISO dates early.
    date.fromisoformat(args.start_date)
    date.fromisoformat(args.end_date)
    if args.start_date > args.end_date:
        raise ValueError("start date is after end date")

    raw = fetch_xml(args.source_url)
    rows = parse_rows(raw, args.start_date, args.end_date)
    if not rows:
        raise RuntimeError("no complete G8 ECB rows found in requested window")
    if rows[-1]["Date"] != args.end_date:
        raise RuntimeError(f"end-date row missing: expected {args.end_date}, got {rows[-1]['Date']}")

    end_row = rows[-1]
    row_errors = {
        c: abs(float(end_row[c]) - expected)
        for c, expected in FROZEN_2026_09_30_ROW.items()
    }
    max_row_error = max(row_errors.values())
    if max_row_error > 1e-12:
        raise RuntimeError(f"ECB fixing does not match frozen OOS row: {row_errors}")

    end_pairs = pair_snapshot(end_row)
    pair_errors = {
        p: abs(end_pairs[p] - FROZEN_PAIR_ANCHORS[p])
        for p in CANONICAL_PAIRS
    }
    max_pair_error = max(pair_errors.values())
    if max_pair_error > 1e-10:
        raise RuntimeError(f"pair anchors do not match frozen OOS baseline: {pair_errors}")

    triangle_errors = [max_triangle_error(r) for r in rows]
    max_tri = max(triangle_errors)
    if not math.isfinite(max_tri) or max_tri > 1e-10:
        raise RuntimeError(f"triangular consistency failed: max error {max_tri}")

    payload = {
        "schema": "GMFQ_ECB_FX_HISTORY_V1",
        "source": "European Central Bank euro foreign exchange reference rates",
        "source_url": args.source_url,
        "basis": "units of quoted currency per 1 EUR; EUR=1",
        "start_date": rows[0]["Date"],
        "end_date": rows[-1]["Date"],
        "currencies": list(CURRENCIES),
        "canonical_pairs": list(CANONICAL_PAIRS),
        "rows": rows,
    }
    summary = {
        "schema": "GMFQ_ECB_FX_HISTORY_VALIDATION_V1",
        "status": "PASS",
        "source": "ECB official euro reference rates",
        "source_url": args.source_url,
        "requested_start": args.start_date,
        "requested_end": args.end_date,
        "first_observation": rows[0]["Date"],
        "last_observation": rows[-1]["Date"],
        "observation_count": len(rows),
        "currency_count": len(CURRENCIES),
        "pair_count": len(CANONICAL_PAIRS),
        "anchor_row": {c: end_row[c] for c in CURRENCIES},
        "max_anchor_row_error": max_row_error,
        "max_pair_anchor_error": max_pair_error,
        "max_triangular_error": max_tri,
        "frozen_oos_anchor_match": True,
        "live_data_modified": False,
        "model_rules_modified": False,
        "rules_fingerprint_expected_unchanged": "3356baf0",
    }

    out = Path(args.output)
    summ = Path(args.summary)
    out.parent.mkdir(parents=True, exist_ok=True)
    summ.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    summ.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
