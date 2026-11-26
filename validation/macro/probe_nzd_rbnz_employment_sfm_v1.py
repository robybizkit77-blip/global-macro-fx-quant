"""Read-only RBNZ M1 and M9 workbook source identity audit."""
import io,json,math,statistics
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,urlopen
from pathlib import Path
from urllib.error import HTTPError
from zipfile import ZipFile
import csv,re
from openpyxl import load_workbook
from validation.macro.prepare_nz_retail_volume_v1 import fetch as stats_fetch
PAGES={"NZ_CORE_INFLATION_SFM_Q_history_value":"https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m1/hm1.xlsx","NZ_EMPLOYED_history_value":"https://rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m9/hm9.xlsx"}
class Links(HTMLParser):
    def __init__(self):super().__init__();self.a=None;self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":self.a=[dict(attrs).get("href",""),[]]
    def handle_data(self,x):
        if self.a is not None:self.a[1].append(x)
    def handle_endtag(self,t):
        if t=="a" and self.a is not None:self.links.append((self.a[0]," ".join(self.a[1])));self.a=None
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"RBNZ-Automated-Agent/GlobalMacroFXQuant/LiquidityResearch"}),timeout=45) as r:
        assert urlsplit(r.geturl()).hostname in ("www.rbnz.govt.nz","rbnz.govt.nz")
        data=r.read(8_000_001)
    assert 0<len(data)<=8_000_000
    return data
def main():
    doc=json.loads(Path("live_data/sections/MACRO_SERIES.json").read_text())
    errors=[]
    for ident,url in PAGES.items():
        links=[(url,ident)]
        print("RBNZ_DIRECT",ident,url)
        row=next(r for r in doc["NZD"] if r["id"]==ident);old=row["values"]
        for link,_ in links:
            try: raw=fetch(link)
            except (OSError,ValueError) as e:
                errors.append((ident,str(e)));print("RBNZ_UNAVAILABLE",ident,str(e));continue
            book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
            try:
                for ws in book.worksheets:
                    if ws.max_row==1 and ws.max_column==1:ws.reset_dimensions()
                    if (ws.max_row or 1)*(ws.max_column or 1)>500000:continue
                    rows=list(ws.iter_rows(values_only=True))
                    if not rows:continue
                    assert sum(len(x) for x in rows)<=500000,"unexpected worksheet size"
                    print("RBNZ_LAYOUT",ident,ws.title,ws.max_row,ws.max_column,json.dumps([[str(v)[:100] for v in x[:20]] for x in rows[:15]],ensure_ascii=False))
                    candidates=[]
                    if ws.title=="Data":
                        from datetime import datetime,date
                        width=max(map(len,rows))
                        old_dates=dict(zip(row["dates"],row["values"]))
                        for k in range(1,width):
                            head=[str(x[k]) if len(x)>k else "" for x in rows[:5]]
                            print("RBNZ_COLUMN",ident,k+1,json.dumps(head,ensure_ascii=False))
                            obs={}
                            for x in rows[5:]:
                                if len(x)<=k or not isinstance(x[0],(datetime,date)):continue
                                v=x[k]
                                if isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v):obs[x[0].strftime("%Y-%m")]=float(v)
                            if not set(old_dates)<=set(obs):continue
                            for scale in (1,1000,.001):
                                errs=[abs(obs[d]*scale-v)/max(abs(v),1) for d,v in old_dates.items()]
                                med=statistics.median(errs)
                                if med<.1:candidates.append({"column":k+1,"scale":scale,"overlap":len(errs),"median_relative":med,"max_relative":max(errs),"following":{d:v*scale for d,v in obs.items() if d>max(old_dates)},"header":head})
                    print("RBNZ_CANDIDATES",ident,ws.title,json.dumps(sorted(candidates,key=lambda x:(x["median_relative"],x["max_relative"]))[:5],ensure_ascii=False))
            finally:book.close()
    ident="NZ_EMPLOYED_history_value"
    row=next(r for r in doc["NZD"] if r["id"]==ident)
    old=dict(zip(row["dates"],row["values"]))
    page="https://www.stats.govt.nz/information-releases/labour-market-statistics-september-2026-quarter/"
    with urlopen(Request(page,headers={"User-Agent":"GMFQ-official-research/1.0"}),timeout=40) as res:
        assert urlsplit(res.geturl()).hostname in ("www.stats.govt.nz","stats.govt.nz")
        h=res.read(3_000_000).decode("utf-8",errors="replace")
    parser=Links();parser.feed(h)
    urls=sorted({urljoin(page,href) for href,t in parser.links if ".zip" in href.lower() and urlsplit(urljoin(page,href)).hostname in ("www.stats.govt.nz","stats.govt.nz")})
    print("STATSNZ_ZIPS",urls)
    for url in urls:
        try:
            raw,_=stats_fetch(url)
        except (OSError,ValueError) as e:
            print("STATSNZ_ARCHIVE_ERROR",url,str(e));continue
        with ZipFile(io.BytesIO(raw)) as z:
            candidates={}
            for ent in z.infolist():
                if not ent.filename.lower().endswith(".csv") or ent.file_size>30_000_000:continue
                for rec in csv.DictReader(io.StringIO(z.read(ent).decode("utf-8-sig"))):
                    title=" ".join(str(rec.get(k,"")) for k in ("Series_title_1","Series_title_2","Series_title_3","Series_title_4","Series_title_5","Group"))
                    if "employed" not in title.lower() and "employment" not in title.lower():continue
                    code=rec.get("Series_reference");period=rec.get("Period","").replace(".","-")
                    if not code or not re.fullmatch(r"20\d{2}-(03|06|09|12)",period):continue
                    try:v=float(rec.get("Data_value",""))
                    except ValueError:continue
                    item=candidates.setdefault(code,{"meta":{k:rec.get(k) for k in ("UNITS","Magnitude","Subject","Group","Series_title_1","Series_title_2","Series_title_3","Series_title_4","Series_title_5")},"obs":{}})
                    item["obs"][period]=v
            ranks=[]
            for code,item in candidates.items():
                obs=item["obs"]
                if not set(old)<=set(obs):continue
                for scale in (1,.001,1000):
                    errs=[abs(obs[d]*scale-v)/max(abs(v),1) for d,v in old.items()]
                    med=statistics.median(errs)
                    if med<.1:ranks.append({"code":code,"meta":item["meta"],"scale":scale,"median_relative":med,"max_relative":max(errs),"next":{d:v*scale for d,v in obs.items() if d>max(old)}})
            print("STATSNZ_CANDIDATES",json.dumps(sorted(ranks,key=lambda x:(x["median_relative"],x["max_relative"]))[:8],ensure_ascii=False))
    print("RBNZ_ERRORS",errors)
    print("DIAGNOSTIC_ONLY_NO_WRITES")
if __name__=="__main__":main()
