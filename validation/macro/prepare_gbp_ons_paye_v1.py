"""ONS PAYE RTI current revised monthly history; flash kept separately in provenance."""
import argparse,copy,csv,io,json,math,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urljoin,urlsplit,parse_qs
from bs4 import BeautifulSoup
from validation.macro.probe_gbp_paye_rti_v1 import PAGE,fetch,month,need,SOURCE
CONFIG={"UK_PAYE_PAYROLLED_EMPLOYEES_SA_history_value":"ONS_PAYE_RTI_UK_SA_FIGURE1"}
def discover(fetcher):
    raw,final=fetcher(PAGE);soup=BeautifulSoup(raw,"html.parser")
    heads=[h for h in soup.find_all("h3") if h.get_text(" ",strip=True).casefold().startswith("figure 1:") and "payrolled employees" in h.get_text(" ",strip=True).casefold()]
    need(len(heads)==1,"unique PAYE figure missing")
    sub=heads[0].find_next("h4").get_text(" ",strip=True).casefold()
    need(sub.startswith("payrolled employees, seasonally adjusted, uk,"),"wrong scope or adjustment")
    links=set()
    for el in heads[0].next_elements:
        if getattr(el,"name",None) in ("h2","h3"):break
        if getattr(el,"name",None)=="a" and el.get("href"):
            u=urljoin(final,el["href"]);p=urlsplit(u);q=parse_qs(p.query)
            if p.scheme=="https" and p.hostname=="www.ons.gov.uk" and p.path=="/generator" and q.get("format")==["csv"]:links.add(u)
    # The chart download can appear after the notes subheading; only h2/h3 end the figure.
    need(len(links)==1,"ambiguous or missing official chart CSV")
    return fetcher(links.pop())
def parse(raw,now):
    data=list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    need(data[1][0].casefold().startswith("payrolled employees, seasonally adjusted, uk,"),"wrong CSV scope")
    need(any(r[:2]==["Unit","Payrolled employees"] for r in data[:12]),"wrong CSV unit")
    headers=[i for i,r in enumerate(data[:15]) if r==["Date","Payrolled employees","Flash estimate"]]
    need(len(headers)==1,"unexpected chart schema")
    obs={};flash={}
    for r in data[headers[0]+1:]:
        if not r or not any(r):continue
        d=month(r[0]);need(d is not None and d<=now.strftime("%Y-%m") and len(r)==3,"invalid observation period")
        for raw_value,target in zip(r[1:],(obs,flash)):
            if not raw_value.strip():continue
            v=float(raw_value.replace(",",""));need(math.isfinite(v) and v.is_integer() and 15_000_000<v<45_000_000 and d not in target,"invalid or repeated employee count")
            target[d]=int(v)
    need(obs and flash,"missing regular or flash series")
    need(all(obs[d]==flash[d] for d in set(obs)&set(flash)),"flash plotting anchor inconsistent")
    future={d:v for d,v in flash.items() if d>max(obs)}
    need(len(future)==1,"expected single preliminary observation")
    d,v=next(iter(future.items()));ordinal=lambda x:int(x[:4])*12+int(x[5:7])
    need(ordinal(d)-ordinal(max(obs))==1,"flash not next month")
    return obs,{"period":d,"value":v,"status":"PROVISIONAL_FLASH_NOT_CANONICAL"}
def prepare_row(row,now,raw,url):
    ident=next(iter(CONFIG))
    need(row["id"]==ident and row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]=="persons" and row["frequency"]=="M","wrong local identity")
    need(len(row["dates"])==len(row["values"])>=36 and row["last_date"]==row["dates"][-1] and row["last_value"]==row["values"][-1],"inconsistent local history")
    old={month(d):float(v) for d,v in zip(row["dates"],row["values"])}
    need(None not in old and len(old)==len(row["dates"]),"invalid legacy dates")
    obs,flash=parse(raw,now);ds=sorted(d for d in obs if d>=min(old))
    need(set(old)<=set(ds) and ds[-1]>=max(old),"regular history regression")
    ordinal=lambda d:int(d[:4])*12+int(d[5:7])
    need(all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])),"monthly gap")
    errors=[abs(obs[d]-v) for d,v in old.items()]
    # Observed official November vintage: median 494, maximum 34,674 persons.
    need(statistics.median(errors)<=5000 and max(errors)<=50000,"historical revisions exceed guard")
    vs=[obs[d] for d in ds];prior=row.get("current_vintage_provenance",{});code=CONFIG[ident]
    need(not prior.get("source_series_id") or prior["source_series_id"]==code,"certified identity changed")
    changed=ds!=row["dates"] or vs!=row["values"] or prior.get("latest_preliminary_observation")!=flash or prior.get("source_series_id")!=code
    if changed:row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={"status":"ONS_PAYE_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_url":url,"source_csv_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"median_abs_revision":statistics.median(errors),"max_abs_revision":max(errors),"latest_preliminary_observation":flash,"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":max(old),"after":ds[-1],"latest":vs[-1],"flash":flash}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);ident=next(iter(CONFIG))
    try:
        hits=[r for r in out["GBP"] if r["id"]==ident];need(len(hits)==1,"unique row required")
        raw,url=discover(fetcher);row=copy.deepcopy(hits[0]);receipt=prepare_row(row,now,raw,url);hits[0].update(row)
    except (OSError,ValueError,KeyError,TypeError,IndexError,AttributeError) as e:receipt={"id":ident,"status":"WITHHELD","reason":str(e)}
    return out,{"schema":"GMFQ_GBP_ONS_PAYE_REVISED_V1","series":[receipt],"status":"READY" if receipt["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
