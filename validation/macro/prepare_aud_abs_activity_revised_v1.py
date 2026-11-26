"""Australian monthly activity: exact official workbook series, revised context only."""
import argparse,copy,io,json,math,re,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urljoin,urlparse
from bs4 import BeautifulSoup
from openpyxl import load_workbook
from validation.sources.aud_abs_core import fetch_bytes,fetch_text,parse_reference_period,text_from_html,LABOUR_LATEST_URL
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
CONFIG={
 "AU_HOUSEHOLD_SPENDING_history_value":("https://www.abs.gov.au/statistics/economy/finance/monthly-household-spending-indicator/latest-release","Table 1: Estimates of Household Spending, Australia","AUD million SA current price","spending"),
 "AU_EMPLOYMENT_history_value":(LABOUR_LATEST_URL,"Table 001. Labour force status by Sex, Australia - Trend, Seasonally adjusted and Original","thousand persons SA","employment"),
}
def need(ok,why):
    if not ok:raise ValueError(why)
def locate(html,url,heading):
    soup=BeautifulSoup(html,"html.parser")
    hits=[h for h in soup.find_all(["h3","h4","h5"]) if " ".join(h.stripped_strings)==heading]
    need(len(hits)==1,"ABS table heading not unique")
    links=[]
    for node in hits[0].next_elements:
        if getattr(node,"name",None) in ("h2","h3","h4","h5"):break
        if getattr(node,"name",None)=="a" and (node.get("href") or "").lower().split("?")[0].endswith(".xlsx"):
            link=urljoin(url,node["href"])
            if link not in links:links.append(link)
    need(len(links)==1 and urlparse(links[0]).scheme=="https" and urlparse(links[0]).hostname=="www.abs.gov.au","ABS workbook link not unique/official")
    return links[0]
def text(x):return str(x or "").strip()
def parse_book(raw,kind,old,latest):
    book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    candidates=[];diagnostics=[]
    try:
        for sheet in book:
            if not sheet.title.lower().startswith("data"):continue
            rows=list(sheet.iter_rows(values_only=True))
            first=next((i for i,r in enumerate(rows) if r and isinstance(r[0],datetime)),None)
            if first is None or not 3<=first<=30:continue
            meta=rows[:first]
            for c in range(1,max(len(r) for r in meta)):
                fields=[(text(r[0]),text(r[c]) if c<len(r) else "") for r in meta]
                title=fields[0][1];combined=" ".join(v for _,v in fields).lower()
                unit=next((v.lower() for k,v in fields if k.lower() in ("unit","units")), "")
                ident=next((v for k,v in fields if k.lower()=="series id"),"")
                if not ident or "seasonally adjusted" not in combined:continue
                if kind=="employment":
                    if not re.search(r"\bemploy(?:ed|ment)\b",title,re.I) or not re.search(r"\bpersons\b",title,re.I) or unit not in ("'000","000","thousand","thousands","'000 persons"):continue
                    if re.search(r"unemploy|underemploy|part.time|full.time|rate|ratio|change|percentage",title,re.I):continue
                else:
                    if not re.search(r"household spending|total spending|total",title,re.I) or not ("million" in unit or unit=="$m"):continue
                    if re.search(r"chain volume|percentage|change|index|quarter",title+" "+unit,re.I):continue
                obs={}
                for rr in rows[first:]:
                    if not rr or not isinstance(rr[0],datetime) or c>=len(rr) or rr[c] is None:continue
                    d=rr[0].strftime("%Y-%m");v=rr[c]
                    if d<min(old):continue
                    if d>latest or d in obs or type(v) not in (int,float) or not math.isfinite(v) or v<=0:obs={};break
                    obs[d]=float(v)
                if not obs or not set(old)<=set(obs) or max(obs)!=latest:continue
                errors=[abs(obs[d]-v)/max(abs(v),1) for d,v in old.items()]
                med=statistics.median(errors);mx=max(errors)
                diagnostics.append((ident,title,unit,med,mx))
                if med<=.005 and mx<=.025:candidates.append((ident,title,unit,obs,med,mx))
    finally:book.close()
    need(len(candidates)==1,"ABS exact history column not uniquely identified: "+str(diagnostics[:20]))
    ident,title,unit,obs,med,mx=candidates[0]
    ds=sorted(obs);ord=lambda m:int(m[:4])*12+int(m[5:7])
    need(all(ord(b)-ord(a)==1 for a,b in zip(ds,ds[1:])),"monthly source gap")
    return ident,title,unit,ds,[obs[d] for d in ds],med,mx
def prepare(current,*,now,html_fetch=fetch_text,book_fetch=fetch_bytes):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);receipts=[]
    for ident,(url,heading,unit,kind) in CONFIG.items():
        try:
            hits=[r for r in out["AUD"] if r["id"]==ident];need(len(hits)==1,"unique local row required");row=hits[0]
            need(row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]==unit and row["frequency"]=="M","local identity mismatch")
            ds0=row["dates"];vs0=row["values"];need(len(ds0)==len(vs0) and ds0[-1]==row["last_date"] and vs0[-1]==row["last_value"],"local terminal mismatch")
            old=dict(zip(ds0,vs0));html=html_fetch(url);y,m=parse_reference_period(text_from_html(html));latest=f"{y:04d}-{m:02d}"
            need(latest<now.strftime("%Y-%m") and latest>=max(old),"unclosed or regressed source month")
            link=locate(html,url,heading);raw=book_fetch(link);need(0<len(raw)<=10_000_000,"unexpected workbook size")
            sid,title,srcunit,ds,vs,med,mx=parse_book(raw,kind,old,latest)
            prior=row.get("current_vintage_provenance",{}).get("source_series_id")
            need(prior in (None,sid),"official series id changed")
            before=row["last_date"];changed=ds!=ds0 or vs!=vs0 or prior!=sid
            if changed:row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={"status":"ABS_CURRENT_REVISED_HISTORY_NOT_PIT","source_url":link,"source_series_id":sid,"source_title":title,"source_unit":srcunit,"source_xlsx_sha256":sha256(raw).hexdigest(),"median_overlap_relative_error":med,"max_overlap_relative_error":mx,"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
            receipts.append({"id":ident,"source_series_id":sid,"source_title":title,"source_unit":srcunit,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1],"median_error":med,"max_error":mx})
        except (OSError,ValueError,KeyError,TypeError) as exc:receipts.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_AUD_ABS_ACTIVITY_REVISED_V1","status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","series":receipts,"first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
