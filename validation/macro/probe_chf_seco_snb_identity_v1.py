"""Read-only Swiss official source identity diagnostics. Never writes canonical data."""
import csv,io,json,math,statistics
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from validation.macro.prepare_chf_snb_revised_v1 import fetch as snb_fetch
from validation.macro.collect_us_nz_household_firm_sources_v1 import fetch
ROOT=Path(__file__).resolve().parents[2]
rows={r["id"]:r for r in json.loads((ROOT/"live_data/sections/MACRO_SERIES.json").read_text())["CHF"]}
def compare(obs,old):
    if not set(old)<=set(obs):return None
    errors=[abs(obs[d]-v)/max(abs(v),1) for d,v in old.items()]
    return {"count":len(errors),"median_relative":statistics.median(errors),"max_relative":max(errors),"exact":sum(e<=1e-9 for e in errors),"last":max(obs),"latest":obs[max(obs)]}
def snb():
    cube="bakredinausbm"
    url="https://data.snb.ch/api/cube/"+cube+"/data/json/en?"+urlencode({"fromDate":"2019-10","toDate":"2026-11"})
    payload=json.loads(snb_fetch(url))
    for ident in ("CH_MORTGAGE_CREDIT_DOMESTIC_history_value","CH_BANK_CREDIT_CUSTOMERS_history_value"):
        row=rows[ident];old=dict(zip(row["dates"],row["values"]));hits=[]
        for ts in payload["timeseries"]:
            meta=ts["metadata"]
            if meta.get("frequency")!="P1M":continue
            obs={p["date"]:float(p["value"]) for p in ts["values"] if p.get("value") not in (None,"")}
            audit=compare(obs,old)
            if audit:hits.append({"metadata":meta,**audit})
        print("CHF_SNB_CANDIDATES",ident,json.dumps(sorted(hits,key=lambda x:x["median_relative"])[:5],sort_keys=True))
def seco():
    meta_url="https://scheduler.swissdatas.ch/scheduled/ch-seco-ks.json"
    csv_url="https://scheduler.swissdatas.ch/scheduled/ks-seco.csv"
    raw,final=fetch(meta_url)
    if urlsplit(final).hostname!="scheduler.swissdatas.ch":raise ValueError("unexpected metadata host")
    meta=json.loads(raw)
    print("CHF_SECO_META",json.dumps({"title":meta["title"],"dim_order":meta["dim_order"],"units":meta["units"],"quarter_label":meta["labels"]["structure"]["ks_i63_index_q"],"adjustment":meta["labels"]["seas_adj"]}))
    raw,final=fetch(csv_url)
    if urlsplit(final).hostname!="scheduler.swissdatas.ch":raise ValueError("unexpected CSV host")
    content=raw.decode("utf-8-sig")
    dialect=csv.Sniffer().sniff(content[:4096],delimiters=",;\t")
    reader=csv.DictReader(io.StringIO(content),dialect=dialect)
    print("CHF_SECO_CSV_HEADER",reader.fieldnames)
    rows_csv=list(reader)
    matches=[r for r in rows_csv if "ks_i63_index_q" in r.values() or "ks_i63_index_m" in r.values()]
    print("CHF_SECO_CSV_EXAMPLES",json.dumps(matches[:8]+matches[-8:],ensure_ascii=False))
    target=rows["CH_SECO_CONSUMER_SENTIMENT_LEAD_history_SECO_Consumer_Sentiment"]
    segments=[[]]
    for d,v in zip(target["dates"],target["values"]):
        if segments[-1] and d<=segments[-1][-1][0]:segments.append([])
        segments[-1].append((d,v))
    print("CHF_SECO_LEGACY_SEGMENTS",json.dumps([{"count":len(s),"first":s[0],"last":s[-1]} for s in segments]))
if __name__=="__main__":
    failed=[]
    for fn in (snb,seco):
        try:fn()
        except Exception as exc:
            print("CHF_PROBE_FAILED",fn.__name__,repr(exc));failed.append(fn.__name__)
    if failed:raise SystemExit("Incomplete diagnostics: "+str(failed))
