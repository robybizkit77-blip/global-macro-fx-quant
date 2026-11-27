"""Official ABS WPI all-sector annual SA change; revised history, not PIT."""
import argparse, calendar, copy, json, math, re, statistics
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from bs4 import BeautifulSoup
from validation.sources.aud_abs_core import fetch_text
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
URL="https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/wage-price-index-australia/latest-release"
ID="AU_WPI_YOY_history_value"
CONFIG={ID:"ABS_WPI_ALL_SECTORS_ANNUAL_SA"}
TITLE="All sector WPI, quarterly and annual movement (%), seasonally adjusted"
MONTHS={"Mar":3,"Jun":6,"Sep":9,"Dec":12}
def need(ok,msg):
    if not ok: raise ValueError(msg)
def parse(html,now):
    soup=BeautifulSoup(html,"html.parser")
    page=" ".join(soup.stripped_strings)
    match=re.search(r"Reference period\s+(March|June|September|December)\s+(20\d{2})",page,re.I)
    need(match is not None,"reference quarter missing")
    month={"march":3,"june":6,"september":9,"december":12}[match[1].lower()]
    year=int(match[2]); latest=f"{year:04d}-{month:02d}"
    need(latest<now.strftime("%Y-%m"),"unclosed or future quarter")
    candidates=[]
    for table in soup.find_all("table"):
        rows=[[c.get_text(" ",strip=True) for c in tr.find_all(["th","td"],recursive=False)] for tr in table.find_all("tr")]
        if not rows or rows[0][-2:]!=["Quarterly (%)","Annual (%)"]: continue
        context=table.get_text(" ",strip=True)
        for parent in list(table.parents)[:5]:
            if len(parent.find_all("table"))!=1: break
            context+=" "+parent.get_text(" ",strip=True)
        if TITLE.casefold() not in context.casefold(): continue
        obs={}
        for cells in rows[1:]:
            need(len(cells)==3,"unexpected WPI row shape")
            m=re.fullmatch(r"(Mar|Jun|Sep|Dec)-(\d{2}|20\d{2})",cells[0])
            need(m is not None,"invalid WPI quarter")
            yy=int(m[2]); yy=2000+yy if yy<100 else yy
            key=f"{yy:04d}-{MONTHS[m[1]]:02d}"
            val=float(cells[2]); need(math.isfinite(val) and -20<val<30 and key not in obs and key<=latest,"invalid WPI observation")
            obs[key]=val
        if obs and max(obs)==latest: candidates.append(obs)
    need(len(candidates)==1,"unique exact WPI annual SA table not found")
    return candidates[0]
def reconcile(row,obs,html,now):
    need(row["id"]==ID and row["frequency"]=="Q" and row["unit"]=="Percent" and row["source_file"]=="AU_WPI_YOY_history.csv","local identity mismatch")
    ds=row["dates"]; vs=row["values"]
    need(len(ds)==len(vs)>=24 and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"local history mismatch")
    old={datetime.strptime(d,"%d/%m/%Y").strftime("%Y-%m"):float(v) for d,v in zip(ds,vs)}
    need(len(old)==len(ds) and list(old)==sorted(old) and set(old)<=set(obs),"incomplete historical overlap")
    keys=sorted(k for k in obs if k>=min(old))
    ordq=lambda k:int(k[:4])*12+int(k[5:])
    need(all(ordq(b)-ordq(a)==3 for a,b in zip(keys,keys[1:])),"quarterly gap")
    errors=[abs(obs[k]-v) for k,v in old.items()]
    need(statistics.median(errors)<=.05+1e-8 and max(errors)<=.15+1e-8,"incompatible WPI history")
    dates=[f"{calendar.monthrange(int(k[:4]),int(k[5:]))[1]:02d}/{k[5:]}/{k[:4]}" for k in keys]
    values=[obs[k] for k in keys]
    prior=row.get("current_vintage_provenance",{}).get("source_series_id")
    need(prior in (None,CONFIG[ID]),"source identity changed")
    changed=dates!=ds or values!=vs or prior!=CONFIG[ID]
    if changed: row.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1],current_vintage_provenance={"status":"ABS_CURRENT_REVISED_HISTORY_NOT_PIT","source_url":URL,"source_series_id":CONFIG[ID],"source_table_title":TITLE,"source_html_sha256":sha256(html.encode()).hexdigest(),"historical_overlap":len(old),"median_absolute_revision":statistics.median(errors),"max_absolute_revision":max(errors),"runner_first_seen_utc":now.isoformat(),"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True})
    return {"id":ID,"status":"READY" if changed else "NO_CHANGE","before":ds[-1],"after":dates[-1],"latest":values[-1],"period":keys[-1],"overlap":len(old),"max_revision":max(errors)}
def prepare(current,*,now,fetcher=fetch_text):
    out=copy.deepcopy(current)
    try:
        need(now.utcoffset() is not None,"aware clock required")
        rows=[r for r in out["AUD"] if r["id"]==ID]; need(len(rows)==1,"unique WPI row required")
        html=fetcher(URL); candidate=copy.deepcopy(rows[0]); rec=reconcile(candidate,parse(html,now),html,now); rows[0].update(candidate)
    except (OSError,ValueError,KeyError,TypeError,IndexError) as exc: rec={"id":ID,"status":"WITHHELD","reason":str(exc)}
    return out,{"schema":"GMFQ_AUD_ABS_WPI_V1","series":[rec],"status":"READY" if rec["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
