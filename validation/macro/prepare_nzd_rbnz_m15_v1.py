"""RBNZ M15 official aggregate business expectations, current-vintage context only."""
import argparse,copy,json,math,re
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from bs4 import BeautifulSoup
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
URL="https://www.rbnz.govt.nz/statistics/series/economic-indicators/business-expectations-survey"
PREFIX="NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_"
COLS=("CPI_1Y","CPI_2Y","CPI_5Y","CPI_10Y","Wage_1Y","Wage_2Y","Unemp_1Y","Unemp_2Y")
CONFIG={PREFIX+k:i for i,k in enumerate(COLS)}
def need(ok,msg):
    if not ok:raise ValueError(msg)
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ-official-research/1.0"}),timeout=35) as r:
        u=urlsplit(r.geturl())
        need(u.scheme=="https" and u.hostname in ("www.rbnz.govt.nz","rbnz.govt.nz") and u.path.rstrip("/").endswith("/business-expectations-survey"),"wrong RBNZ response")
        raw=r.read(3_000_001)
    need(0<len(raw)<=3_000_000,"invalid response size")
    return raw
def parse(raw,now):
    soup=BeautifulSoup(raw,"html.parser")
    def norm(x):return " ".join(x.split())
    text=norm(soup.get_text(" ",strip=True))
    need("Business Expectations Survey (M15)" in text,"missing exact M15 title")
    hit=re.search(r"Released:\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})",text)
    need(hit is not None,"missing official release date")
    release=datetime.strptime(hit[1],"%d %B %Y").date()
    need(release<=now.date(),"future release")
    groups=("Annual CPI growth (%)","Annual Wage Growth (%)","Unemployment Rate (%)")
    heads=("Date","1 year ahead","2 years ahead","5 years ahead","10 years ahead","1 year ahead","2 years ahead","1 year ahead","2 years ahead")
    candidates=[]
    for t in soup.find_all("table"):
        rows=[[norm(c.get_text(" ",strip=True)) for c in tr.find_all(["th","td"],recursive=False)] for tr in t.find_all("tr")]
        if any(tuple(x for x in rr if x)==groups for rr in rows) and list(heads) in rows:candidates.append(rows)
    need(len(candidates)==1,"exact M15 summary table not unique")
    obs={}
    months={"Mar":3,"Jun":6,"Sep":9,"Sept":9,"Dec":12}
    for rr in candidates[0]:
        if not rr:continue
        h=re.fullmatch(r"(Mar|Jun|Sep|Sept|Dec) (\d{4})",rr[0])
        if not h:continue
        d=f"{int(h[2]):04d}-{months[h[1]]:02d}"
        need(len(rr)==9 and d not in obs,"bad or duplicate summary row")
        vals=[float(v.replace(",",".")) for v in rr[1:]]
        need(all(math.isfinite(v) and -10<v<30 for v in vals),"invalid survey value")
        obs[d]=vals
    need(bool(obs),"empty M15 summary")
    quarter=f"{release.year:04d}-{((release.month-1)//3+1)*3:02d}"
    need(max(obs)==quarter,"survey reference quarter does not match actual release quarter")
    return obs,release.isoformat()
def prepare(current,*,now,fetcher=fetch):
    out=copy.deepcopy(current);rows=[]
    try:
        raw=fetcher(URL);obs,release=parse(raw,now)
        for ident,col in CONFIG.items():
            hits=[r for r in out["NZD"] if r["id"]==ident]
            need(len(hits)==1,"nonunique M15 row")
            row=hits[0];ds=row["dates"];vs=row["values"]
            need(row["source_file"]=="NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent.csv" and len(ds)==len(vs)==len(set(ds)) and ds==sorted(ds) and row["last_date"]==ds[-1] and row["last_value"]==vs[-1],"local identity mismatch")
            old=dict(zip(ds,vs));overlap=sorted(set(old)&set(obs))
            need(len(overlap)>=3 and ds[-1] in overlap and all(abs(old[d]-obs[d][col])<.005 for d in overlap),"published summary historical overlap mismatch")
            new=sorted(d for d in obs if d>ds[-1])
            ordinal=lambda d:int(d[:4])*12+int(d[5:])
            need(max(obs)>=ds[-1] and all(ordinal(b)-ordinal(a)==3 for a,b in zip([ds[-1]]+new,new)),"missing new quarter or regression")
            prior=row.get("current_vintage_provenance",{})
            code="RBNZ_M15_AGGREGATE_WEIGHTED_MEAN_"+COLS[col]
            need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source changed")
            if new:
                row.update(dates=ds+new,values=vs+[obs[d][col] for d in new],last_date=new[-1],last_value=obs[new[-1]][col],current_vintage_provenance={"status":"RBNZ_M15_CURRENT_PUBLISHED_SURVEY_NOT_PIT","source_series_id":code,"source_url":URL,"release_date":release,"reference_period_semantics":"survey quarter, published before quarter end","source_payload_sha256":sha256(raw).hexdigest(),"historical_overlap":len(overlap),"source_series_first_release_PIT_certified":False,"methodology_note":"Wage question wording revised starting December 2026 quarter","runner_first_seen_utc":now.isoformat()})
            rows.append({"id":ident,"status":"READY" if new else "NO_CHANGE","before":ds[-1],"after":row["last_date"],"latest":row["last_value"],"overlap":len(overlap),"release_date":release})
    except (OSError,ValueError,KeyError,TypeError,IndexError,AssertionError) as e:
        out=copy.deepcopy(current);rows=[{"id":k,"status":"WITHHELD","reason":str(e)} for k in CONFIG]
    return out,{"schema":"GMFQ_NZD_RBNZ_M15_V1","series":rows,"status":"READY" if any(r["status"]=="READY" for r in rows) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
