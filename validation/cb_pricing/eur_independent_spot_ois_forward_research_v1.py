#!/usr/bin/env python3
"""EUR independent spot OIS -> approximate FST3-period forward research.

Never confuse a 3M spot-start OIS par quote with a 3M future-start €STR
contract. Build discount factors from independently supplied spot OIS par
quotes *assuming a single fixed payment for <=1Y with ACT/360*.
This assumption, market-timestamp match, and convexity/basis are
NOT certified; source snapshots are supplied from /tmp only, and are never
persisted or reproduced in the repository.

This is an independent SOURCE-comparison research receipt, not an OIS
forecast error/backtest and not an operational repricing feed.
"""
from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timezone
from pathlib import Path
import bisect
import json
import math

from validation.cb_pricing.audit_estimated_ois_reliability_v1 import require
from validation.cb_pricing.eur_estr_contract_benchmark_bridge_v1 import (
    SOURCE, eur_archive
)

SCHEMA = "GMFQ_EUR_INDEPENDENT_SPOT_OIS_FWD_RESEARCH_V1"
INPUT_SCHEMA = "GMFQ_EUR_INDEPENDENT_SPOT_OIS_RESEARCH_INPUT_V1"
METHODS = ("LOG_DISCOUNT", "LINEAR_DISCOUNT", "LINEAR_ZERO")
MODERATE_GAP_DAYS = 42


def date_checked(value):
    require(isinstance(value, str), "date string expected")
    x=date.fromisoformat(value)
    require(x.isoformat() == value, "strict source date")
    return x


def add_months(d, months):
    y = d.year + (d.month - 1 + months)//12
    m = (d.month - 1 + months)%12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def spot_nodes(data):
    require(isinstance(data, dict) and data.get("schema")==INPUT_SCHEMA,
            "research spot input schema")
    require(data.get("currency")=="EUR" and data.get("floating_index")=="ESTR",
            "not EUR €STR reference")
    require(data.get("reference_kind")=="PUBLIC_SPOT_OIS_PAR_NOT_FUTURES",
            "not an independent spot OIS par reference")
    require(data.get("fixed_leg_assumption")=="SINGLE_PAYMENT_ACT360_UNVERIFIED",
            "must acknowledge unverified fixed leg convention")
    require(data.get("market_timestamp_alignment_verified") is False and
            data.get("independent_fwd_OIS_benchmark_certified") is False and
            data.get("license_to_redistribute_snapshot") is False and
            data.get("eligible_to_change_live_OIS") is False,
            "cannot promote unlicensed/incomparable source")
    require(isinstance(data.get("source_url"),str) and
            data["source_url"].startswith("https://"),
            "source URL required")
    source_day = date_checked(data["quote_date"])
    quotes = data.get("tenors")
    require(isinstance(quotes,list) and len(quotes)>=5,
            "requires documented spot curve shape")
    pts=[]
    seen=set()
    for row in quotes:
        require(isinstance(row,dict), "spot row object required")
        months=row.get("months")
        rate=row.get("par_rate_pct")
        require(type(months) is int and 1<=months<=12 and months not in seen,
                "unique 1M..12M spot maturities only")
        require(type(rate) in (int,float) and math.isfinite(rate) and -2 < rate < 20,
                "finite spot par OIS level expected")
        seen.add(months)
        maturity=add_months(source_day, months)
        days=(maturity-source_day).days
        require(days>0,"spot maturity must be future")
        df=1/(1+rate/100*(days/360))
        require(df>0 and math.isfinite(df),"invalid discount factor")
        pts.append((days, df, months))
    pts.sort()
    return source_day, pts


def interpolate_df(points, elapsed_days, method):
    require(method in METHODS, "unknown interpolation")
    ts=[x[0] for x in points]
    pos=bisect.bisect_left(ts, elapsed_days)
    require(0<pos<len(ts), "no extrapolation from incomplete curve")
    a,da,_=points[pos-1]
    b,db,_=points[pos]
    require(b-a<=MODERATE_GAP_DAYS, "spot tenor gap >42 days")
    w=(elapsed_days-a)/(b-a)
    if method=="LOG_DISCOUNT":
        return math.exp((1-w)*math.log(da)+w*math.log(db))
    if method=="LINEAR_DISCOUNT":
        return (1-w)*da+w*db
    za=-math.log(da)/(a/360)
    zb=-math.log(db)/(b/360)
    return math.exp(-((1-w)*za+w*zb)*(elapsed_days/360))


