#!/usr/bin/env python3
"""G8 Growth and Inflation source freshness; descriptive, NEVER PIT-certified."""
import argparse,json,math
from datetime import date
from pathlib import Path
from validation.macro.v2_shadow_features_v1 import ROOT,require
CURRENCIES=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
CATS={"growth":"Crescita","inflation":"Inflazione"}
AS_OF=date(2026,10,23)
def inspect(data,*,as_of=AS_OF):
    require(set(data)==set(CURRENCIES),"G8 series keys drift")
    rows=[]
    for ccy in CURRENCIES:
        for pillar,cat in CATS.items():
            candidates=[x for x in data[ccy] if x.get("category")==cat]
            require(candidates,ccy+" "+pillar+" has no observed series")
            selected=[]
            for x in candidates:
                raw=x.get("last_date")
                try:dt=date.fromisoformat(raw)
                except (ValueError,TypeError):continue
                v=x.get("last_value")
                if type(v) not in (int,float) or not math.isfinite(v) or dt>as_of:continue
                selected.append((dt,x))
            if selected:
                dt,x=max(selected,key=lambda p:(p[0],p[1]["id"]))
                age=(as_of-dt).days
            else:
                dt,x,age=None,None,None
            rows.append({"currency":ccy,"pillar":pillar,"series_id":x["id"] if x else None,
              "latest_observed_on":dt.isoformat() if dt else None,
              "latest_observed_value":x["last_value"] if x else None,
              "unit":(x.get("unit") or "SOURCE_UNIT_NOT_DECLARED") if x else None,
              "candidate_series_count":len(candidates),"observation_age_days":age,
              "research_freshness":("OBSERVATION_WITHIN_60_DAYS" if age<=60 else
                  "STALE_OBSERVATION_GT_60_DAYS") if age is not None else "NO_VALID_DATED_VALUE",
              "release_timestamp_first_vintage_verified":False,
              "source_consensus_verified":False,"growth_or_inflation_macro_score":None,
              "note":"Latest observed date is not a first-release timestamp and may be revised"})
    return {"schema":"GMFQ_MACRO_V2_G8_GROWTH_INFLATION_DESK_INVENTORY_V1",
      "as_of":as_of.isoformat(),"status":"OBSERVED_SERIES_RESEARCH_ONLY_NOT_PIT",
      "rows":rows,"currencies":8,"pillars":16,
      "stale_slots_gt_60_days":sum(r["observation_age_days"] is not None and r["observation_age_days"]>60 for r in rows),
      "missing_valid_dated_value_slots":sum(r["observation_age_days"] is None for r in rows),
      "certified_first_release_slots":0,"observational_selection_method":
      "latest_date_among_currently_available_source_series_not_model_selection",
      "source_selection_validated_for_scoring":False,
      "economic_score_computed":False,"eligible_for_backtest":False,
      "safe_to_publish_new_D":False,"safe_to_update_pair_theses":False,
      "writes_live_data":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path);args=p.parse_args()
    data=json.loads((ROOT/"live_data/sections/MACRO_SERIES.json").read_text())
    result=inspect(data)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")),"research receipts only /tmp")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"pillars":result["pillars"],"stale":result["stale_slots_gt_60_days"],
        "certified":result["certified_first_release_slots"]}))
if __name__=="__main__":main()
