#!/usr/bin/env python3
"""PDF 23.3, steps 4/5: read-only 52-week HC3 + Huber sensitivity diagnostics.

The original 52W FX-vs-delta-relative-2Y OLS estimate is NOT replaced.
Returns never become PIT-certified or a source for Core, signals or ranking.
All input rows must be weekly, contiguous, chronological and numeric.
"""
from __future__ import annotations

import datetime as dt
import math
from statistics import median

from validation.beta.rate_beta_observational_v1 import WINDOW, ols_beta

SCHEMA = "GMFQ_BETA_52W_ROBUST_SE_SENSITIVITY_RESEARCH_V1"


def _weighted_fit(xs, ys, weights):
    total = sum(weights)
    if not math.isfinite(total) or total <= 0:
        return None
    mx = sum(w*x for w,x in zip(weights,xs))/total
    my = sum(w*y for w,y in zip(weights,ys))/total
    sxx = sum(w*(x-mx)**2 for w,x in zip(weights,xs))
    if sxx <= 1e-14 or not math.isfinite(sxx):
        return None
    slope = sum(w*(x-mx)*(y-my) for w,x,y in zip(weights,xs,ys))/sxx
    intercept = my-slope*mx
    return (intercept,slope) if all(math.isfinite(v) for v in (intercept,slope)) else None


def _huber(xs, ys, intercept, slope, *, max_steps=120):
    """Intercept + slope Huber IRLS, fixed 1.345 tuning, MAD residual scale."""
    converged = False
    for _ in range(max_steps):
        residuals = [y-intercept-slope*x for x,y in zip(xs,ys)]
        med = median(residuals)
        scale = median(abs(e-med) for e in residuals)/0.6745
        if scale <= 1e-12:
            nz = [abs(e) for e in residuals if abs(e)>1e-10]
            if not nz:
                return intercept,slope,True
            # Median=0 with sparse spikes: robustly reject the spike.
            scale = max(1e-10,min(nz)*0.05)
        cap = 1.345*scale
        weights = [min(1.0,cap/abs(e)) if abs(e)>cap else 1.0 for e in residuals]
        fit = _weighted_fit(xs,ys,weights)
        if fit is None:
            return None,None,False
        a,b = fit
        if abs(a-intercept)<=1e-11 and abs(b-slope)<=1e-11:
            intercept,slope,converged=a,b,True
            break
        intercept,slope=a,b
    return intercept,slope,converged


def diagnose(rows):
    """Rows: (datetime.date, simple FX return, 2Y-differential change in pp)."""
    if len(rows)!=WINDOW:
        raise ValueError("strict exactly 52 weekly training observations required")
    xs,ys,days=[],[],[]
    for r in rows:
        if not isinstance(r,(tuple,list)) or len(r)!=3:
            raise ValueError("expected (date, fx_return, delta_rel_2y)")
        day,y,x=r
        if not isinstance(day,dt.date) or isinstance(day,dt.datetime):
            raise ValueError("noncanonical weekly date")
        if type(x) not in (int,float) or type(y) not in (int,float) or (
            not math.isfinite(x) or not math.isfinite(y)):
            raise ValueError("no missing or synthetic beta training values")
        if days and (day-days[-1]).days!=7:
            raise ValueError("missing/duplicate/nonconsecutive historical week")
        days.append(day);xs.append(float(x));ys.append(float(y))
    base={
        "schema":SCHEMA,"state":"SHADOW_HISTORICAL_NOT_PIT_CERTIFIED",
        "sample_weeks":WINDOW,"sample_first":days[0].isoformat(),
        "sample_last":days[-1].isoformat(),
        "beta_ols_original_contract":None,
        "ols_hc3_standard_error":None,"huber_beta":None,
        "huber_converged":False,"huber_minus_ols":None,
        "max_single_week_leave_one_out_ols_change":None,
        "max_observation_leverage":None,
        "status":"NO_VALID_VARIANCE",
        "source_first_publication_pit_verified":False,
        "rates_instrument_comparability_verified":False,
        "robust_diagnostic_not_predictive_validation":True,
        "b1_b2_rules_inferred":False,"beta_promoted":False,
        "core_effect":"NONE","pair_signal_effect":"NONE",
        "performance_claim":False,
    }
    beta = ols_beta(rows)
    fit = _weighted_fit(xs,ys,[1.0]*WINDOW)
    if beta is None or fit is None:
        return base
    intercept=fit[0]
    if abs(fit[1]-beta)>1e-10:
        raise ValueError("OLS contract slope discrepancy")
    mx=sum(xs)/WINDOW
    sxx=sum((x-mx)**2 for x in xs)
    h=[1/WINDOW+(x-mx)**2/sxx for x in xs]
    if any(v>=1-1e-10 for v in h):
        return base
    resid=[y-intercept-beta*x for x,y in zip(xs,ys)]
    var_hc3=sum((x-mx)**2*(e/(1-v))**2 for x,e,v in zip(xs,resid,h))/(sxx*sxx)
    if var_hc3<0 or not math.isfinite(var_hc3):
        return base
    a_hub,b_hub,converged=_huber(xs,ys,intercept,beta)
    delete_one=[]
    for i in range(WINDOW):
        remain=rows[:i]+rows[i+1:]
        b=ols_beta(remain)
        if b is None or not math.isfinite(b):
            return base
        delete_one.append(abs(b-beta))
    base.update({
        "status":"RESEARCH_DIAGNOSTIC_ONLY",
        "beta_ols_original_contract":beta,
        "ols_hc3_standard_error":math.sqrt(var_hc3),
        "huber_beta":b_hub if converged else None,
        "huber_converged":converged,
        "huber_minus_ols":b_hub-beta if converged else None,
        "max_single_week_leave_one_out_ols_change":max(delete_one),
        "max_observation_leverage":max(h),
    })
    return base
