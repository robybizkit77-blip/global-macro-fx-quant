"""Read-only ABS legacy quarterly trimmed mean source identity proof."""
import io,json,math,statistics
from datetime import date,datetime
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,urlopen
from bs4 import BeautifulSoup
from openpyxl import load_workbook
PAGE="https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/sep-2026"
ID="AU_CPI_TRIMMED_MEAN_Q_YOY_history_value"
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ-official-research/1.0"}),timeout=45) as r:
        assert urlsplit(r.geturl()).hostname=="www.abs.gov.au"
        raw=r.read(8_000_001)
    assert 0<len(raw)<=8_000_000
    return raw
def main():
    row=next(x for x in json.loads(Path("live_data/sections/MACRO_SERIES.json").read_text())["AUD"] if x["id"]==ID)
    old=dict(zip(row["dates"],row["values"]))
    soup=BeautifulSoup(fetch(PAGE),"html.parser")
    links=[]
    for a in soup.find_all("a",href=True):
        href=urljoin(PAGE,a["href"])
        if urlsplit(href).hostname!="www.abs.gov.au" or not urlsplit(href).path.lower().endswith(".xlsx"):continue
        prev=a.find_previous(["h3","h4","h5"])
        if prev and "APPENDIX 1a" in prev.get_text(" ",strip=True):links.append(href)
        elif "appendix1a" in href.lower() or "640101a" in href.lower():links.append(href)
    links=sorted(set(links));print("ABS_QUARTERLY_LINKS",links);assert len(links)==1
    book=load_workbook(io.BytesIO(fetch(links[0])),read_only=True,data_only=True)
    try:
        for ws in book.worksheets:
            if ws.max_row==1 and ws.max_column==1:ws.reset_dimensions()
            rows=list(ws.iter_rows(values_only=True));print("ABS_LAYOUT",ws.title,len(rows),max(map(len,rows),default=0),json.dumps([[str(x)[:180] for x in row[:12]] for row in rows[:12]],ensure_ascii=False))
            if not rows or sum(map(len,rows))>800000:continue
            candidates=[]
            for k in range(1,max(map(len,rows))):
                header=[str(x[k]) if len(x)>k else "" for x in rows[:10]]
                if any("trimmed mean" in x.lower() for x in header):print("ABS_TRIMMED_HEADER",ws.title,k+1,json.dumps(header,ensure_ascii=False))
                obs={}
                for x in rows:
                    if len(x)<=k or not isinstance(x[0],(date,datetime)):continue
                    v=x[k]
                    if isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v):obs[x[0].strftime("%Y-%m")]=float(v)
                if not set(old)<=set(obs):continue
                errors=[abs(obs[d]-v) for d,v in old.items()]
                if statistics.median(errors)<=.6:candidates.append({"column":k+1,"header":header,"overlap":len(errors),"median_abs":statistics.median(errors),"max_abs":max(errors),"exact":sum(e<1e-8 for e in errors),"new":{d:v for d,v in obs.items() if d>max(old)}})
            print("ABS_QUARTERLY_CANDIDATES",ws.title,json.dumps(sorted(candidates,key=lambda x:(x["median_abs"],x["max_abs"]))[:10],ensure_ascii=False))
    finally:book.close()
    print("DIAGNOSTIC_ONLY_NO_WRITES")
if __name__=="__main__":main()
