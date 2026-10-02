#!/usr/bin/env python3
import json
from pathlib import Path

MACRO=Path("validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json")
RATES=Path("validation/PIT_REPLAY_CA_RATES_POLICY_2020_2026_V1_2026-10-02.json")
OUT=Path("validation/PIT_REPLAY_CA_CORE_MACRO_RATES_2020_2026_V1_2026-10-02.json")

m=json.loads(MACRO.read_text())
r=json.loads(RATES.read_text())

macro_rows=sorted(m["comparisons"],key=lambda x:x["checkpoint"])
rates_rows=sorted(r["rows"],key=lambda x:x["date"])

def sign(x):
    return 1 if x>0 else -1 if x<0 else 0

def core_state(macro_pol,rates_dir):
    # Frozen core interpretation: Macro + Rates/CB are the two structural pillars.
    if macro_pol>0 and rates_dir>0: return "FORTE"
    if macro_pol<0 and rates_dir<0: return "FRAGILE"
    if macro_pol==0 and rates_dir==0: return "MISTA"
    if macro_pol==0 and rates_dir!=0: return "COSTRUTTIVA" if rates_dir>0 else "DEBOLE"
    if macro_pol!=0 and rates_dir==0: return "COSTRUTTIVA" if macro_pol>0 else "DEBOLE"
    return "MISTA"

def core_polarity(macro_pol,rates_dir):
    s=(macro_pol or 0)+(rates_dir or 0)
    return sign(s)

# Macro updates on release dates; rates update daily. Build union timeline,
# forward-filling only information already known by each date.
events=sorted(set([x["checkpoint"] for x in macro_rows] + [x["date"] for x in rates_rows]))
mi=ri=0
latest_m=None
latest_r=None
rows=[]
for dt in events:
    while mi<len(macro_rows) and macro_rows[mi]["checkpoint"]<=dt:
        latest_m=macro_rows[mi]; mi+=1
    while ri<len(rates_rows) and rates_rows[ri]["date"]<=dt:
        latest_r=rates_rows[ri]; ri+=1
    if not latest_m or not latest_r: continue

    fm=latest_m["first_release"]["macro_polarity"]
    rm=latest_m["current_revised"]["macro_polarity"]
    rd=latest_r["front_end_direction"]
    rt=latest_r["front_end_turning"]

    first_state=core_state(fm,rd)
    revised_state=core_state(rm,rd)
    first_pol=core_polarity(fm,rd)
    revised_pol=core_polarity(rm,rd)

    rows.append({
      "checkpoint":dt,
      "latest_macro_checkpoint":latest_m["checkpoint"],
      "latest_rates_checkpoint":latest_r["date"],
      "rates":{
        "front_end_direction":rd,
        "front_end_turning":rt,
        "y2":latest_r["y2"],
        "y10":latest_r["y10"],
        "policy_rate":latest_r.get("policy_rate"),
        "policy_gap_bp":latest_r.get("policy_gap_bp"),
        "lead_tenor":latest_r.get("lead_tenor")
      },
      "first_release":{
        "macro_polarity":fm,
        "macro_turning_present":latest_m["first_release"]["turning_present"],
        "core_state":first_state,
        "core_polarity":first_pol
      },
      "current_revised":{
        "macro_polarity":rm,
        "macro_turning_present":latest_m["current_revised"]["turning_present"],
        "core_state":revised_state,
        "core_polarity":revised_pol
      },
      "core_state_changed":first_state!=revised_state,
      "core_polarity_changed":first_pol!=revised_pol,
      "macro_turning_changed":latest_m["first_release"]["turning_present"]!=latest_m["current_revised"]["turning_present"]
    })

statechg=[x["checkpoint"] for x in rows if x["core_state_changed"]]
polchg=[x["checkpoint"] for x in rows if x["core_polarity_changed"]]
turnchg=[x["checkpoint"] for x in rows if x["macro_turning_changed"]]

report={
 "schema":"GMFQ_CA_CORE_MACRO_RATES_PIT_REPLAY_V1",
 "created_at":"2026-10-02",
 "freeze":{"branch":"engine-freeze-v1-2026-10-02","model_rules_version":"9.3-pair-attention-hierarchy","rules_fingerprint":"3356baf0"},
 "scope":{"currency":"CAD","core":["Macro PIT","Rates 2Y PIT","BoC policy rate PIT"]},
 "construction":{
   "timeline":"Union of Macro release checkpoints and daily Bank of Canada rates observations.",
   "macro":"Latest available official first-release Macro state vs latest available current-revised replay state.",
   "rates":"Same native PIT 2Y front-end dynamics in both branches; no revision ambiguity.",
   "core_state_rule":"FORTE when Macro and Rates both positive; FRAGILE when both negative; COSTRUTTIVA/DEBOLE when one pillar is neutral and the other directional; MISTA when they conflict or are both neutral.",
   "core_polarity_rule":"sign(Macro polarity + Rates 2Y direction)."
 },
 "rows":rows,
 "summary":{
   "checkpoints_compared":len(rows),
   "core_state_changes":len(statechg),
   "core_state_change_pct":round(100*len(statechg)/len(rows),2) if rows else None,
   "core_polarity_changes":len(polchg),
   "core_polarity_change_pct":round(100*len(polchg)/len(rows),2) if rows else None,
   "macro_turning_changes":len(turnchg),
   "changed_core_state_checkpoints":statechg,
   "changed_core_polarity_checkpoints":polchg,
   "changed_macro_turning_checkpoints":turnchg
 },
 "caveat":"This is the CAD structural core replay. It intentionally excludes Price confirmation, COT, Liquidity overlay and contextual risk layers from the core-state comparison."
}
OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report["summary"],indent=2))
