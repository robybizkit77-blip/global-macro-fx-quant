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
# The first 23 signed-off observations are the immutable October replay.
# Production history grows by append-only validated bars: later observations
# must not change the historical fixture or make CI demand exactly 23 rows.
assert len(seed) >= 23, len(seed)
bootstrap = seed[:23]
assert len({(x["currency"], x["contract"], x["observation_date"]) for x in seed}) == len(seed)
assert all(validate_row(x) is x for x in seed)
# Build a dated, immutable replay from the archived 2026-10-16/19/20 bars.
# Daily source feeds are allowed to move on: tests must not demand that 2026-10-21
# quote dates remain the latest on every future scheduled execution.
BASE = copy.deepcopy(LIVE)
BASE["generated_at_utc"] = "2026-10-21T06:57:19Z"
for code in ("USD", "EUR", "CHF"):
    for term in ("3m", "6m", "12m"):
        observed = [r for r in bootstrap if r["currency"] == code and
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
assert len(bootstrap) == 23, len(bootstrap)
assert len({(x["currency"], x["contract"], x["observation_date"]) for x in bootstrap}) == 23
assert {x["currency"] for x in bootstrap} == {"USD", "EUR", "CHF"}
assert {x["observation_date"] for x in bootstrap} == {
    "2026-10-16", "2026-10-19", "2026-10-20"
}
assert all(x["official_ois_quote"] is False and
           x["policy_delta_eligible"] is False and
           x["backtest_eligible_as_official"] is False for x in bootstrap)
assert len({x["source_commit"] for x in bootstrap}) == 3

deltas = matched_moves(bootstrap)
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
    # Replay tests start from the fixed 23-row research seed rather than
    # copying today's mutable production history (which may include the
    # deliberately synthetic 21 October scenario used below).
    p.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n"
                         for x in bootstrap), encoding="utf-8")
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
    assert len(load_history(p)) == len(bootstrap) + 1
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

    forged = copy.deepcopy(bootstrap[0])
    forged["official_ois_quote"] = True
    try:
        validate_row(forged)
        raise AssertionError("fake official futures quote accepted")
    except ValueError as e:
        assert "forbidden promotion" in str(e), e

def _same_contract_current_only():
    """All historic source dates in this dataset are real, not capture run dates."""
    out = {}
    for row in bootstrap:
        out.setdefault(row["currency"], set()).add(row["contract"])
    assert all(len(x) >= 3 for x in out.values())
    assert all(row["source_timestamp_evidence"] == "SSR_DAILY_BAR_DATA_UPDATE_TIME" for row in bootstrap)



# New ICE SARON starts can be captured without rewriting the original 93+
# observations. Entirely simulated Nov 2 identities for schema regression;
# these are NOT observed Nov 2 SARON market prices.
from collect_cb_pricing_estimated_live_v1 import saron_window
feb = copy.deepcopy(LIVE)
feb["generated_at_utc"] = "2026-11-02T17:15:00Z"
for t,contract in (("3m","SA3Z2026"),("6m","SA3H2027"),("12m","SA3U2027")):
    p=feb["currencies"]["CHF"]["horizons"][t]
    start,end=saron_window(contract)
    p.update({"contract":contract,"symbol":"ICEEUR:"+contract,
        "expiration":end.isoformat(),"accrual_start":start.isoformat(),
        "quote_as_of":"2026-11-02","futures_price":99.9,"rate":0.1,
        "quote_timestamp_verified":True,
        "quote_timestamp_source":"SSR_DAILY_BAR_DATA_UPDATE_TIME",
        "mapping":"nearest ICE SARON accrual start to today+"+
          str({"3m":90,"6m":180,"12m":365}[t])+"d; no interpolation"})
    feb["currencies"]["CHF"]["source_quality"]="SECONDARY_PUBLIC_LIVE_PROXY"
q,_=candidates(feb)
assert len([x for x in q if x["currency"]=="CHF"])==3
bad=copy.deepcopy(feb)
bad["currencies"]["CHF"]["horizons"]["6m"]["mapping"]=(
 "nearest dated listed contract expiry to today+180d; no interpolation")
q,ex=candidates(bad)
assert len([x for x in q if x["currency"]=="CHF"])==2
assert any("CHF/6m" in x for x in ex)
bad=copy.deepcopy(feb)
bad["currencies"]["CHF"]["horizons"]["6m"]["accrual_start"]="2027-03-18"
q,ex=candidates(bad)
assert len([x for x in q if x["currency"]=="CHF"])==2
assert any("CHF/6m" in x for x in ex)

# ICE March 2027 is listed, and its SARON window runs March-June 2027.
# If the secondary SSR contract parser skips the March metadata entirely,
# bounded ICE calendar recovery supplies only its CONTRACT ID, NOT a quote.
from datetime import date as _date
from collect_cb_pricing_estimated_live_v1 import (
    recover_chf_ice_quarters, select_contracts, saron_window,
)
def _chf_row(code):
    start,expiry=saron_window(code)
    return {"symbol":"ICEEUR:"+code,"contract":code,"expiration":expiry,
            "description":code,"instrument_name":"Three Month SARON"}
short_chain=[_chf_row(c) for c in (
    "SA3Z2026","SA3M2027","SA3U2027","SA3Z2027",
    "SA3H2028","SA3M2028","SA3U2028")]
recovered=recover_chf_ice_quarters(short_chain)
q={r["contract"]:r for r in recovered}
assert "SA3H2027" in q, "ICE March quarter must be recovered"
assert q["SA3H2027"]["roster_quality"] == "ICE_LISTED_QUARTER_CALENDAR_DERIVED_UNQUOTED"
assert not any("price" in r or "rate" in r or "quote_as_of" in r for r in recovered), (
    "calendar may reconstruct identity only, never market rates")
chosen=select_contracts(short_chain,_date(2026,10,30),currency="CHF")
assert chosen["3m"]["contract"]=="SA3Z2026"
assert chosen["6m"]["contract"]=="SA3H2027", chosen
assert chosen["12m"]["contract"]=="SA3U2027", chosen
assert abs((chosen["6m"]["accrual_start"]-_date(2026,10,30)).days-180)<=45
# If one bookend has false expiry, it cannot authorize synthesizing the gap.
poison=copy.deepcopy(short_chain)
poison[1]["expiration"]=_date(2027,9,13)
assert "SA3H2027" not in {x["contract"] for x in recover_chf_ice_quarters(poison)}
# Never project missing contracts beyond the final verified quarter.
assert "SA3Z2028" not in q
# Even if a code is recovered, an independently timestamped quote must still
# be fetched from that exact contract page before it can enter pricing.
from collect_cb_pricing_estimated_live_v1 import parse_quote
try:
    parse_quote('<title>SA3H2027</title>',"SA3H2027",_date(2026,11,2))
    raise AssertionError("unquoted ICE quarter passed market-data verification")
except RuntimeError as err:
    assert "no SSR Offer quote" in str(err)
print("CHF_ICE_QUARTER_ROSTER_GAP_RECOVERY_PASS")

_same_contract_current_only()
print(f"OIS_SAME_CONTRACT_HISTORY_V1_PASS: immutable 23-row replay; "
      f"production {len(seed)} verified rows; matched changes, no roll, fail closed")
