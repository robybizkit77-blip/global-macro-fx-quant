"""BIS Japan broad nominal effective exchange rate, FRED revised research only."""
import argparse,copy,csv,io,json,math,re
from datetime import datetime,timezone,date
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from bs4 import BeautifulSoup
from validation.macro.collect_us_nz_household_firm_sources_v1 import fetch
from validation.macro.prepare_us_quarterly_cfna_revised_v1 import need,norm
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
ID="JP_YEN_BROAD_NEER_history_value"
CODE="NBJPBIS"
CONFIG={ID:CODE}
def prepare_row(row,now,fetcher):
    need(row["id"]==ID and row["unit"]=="Index 2020=100" and row["frequency"]=="M" and row["source_file"]=="JP_YEN_BROAD_NEER_history.csv","canonical identity mismatch")
    ds=row["dates"];vs=row["values"]
    need(len(ds)==len(vs)>=24 and ds==sorted(set(ds)) and row["last_date"]==ds[-1] and row["last_value"]==vs[-1] and all(re.fullmatch(r"\d{4}-\d{2}",d) for d in ds),"bad canonical history")
    old=dict(zip(ds,vs))
    meta_url="https://fred.stlouisfed.org/series/"+CODE
    meta,final=fetcher(meta_url)
    need(urlsplit(final).hostname=="fred.stlouisfed.org" and urlsplit(final).path.rstrip("/")=="/series/"+CODE,"wrong metadata endpoint")
    soup=BeautifulSoup(meta,"html.parser")
    heading=norm(soup.title.get_text(" ",strip=True) if soup.title else "")
    txt=norm(soup.get_text(" ",strip=True))
    need("broad effective exchange rate for japan" in heading and CODE.casefold() in heading and "bank for international settlements" in txt,"wrong BIS series")
    units=re.search(r"units:\s*(.*?)\s*frequency:",txt)
    need(units and "index 2020=100" in units.group(1).replace(" = ","=") and "not seasonally adjusted" in units.group(1) and re.search(r"frequency:\s*monthly\b",txt),"wrong index metadata")
    url="https://fred.stlouisfed.org/graph/fredgraph.csv?"+urlencode({"id":CODE,"cosd":ds[0]+"-01"})
    raw,final=fetcher(url)
    need(urlsplit(final).hostname=="fred.stlouisfed.org" and urlsplit(final).path=="/graph/fredgraph.csv","wrong CSV endpoint")
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    need(reader.fieldnames in (["observation_date",CODE],["DATE",CODE]),"wrong CSV identity")
    obs={};seen=set()
    for x in reader:
        d=date.fromisoformat(x[reader.fieldnames[0]]);k=d.strftime("%Y-%m")
        need(d.day==1 and k not in seen,"duplicate or invalid date");seen.add(k)
        if x[CODE] in ("","."):continue
        v=float(x[CODE])
        need(k<now.strftime("%Y-%m") and math.isfinite(v) and 0<v<300,"future/unclosed month or invalid index")
        if k>=ds[0]:obs[k]=v
    dates=sorted(obs)
    need(set(old)<=set(obs) and dates and dates[-1]>=ds[-1],"history regression")
    need(all((int(b[:4])-int(a[:4]))*12+int(b[5:])-int(a[5:])==1 for a,b in zip(dates,dates[1:])),"monthly gap")
    errors=[abs(obs[d]-v) for d,v in old.items()]
    need(all(e<=.011 for e in errors),"full history mismatch beyond rounding")
    previous=row.get("current_vintage_provenance",{})
    need(not previous.get("source_series_id") or previous["source_series_id"]==CODE,"source changed")
    values=[obs[d] for d in dates];before=ds[-1]
    changed=dates!=ds or values!=vs or previous.get("source_series_id")!=CODE
    if changed:row.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1],current_vintage_provenance={"status":"FRED_BIS_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":CODE,"source_url":meta_url,"source_csv_url":url,"source_csv_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"max_absolute_revision":max(errors),"source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat()})
    return {"id":ID,"status":"READY" if changed else "NO_CHANGE","before":before,"after":dates[-1],"latest":values[-1],"source_series_id":CODE,"overlap":len(old)}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current)
    try:
        hits=[x for x in out["JPY"] if x["id"]==ID];need(len(hits)==1,"unique source required")
        row=copy.deepcopy(hits[0]);r=prepare_row(row,now,fetcher);hits[0].update(row)
    except (OSError,ValueError,KeyError,TypeError) as exc:r={"id":ID,"status":"WITHHELD","reason":str(exc)}
    return out,{"schema":"GMFQ_JPY_BIS_NEER_V1","series":[r],"status":"READY" if r["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
