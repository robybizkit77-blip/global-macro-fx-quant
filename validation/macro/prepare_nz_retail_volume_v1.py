"""Official Stats NZ quarterly real retail volume, revised research only."""
import argparse,copy,csv,io,json,math,re,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from zipfile import ZipFile,BadZipFile
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
ID="NZ_RETAIL_VOLUME_Q_history_value"
CODE="RTTQ.SF91KS"
CONFIG={ID:CODE}
META={"UNITS":"Dollars","Magnitude":"6","Subject":"Retail Trade (ANZSIC06) - RTT","Group":"Sales and stocks by industry, in current and constant prices (SAFC)","Series_title_1":"All industries total","Series_title_2":"Sales (operating income)","Series_title_3":"Deflated, at September 2010 quarter prices","Series_title_4":"Seasonally adjusted"}
def need(ok,why):
    if not ok:raise ValueError(why)
def archive_url(y,m):
    month={3:"March",6:"June",9:"September",12:"December"}[m]
    return f"https://www.stats.govt.nz/assets/Uploads/Retail-trade-survey/Retail-trade-survey-{month}-{y}-quarter/Download-data/retail-trade-survey-{month.lower()}-{y}-quarter.zip"
def fetch(url):
    req=Request(url,headers={"User-Agent":"GMFQ-official-research/1.0","Accept":"application/zip,application/octet-stream"})
    with urlopen(req,timeout=30) as res:
        final=res.geturl()
        need(res.status==200 and urlsplit(final).scheme=="https" and urlsplit(final).hostname in ("www.stats.govt.nz","stats.govt.nz"),"unexpected issuer endpoint")
        raw=res.read(5_000_001)
    need(0<len(raw)<=5_000_000 and raw.startswith(b"PK"),"invalid ZIP")
    return raw,final
def latest_archive(now,fetcher):
    q=now.year*4+(now.month-1)//3-1
    for i in range(3):
        y,k=divmod(q-i,4);m=(k+1)*3;url=archive_url(y,m)
        try:raw,final=fetcher(url)
        except HTTPError as e:
            if e.code==404:continue
            raise
        return raw,final,f"{y}-{m:02d}"
    raise ValueError("no recent official archive found")
def prepare_row(row,now,fetcher):
    need(row["id"]==ID and row["unit"]=="NZD million, deflated Sep 2010 quarter prices, SA" and row["frequency"]=="Q" and row["source_file"]=="NZ_RETAIL_VOLUME_Q_history.csv","canonical identity mismatch")
    ds=row["dates"];vs=row["values"]
    need(len(ds)==len(vs)>=24 and ds==sorted(set(ds)) and row["last_date"]==ds[-1] and row["last_value"]==vs[-1],"invalid canonical history")
    raw,url,period=latest_archive(now,fetcher);obs={}
    with ZipFile(io.BytesIO(raw)) as z:
        entries=[x for x in z.infolist() if not x.is_dir() and x.filename.lower().endswith(".csv")]
        need(entries and len(entries)<=30 and sum(x.file_size for x in entries)<=20_000_000,"unexpected archive")
        for ent in entries:
            reader=csv.DictReader(io.StringIO(z.read(ent).decode("utf-8-sig")))
            for r in reader:
                if r.get("Series_reference")!=CODE:continue
                need(all(r.get(k)==v for k,v in META.items()),"wrong Stats NZ metadata")
                m=re.fullmatch(r"(\d{4})[.-](03|06|09|12)",r["Period"]);need(m is not None,"invalid quarter")
                d=m[1]+"-"+m[2]
                if not r["Data_value"].strip():continue
                v=float(r["Data_value"]);need(d not in obs and d<=period and math.isfinite(v) and v>0,"duplicate, future or invalid observation")
                obs[d]=v
    old=dict(zip(ds,vs));need(set(old)<=set(obs) and max(obs)==period,"history or release coverage mismatch")
    err=[abs(obs[d]-v)/abs(v) for d,v in old.items()]
    need(statistics.median(err)<=.005 and max(err)<=.025,"full historical identity mismatch")
    if period=="2026-09" and now.strftime("%Y-%m")=="2026-11":need(abs(obs[period]-26488)<=.1,"release anchor mismatch")
    dates=sorted(d for d in obs if d>=ds[0]);need(dates[-1]>=ds[-1] and all((int(b[:4])-int(a[:4]))*12+int(b[5:])-int(a[5:])==3 for a,b in zip(dates,dates[1:])),"quarterly gap or regression")
    prior=row.get("current_vintage_provenance",{});need(not prior.get("source_series_id") or prior["source_series_id"]==CODE,"source changed")
    values=[obs[d] for d in dates];before=ds[-1];changed=ds!=dates or vs!=values or prior.get("source_series_id")!=CODE
    if changed:row.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1],current_vintage_provenance={"status":"STATSNZ_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":CODE,"source_metadata":META,"source_url":url,"source_zip_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"median_relative_revision":statistics.median(err),"max_relative_revision":max(err),"source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat()})
    return {"id":ID,"status":"READY" if changed else "NO_CHANGE","before":before,"after":dates[-1],"latest":values[-1],"source_series_id":CODE,"overlap":len(old)}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current)
    try:
        hits=[r for r in out["NZD"] if r["id"]==ID];need(len(hits)==1,"unique row required")
        row=copy.deepcopy(hits[0]);receipt=prepare_row(row,now,fetcher);hits[0].update(row)
    except (OSError,ValueError,KeyError,TypeError,BadZipFile) as exc:receipt={"id":ID,"status":"WITHHELD","reason":str(exc)}
    return out,{"schema":"GMFQ_NZ_RETAIL_VOLUME_V1","series":[receipt],"status":"READY" if receipt["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
