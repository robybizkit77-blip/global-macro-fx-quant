#!/usr/bin/env python3
"""Frozen point-of-capture market context for the future-only quality-aware V2 cohort.

Not a macro FX score or validated prediction. All 8 policy/2Y/6M contexts are
source-dated; only official, same-day government 2Y observations can form a
descriptive 28-cross differential. Other 6M instruments are deliberately
NON-COMPARABLE, even when their calendar dates coincide.
"""
from __future__ import annotations

import itertools
import math
from datetime import date

SCHEMA = "GMFQ_V2_QUALITY_COHORT_MARKET_CONTEXT_V1"
FX = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
PAIRS = {frozenset(p) for p in itertools.combinations(FX, 2)}
OFFICIAL = "OFFICIAL_MONETARY_SOURCE"
FUTURES = "ESTIMATED_DATED_FUTURES_NOT_OIS"
INDICATIVE = "INDICATIVE_SECONDARY_FUTURES_NOT_OIS"
BANK_BILL = "NZD_BANK_BILL_BASIS_PROXY_NOT_OIS"
MISSING = "NO_VERIFIED_6M_MARKET_CONTEXT"
TIERS = {OFFICIAL, FUTURES, INDICATIVE, BANK_BILL, MISSING}


def need(ok, message):
    if not ok:
        raise ValueError("V2_QUALITY_MARKET_CONTEXT_REJECTED: " + message)


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def civil(value, limit):
    need(isinstance(value, str) and len(value) == 10, "source date absent")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("V2_QUALITY_MARKET_CONTEXT_REJECTED: invalid date") from exc
    need(parsed.isoformat() == value and parsed <= limit, "future or malformed date")
    return parsed


def market_country(day, ccy, rate, curve, bank, nzd_proxy):
    policy_day = civil(bank.get("last_date"), day)
    price_day = civil(rate.get("date"), day)
    curve_day = civil(curve.get("as_of"), day)
    need(finite(bank.get("rate")) and -5 < bank["rate"] < 30,
         ccy + " central bank policy rate invalid")
    need(isinstance(rate.get("source"), str) and rate["source"].strip(),
         ccy + " missing 2Y provenance")
    # Historical observations are allowed but never re-dated as current.
    sovereign_valid = (
        str(rate.get("quality", "")).startswith("FULL_CURRENT_OFFICIAL")
        and finite(rate.get("2Y"))
        and finite(rate.get("10Y"))
    )
    if sovereign_valid:
        need(-5 < rate["2Y"] < 30 and -5 < rate["10Y"] < 30,
             ccy + " sovereign rate out of domain")
    policy_rate = float(bank["rate"])
    six = curve.get("horizons", {}).get("6m", {})
    need(isinstance(six, dict), ccy + " malformed 6m source")
    tier = MISSING
    v = None
    six_date = None
    contract = None
    status = curve.get("operational_status")
    if status == "GREEN_OFFICIAL":
        need(curve.get("official_status") == "ACTIVE" and
             curve.get("quality") == "OFFICIAL_CERTIFIED" and
             curve.get("backtest_eligible_as_official") is True and
             finite(six.get("rate")),
             ccy + " false official 6m")
        tier, v, six_date = OFFICIAL, float(six["rate"]), curve_day
    elif status == "GREEN_ESTIMATED":
        need(curve.get("quality") == "ESTIMATED_INFORMATIONAL" and
             curve.get("backtest_eligible_as_official") is False and
             finite(six.get("rate")), ccy + " false estimated 6m")
        tier, v, six_date = FUTURES, float(six["rate"]), curve_day
    elif status == "WITHHELD":
        need(curve.get("official_status") == "WITHHELD" and
             curve.get("backtest_eligible_as_official") is False and
             six.get("rate") is None, ccy + " withheld 6m promoted")
        context = curve.get("secondary_quote_context") or {}
        if (ccy in ("EUR", "CHF") and
                context.get("status") == "INDICATIVE_OBSERVATIONS_NON_OIS" and
                context.get("policy_delta_allowed") is False and
                context.get("cross_date_join_allowed") is False):
            q = context.get("horizons", {}).get("6m") or {}
            if (finite(q.get("rate_indicative")) and
                    q.get("source_quality") == "SECONDARY_VERIFIED_DAILY_BAR"):
                six_date = civil(q.get("quote_as_of"), day)
                tier, v, contract = INDICATIVE, float(q["rate_indicative"]), q.get("contract")
        elif ccy == "NZD" and isinstance(nzd_proxy, dict):
            if (nzd_proxy.get("schema") == "GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1" and
                    nzd_proxy.get("status") == "LIVE_DIRECTIONAL_PROXY_READY" and
                    nzd_proxy.get("currency") == "NZD"):
                q = nzd_proxy.get("horizons", {}).get("6m") or {}
                if finite(q.get("implied_bank_bill_rate")):
                    six_date = civil(nzd_proxy.get("as_of"), day)
                    tier, v = BANK_BILL, float(q["implied_bank_bill_rate"])
    else:
        need(False, ccy + " unknown monetary source status")

    if v is not None:
        need(-5 < v < 30 and six_date is not None, ccy + " rate not date-certified")
    # Policy quote before a fresh central-bank decision is not repricing of
    # the current CB target; a mismatch at/after that decision is a blocker.
    quote_pre_decision = six_date is not None and six_date < policy_day
    if (tier == OFFICIAL or tier == FUTURES) and six_date is not None:
        need(quote_pre_decision or
             (finite(curve.get("policy_rate")) and
              abs(curve["policy_rate"] - policy_rate) <= 1e-7),
             ccy + " monetaries inconsistent with current policy decision")
    return {
        "currency": ccy,
        "policy_pct": policy_rate, "policy_decision_date": policy_day.isoformat(),
        "sovereign_2y_pct": float(rate["2Y"]) if sovereign_valid else None,
        "sovereign_10y_pct": float(rate["10Y"]) if sovereign_valid else None,
        "sovereign_date": price_day.isoformat(),
        "sovereign_age_days": (day-price_day).days,
        "sovereign_official": sovereign_valid,
        "sovereign_current_5d": sovereign_valid and (day-price_day).days <= 5,
        "sovereign_source": rate["source"],
        "six_month_value_pct": v, "six_month_source_tier": tier,
        "six_month_source_date": six_date.isoformat() if six_date else None,
        "six_month_age_days": (day-six_date).days if six_date else None,
        "six_month_recent_5d": six_date is not None and (day-six_date).days <= 5,
        "six_month_contract_if_secondary": contract,
        "six_month_is_official_ois_only": tier == OFFICIAL,
        "six_month_is_policy_delta_of_current_CB": False,
        "quote_precedes_last_policy_decision": bool(quote_pre_decision),
        "historical_PIT_market_series_certified": False,
        "FX_strength_score": None,
    }


