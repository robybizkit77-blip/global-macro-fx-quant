#!/usr/bin/env python3
import json
from pathlib import Path

CORE=Path("validation/PIT_REPLAY_CA_CORE_MACRO_RATES_2020_2026_V1_2026-10-02.json")
OUT=Path("validation/PIT_REPLAY_CA_V93_MONTHLY_COMPATIBILITY_2021_2026_V1_2026-10-02.json")
j=json.loads(CORE.read_text())
rows=j["rows"]

# Match the historical v9.3 walk-forward cadence: one checkpoint per month.
# Use the first available reconstructible checkpoint in each YYYY-MM month.
monthly={}
for r in rows:
    ym=r["checkpoint"][:7]
    monthly.setdefault(ym,r)
sample=[monthly[k] for k in sorted(monthly)]

def quality(macro,rates):
    if macro!=0 and rates!=0 and macro==rates:
        return "ALIGNED_STRONG"
    if macro==0 and rates==0:
        return "NO_CONTRAST"
    if macro==0 or rates==0:
        return "PARTIAL"
    return "PILLARS_SPLIT"

out=[]
for r in sample:
    rd=r["rates"]["front_end_direction"]
    fm=r["first_release"]["macro_polarity"]
    rm=r["current_revised"]["macro_polarity"]
    fq=quality(fm,rd); rq=quality(rm,rd)
    out.append({
      "checkpoint":r["checkpoint"],
      "rates_direction":rd,
      "pit_macro":fm,
      "revised_macro":rm,
      "pit_quality":fq,
      "revised_quality":rq,
      "quality_changed":fq!=rq,
      "polarity_changed":r["first_release"]["core_polarity"]!=r["current_revised"]["core_polarity"]
    })

qchg=[x for x in out if x["quality_changed"]]
pchg=[x for x in out if x["polarity_changed"]]
def counts(side):
    z={}
    for x in out:
        k=x[side]
        z[k]=z.get(k,0)+1
    return z

report={
 "schema":"GMFQ_CA_V93_MONTHLY_PIT_COMPATIBILITY_V1",
 "created_at":"2026-10-02",
 "freeze":{"model_rules_version":"9.3-pair-attention-hierarchy","rules_fingerprint":"3356baf0"},
 "methodology":{
   "cadence":"Monthly; first available reconstructible checkpoint in each month.",
   "rates":"Same native PIT 2Y seriesDynamics branch in PIT and revised comparisons.",
   "macro":"Official first-release CAD Growth+Labour vs current-revised historical Macro.",
   "quality_mapping":"Matches reconstructible v9.3 historical hierarchy semantics at currency-pillar level: aligned Macro+Rates = strong; one neutral = partial; opposing = split; both neutral = no contrast.",
   "purpose":"Direct compatibility check against the old pseudo-OOS methodology, isolating the effect of replacing revised Macro history with PIT Macro."
 },
 "rows":out,
 "summary":{
   "months_compared":len(out),
   "quality_changes":len(qchg),
   "quality_change_pct":round(100*len(qchg)/len(out),2) if out else None,
   "core_polarity_changes":len(pchg),
   "core_polarity_change_pct":round(100*len(pchg)/len(out),2) if out else None,
   "pit_quality_counts":counts("pit_quality"),
   "revised_quality_counts":counts("revised_quality"),
   "changed_months":[x["checkpoint"] for x in qchg]
 },
 "caveat":"This is a CAD pillar-level compatibility audit, not a 28-pair return backtest. Pair-level performance requires PIT reconstruction for the counterpart currencies too."
}
OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report["summary"],indent=2))
