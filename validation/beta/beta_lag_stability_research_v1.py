#!/usr/bin/env python3
"""PDF 23.3 steps 6/7: retrospective Dimson and frozen 52W rolling stability.

This file never changes the original 52W OLS, production signals or rankings.
One-lead Dimson coefficient uses x[t+1] ONLY within the historical training
window, not at the as-of cutoff or in a live forecast. Research-only.
"""
from __future__ import annotations
from datetime import date,datetime
from math import isfinite
from statistics import pstdev
from validation.beta.rate_beta_observational_v1 import WINDOW,ols_beta

SCHEMA="GMFQ_BETA_52W_LAG_AND_ROLLING_RESEARCH_V1"

def _window(rows):
    if len(rows)!=WINDOW: raise ValueError("exactly 52 contiguous prior weeks required")
    for i,row in enumerate(rows):
        if not isinstance(row,(tuple,list)) or len(row)!=3:
            raise ValueError("expected 3-column week/FX/2Y record")
        day,y,x=row
        if not isinstance(day,date) or isinstance(day,datetime) or any(
            type(z) not in (float,int) or not isfinite(z) for z in (x,y)):
            raise ValueError("invalid timestamp or nonfinite historical input")
        if i and (day-rows[i-1][0]).days!=7:
            raise ValueError("not a continuous 52W historical window")
    return rows

def _solve(matrix,vector):
    n=len(vector)
    a=[list(map(float,matrix[i]))+[float(vector[i])] for i in range(n)]
    largest=max((abs(z) for row in a for z in row[:-1]),default=0)
    if not largest: return None
    for j in range(n):
        i=max(range(j,n),key=lambda k:abs(a[k][j]))
        if abs(a[i][j])<=largest*1e-12: return None
        a[j],a[i]=a[i],a[j]
        scale=a[j][j]
        a[j]=[z/scale for z in a[j]]
        for k in range(n):
            if k==j:continue
            factor=a[k][j]
            a[k]=[v-factor*u for v,u in zip(a[k],a[j])]
    v=[r[-1] for r in a]
    return v if all(isfinite(z) for z in v) else None

def historical_dimson_52w(rows):
    rows=_window(rows)
    y=[float(r[1]) for r in rows]
    x=[float(r[2]) for r in rows]
    # t=1,...,50 guarantees x[t+1] remains inside the 52-week
    # HISTORICAL training sample. t=51 is deliberately unused.
    design=[[1.,x[t-1],x[t],x[t+1]] for t in range(1,51)]
    response=y[1:51]
    gram=[[sum(z[i]*z[j] for z in design) for j in range(4)] for i in range(4)]
    rhs=[sum(z[i]*r for z,r in zip(design,response)) for i in range(4)]
    coefficients=_solve(gram,rhs)
    base={"schema":SCHEMA,"state":"HISTORICAL_DIAGNOSTIC_NOT_PIT_CERTIFIED",
          "first_week":rows[0][0].isoformat(),"last_week":rows[-1][0].isoformat(),
          "training_weeks":52,"regression_rows":50,
          "dimson_lag_beta":None,"dimson_contemporaneous_beta":None,
          "dimson_lead_beta":None,"dimson_sum_beta":None,
          "status":"SINGULAR_DESIGN_NO_DIAGNOSTIC" if coefficients is None else "DESCRIPTIVE_ONLY",
          "lead_term_is_historical_train_window_not_live_feature":True,
          "no_future_observation_beyond_training_cutoff":True,
          "pit_first_release_certified":False,"yield_basis_comparable":False,
          "b1_b2_not_evaluated":True,"core_effect":"NONE","pair_effect":"NONE"}
    if coefficients is not None:
        base.update({"dimson_lag_beta":coefficients[1],
                     "dimson_contemporaneous_beta":coefficients[2],
                     "dimson_lead_beta":coefficients[3],
                     "dimson_sum_beta":sum(coefficients[1:])})
    return base

def rolling_52w_stability(rows):
    """Return up to four latest consecutive 52-week OLS fits; no EWMA tuning."""
    if len(rows)<WINDOW: return {"status":"LESS_THAN_52_WEEKS",
                                "betas":[],"beta_range":None,"beta_population_sd":None,
                                "model_effect":"NONE"}
    starts=max(0,len(rows)-WINDOW-3)
    candidates=[rows[i:i+WINDOW] for i in range(starts,len(rows)-WINDOW+1)]
    for window in candidates:_window(window)
    vals=[ols_beta(window) for window in candidates]
    complete=all(v is not None and isfinite(v) for v in vals)
    return {"status":"DESCRIPTIVE_ONLY" if complete else "ZERO_VARIANCE",
            "rolling_window_weeks":52,
            "last_training_week":rows[-1][0].isoformat(),
            "betas":vals if complete else [],
            "beta_range":max(vals)-min(vals) if complete else None,
            "beta_population_sd":pstdev(vals) if complete else None,
            "windows_observed":len(vals),
            "four_windows_available":len(vals)==4,
            "no_hyperparameter_tuning":True,"threshold_classification":"NOT_DEFINED",
            "first_release_pit_certified":False,"model_effect":"NONE"}

def diagnose(rows):
    if len(rows)<WINDOW:
        return {"status":"INSUFFICIENT_HISTORY","dimson":None,"rolling":None,
                "core_effect":"NONE","beta_promoted":False}
    _window(rows[-WINDOW:])
    return {"status":"RESEARCH_ONLY","dimson":historical_dimson_52w(rows[-WINDOW:]),
            "rolling":rolling_52w_stability(rows),
            "historical_pseudo_oos_only":True,"pit_certified":False,
            "core_effect":"NONE","beta_promoted":False}
