"""Read-only RBA F11 monthly TWI identity proof; no canonical writes."""
import csv,io,json,math,statistics
from datetime import datetime,timezone
from validation.macro.prepare_aud_rba_stocks_revised_v1 import SOURCE,fetch,parse_date,need
URL="https://www.rba.gov.au/statistics/tables/csv/f11-data.csv"
def main():
    key="AU_AUD_TWI_history_value"
    rows=[r for r in json.loads(SOURCE.read_text())["AUD"] if r["id"]==key]
    need(len(rows)==1,"unique legacy row")
    row=rows[0];need(row["frequency"]=="M" and row["unit"]=="Index","legacy identity")
    old={parse_date(d):float(v) for d,v in zip(row["dates"],row["values"])}
    need(None not in old and len(old)==len(row["dates"])>=36,"invalid legacy dates")
    raw=fetch(URL);data=list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    meta={r[0].strip().casefold():r for r in data[:30] if r and r[0].strip().casefold() in ("title","description","units","frequency","series id")}
    ids=meta["series id"];cols=[i for i,s in enumerate(ids) if s.strip().upper()=="FXRTWI"]
    need(len(cols)==1,"expected FXRTWI")
    i=cols[0];details={k:v[i] for k,v in meta.items() if len(v)>i}
    print("AUD_TWI_METADATA",json.dumps(details))
    need(details["frequency"].strip().casefold()=="monthly","not monthly")
    need("trade" in (details.get("title","")+" "+details.get("description","")).casefold(),"not trade-weighted")
    now=datetime.now(timezone.utc);obs={}
    for r in data:
        if len(r)<=i:continue
        d=parse_date(r[0].strip())
        if d is None or r[i].strip() in ("","..","-","NA"):continue
        v=float(r[i]);need(math.isfinite(v) and v>0 and d.strftime("%Y-%m")<now.strftime("%Y-%m") and d not in obs,"invalid observation")
        obs[d]=v
    need(set(old)<=set(obs),"missing historic periods")
    err=[abs(obs[d]-v) for d,v in old.items()]
    print("AUD_TWI_OVERLAP",json.dumps({"count":len(old),"exact":sum(e<=1e-6 for e in err),"median_abs":statistics.median(err),"max_abs":max(err),"new":{d.isoformat():obs[d] for d in sorted(obs) if d>max(old)}}))
if __name__=="__main__":main()
