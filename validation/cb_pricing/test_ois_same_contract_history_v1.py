#!/usr/bin/env python3
"""Deterministic production-history and negative tests for futures contracts."""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from ois_same_contract_history_v1 import (
    HISTORY, SOURCE, append_verified, candidates, load_history, matched_moves,
    quote_fingerprint, validate_row,
)

LIVE = json.loads(SOURCE.read_text(encoding="utf-8"))
seed = load_history()
# Build a dated, immutable replay from the archived 2026-10-16/19/20 bars.
# Daily source feeds are allowed to move on: tests must not demand that 2026-10-21
# quote dates remain the latest on every future scheduled execution.
BASE = copy.deepcopy(LIVE)
BASE["generated_at_utc"] = "2026-10-21T06:57:19Z"
for code in ("USD", "EUR", "CHF"):
    for term in ("3m", "6m", "12m"):
        observed = [r for r in seed if r["currency"] == code and
                    r["observed_under_horizon"] == term]
        assert observed
        row = max(observed, key=lambda r: r["observation_date"])
        raw = BASE["currencies"][code]["horizons"][term]
        raw.update({
            "contract": row["contract"], "symbol": row["symbol"],
            "expiration": row["expiration"], "quote_as_of": row["observation_date"],
            "futures_price": row["futures_price"], "rate": row["implied_rate"],
            "quote_timestamp_verified": True,
            "quote_timestamp_source": "SSR_DAILY_BAR_DATA_UPDATE_TIME",
            "mapping": "nearest dated listed contract expiry to today+" +
             str({"3m": 90, "6m": 180, "12m": 365}[term]) + "d; no interpolation",
        })
assert len(seed) == 23, len(seed)
assert len({(x["currency"], x["contract"], x["observation_date"]) for x in seed}) == 23
assert {x["currency"] for x in seed} == {"USD", "EUR", "CHF"}
assert {x["observation_date"] for x in seed} == {
    "2026-10-16", "2026-10-19", "2026-10-20"
}
assert all(x["official_ois_quote"] is False and
           x["policy_delta_eligible"] is False and
           x["backtest_eligible_as_official"] is False for x in seed)
assert len({x["source_commit"] for x in seed}) == 3

deltas = matched_moves(seed)
def find(ccy, code, initial, final):
    data = [r for r in deltas if r["currency"] == ccy and
            r["symbol"].endswith(":" + code) and
            r["from_date"] == initial and r["to_date"] == final]
    assert len(data) == 1, (ccy, code, initial, final, data)
    assert data[0]["is_same_instrument"] and not data[0]["is_exactly_one_session"]
    assert data[0]["is_verified_daily_ois_repricing"] is False
    assert data[0]["policy_repricing_signal"] is False
    return data[0]["observed_change_bp"]

assert find("USD", "ZQZ2026", "2026-10-19", "2026-10-20") == -1.0
assert find("USD", "ZQV2027", "2026-10-19", "2026-10-20") == 2.5
assert find("EUR", "FST3M2027", "2026-10-19", "2026-10-20") == -1.0
assert find("EUR", "FST3V2026", "2026-10-16", "2026-10-19") == 0.25
assert find("CHF", "SA3M2027", "2026-10-19", "2026-10-20") == 1.5
assert find("CHF", "SA3U2026", "2026-10-19", "2026-10-20") == 0.25
assert not [x for x in deltas if x["symbol"] in ("CBOT:ZQH2027", "CBOT:ZQJ2027")
            and x["from_date"] == "2026-10-16" and x["to_date"] == "2026-10-20"]
# A rolling sequence of selected '6m' futures is never misinterpreted as repricing.
assert not [x for x in deltas if x["symbol"] == "CBOT:ZQH2027" and
            x["to_date"] == "2026-10-20"]

live_eligible, live_excluded = candidates(LIVE)
assert len(live_eligible) + len(live_excluded) == 9, (
    live_eligible, live_excluded)
source_rows, excluded = candidates(BASE)
assert not excluded, excluded
assert len(source_rows) == 9
assert all(validate_row(x) is x for x in source_rows)

def find_from(rows, ccy, contract, a, b):
    matches = [x for x in matched_moves(rows)
               if x["currency"] == ccy and x["symbol"].endswith(":" + contract)
               and x["from_date"] == a and x["to_date"] == b]
    assert len(matches) == 1
    return matches[0]["observed_change_bp"]


