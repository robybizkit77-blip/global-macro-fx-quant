"""ABS complete monthly CPI headline and trimmed mean current-vintage context.
Never replace the frozen quarterly inflation input or first-release history.
"""
import argparse,copy,json,math,re,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from bs4 import BeautifulSoup
from validation.sources.aud_abs_core import CPI_LATEST_URL,fetch_text,parse_reference_period,text_from_html
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
CONFIG={"AU_CPI_HEADLINE_M_YOY_context_value":(1,"percent YoY"),"AU_CPI_TRIMMED_MEAN_M_YOY_context_value":(2,"percent YoY SA")}
MONTHS={m:i for i,m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),1)}
def need(ok,why):
    if not ok:raise ValueError(why)
def parse(raw,now):
    year,mo=parse_reference_period(text_from_html(raw));latest=f"{year:04d}-{mo:02d}"
    need(latest<now.strftime("%Y-%m"),"future or unclosed reference month")
    soup=BeautifulSoup(raw,"html.parser")
    tables=[]
    for table in soup.find_all("table"):
        rows=[[re.sub(r"\s+"," ",c.get_text(" ",strip=True)) for c in tr.find_all(["th","td"],recursive=False)] for tr in table.find_all("tr")]
        if any(len(r)==3 and r[1]=="All groups CPI (%)" and r[2]=="Trimmed mean (%)" for r in rows):
            tables.append(rows)
    need(len(tables)==1,"ABS annual headline/trimmed mean table not unique")
    observations={}
    for r in tables[0]:
        if len(r)!=3:continue
        match=re.fullmatch(r"([A-Za-z]{3})-(\d{2}|\d{4})",r[0])
        if not match:continue
        y=int(match[2]);y=y+2000 if y<100 else y
        m=f"{y:04d}-{MONTHS[match[1]]:02d}"
        if m<"2025-04":continue # pre-complete-monthly observations include quarterly values
        need(m<=latest and m not in observations,"future or duplicate ABS month")
        vals=[float(x) for x in r[1:]]
        need(all(math.isfinite(v) and -20<=v<=50 for v in vals),"invalid CPI rate")
        observations[m]=vals
    need(bool(observations) and max(observations)==latest,"table doesn't reach reference month")
    return observations,latest
def prepare(current,*,now,fetcher=fetch_text):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);receipts=[]
    try:
        raw=fetcher(CPI_LATEST_URL);obs,latest=parse(raw,now)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return out,{"status":"NO_CHANGE_OR_WITHHELD","series":[{"id":i,"status":"WITHHELD","reason":str(exc)} for i in CONFIG],"first_release_PIT_certified":False,"affects_fx_core":False}
    for ident,(column,unit) in CONFIG.items():
        try:
            hits=[r for r in out["AUD"] if r["id"]==ident];need(len(hits)==1,"unique context required");row=hits[0]
            need(row["frequency"]=="M" and row["unit"]==unit,"local context identity mismatch")
            ds0=row["dates"];vs0=row["values"];need(len(ds0)==len(vs0) and ds0[-1]==row["last_date"] and vs0[-1]==row["last_value"],"invalid local history")
            ds=sorted(d for d in obs if d>=ds0[0]);need(len(ds)>=12 and set(ds0)<=set(ds) and ds[-1]==latest,"history coverage regression")
            ord=lambda m:int(m[:4])*12+int(m[5:7])
            need(all(ord(b)-ord(a)==1 for a,b in zip(ds,ds[1:])),"monthly context has gaps")
            errs=[abs(obs[d][column-1]-v) for d,v in zip(ds0,vs0)]
            need(statistics.median(errs)<=.11 and max(errs)<=.51,"historical identity mismatch")
            vs=[obs[d][column-1] for d in ds];before=row["last_date"];key="ABS_COMPLETE_MONTHLY_CPI_HEADLINE_YOY" if column==1 else "ABS_COMPLETE_MONTHLY_TRIMMED_MEAN_YOY"
            changed=ds!=ds0 or vs!=vs0 or row.get("current_vintage_provenance",{}).get("source_series_id")!=key
            if changed:row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={"status":"ABS_CURRENT_REVISED_CONTEXT_NOT_PIT","source_url":CPI_LATEST_URL,"source_series_id":key,"source_html_sha256":sha256(raw.encode()).hexdigest(),"historical_overlap_exact":sum(e<1e-6 for e in errs),"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
            receipts.append({"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1]})
        except (OSError,ValueError,KeyError,TypeError) as exc:receipts.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_AUD_ABS_MONTHLY_CPI_CONTEXT_V1","status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","series":receipts,"first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
