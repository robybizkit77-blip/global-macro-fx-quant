#!/usr/bin/env python3
import json, math, statistics
from pathlib import Path

RATES=Path("validation/cad_rates_pit/CA_BOC_BENCHMARK_RATES_DAILY_2020_2026_V1.json")
OUT=Path("validation/PIT_REPLAY_CA_RATES_POLICY_2020_2026_V1_2026-10-02.json")

def median(a):
    b=sorted(x for x in a if math.isfinite(x))
    if not b: return None
    n=len(b)
    return b[n//2] if n%2 else (b[n//2-1]+b[n//2])/2

def series_dynamics(vals):
    vals=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
    if len(vals)<10: return None
    n=len(vals)
    fast=min(5,n//3)
    def slope(end,length):
        st=end-length+1
        if st<0: return None
        return (vals[end]-vals[st])/(length-1)
    recent=slope(n-1,fast)
    prior=slope(n-fast,fast)
    if recent is None or prior is None: return None
    diffs=[abs(vals[i]-vals[i-1]) for i in range(max(1,n-52),n)]
    typical=median(diffs) or 0
    direction=0 if abs(recent)<typical*0.15 else (1 if recent>0 else -1)
    speed=abs(recent)/typical if typical>0 else None
    accel=recent-prior
    accel_dir=0 if abs(accel)<typical*0.15 else (1 if accel>0 else -1)
    turn=(prior!=0 and recent!=0 and (1 if prior>0 else -1)!=(1 if recent>0 else -1))
    return {
      "recent":recent,"prior":prior,"dir":direction,"speed":speed,
      "accel":accel,"accelDir":accel_dir,"turn":turn
    }

j=json.loads(RATES.read_text())
rows=j["rows"]
y2=[]; y10=[]; replay=[]
for r in rows:
    y2.append(r["y2"]); y10.append(r["y10"])
    d2=series_dynamics(y2)
    d10=series_dynamics(y10)
    if not d2 or not d10: continue
    lead="2Y" if abs(d2["recent"])>abs(d10["recent"]) else "10Y"
    policy_gap_bp=(r["y2"]-r["policy_rate"])*100 if r.get("policy_rate") is not None else None
    replay.append({
      "date":r["date"],
      "y2":r["y2"],"y10":r["y10"],"policy_rate":r.get("policy_rate"),
      "policy_gap_bp":round(policy_gap_bp,4) if policy_gap_bp is not None else None,
      "curve_bp":r["curve_bp"],
      "rates_2y":{k:(round(v,6) if isinstance(v,float) else v) for k,v in d2.items()},
      "rates_10y":{k:(round(v,6) if isinstance(v,float) else v) for k,v in d10.items()},
      "lead_tenor":lead,
      "front_end_direction":d2["dir"],
      "front_end_turning":d2["turn"]
    })

report={
 "schema":"GMFQ_CA_RATES_POLICY_PIT_REPLAY_V1",
 "created_at":"2026-10-02",
 "freeze":{"branch":"engine-freeze-v1-2026-10-02","model_rules_version":"9.3-pair-attention-hierarchy","rules_fingerprint":"3356baf0"},
 "source":"Bank of Canada Valet API",
 "construction":{
   "rates":"Official daily 2Y and 10Y Government of Canada benchmark yields; native point-in-time market observations.",
   "policy":"Official Bank of Canada target overnight rate, forward-filled only after its dated observation exists.",
   "engine_equivalence":"2Y dynamics replicate frozen seriesDynamics(): 5-observation recent slope vs prior 5-observation slope, scaled against median absolute daily changes over up to 52 observations, with 0.15 threshold."
 },
 "rows":replay,
 "summary":{
   "count":len(replay),
   "from":replay[0]["date"] if replay else None,
   "to":replay[-1]["date"] if replay else None,
   "front_end_positive_days":sum(1 for x in replay if x["front_end_direction"]>0),
   "front_end_negative_days":sum(1 for x in replay if x["front_end_direction"]<0),
   "front_end_neutral_days":sum(1 for x in replay if x["front_end_direction"]==0),
   "front_end_turning_days":sum(1 for x in replay if x["front_end_turning"]),
   "two_year_lead_days":sum(1 for x in replay if x["lead_tenor"]=="2Y"),
   "ten_year_lead_days":sum(1 for x in replay if x["lead_tenor"]=="10Y")
 }
}
OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report["summary"],indent=2))