with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "bars.jsonl"
    p.write_text(HISTORY.read_text(encoding="utf-8"), encoding="utf-8")
    initial_bytes = p.read_bytes()
    first = append_verified(copy.deepcopy(BASE), p, write=True)
    assert first["status"] == "PASS_SOURCE_GOVERNANCE_RESEARCH_ONLY"
    assert first["would_append"] == 0 and first["written"] == 0
    assert p.read_bytes() == initial_bytes, "duplicate collection changed archive"

    # New observed *source* session: same contract and verified next day.
    newer = copy.deepcopy(BASE)
    newer["generated_at_utc"] = "2026-10-22T09:30:00Z"
    for ccy in newer["currencies"]:
        for t, h in newer["currencies"][ccy]["horizons"].items():
            h["quote_timestamp_verified"] = False
            h["quote_timestamp_source"] = "UNVERIFIED"
    USD = newer["currencies"]["USD"]["horizons"]["3m"]
    USD["quote_as_of"] = "2026-10-21"
    USD["quote_timestamp_verified"] = True
    USD["quote_timestamp_source"] = "SSR_DAILY_BAR_DATA_UPDATE_TIME"
    USD["futures_price"] = 95.92
    USD["rate"] = 4.08
    out = append_verified(newer, p, write=True)
    assert out["eligible"] == 1 and out["written"] == 1, out
    assert len(load_history(p)) == len(seed) + 1
    assert find_from(load_history(p), "USD", "ZQZ2026", "2026-10-20", "2026-10-21") == 1.0
    assert append_verified(newer, p, write=True)["written"] == 0

    # Same source day, different price (even if both rates internally consistent)
    # is an unverified revision: reject rather than overwriting the old print.
    conflict = copy.deepcopy(newer)
    conflict["currencies"]["USD"]["horizons"]["3m"]["rate"] = 4.09
    conflict["currencies"]["USD"]["horizons"]["3m"]["futures_price"] = 95.91
    try:
        append_verified(conflict, p, write=True)
        raise AssertionError("conflicting quote version was accepted")
    except ValueError as e:
        assert "contradictory" in str(e), e

    # A bogus price, unverified timestamp or future observation is never backfilled.
    bad = copy.deepcopy(newer)
    bad["currencies"]["USD"]["horizons"]["3m"]["rate"] = 4.53
    rejected = append_verified(bad, p, write=False)
    assert rejected["eligible"] == 0 and rejected["excluded"], rejected

    bad = copy.deepcopy(newer)
    bad["currencies"]["USD"]["horizons"]["3m"]["quote_as_of"] = "2026-10-24"
    rejected = append_verified(bad, p, write=False)
    assert rejected["eligible"] == 0 and rejected["excluded"], rejected

    bad = copy.deepcopy(newer)
    bad["currencies"]["USD"]["horizons"]["3m"]["symbol"] = "CBOT:ZQH2027"
    rejected = append_verified(bad, p, write=False)
    assert rejected["eligible"] == 0 and rejected["excluded"], rejected

    bad = copy.deepcopy(newer)
    bad["currencies"]["USD"]["horizons"]["3m"]["mapping"] = "roll-adjusted interpolation"
    rejected = append_verified(bad, p, write=False)
    assert rejected["eligible"] == 0 and rejected["excluded"], rejected

    # History duplicate identity and false official promotion must fail closed.
    p.write_bytes(initial_bytes + initial_bytes.splitlines(True)[0])
    try:
        load_history(p)
        raise AssertionError("duplicate history identity accepted")
    except ValueError as e:
        assert "duplicate archive" in str(e), e

    forged = copy.deepcopy(seed[0])
    forged["official_ois_quote"] = True
    try:
        validate_row(forged)
        raise AssertionError("fake official futures quote accepted")
    except ValueError as e:
        assert "forbidden promotion" in str(e), e

def _same_contract_current_only():
    """All historic source dates in this dataset are real, not capture run dates."""
    out = {}
    for row in seed:
        out.setdefault(row["currency"], set()).add(row["contract"])
    assert all(len(x) >= 3 for x in out.values())
    assert all(row["source_timestamp_evidence"] == "SSR_DAILY_BAR_DATA_UPDATE_TIME" for row in seed)


_same_contract_current_only()
print("OIS_SAME_CONTRACT_HISTORY_V1_PASS: 23 verified bars, matched changes, no roll, fail closed")
