"""Official FSO seasonally adjusted monthly production and real retail, revised research only."""
import argparse, copy, io, json, math, re, statistics
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,urlopen
from openpyxl import load_workbook
from validation.macro.probe_chf_fso_growth_history_v1 import month, BASE
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
CONFIG={
 "CH_PRODUCTION_history_value":(37030901,"Monthly industrial development - seasonally adjusted","je-e-06.03.01.02.01-01","FSO_INDPAU_BE_SA_2021",.20,2.0),
 "CH_RETAIL_REAL_history_value":(36875605,"Indices and variation rates of turnover in retail sector (seasonally adjusted)","je-e-06.03.02.01.01","FSO_DHU_47_REAL_SA_2021",.15,.8),
}
def need(ok,msg):
    if not ok: raise ValueError(msg)
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ official macro research"}),timeout=45) as r:
        need(urlsplit(r.geturl()).hostname==urlsplit(url).hostname,"unexpected source host")
        raw=r.read(10_000_001)
    need(0<len(raw)<=10_000_000,"source size")
    return raw
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.active=None;self.words=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a": self.active=[dict(attrs).get("href",""),[]]
    def handle_data(self,data):
        self.words.append(data)
        if self.active is not None:self.active[1].append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.active is not None:
            self.links.append((self.active[0]," ".join(" ".join(self.active[1]).split())));self.active=None
def discover(seed,title,code,fetcher):
    visited=set();asset=seed
    for _ in range(24):
        need(asset not in visited,"cyclic FSO edition links");visited.add(asset)
        url=f"https://statistik.admin.ch/en/asset/{asset}"
        parser=Page();parser.feed(fetcher(url).decode("utf-8"))
        words=" ".join(" ".join(parser.words).split())
        need(title in words and code in words,"FSO page identity mismatch")
        newer=set()
        for href,label in parser.links:
            dest=urlsplit(urljoin(url,href))
            m=re.fullmatch(r"/en/asset/(\d+)/?",dest.path)
            if dest.hostname=="statistik.admin.ch" and m and label==title and int(m[1])!=asset:
                newer.add(int(m[1]))
        if "available in a newer version" in words:
            need(len(newer)==1,"newer FSO edition link ambiguous");asset=newer.pop();continue
        need(not newer,"unexpected same-title FSO link")
        return asset,url
    raise ValueError("FSO edition traversal limit")
def parse(ident,raw,now):
    book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    try:
        rows=list(book["Indices"].iter_rows(values_only=True))
        if ident=="CH_PRODUCTION_history_value":
            need(rows[0][0]=="Monthly indices industry (seasonally adjusted)" and rows[1][0]=="Annual average 2021 = 100","wrong industrial basis")
            axis=rows[2];line=rows[4]
            need(tuple(line[:3])==("B-E","5-39","Production total (economic activities)"),"wrong industrial scope")
        else:
            need(rows[0][0]=="Indices and variation rates of turnover in retail sector (seasonally adjusted)","wrong retail adjustment")
            axis=rows[26];line=rows[30]
            need("real turnover" in str(axis[0]).lower() and "2021=100" in str(axis[0]).replace(" ","") and line[1]=="47: Total retail sector","wrong retail definition")
        obs={}
        for d,v in zip(axis,line):
            p=month(d)
            if p is None or v is None or v in ("...","*"):continue
            need(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and 0<v<400,"invalid index")
            need(p not in obs and p<now.strftime("%Y-%m"),"duplicate/future period");obs[p]=float(v)
        return obs
    finally:book.close()
def reconcile(row,obs,now,asset,url,raw):
    ident=row["id"];_,_,_,code,median_limit,max_limit=CONFIG[ident]
    need(row["unit"]=="Index 2021=100" and row["frequency"]=="M" and row["source_file"]==ident.removesuffix("_value")+".csv","canonical identity mismatch")
    ds=row["dates"];vs=row["values"];old=dict(zip(ds,vs))
    need(len(old)==len(ds)==len(vs)>=36 and ds==sorted(ds) and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid legacy history")
    need(set(old)<=set(obs),"history coverage regression")
    dates=sorted(d for d in obs if d>=ds[0])
    ordinal=lambda d:int(d[:4])*12+int(d[5:7])
    need(all(ordinal(b)-ordinal(a)==1 for a,b in zip(dates,dates[1:])) and dates[-1]>=ds[-1],"monthly gap or stale source")
    err=[abs(obs[d]-old[d]) for d in old]
    need(statistics.median(err)<=median_limit and max(err)<=max_limit,"historical revision exceeds reviewed limit")
    prior=row.get("current_vintage_provenance",{})
    need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source identity changed")
    values=[obs[d] for d in dates];changed=ds!=dates or vs!=values or prior.get("source_series_id")!=code
    if changed:row.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1],current_vintage_provenance={"status":"FSO_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_url":url,"source_asset_id":asset,"source_workbook_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"median_absolute_revision":statistics.median(err),"max_absolute_revision":max(err),"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":ds[-1],"after":dates[-1],"latest":values[-1],"overlap":len(old),"median_abs":statistics.median(err),"max_abs":max(err),"asset":asset}
def prepare(current,*,now,fetcher=fetch):
    out=copy.deepcopy(current);receipts=[]
    for ident,(seed,title,code,*_) in CONFIG.items():
        try:
            hits=[x for x in out["CHF"] if x["id"]==ident];need(len(hits)==1,"unique row required")
            asset,url=discover(seed,title,code,fetcher)
            raw=fetcher(BASE.format(asset));row=copy.deepcopy(hits[0])
            receipt=reconcile(row,parse(ident,raw,now),now,asset,url,raw);hits[0].update(row)
        except (OSError,ValueError,KeyError,TypeError,IndexError) as e:receipt={"id":ident,"status":"WITHHELD","reason":str(e)}
        receipts.append(receipt)
    return out,{"schema":"GMFQ_CHF_FSO_GROWTH_V1","series":receipts,"status":"READY" if any(x["status"]=="READY" for x in receipts) else "NO_CHANGE_OR_WITHHELD","affects_fx_core":False,"first_release_PIT_certified":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
