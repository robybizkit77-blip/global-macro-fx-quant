"""Read-only RBNZ M1 and M9 workbook source identity audit."""
import io,json,math,statistics
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,urlopen
from pathlib import Path
from openpyxl import load_workbook
PAGES={"NZ_CORE_INFLATION_SFM_Q_history_value":"https://rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m1/hm1.xlsx","NZ_EMPLOYED_history_value":"https://rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m9/hm9.xlsx"}
class Links(HTMLParser):
    def __init__(self):super().__init__();self.a=None;self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":self.a=[dict(attrs).get("href",""),[]]
    def handle_data(self,x):
        if self.a is not None:self.a[1].append(x)
    def handle_endtag(self,t):
        if t=="a" and self.a is not None:self.links.append((self.a[0]," ".join(self.a[1])));self.a=None
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ official research"}),timeout=45) as r:
        assert urlsplit(r.geturl()).hostname in ("www.rbnz.govt.nz","rbnz.govt.nz")
        data=r.read(8_000_001)
    assert 0<len(data)<=8_000_000
    return data
def main():
    doc=json.loads(Path("live_data/sections/MACRO_SERIES.json").read_text())
    for ident,url in PAGES.items():
        links=[(url,ident)]
        print("RBNZ_DIRECT",ident,url)
        row=next(r for r in doc["NZD"] if r["id"]==ident);old=row["values"]
        for link,_ in links:
            book=load_workbook(io.BytesIO(fetch(link)),read_only=True,data_only=True)
            try:
                for ws in book.worksheets:
                    if ws.max_row*ws.max_column>500000:continue
                    rows=list(ws.iter_rows(values_only=True))
                    print("RBNZ_LAYOUT",ident,ws.title,ws.max_row,ws.max_column,json.dumps([[str(v)[:100] for v in x[:20]] for x in rows[:15]],ensure_ascii=False))
                    candidates=[]
                    for k,line in enumerate(zip(*rows)):
                        nums=[(i,float(v)) for i,v in enumerate(line) if isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v)]
                        for start in range(len(nums)-len(old)+1):
                            part=nums[start:start+len(old)]
                            for scale in (1,1000,.001):
                                errs=[abs(v*scale-o)/max(abs(o),1) for (_,v),o in zip(part,old)]
                                med=statistics.median(errs)
                                if med<.1:
                                    candidates.append({"column":k+1,"first_row":part[0][0]+1,"last_row":part[-1][0]+1,"scale":scale,"median_relative":med,"max_relative":max(errs),"following":[(i+1,v*scale) for i,v in nums[start+len(old):start+len(old)+3]],"header":[str(v)[:80] for v in line[:12]]})
                    print("RBNZ_CANDIDATES",ident,ws.title,json.dumps(sorted(candidates,key=lambda x:(x["median_relative"],x["max_relative"]))[:5],ensure_ascii=False))
            finally:book.close()
    print("DIAGNOSTIC_ONLY_NO_WRITES")
if __name__=="__main__":main()