def build(day_string, rates, ois, banks, nzd_proxy, pair_setup):
    day = civil(day_string, date.today() if date.today() >= date.fromisoformat(day_string) else date.fromisoformat(day_string))
    need(isinstance(rates, dict) and set(rates) == set(FX) and
         isinstance(banks, dict) and set(banks) == set(FX) and
         isinstance(ois, dict) and ois.get("schema") == "GMFQ_OIS_OPERATIONAL_VIEW_V1" and
         set(ois.get("currencies", {})) == set(FX),
         "complete G8 official/proxy inputs required")
    need(pair_setup.get("schema") == "GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1" and
         pair_setup.get("pair_count") == 28 and
         len(pair_setup.get("pairs", {})) == 28, "canonical 28 pair universe")
    rows = {c: market_country(day, c, rates[c], ois["currencies"][c], banks[c], nzd_proxy)
            for c in FX}
    pairs = {}
    seen = set()
    for item in pair_setup["pairs"].values():
        label = item.get("canonical_pair")
        need(isinstance(label, str) and len(label) == 7 and label[3] == "/",
             "invalid canonical pair")
        a, b = label.split("/")
        key = frozenset((a, b))
        need(key in PAIRS and key not in seen, "duplicate/noncanonical pair")
        seen.add(key)
        x, y = rows[a], rows[b]
        same = (x["sovereign_official"] and y["sovereign_official"] and
                x["sovereign_date"] == y["sovereign_date"])
        pairs[label] = {
            "pair": label, "base": a, "quote": b,
            "2y_same_official_observation_day": same,
            "2y_observation_date_if_matched": x["sovereign_date"] if same else None,
            "2y_sovereign_spread_bp_DESCRIPTIVE_ONLY":
                round(100*(x["sovereign_2y_pct"] - y["sovereign_2y_pct"]), 6) if same else None,
            "6m_cross_market_policy_spread_bp": None,
            "6m_not_identical_risk_free_instruments": True,
            "FX_signal": None, "FX_strength_rank": None,
        }
    need(seen == PAIRS, "missing one of 28 pairs")
    return {
        "schema": SCHEMA, "as_of_rome": day_string,
        "countries": rows, "pairs": pairs,
        "summary": {
            "eight_economies": len(rows), "28_pairs": len(pairs),
            "official_6m": sum(x["six_month_source_tier"] == OFFICIAL for x in rows.values()),
            "estimated_or_proxy_6m": sum(x["six_month_source_tier"] in (FUTURES, INDICATIVE, BANK_BILL) for x in rows.values()),
            "missing_6m": sum(x["six_month_source_tier"] == MISSING for x in rows.values()),
            "same_day_2y_pair_spreads_descriptive": sum(x["2y_same_official_observation_day"] for x in pairs.values()),
            "FX_scores": 0, "model_predictions": 0,
        },
        "no_cross_country_z_subtraction": True,
        "no_OIS_policy_delta_from_proxy": True,
        "no_2y_yield_spread_as_trading_signal": True,
        "not_a_historical_PIT_or_forward_model": True,
        "eligible_for_H1_or_live_Core": False,
    }


