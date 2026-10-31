#!/usr/bin/env python3
"""Read-only, exactly matched 7-calendar-day 2Y/ECB FX observations.

This is an ex-post research comparison, not point-in-time historical replay,
FX alpha, CB repricing, event causality, valuation or a rebuild of D.json.
Do not use NATIVE_RATES_DATA.chg2_bp: its reference clock is not certified.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "live_data" / "sections"
G8 = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD", "CHF")
SCHEMA = "GMFQ_MACRO_V2_EXACT_WEEKLY_2Y_ECB_FX_CONTEXT_V1"


def need(check, message):
    if not check:
        raise ValueError("EXACT_WEEKLY_2Y_FX_CONTEXT_REJECTED: " + message)


def iso(value):
    need(isinstance(value, str) and re.fullmatch(r"20\d\d-\d\d-\d\d", value),
         "strict ISO day required")
    result = date.fromisoformat(value)
    need(result.isoformat() == value, "noncanonical calendar day")
    return result


def number(value):
    need(type(value) in (int, float) and math.isfinite(value), "finite numeric value")
    return float(value)


def history_index(rate):
    h = rate.get("history2") or {}
    ds, vs = h.get("dates"), h.get("values")
    need(isinstance(ds, list) and isinstance(vs, list) and
         len(ds) == len(vs) and len(ds) >= 3, "official 2Y source history")
    need(h.get("last_date") == rate.get("date") and
         math.isclose(number(h.get("last_value")), number(rate.get("2Y")),
                      rel_tol=0, abs_tol=1e-9), "2Y last point metadata mismatch")
    # Older JPY source dates may be unpadded; do not use lexical date sorting.
    result = {}
    for raw, value in zip(ds, vs):
        need(isinstance(raw, str) and re.fullmatch(r"20\d\d-\d{1,2}-\d{1,2}", raw),
             "history date syntax")
        bits = [int(x) for x in raw.split("-")]
        normalized = date(*bits).isoformat()
        need(normalized not in result, "duplicate history date after normalization")
        result[normalized] = number(value)
    need(rate.get("date") in result and
         math.isclose(result[rate["date"]], number(rate["2Y"]),
                      rel_tol=0, abs_tol=1e-9), "2Y value/day source mismatch")
    return result


def build(rates, fx, setup, core, audit_day: str):
    asof = iso(audit_day)
    need(set(rates) == set(G8), "exact eight 2Y source countries")
    need(core.get("asOf") == setup.get("macro_baseline_asof"),
         "canonical Core and Pair baseline dates mismatch")
    need(set(core.get("macro", {})) == set(G8), "canonical G8 Core baseline")
    pairs = setup.get("pairs")
    need(setup.get("pair_count") == 28 and isinstance(pairs, dict) and
         len(pairs) == 28, "28 canonical pairs")
    need({frozenset((key[:3], key[3:])) for key in pairs} ==
         {frozenset((a, b)) for a, b in itertools.combinations(G8, 2)} and
         all(key == entry.get("canonical_pair", "").replace("/", "") and
             key[:3] in G8 and key[3:] in G8 and key[:3] != key[3:]
             for key, entry in pairs.items()), "pair identities or orientations")
    need(fx.get("base") == "EUR" and fx.get("status") == "CURRENT_OFFICIAL_HISTORY" and
         fx.get("pair_count") == 28 and fx.get("row_count") == len(fx.get("rows", [])),
         "complete ECB euro-base FX history")
    need(iso(fx.get("last_as_of")) <= asof and
         fx["rows"][-1].get("Date") == fx["last_as_of"],
         "latest official FX evidence not available at research cutoff")
    fxrows = {}
    for row in fx["rows"]:
        d = iso(row.get("Date"))
        need(d.isoformat() not in fxrows, "duplicate ECB fixing day")
        fxrows[d.isoformat()] = row
    country = {}
    for c in G8:
        r = rates[c]
        end_day = iso(r.get("date"))
        need(end_day <= asof, "rate feed after research cutoff " + c)
        need(str(r.get("quality", "")).startswith("FULL_CURRENT_OFFICIAL"),
             "2Y source not official " + c)
        country[c] = {"last_as_of":r["date"], "source":r.get("source"),
                      "history":history_index(r)}
    # Choose the latest day with both ECB reference fixings and >=2 official
    # 2Y series covering the SAME exact start/end dates, seven days apart.
    candidates = []
    for end_text in sorted(fxrows, reverse=True):
        end_day = iso(end_text)
        if end_day > asof:
            continue
        start_text = (end_day - timedelta(days=7)).isoformat()
        if start_text not in fxrows:
            continue
        eligible = [c for c in G8 if end_text in country[c]["history"] and
                    start_text in country[c]["history"] and
                    iso(country[c]["last_as_of"]) >= end_day]
        if len(eligible) >= 2:
            candidates.append((end_text, start_text, eligible))
            break
    need(candidates, "no exact common-date 2Y and FX comparison")
    end, start, eligible = candidates[0]
    # This is a historical snapshot in the *currently retrieved* data,
    # NOT contemporaneous publication time and NOT a predictive return.
    def ecb_pair_rate(row, base, quote):
        need(all(number(row.get(c)) > 0 for c in (base, quote)) and
             math.isclose(number(row.get("EUR")), 1., abs_tol=1e-10),
             "invalid ECB base or quote")
        return number(row[quote]) / number(row[base])

    observations = {}
    for p in sorted(pairs):
        a, b = p[:3], p[3:]
        if a not in eligible or b not in eligible:
            observations[p] = {
                "status": "EXCLUDED_NON_SYNCHRONIZED_2Y_OR_ECB", "interval": None,
                "relative_2Y_change_bp": None, "fx_reference_change_pct": None,
                "not_a_trading_signal": True}
            continue
        ha, hb = country[a]["history"], country[b]["history"]
        delta_a = (ha[end] - ha[start]) * 100.
        delta_b = (hb[end] - hb[start]) * 100.
        p0 = ecb_pair_rate(fxrows[start], a, b)
        p1 = ecb_pair_rate(fxrows[end], a, b)
        observations[p] = {
            "status": "EXACT_DATE_MATCH_DESCRIPTIVE_ONLY",
            "interval": [start, end], "base_2Y_change_bp": round(delta_a, 6),
            "quote_2Y_change_bp": round(delta_b, 6),
            "relative_2Y_change_bp": round(delta_a - delta_b, 6),
            "fx_reference_change_pct": round(100 * (p1 / p0 - 1), 6),
            "2Y_benchmark_basis_harmonized": False,
            "FX_and_2Y_intraday_clock_harmonized": False,
            "not_a_trading_signal": True}
    eligible_pairs = [p for p, v in observations.items()
                      if v["status"] == "EXACT_DATE_MATCH_DESCRIPTIVE_ONLY"]
    need(len(eligible_pairs) == len(eligible) * (len(eligible) - 1) // 2,
         "unexpected 28-pair eligibility partition")
    return {
        "schema": SCHEMA, "status": "RESEARCH_ONLY_NO_FX_MODEL_SIGNAL",
        "analysis_as_of": asof.isoformat(),
        "observation_window": [start, end],
        "original_macro_baseline_as_of": core["asOf"],
        "current_pair_price_as_of": setup.get("price_asof"),
        "source_vintage_is_as_retrieved_not_historic_PIT": True,
        "ECB_reference_is_not_executable_price_or_intraday_reaction": True,
        "sovereign_2Y_instrument_conventions_not_identical": True,
        "COT_OIS_CB_macro_surprise_not_inferred": True,
        "no_D_or_pair_updates": True,
        "no_OOS_or_predictive_success_claim": True,
        "summary": {"countries": 8, "pairs": 28,
                    "common_date_2Y_currencies": len(eligible),
                    "eligible_pairs": len(eligible_pairs),
                    "excluded_pairs": 28 - len(eligible_pairs),
                    "FX_signals": 0, "Core_rebased": 0},
        "eligible_currency_codes": eligible,
        "excluded_currency_codes": [c for c in G8 if c not in eligible],
        "pair_observations": observations
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True, help="Actual research cutoff YYYY-MM-DD")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out:
        need(args.out.is_absolute() and str(args.out.resolve()).startswith("/tmp/"),
             "research output only allowed under /tmp/")
    report = build(*[json.loads((DATA / name).read_text())
                     for name in ("NATIVE_RATES_DATA.json", "ECB_G8_PRICE_HISTORY.json",
                                  "PAIR_SETUP_OPERATIONAL_VIEW.json", "D.json")],
                   audit_day=args.as_of)
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "window": report["observation_window"],
                      "summary": report["summary"], "eligible": report["eligible_currency_codes"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
