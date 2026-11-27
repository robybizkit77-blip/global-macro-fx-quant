"""Fail closed on malformed CAD CORRA prices, rates or inconsistent changes."""
import math
TENORS=("3m","6m","12m")
def num(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def settlement(x):
    # Wide economic guard, not a quote estimate. Implied rate -5% to +25%.
    if not num(x) or not 75<=x<=105:
        raise ValueError("CAD CRA settlement outside [75,105]; possible column shift")
    return x
def validate_observations(obs):
    for key in ("current","t_minus_1","weekly_reference"):
        row=obs[key]
        for t in TENORS:
            price=settlement(row["raw"][t]["settlement"])
            rate=row[t]
            if not num(rate) or abs(rate-(100-price))>1e-6:
                raise ValueError("CAD CRA rate/settlement mismatch")
    for t in TENORS:
        cur=obs["current"][t]
        for key in ("t_minus_1","weekly_reference"):
            if abs(cur-obs[key][t])>5:
                raise ValueError("CAD CRA change exceeds 500bp: manual review required")
def validate_changes(obs,daily,weekly):
    validate_observations(obs)
    for t in TENORS:
        for got,key in ((daily[t],"t_minus_1"),(weekly[t],"weekly_reference")):
            want=(obs["current"][t]-obs[key][t])*100
            if not num(got) or abs(got-want)>.051:
                raise ValueError("CAD CRA published delta does not reconcile")
