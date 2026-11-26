"""Read-only SNB source identity for central-bank balance sheet, 20Y spot and mortgage pricing."""
import json,statistics,math
from datetime import datetime,timezone
from urllib.parse import urlencode
from validation.macro.prepare_chf_snb_revised_v1 import SOURCE,fetch,need
CUBES={
 "snbbipo":["CH_SNB_TOTAL_ASSETS_history_value","CH_SNB_SIGHT_DEPOSITS_DOMESTIC_BANKS_history_value"],
 "rendeiduebd":["CH_CONFED_SPOT_20Y_history_CH_CONFED_SPOT_20Y"],
 "zikrepro":["CH_MORTGAGE_RATE_FIXED_3_5Y_history_value"],
 "zikredlauf":["CH_MORTGAGE_RATE_FIXED_3_5Y_history_value"],
}
def main():
    doc=json.loads(SOURCE.read_text());rows={r["id"]:r for r in doc["CHF"]};now=datetime.now(timezone.utc)
    failed=[]
    for cube,ids in CUBES.items():
        try:
            base="https://data.snb.ch/api/cube/"+cube
            dims=json.loads(fetch(base+"/dimensions/en"))
            print("SNB_DIMENSIONS",cube,json.dumps(dims,ensure_ascii=False))
            # Daily bond cube can have hundreds of columns; request dates only for existing legacy window.
            first=min(rows[i]["dates"][0][:10] for i in ids)
            end=now.date().isoformat() if len(first)==10 else now.strftime("%Y-%m")
            data=json.loads(fetch(base+"/data/json/en?"+urlencode({"fromDate":first,"toDate":end})))
            for ident in ids:
                row=rows[ident];old=dict(zip(row["dates"],row["values"]));need(len(old)==len(row["dates"])>=36,"duplicate or short legacy history")
                hits=[]
                for ts in data["timeseries"]:
                    meta=ts["metadata"];obs={}
                    for p in ts["values"]:
                        d=p["date"];v=p.get("value")
                        if v in (None,""):continue
                        v=float(v)
                        if not math.isfinite(v) or d in obs or d>end:continue
                        obs[d]=v
                    if not set(old)<=set(obs):continue
                    for scale in ([1,.001] if row["unit"]=="CHF millions" else [1]):
                        errors=[abs(obs[d]*scale-v) for d,v in old.items()]
                        relative=[e/max(abs(v),1) for e,v in zip(errors,old.values())]
                        hits.append({"meta":meta,"scale":scale,"overlap":len(old),"exact":sum(e<=1e-7 for e in errors),"median_abs":statistics.median(errors),"max_abs":max(errors),"median_relative":statistics.median(relative),"max_relative":max(relative),"latest_date":max(obs),"latest":obs[max(obs)]*scale})
                print("SNB_CANDIDATES",cube,ident,json.dumps(sorted(hits,key=lambda x:x["median_relative"])[:6],sort_keys=True))
        except (OSError,ValueError,KeyError,TypeError,RuntimeError) as e:
            failed.append(cube);print("SNB_PROBE_WITHHELD",cube,repr(e))
    if failed:raise SystemExit("Unresolved cubes: "+str(failed))
if __name__=="__main__":main()