def forward_period(source_day, spot_points, start, end):
    st=date_checked(start)
    ed=date_checked(end)
    require(source_day < st < ed,
            "started futures or nonfuture period require realized fixings")
    duration=(ed-st).days
    require(85<=duration<=100,"futures accrual length not 3M")
    t0=(st-source_day).days
    t1=(ed-source_day).days
    output={}
    for method in METHODS:
        d0=interpolate_df(spot_points,t0,method)
        d1=interpolate_df(spot_points,t1,method)
        rate=(d0/d1-1)*(360/duration)*100
        require(-5<=rate<=25 and math.isfinite(rate),"implausible reconstructed forward")
        output[method]=round(rate,8)
    return output


def compare(archive, spot):
    source_day, nodes=spot_nodes(spot)
    records=eur_archive(archive)["observations"]
    futures=[r for r in records if r["quote_date"]==source_day.isoformat()]
    eligible=[]
    skip=[]
    for f in futures:
        if date_checked(f["accrual_start"])<=source_day:
            skip.append({"contract":f["contract"],"reason":"STARTED_OR_START_DAY_NO_PURE_FORWARD"})
            continue
        try:
            fwd=forward_period(source_day,nodes,
                               f["accrual_start"],f["accrual_end"])
        except ValueError as exc:
            skip.append({"contract":f["contract"],"reason":"INSUFFICIENT_SPOT_CURVE_NO_EXTRAPOLATION"})
            continue
        spreads={m:round((f["rate_pct"]-fwd[m])*100,6) for m in METHODS}
        eligible.append({"contract":f["contract"],"quote_date":f["quote_date"],
            "accrual_start":f["accrual_start"],"accrual_end":f["accrual_end"],
            "futures_rate_pct":f["rate_pct"],
            "independent_spot_OIS_curve_forward_by_assumption_pct":fwd,
            "futures_minus_modelled_OIS_curve_spread_bp":spreads,
            "interpolation_spread_range_bp":round(max(spreads.values())-min(spreads.values()),6),
            "OIS_true_forward_quote_observed":False,
            "original_futures_first_seen_at_utc":f["first_seen_at_utc"],
            "forward_reconstruction_is_indicative":True,
            "source_time_alignment_verified":False,
            "not_PIT_trading_eligible":True})
    return {"schema":SCHEMA,"status":"SINGLE_DATE_INDEPENDENT_SPOT_CURVE_RECONSTRUCTION",
        "spot_source_url":spot["source_url"],"spot_quote_day":source_day.isoformat(),
        "spot_nodes_count":len(nodes),
        "EUR_futures_rows_on_spot_source_day":len(futures),
        "comparable_reconstructed_forward_count":len(eligible),
        "comparisons":eligible,"skipped":skip,
        "benchmark_is_independent_spot_OIS_quotes_not_forward_contracts":True,
        "spot_to_discount_assumption":"ONE_FIXED_PAYMENT_ACT360_UNVERIFIED",
        "interpolation_methods":list(METHODS),
        "underlying_OIS_quotes_time_aligned_to_futures":False,
        "rates_are_NOT_a_direct_forward_OIS_benchmark":True,
        "cross_instrument_convexity_and_basis_NOT_calibrated":True,
        "historical_OIS_level_prediction_MAE_bp":None,
        "historical_OIS_direction_hit_rate":None,
        "OOS_model_skill_validated":False,
        "eligible_to_change_live_OIS":False,
        "eligible_to_change_FX_bias_pairs_or_forward":False,
        "writes_live_data":False,
        "redistributes_underlying_vendor_spot_rates":False}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--spot-input",type=Path,required=True,
        help="One-time external source input in /tmp (never stored in repository)")
    ap.add_argument("--out",type=Path,default=Path("/tmp/eur-spot-ois-forward-research.json"))
    a=ap.parse_args()
    require(a.spot_input.resolve().is_relative_to(Path("/tmp")) and
            a.out.resolve().is_relative_to(Path("/tmp")),
            "source & receipt must be outside repository under /tmp")
    d=json.loads(a.spot_input.read_text(encoding="utf-8"))
    r=compare(SOURCE.read_text(encoding="utf-8"),d)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"date":r["spot_quote_day"],
        "comparisons":r["comparable_reconstructed_forward_count"],
        "status":r["status"],"historical_MAE":r["historical_OIS_level_prediction_MAE_bp"]}))


if __name__=="__main__":
    main()
