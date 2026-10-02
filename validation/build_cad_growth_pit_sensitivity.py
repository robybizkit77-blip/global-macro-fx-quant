#!/usr/bin/env python3
# Strict matched-availability comparison.
import json, math, statistics
from pathlib import Path
from datetime import date

GDP=Path("validation/CA_GDP_FIRST_RELEASE_SERIES_FULL_2020_2026_V1.json")
RETAIL=Path("validation/cad_retail_volume_release_crawl/CA_RETAIL_VOLUME_DATED_RELEASE_CRAWL_V1.json")
PAYLOAD=Path("payload/part-01.txt")
OUT=Path("validation/PIT_SIGNAL_SENSITIVITY_CA_GROWTH_FULL_2020_2026_V1_2026-10-02.json")

def extract_runtime_series(text, series_id):
    marker='{"id":"'+series_id+'"'
    start=text.find(marker)
    if start<0:
        raise RuntimeError(f"runtime series not found: {series_id}")
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
                if depth==0:
                    return json.loads(text[start:i+1])
    raise RuntimeError(f"unterminated runtime object: {series_id}")

def robust_scale_diffs(vals):
    vals=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
    diffs=[abs(vals[i]-vals[i-1]) for i in range(1,len(vals))]
    if not diffs: return None
    m=statistics.median(diffs)
    return m if math.isfinite(m) and m>0 else None

def impulse(vals):
    vals=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
    if len(vals)<8: return None
    scale=robust_scale_diffs(vals[-80:])
    if not scale: return None
    d0=(vals[-1]-vals[-2])/scale
    d1=(vals[-2]-vals[-3])/scale
    return {"current":d0,"previous":d1}

def block(series_values):
    xs=[impulse(v) for v in series_values]
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

def chain(first_rows, anchor):
    out={}
    level=float(anchor)
    for r in sorted(first_rows,key=lambda x:x["reference_month"]):
        v=r.get("first_release_mom_pct")
        if v is None: continue
        level*=1+float(v)/100.0
        out[r["reference_month"]]=level
    return out

gdp=json.loads(GDP.read_text())
retail=json.loads(RETAIL.read_text())
if retail["summary"].get("missing_values"):
    raise RuntimeError(f"retail first-release series still has gaps: {retail['summary']['missing_values']}")

payload=PAYLOAD.read_text()
rgdp=extract_runtime_series(payload,"CA_REAL_GDP_M_history_value")
rret=extract_runtime_series(payload,"CA_RETAIL_VOLUME_history_value")
rgdp_map=dict(zip(rgdp["dates"],map(float,rgdp["values"])))
rret_map=dict(zip(rret["dates"],map(float,rret["values"])))

gdp_rows=gdp["rows"]
ret_rows=retail["rows"]
gdp_first=chain(gdp_rows,rgdp_map["2020-04"])
ret_first=chain(ret_rows,rret_map["2020-04"])

events=[]
for family,rows in [("GDP",gdp_rows),("RETAIL",ret_rows)]:
    for r in rows:
        events.append((r["release_date"],family,r["reference_month"]))
events=sorted(set(events))

gdp_release={r["reference_month"]:r["release_date"] for r in gdp_rows}
ret_release={r["reference_month"]:r["release_date"] for r in ret_rows}

def available_values(level_map, release_map, checkpoint):
    months=sorted(m for m,d in release_map.items() if d<=checkpoint and m in level_map)
    return [level_map[m] for m in months], months

comparisons=[]
for checkpoint,_,_ in events:
    fg,mg=available_values(gdp_first,gdp_release,checkpoint)
    fr,mr=available_values(ret_first,ret_release,checkpoint)
    # Compare only when the current revised runtime contains the exact same
    # latest observation months available to the first-release reconstruction.
    # Never silently fall back to an older revised observation.
    if not mg or not mr:
        continue
    if mg[-1] not in rgdp_map or mr[-1] not in rret_map:
        continue
    rg=[rgdp_map[m] for m in mg if m in rgdp_map]
    rr=[rret_map[m] for m in mr if m in rret_map]
    first=block([fg,fr])
    revised=block([rg,rr])
    if not first or not revised: continue
    row={
      "checkpoint":checkpoint,
      "latest_gdp_month":mg[-1] if mg else None,
      "latest_retail_month":mr[-1] if mr else None,
      "first_release":first,
      "current_revised":revised,
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
 "schema":"GMFQ_PIT_SIGNAL_SENSITIVITY_CA_GROWTH_FULL_2020_2026_V1",
 "created_at":"2026-10-02",
 "freeze":{"branch":"engine-freeze-v1-2026-10-02","model_rules_version":"9.3-pair-attention-hierarchy","rules_fingerprint":"3356baf0"},
 "scope":{"currency":"CAD","category":"Crescita","series":["CA_REAL_GDP_M_history_value","CA_RETAIL_VOLUME_history_value"]},
 "construction":{
   "first_release":"Synthetic level chains compounded from official contemporaneous m/m first-release growth, truncated by each series' actual historical release date.",
   "revised":"Current runtime revised levels, but truncated to the same observation months that were available at each historical checkpoint.",
   "engine_equivalence":"Per-series normalizedSeriesImpulse then median across eligible Growth series; thresholds 0.20 for direction and acceleration, matching frozen v9.3 blockDynamics.",
   "checkpoint_frequency":"Union of official GDP and Retail release dates."
 },
 "comparisons":comparisons,
 "summary":{
   "revised_runtime_support":{"gdp_through":rgdp["dates"][-1],"retail_through":rret["dates"][-1]},
   "event_checkpoints_compared":len(comparisons),
   "both_series_ready_checkpoints":len(usable),
   "direction_changes":len(dirchg),
   "direction_change_pct":round(100*len(dirchg)/len(usable),2) if usable else None,
   "turning_changes":len(turnchg),
   "acceleration_direction_changes":len(accchg),
   "changed_direction_checkpoints":dirchg,
   "changed_turning_checkpoints":turnchg,
   "changed_acceleration_checkpoints":accchg
 },
 "caveat":"This reconstructs the CAD Growth block only. Full CAD macro state also requires PIT Labour series and historical Rates/CB inputs."
}
OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report["summary"],indent=2))
