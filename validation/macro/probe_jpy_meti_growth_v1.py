"""Read-only METI workbook discovery and numerical identity diagnostics."""
import io,json,math,re,statistics
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,urlopen
from openpyxl import load_workbook
PAGES={
 "JP_IIP_history_value":("https://www.meti.go.jp/english/statistics/tyo/iip/b2020_result-2.html",r"b2020_g[os]m1e\.xlsx"),
 "JP_RETAIL_history_value":("https://www.meti.go.jp/statistics/tyo/syoudou/result-2/index.html",r"業種別商業販売額指数"),
}
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.a=None
    def handle_starttag(self,tag,attrs):
        if tag=="a":self.a=[dict(attrs).get("href",""),[]]
    def handle_data(self,data):
        if self.a is not None:self.a[1].append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.a is not None:self.links.append((self.a[0]," ".join(self.a[1])));self.a=None
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0 GMFQ research"}),timeout=45) as r:
        raw=r.read(15_000_001)
        assert urlsplit(r.geturl()).hostname=="www.meti.go.jp"
        charset=r.headers.get_content_charset() or "utf-8"
    assert 0<len(raw)<=15_000_000
    return raw,charset
def compare_sequences(lines,old,orientation):
    matches=[]
    for i,line in enumerate(lines):
        vals=[(j,float(x)) for j,x in enumerate(line) if isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)]
        n=len(old)
        for off in range(len(vals)-n+1):
            v=vals[off:off+n]
            # This ranks numerical candidates only. Dates and adjustment identity must be verified separately.
            err=[abs(y-a) for (_,y),a in zip(v,old)]
            med=statistics.median(err)
            if med<=5:
                matches.append({"orientation":orientation,"line":i+1,"start":v[0][0]+1,"end":v[-1][0]+1,"exact":sum(e<1e-7 for e in err),"median_abs":med,"max_abs":max(err),"following":vals[off+n:off+n+5],"header":[str(x)[:100] for x in line[:8]]})
    return sorted(matches,key=lambda x:(x["median_abs"],x["max_abs"]))[:5]
def main():
    doc=json.loads(Path("live_data/sections/MACRO_SERIES.json").read_text())
    for ident,(page,pattern) in PAGES.items():
        row=next(r for r in doc["JPY"] if r["id"]==ident)
        assert len(row["dates"])==len(row["values"])>=36
        raw,charset=fetch(page);p=Links();p.feed(raw.decode(charset,errors="replace"))
        urls=sorted({urljoin(page,h) for h,label in p.links if re.search(pattern,h+" "+label) and urlsplit(urljoin(page,h)).hostname=="www.meti.go.jp" and urlsplit(urljoin(page,h)).path.endswith(".xlsx")})
        print("METI_LINKS",ident,urls)
        assert 1<=len(urls)<=5
        for url in urls:
            raw,_=fetch(url);book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
            try:
                for ws in book.worksheets:
                    if ws.max_row and ws.max_column and ws.max_row*ws.max_column>600000:continue
                    lines=list(ws.iter_rows(values_only=True))
                    print("METI_LAYOUT",ident,url,ws.title,ws.max_row,ws.max_column,json.dumps([[str(v)[:80] for v in line[:16]] for line in lines[:16]],ensure_ascii=False))
                    candidates=compare_sequences(lines,row["values"],"row")+compare_sequences(list(zip(*lines)),row["values"],"column")
                    print("METI_CANDIDATES",ident,url,ws.title,json.dumps(candidates,ensure_ascii=False))
            finally:book.close()
    print("DIAGNOSTIC_ONLY_NO_CANONICAL_WRITES")
if __name__=="__main__":main()
