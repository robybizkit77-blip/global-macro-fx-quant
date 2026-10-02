#!/usr/bin/env python3
import json
from pathlib import Path

GROWTH=Path("validation/PIT_SIGNAL_SENSITIVITY_CA_GROWTH_FULL_2020_2026_V1_2026-10-02.json")
LABOUR=Path("validation/PIT_SIGNAL_SENSITIVITY_CA_LABOUR_FULL_2020_2026_V1_2026-10-02.json")
OUT=Path("validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json")

g=json.loads(GROWTH.read_text())
l=json.loads(LABOUR.read_text())

gmap={x["checkpoint"]:x for x in g["comparisons"] if x.get("both_series_ready")}
lmap={x["checkpoint"]:x for x in l["comparisons"] if x.get("both_series_ready")}
events=sorted(set(gmap)|set(lmap))

def pol(gdir,ldir):
    s=(gdir or 0)+(ldir or 0)
    return 1 if s>0 else -1 if s<0 else 0

def alignment(gdir,ldir):
    if gdir>0 and ldir>0: return "BOTH_POSITIVE"
    if gdir<0 and ldir<0: return "BOTH_NEGATIVE"
    if gdir==0 and ldir==0: return "BOTH_NEUTRAL"
    if gdir*ldir<0: return "CONFLICT"
    return "PARTIAL"

latest_g=None
latest_l=None
rows=[]
for dt in events:
    if dt in gmap: latest_g=gmap[dt]
    if dt in lmap: latest_l=lmap[dt]
    if not latest_g or not latest_l: continue

    fg=latest_g["first_release"]; fl=latest_l["first_release"]
    rg=latest_g["current_revised"]; rl=latest_l["current_revised"]
    fp=pol(fg["direction"],fl["direction"])
    rp=pol(rg["direction"],rl["direction"])
    ft=bool(fg["turning"] or fl["turning"])
    rt=bool(rg["turning"] or rl["turning"])

    rows.append({
      "checkpoint":dt,
      "latest_growth_checkpoint":latest_g["checkpoint"],
      "latest_labour_checkpoint":latest_l["checkpoint"],
      "first_release":{
        "growth_direction":fg["direction"],
        "labour_direction":fl["direction"],
        "macro_polarity":fp,
        "alignment":alignment(fg["direction"],fl["direction"]),
        "turning_present":ft
      },
      "current_revised":{
        "growth_direction":rg["direction"],
        "labour_direction":rl["direction"],
        "macro_polarity":rp,
        "alignment":alignment(rg["direction"],rl["direction"]),
        "turning_present":rt
      },
      "macro_polarity_changed":fp!=rp,
      "macro_turning_changed":ft!=rt,
      "growth_direction_changed":fg["direction"]!=rg["direction"],
      "labour_direction_changed":fl["direction"]!=rl["direction"]
    })

polchg=[x["checkpoint"] for x in rows if x["macro_polarity_changed"]]
turnchg=[x["checkpoint"] for x in rows if x["macro_turning_changed"]]
gchg=[x["checkpoint"] for x in rows if x["growth_direction_changed"]]
lchg=[x["checkpoint"] for x in rows if x["labour_direction_changed"]]

report={
 "schema":"GMFQ_PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1",
 "created_at":"2026-10-02",
 "freeze":{"branch":"engine-freeze-v1-2026-10-02","model_rules_version":"9.3-pair-attention-hierarchy","rules_fingerprint":"3356baf0"},
 "scope":{"currency":"CAD","macro_core":["Crescita","Lavoro"]},
 "construction":{
   "growth":"Latest available CAD Growth block state from the strict first-release vs revised matched-availability reconstruction.",
   "labour":"Latest available CAD Labour block state from official LFS first-release vs revised reconstruction.",
   "macro_rule":"Matches frozen runtime macro combination used by shadowMacro/v228MacroDir: sign(Growth.direction + Labour.direction).",
   "checkpoint_frequency":"Union of GDP, Retail and LFS official release dates; unchanged blocks are forward-filled until their next official release.",
   "turning_rule":"True when either Growth or Labour block reports a turning point, matching shadowMacro."
 },
 "comparisons":rows,
 "summary":{
   "checkpoints_compared":len(rows),
   "macro_polarity_changes":len(polchg),
   "macro_polarity_change_pct":round(100*len(polchg)/len(rows),2) if rows else None,
   "macro_turning_changes":len(turnchg),
   "checkpoints_with_growth_revision_effect":len(gchg),
   "checkpoints_with_labour_revision_effect":len(lchg),
   "changed_macro_polarity_checkpoints":polchg,
   "changed_macro_turning_checkpoints":turnchg
 },
 "caveat":"This closes the CAD Macro core (Growth + Labour) only. Full historical FX decision state still requires historical Rates/CB and other contextual layers."
}
OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report["summary"],indent=2))
