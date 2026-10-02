#!/usr/bin/env python3
import json, math, statistics
from pathlib import Path

LFS=Path("validation/cad_lfs_release_crawl/CA_LFS_DATED_RELEASE_CRAWL_V1.json")
PAYLOAD=Path("payload/part-01.txt")
OUT=Path("validation/PIT_SIGNAL_SENSITIVITY_CA_LABOUR_FULL_2020_2026_V1_2026-10-02.json")

def extract_runtime_series(text, series_id):
    marker='{"id":"'+series_id+'"'
    start=text.find(marker)
    if start<0: raise RuntimeError(f"runtime series not found: {series_id}")
    depth=0; instr=False; esc=False
    for i in range(start,len(text)):
        ch=text[i]
        if instr:
            if esc: esc=False
            elif ch=="\\": esc=True
            elif ch=='"': instr=False
        else:
            if ch=='"': instr=True
            elif ch=='{': depth+=1
            elif ch=='}':
                depth-=1
                if depth==0: return json.loads(text[start:i+1])
    raise RuntimeError("unterminated runtime object")

def robust_scale_diffs(vals):
    diffs=[abs(float(vals[i])-float(vals[i-1])) for i in range(1,len(vals))]
    if not diffs: return None
    m=statistics.median(diffs)
    return m if math.isfinite(m) and m>0 else None

def impulse(vals,polarity):
    vals=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
    if len(vals)<8: return None
    scale=robust_scale_diffs(vals[-80:])
    if not scale: return None
    d0=(vals[-1]-vals[-2])*polarity/scale
    d1=(vals[-2]-vals[-3])*polarity/scale
    return {"current":d0,"previous":d1}

def block(emp_vals,unemp_vals):
    xs=[impulse(emp_vals,1),impulse(unemp_vals,-1)]
    xs=[x for x in xs if x]
    if not xs: return None
    current=statistics.median([x["current"] for x in xs])
    previous=statistics.median([x["previous"] for x in xs])
    direction=0 if abs(current)<0.20 else (1 if current>0 else -1)
    acceleration=current-previous
    accel_dir=0 if abs(acceleration)<0.20 else (1 if acceleration>0 else -1)
    prev_sign=0 if previous==0 else (1 if previous>0 else -1)
    turning=(prev_sign!=0 and direction!=0 and prev_sign!=direction)
    return {
      "current":current,"previous":previous,"direction":direction,
      "speed":abs(current),"acceleration":acceleration,
      "accelDir":accel_dir,"turning":turning,"n":len(xs)
    }

lfs=json.loads(LFS.read_text())
if not lfs["summary"].get("complete"):
    raise RuntimeError("LFS first-release panel is not complete")
payload=PAYLOAD.read_text()
remp=extract_runtime_series(payload,"CA_EMPLOYMENT_history_value")
runemp=extract_runtime_series(payload,"CA_UNEMP_RATE_history_value")
remp_map=dict(zip(remp["dates"],map(float,remp["values"])))
runemp_map=dict(zip(runemp["dates"],map(float,runemp["values"])))

rows=sorted(lfs["rows"],key=lambda r:r["release_date"])
comparisons=[]
first_emp=[]; first_unemp=[]; rev_emp=[]; rev_unemp=[]
for r in rows:
    m=r["reference_month"]
    if m not in remp_map or m not in runemp_map:
        continue
    first_emp.append(float(r["employment_first_release_thousands"]))
    first_unemp.append(float(r["unemployment_rate_first_release_pct"]))
    rev_emp.append(remp_map[m]); rev_unemp.append(runemp_map[m])
    first=block(first_emp,first_unemp)
    revised=block(rev_emp,rev_unemp)
    if not first or not revised: continue
    row={
      "checkpoint":r["release_date"],"observation_month":m,
      "first_release":first,"current_revised":revised,
      "direction_changed":first["direction"]!=revised["direction"],
      "turning_changed":first["turning"]!=revised["turning"],
      "acceleration_direction_changed":first["accelDir"]!=revised["accelDir"],
      "both_series_ready":first["n"]>=2 and revised["n"]>=2
    }
    comparisons.append(row)

for row in comparisons:
    for side in ("first_release","current_revised"):
        for k,v in list(row[side].items()):
            if isinstance(v,float): row[side][k]=round(v,4)

usable=[x for x in comparisons if x["both_series_ready"]]
dirchg=[x["checkpoint"] for x in usable if x["direction_changed"]]
turnchg=[x["checkpoint"] for x in usable if x["turning_changed"]]
accchg=[x["checkpoint"] for x in usable if x["acceleration_direction_changed"]]

report={
 "schema":"GMFQ_PIT_SIGNAL_SENSITIVITY_CA_LABOUR_FULL_2020_2026_V1",
 "created_at":"2026-10-02",
 "freeze":{"branch":"engine-freeze-v1-2026-10-02","model_rules_version":"9.3-pair-attention-hierarchy","rules_fingerprint":"3356baf0"},
 "scope":{"currency":"CAD","category":"Lavoro","series":["CA_EMPLOYMENT_history_value","CA_UNEMP_RATE_history_value"]},
 "construction":{
   "first_release":"Official contemporaneous Statistics Canada LFS levels for total employment and unemployment rate.",
   "revised":"Current runtime revised levels for the same observation month.",
   "polarity":{"employment":1,"unemployment_rate":-1},
   "engine_equivalence":"Per-series normalizedSeriesImpulse then median across eligible Labour series; 0.20 direction/acceleration thresholds, matching frozen v9.3 blockDynamics."
 },
 "comparisons":comparisons,
 "summary":{
   "runtime_support":{"employment_through":remp["dates"][-1],"unemployment_through":runemp["dates"][-1]},
   "checkpoints_compared":len(comparisons),
   "both_series_ready_checkpoints":len(usable),
   "direction_changes":len(dirchg),
   "direction_change_pct":round(100*len(dirchg)/len(usable),2) if usable else None,
   "turning_changes":len(turnchg),
   "acceleration_direction_changes":len(accchg),
   "changed_direction_checkpoints":dirchg,
   "changed_turning_checkpoints":turnchg,
   "changed_acceleration_checkpoints":accchg
 }
}
OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report["summary"],indent=2))
