#!/usr/bin/env python3
"""Shadow-only 28-pair FX vs 2Y weekly rolling-beta panel and OOS audit.

Daily FX = ECB EUR-base official reference fixing. Daily 2Y = each
currency's own published instrument definition; these 2Y series are not
necessarily curve-basis comparable. Historical first-release PIT vintage is
NOT certified, so statistical OOS here is NOT a prospective forward test.
No proxy substitution, no gap interpolation, no production writes.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from itertools import combinations
import json
import math
import re
from pathlib import Path
from statistics import pvariance

from validation.beta.rate_beta_observational_v1 import ols_beta

ROOT = Path(__file__).resolve().parents[2]
FX_PATH = ROOT / "live_data/sections/ECB_G8_PRICE_HISTORY.json"
RATE_PATH = ROOT / "live_data/sections/NATIVE_RATES_DATA.json"
G8 = ("EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
CONTRACT = ROOT / "validation/beta/RATE_BETA_OBSERVATIONAL_CONTRACT_V1_2026-10-15.json"
SCHEMA = "GMFQ_FX_2Y_MATCHED_WEEKLY_OOS_RESEARCH_V1"
RATE_STATES = ("FULL_CURRENT_OFFICIAL", "FULL_CURRENT_OFFICIAL_MANUAL_VERIFIED")
FX_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
WINDOW = 52


def strict_date(raw):
    if not isinstance(raw, str):
        raise ValueError("ISO date required")
    # Different Python versions parse loose ISO dates differently; reject
    # unpadded Japanese source strings deterministically before parsing.
    if not re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", raw):
        raise ValueError("noncanonical ISO date")
    try:
        d = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("invalid date") from exc
    if d.isoformat() != raw:
        raise ValueError("noncanonical ISO date")
    return d


def finite(v):
    return type(v) in (int, float) and math.isfinite(v)


def official_fx(fx, as_of):
    if (not isinstance(fx, dict)
            or fx.get("schema") != "GMFQ_ECB_G8_PRICE_HISTORY_V1"
            or fx.get("status") != "CURRENT_OFFICIAL_HISTORY"
            or fx.get("source_url") != FX_URL
            or fx.get("base") != "EUR"
            or set(fx.get("currencies", [])) != set(G8)):
        raise ValueError("unverified ECB source")
    rows = fx.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("empty ECB history")
    previous = None
    out = {}
    for row in rows:
        d = strict_date(row["Date"])
        if previous is not None and d <= previous:
            raise ValueError("unordered/duplicate ECB date")
        previous = d
        if row.get("EUR") != 1:
            raise ValueError("ECB EUR base not 1")
        for cc in G8:
            val = row.get(cc)
            if not finite(val) or val <= 0:
                raise ValueError("ECB missing or nonpositive official rate")
        if d <= as_of:
            out[d] = row
    if previous.isoformat() != fx.get("last_as_of"):
        raise ValueError("ECB last as-of differs from last row")
    return out


def rate_history(ccy, data, as_of):
    obj = data.get(ccy) if isinstance(data, dict) else None
    if not isinstance(obj, dict) or obj.get("quality") not in RATE_STATES:
        return None, "SOURCE_QUALITY_NOT_CERTIFIED"
    hist = obj.get("history2")
    if not isinstance(hist, dict):
        return None, "NO_2Y_HISTORY"
    days, values = hist.get("dates"), hist.get("values")
    if (not isinstance(days, list) or not isinstance(values, list)
            or not days or len(days) != len(values)):
        return None, "INCONSISTENT_2Y_HISTORY"
    parsed, previous = {}, None
    for raw, v in zip(days, values):
        try:
            d = strict_date(raw)
        except ValueError:
            return None, "NONCANONICAL_2Y_HISTORY_DATE"
        if previous is not None and d <= previous:
            return None, "UNORDERED_OR_DUPLICATE_2Y_HISTORY"
        if not finite(v):
            return None, "INVALID_2Y_HISTORY_VALUE"
        parsed[d] = float(v)  # percent yield; negative rates allowed
        previous = d
    try:
        report_date = strict_date(obj.get("date"))
    except ValueError:
        return None, "INVALID_2Y_SOURCE_ASOF"
    if previous != report_date:
        return None, "2Y_SOURCE_ASOF_MISMATCH"
    return {d:v for d,v in parsed.items() if d <= as_of}, None


def friday(day):
    return day + timedelta(days=4-day.weekday())


def weekly_points(fx_rows, base_hist, quote_hist, base, quote):
    common = set(fx_rows).intersection(base_hist).intersection(quote_hist)
    slots = {}
    for d in sorted(common):
        if d.weekday() >= 5:
            continue
        row = fx_rows[d]
        rate = float(row[quote]) / float(row[base])
        week = friday(d)
        slots[week] = {
            "week_end": week,
            "observed_date": d,
            "fx_rate": rate,
            "two_y_base_pct": base_hist[d],
            "two_y_quote_pct": quote_hist[d],
            "two_y_relative_pp": base_hist[d]-quote_hist[d],
        }
    return [slots[key] for key in sorted(slots)]


def consecutive_returns(points):
    rows = []
    for old, new in zip(points, points[1:]):
        if (new["week_end"]-old["week_end"]).days != 7:
            continue  # whole observation week missing; never bridge it
        if new["fx_rate"] <= 0 or old["fx_rate"] <= 0:
            raise ValueError("invalid FX pair cross")
        rows.append({
            "week_end": new["week_end"],
            "observed_date": new["observed_date"],
            "fx_return": new["fx_rate"]/old["fx_rate"]-1.0,
            "delta_rel_2y": new["two_y_relative_pp"]-old["two_y_relative_pp"],
            "input_weeks": (old["week_end"].isoformat(), new["week_end"].isoformat()),
        })
    return rows


def strict_oos(rows):
    # Re-use pre-registered 52 aligned-week OLS unchanged. Prevent an OOS
    # score if its complete contiguous 52W reference training panel is absent.
    result = []
    for i in range(WINDOW, len(rows)):
        sample = rows[i-WINDOW:i]
        if any((b["week_end"]-a["week_end"]).days != 7
               for a,b in zip(sample,sample[1:])):
            continue
        if (rows[i]["week_end"]-sample[-1]["week_end"]).days != 7:
            continue
        train = [(x["week_end"], x["fx_return"], x["delta_rel_2y"])
                 for x in sample]
        beta = ols_beta(train)
        if beta is None or not finite(beta):
            continue
        observation = rows[i]
        result.append({
            "evaluation_week_end": observation["week_end"].isoformat(),
            "training_last_week_end": sample[-1]["week_end"].isoformat(),
            "train_count": WINDOW,
            "beta_trained_prior_only": beta,
            "fx_return_observed": observation["fx_return"],
            "hedged_reference_residual": observation["fx_return"]-
                                        beta*observation["delta_rel_2y"],
        })
    return result


def audit(fx, rates, *, as_of="2026-10-26"):
    asof = strict_date(as_of)
    cfg = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if (cfg.get("status") != "RESEARCH_NOT_VALIDATED"
            or cfg.get("model", {}).get("window_observations") != WINDOW
            or cfg.get("model", {}).get("estimator") != "rolling_ols_with_intercept"):
        raise ValueError("canonical rate Beta contract changed unexpectedly")
    prices = official_fx(fx, asof)
    panels = {}
    problems = {}
    for cc in G8:
        panels[cc], problems[cc] = rate_history(cc, rates, asof)
    pairs = []
    for a,b in combinations(G8,2):
        name = a+b
        reason = None
        weekly = []
        obs = []
        oos = []
        if problems[a] or problems[b]:
            reason = "INVALID_RATE_SERIES_" + (
                a+":"+problems[a] if problems[a] else b+":"+problems[b])
        else:
            weekly = weekly_points(prices, panels[a], panels[b], a, b)
            obs = consecutive_returns(weekly)
            oos = strict_oos(obs)
            if len(obs) < WINDOW:
                reason = "BELOW_52_ALIGNED_WEEKLY_RETURNS"
            elif not oos:
                reason = "NO_FULL_52W_PRIOR_TRAINING_PLUS_LATER_TEST"
        vals_y = [z["fx_return_observed"] for z in oos]
        vals_z = [z["hedged_reference_residual"] for z in oos]
        var_y = pvariance(vals_y) if len(vals_y) >= 2 else None
        var_z = pvariance(vals_z) if len(vals_z) >= 2 else None
        # Small OOS sample results are descriptive only, not predictive edge.
        improvement = (
            1-var_z/var_y if len(oos) >= 4 and var_y is not None and var_y > 0
            else None
        )
        pairs.append({
            "pair":name,"rate_history_base":a,"rate_history_quote":b,
            "status":"ILLUSTRATIVE_HISTORICAL_OOS_NOT_PIT" if oos else
                     "INSUFFICIENT_OR_INVALID_REFERENCE_PANEL",
            "blocking_reason":reason,
            "aligned_weekly_fixing_points":len(weekly),
            "consecutive_weekly_returns":len(obs),
            "observed_latest_week_end":weekly[-1]["week_end"].isoformat() if weekly else None,
            "historical_oos_observations":len(oos),
            "historical_oos_last_week":oos[-1]["evaluation_week_end"] if oos else None,
            "variance_reduction_vs_unhedged_descriptive_only":improvement,
            "actual_oos_y_variance":var_y,
            "actual_oos_hedged_residual_variance":var_z,
            "recent_oos_samples":oos[-3:],
            "source_definition_comparability_verified":False,
            "first_publication_pit_verified":False,
            "forward_prospective_certified":False,
        })
    return {
        "schema":SCHEMA,
        "as_of":asof.isoformat(),
        "state":"SHADOW_HISTORICAL_PSEUDO_OOS_NOT_LIVE",
        "fx_source":FX_URL,
        "rates_source":"live_data/sections/NATIVE_RATES_DATA.json",
        "rate_2y_series_quality":{k:{"status":"BLOCKED" if problems[k] else "OBSERVATIONS_AVAILABLE",
                                      "reason":problems[k],
                                      "reported_as_of":rates[k].get("date") if k in rates else None,
                                      "instrument_source":rates[k].get("source") if k in rates else None}
                                  for k in G8},
        "pair_count":len(pairs),
        "pairs_with_any_oos":sum(x["historical_oos_observations"]>0 for x in pairs),
        "pairs_with_descriptive_variance_measure":
             sum(x["variance_reduction_vs_unhedged_descriptive_only"] is not None for x in pairs),
        "baseline_window_weeks":WINDOW,
        "dependent_variable":"SIMPLE_FX_WEEKLY_RETURN",
        "independent_variable":"WEEKLY_DELTA_2Y_BASE_MINUS_QUOTE_PERCENTAGE_POINTS",
        "data_method":"LATEST_COMMON_IN_WEEK_ECB_AND_BOTH_2Y_SAME_DATE",
        "historical_point_in_time_vintages_verified":False,
        "yield_instrument_basis_comparable_across_countries":False,
        "training_window_past_only":True,
        "no_calendar_gap_interpolation":True,
        "b1_b2_rule_validated":False,
        "beta_promoted":False,
        "core_scores_modified":False,
        "dashboard_changed":False,
        "trading_performance_claim":False,
        "explanation":"OOS calculations are illustrative on current-revised stored observations. The latest historical dataset can incorporate post-event revisions; no verified release-vintage panel or source harmonization. Performance inference is forbidden.",
        "pairs":pairs,
    }


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--as-of",default="2026-10-26")
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    if not args.out.resolve().is_relative_to(Path("/tmp")):
        ap.error("shadow research output must remain under /tmp")
    data=audit(json.loads(FX_PATH.read_text(encoding="utf-8")),
               json.loads(RATE_PATH.read_text(encoding="utf-8")),
               as_of=args.as_of)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
                       encoding="utf-8")
    print(json.dumps({"schema":SCHEMA,"state":data["state"],
                      "pair_count":data["pair_count"],
                      "pairs_with_any_oos":data["pairs_with_any_oos"],
                      "pairs_with_descriptive_variance_measure":
                       data["pairs_with_descriptive_variance_measure"],
                      "rate_quality":{k:v["reason"] for k,v in data["rate_2y_series_quality"].items()}},
                     ensure_ascii=False))


if __name__=="__main__":
    main()
