"""Read-only SNB daily nominal effective overall index full overlap diagnostic."""
import json,math,statistics
from datetime import datetime,timezone
from urllib.parse import urlencode
from validation.macro.prepare_chf_snb_revised_v1 import SOURCE,fetch,need
CUBE="devwkieffid"
BASE="https://data.snb.ch/api/cube/"+CUBE
def main():
    rows=[x for x in json.loads(SOURCE.read_text())["CHF"] if x["id"]=="CH_NEER_NOMINAL_OVERALL_history_value"]
    need(len(rows)==1,"unique legacy series")
    row=rows[0];need(row["unit"]=="Index, Dec 2000=100" and row["frequency"]=="D","legacy metadata mismatch")
    old=dict(zip(row["dates"],row["values"]));need(len(old)==len(row["dates"])>=36,"duplicate or short legacy history")
    now=datetime.now(timezone.utc).date().isoformat()
    dims=json.loads(fetch(BASE+"/dimensions/en"));print("CHF_NEER_DIMENSIONS",json.dumps(dims))
    raw=fetch(BASE+"/data/json/en?"+urlencode({"fromDate":min(old),"toDate":now}))
    payload=json.loads(raw);results=[]
    for x in payload["timeseries"]:
        meta=x["metadata"];obs={}
        for p in x["values"]:
            d=p["date"];v=p.get("value")
            if v in (None,""):continue
            v=float(v);need(math.isfinite(v) and d<=now and d not in obs,"invalid daily observation")
            obs[d]=v
        if not set(old)<=set(obs):continue
        errors=[abs(obs[d]-v) for d,v in old.items()]
        results.append({"meta":meta,"overlap":len(old),"exact_4dp":sum(round(obs[d],4)==round(v,4) for d,v in old.items()),"median_abs":statistics.median(errors),"max_abs":max(errors),"latest_date":max(obs),"latest":obs[max(obs)],"new_count":sum(d>max(old) for d in obs)})
    print("CHF_NEER_OVERLAP",json.dumps(sorted(results,key=lambda x:x["median_abs"])[:12],sort_keys=True))
    need(bool(results),"no full-overlap source")
if __name__=="__main__":main()
