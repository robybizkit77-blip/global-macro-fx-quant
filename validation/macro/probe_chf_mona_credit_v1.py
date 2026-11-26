"""Read-only SNB monthly bank-balance-sheet credit identity discovery."""
import json,math,statistics
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
BASE="https://data.snb.ch/api/warehouse/cube/"
CUBES={"CH_MORTGAGE_CREDIT_DOMESTIC_history_value":"BSTA.SNB.MONA_B.BIL.AKT.HYP","CH_BANK_CREDIT_CUSTOMERS_history_value":"BSTA.SNB.MONA_B.BIL.AKT.FKU"}
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ official source audit","Accept":"application/json"}),timeout=45) as r:
        raw=r.read(30_000_001)
    assert 0<len(raw)<=30_000_000
    return json.loads(raw)
def main():
    doc=json.loads(Path("live_data/sections/MACRO_SERIES.json").read_text())
    for ident,cube in CUBES.items():
        row=next(r for r in doc["CHF"] if r["id"]==ident)
        old=dict(zip(row["dates"],row["values"]))
        assert len(old)==len(row["dates"])==len(row["values"])
        dimensions=fetch(BASE+cube+"/dimensions/en")
        print("MONA_DIMENSIONS",ident,json.dumps(dimensions,ensure_ascii=False)[:30000])
        dims={x["id"]:{i["id"] for i in x["dimensionItems"]} for x in dimensions["dimensions"]}
        selections={"KONSOLIDIERUNGSSTUFE":"B","INLANDAUSLAND":"I,T","WAEHRUNG":"T,CHF","FAELLIGKEIT":"T","BANKENGRUPPE":"A40"}
        if "DECKUNG" in dims:selections.update(DECKUNG="T",SEKTORDECKUNG="T")
        assert all(set(v.split(","))<=dims[k] for k,v in selections.items())
        dimsel=",".join(k+"("+v+")" for k,v in selections.items())
        data=fetch(BASE+cube+"/data/json/en?"+urlencode({"dimSel":dimsel,"fromDate":min(old),"toDate":"2026-11"}))
        print("MONA_STRUCTURE",ident,list(data),len(data.get("timeseries",[])))
        candidates=[]
        for s in data.get("timeseries",[]):
            obs={p["date"]:float(p["value"]) for p in s["values"] if p.get("value") not in (None,"")}
            if not set(old)<=set(obs):continue
            if not all(math.isfinite(obs[d]) for d in old):continue
            for factor in (1,0.001,1000):
                err=[abs(obs[d]*factor-v)/max(abs(v),1) for d,v in old.items()]
                candidates.append({"metadata":s["metadata"],"factor":factor,"overlap":len(err),"median_relative":statistics.median(err),"max_relative":max(err),"new":{d:v*factor for d,v in obs.items() if max(old)<d<"2026-11"}})
        candidates.sort(key=lambda x:(x["median_relative"],x["max_relative"]))
        print("MONA_CANDIDATES",ident,json.dumps(candidates[:10],ensure_ascii=False))
    print("DIAGNOSTIC_ONLY_NO_CANONICAL_WRITES")
if __name__=="__main__":main()