def validate(row):
    need(row.get("schema") == SCHEMA and row.get("eligible_for_H1_or_live_Core") is False
         and row.get("no_cross_country_z_subtraction") is True
         and row.get("no_OIS_policy_delta_from_proxy") is True
         and row.get("no_2y_yield_spread_as_trading_signal") is True
         and row.get("not_a_historical_PIT_or_forward_model") is True,
         "research-only provenance")
    day = civil(row.get("as_of_rome"), date.fromisoformat(row["as_of_rome"]))
    cs, ps = row.get("countries"), row.get("pairs")
    need(isinstance(cs, dict) and set(cs) == set(FX) and
         isinstance(ps, dict) and len(ps) == 28, "8/28 market coverage")
    for c, x in cs.items():
        need(x.get("currency") == c and x.get("six_month_source_tier") in TIERS
             and x.get("FX_strength_score") is None and
             x.get("six_month_is_policy_delta_of_current_CB") is False
             and x.get("historical_PIT_market_series_certified") is False,
             c + " unexpected source certification")
        d = civil(x.get("sovereign_date"), day)
        civil(x.get("policy_decision_date"), day)
        age = (day-d).days
        need(x.get("sovereign_age_days") == age and
             x.get("sovereign_current_5d") is
             (x.get("sovereign_official") is True and age <= 5),
             c + " official curve recency mismatched")
        tier = x["six_month_source_tier"]
        rate = x.get("six_month_value_pct")
        if tier == MISSING:
            need(rate is None and x.get("six_month_source_date") is None,
                 c + " missing 6M is not zero")
        else:
            need(finite(rate) and -5 < rate < 30, c + " invalid 6M")
            qd = civil(x.get("six_month_source_date"), day)
            qage = (day-qd).days
            need(x.get("six_month_age_days") == qage and
                 x.get("six_month_recent_5d") is (qage <= 5),
                 c + " 6M actual quote freshness mismatch")
        need(x.get("six_month_is_official_ois_only") is (tier == OFFICIAL),
             c + " false official 6m promotion")
    seen = set()
    for label, x in ps.items():
        need(x.get("pair") == label and x.get("FX_signal") is None
             and x.get("FX_strength_rank") is None
             and x.get("6m_cross_market_policy_spread_bp") is None
             and x.get("6m_not_identical_risk_free_instruments") is True,
             "a market context is not an FX prediction")
        a, b = x.get("base"), x.get("quote")
        need(label == str(a)+"/"+str(b) and frozenset((a,b)) in PAIRS,
             "pair identity or orientation")
        seen.add(frozenset((a,b)))
        ca, cb = cs[a], cs[b]
        matched = (ca["sovereign_official"] and cb["sovereign_official"] and
                   ca["sovereign_date"] == cb["sovereign_date"])
        actual = x.get("2y_sovereign_spread_bp_DESCRIPTIVE_ONLY")
        expected = (round(100*(ca["sovereign_2y_pct"] -
                         cb["sovereign_2y_pct"]), 6) if matched else None)
        need(x.get("2y_same_official_observation_day") is matched and
             x.get("2y_observation_date_if_matched") ==
                 (ca["sovereign_date"] if matched else None) and
             actual == expected,
             "mismatched-date or forged 2Y spread")
    need(seen == PAIRS and row["summary"]["28_pairs"] == 28 and
         row["summary"]["eight_economies"] == 8 and
         row["summary"]["FX_scores"] == 0 and
         row["summary"]["model_predictions"] == 0,
         "market count/prohibition mismatch")
    return True
