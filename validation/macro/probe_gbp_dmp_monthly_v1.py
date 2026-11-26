"""Read-only BoE October 2026 DMP workbook identity and complete overlap diagnostics."""
import io,json,math,re,statistics
from datetime import date,datetime
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,urlopen
from bs4 import BeautifulSoup
from openpyxl import load_workbook
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
PAGE="https://www.bankofengland.co.uk/decision-maker-panel/2026/october-2026"
def need(ok,why):
    if not ok:raise ValueError(why)
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ-official-research/1.0"}),timeout=40) as r:
        final=r.geturl();need(r.status==200 and urlsplit(final).scheme=="https" and urlsplit(final).hostname in ("www.bankofengland.co.uk","bankofengland.co.uk"),"wrong publisher endpoint")
        raw=r.read(5_000_001)
    need(0<len(raw)<=5_000_000,"unexpected size");return raw,final
def month(x):
    if isinstance(x,(datetime,date)):return x.strftime("%Y-%m")
    if not isinstance(x,str):return None
    x=x.strip()
    for fmt in ("%b-%y","%b-%Y","%B %Y","%Y-%m","%Y-%m-%d","%b %Y","%b %y"):
        try:return datetime.strptime(x,fmt).strftime("%Y-%m")
        except ValueError:pass
    return None
def main():
    raw,final=fetch(PAGE);soup=BeautifulSoup(raw,"html.parser")
    links=[]
    for a in soup.find_all("a",href=True):
        label=" ".join(a.get_text(" ",strip=True).casefold().split())
        if "monthly aggregate-level data" in label and "october 2026" in label:
            links.append(urljoin(final,a["href"]))
    links=list(set(links));need(len(links)==1,"missing unique official workbook link: "+repr(links))
    raw,url=fetch(links[0]);need(raw.startswith(b"PK"),"not XLSX")
    book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    old=[z for z in json.loads(SOURCE.read_text())["GBP"] if "DMP_LEAD" in z["id"]]
    need(len(old)==7,"unexpected canonical DMP count")
    candidates={z["id"]:[] for z in old}
    print("DMP_WORKBOOK",url,book.sheetnames)
    for sheet in book:
        rows=list(sheet.iter_rows(max_row=min(sheet.max_row or 1000,1000),max_col=min(sheet.max_column or 100,100),values_only=True))
        print("DMP_SHEET_HEAD",sheet.title,json.dumps(rows[:7],default=str)[:5000])
        # Search date columns; compare only full, consistently aligned histories.
        for dc in range(len(rows[0]) if rows else 0):
            date_rows=[(i,month(row[dc])) for i,row in enumerate(rows) if month(row[dc])]
            if len(date_rows)<24 or len({d for _,d in date_rows})!=len(date_rows):continue
            first=date_rows[0][0];headers=rows[:first][-8:]
            for col in range(len(rows[0])):
                if col==dc:continue
                obs={d:float(rows[i][col]) for i,d in date_rows if isinstance(rows[i][col],(int,float)) and not isinstance(rows[i][col],bool) and math.isfinite(rows[i][col])}
                for z in old:
                    prior={month(d):v for d,v in zip(z["dates"],z["values"])}
                    if None in prior or not set(prior)<=set(obs):continue
                    errs=[abs(obs[d]-v) for d,v in prior.items()]
                    candidate={"sheet":sheet.title,"date_col":dc+1,"value_col":col+1,"headers":[h[col] for h in headers if h[col] is not None],"overlap":len(errs),"median_abs":statistics.median(errs),"max_abs":max(errs),"exact_round3":sum(e<=.00051 for e in errs),"latest_date":max(obs),"latest":obs[max(obs)]}
                    candidates[z["id"]].append(candidate)
    for key,vals in candidates.items():
        print("DMP_HISTORY_MATCH",key,json.dumps(sorted(vals,key=lambda x:(x["median_abs"],x["max_abs"]))[:4],default=str))
    need(all(v for v in candidates.values()),"one or more histories not found")
if __name__=="__main__":main()
