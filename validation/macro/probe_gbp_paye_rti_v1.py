"""Read-only official ONS PAYE RTI chart historical proof, including provisional series."""
import csv,io,json,math,statistics
from datetime import datetime
from urllib.parse import urljoin,urlsplit,parse_qs
from urllib.request import Request,urlopen
from bs4 import BeautifulSoup
from validation.macro.prepare_gbp_boe_revised_v1 import SOURCE,need
PAGE="https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/bulletins/earningsandemploymentfrompayasyouearnrealtimeinformationuk/latest"
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ-official-research/1.0"}),timeout=40) as r:
        final=r.geturl();need(r.status==200 and urlsplit(final).scheme=="https" and urlsplit(final).hostname=="www.ons.gov.uk","wrong publisher endpoint")
        raw=r.read(5_000_001)
    need(0<len(raw)<=5_000_000,"invalid source size");return raw,final
def month(v):
    for fmt in ("%Y-%m","%Y-%m-%d","%Y %b","%b %Y","%B %Y","%b-%y","%b-%Y","%Y%b","%d/%m/%Y"):
        try:return datetime.strptime(v.strip(),fmt).strftime("%Y-%m")
        except ValueError:pass
    return None
def main():
    key="UK_PAYE_PAYROLLED_EMPLOYEES_SA_history_value"
    rows=[r for r in json.loads(SOURCE.read_text())["GBP"] if r["id"]==key]
    need(len(rows)==1,"unique legacy row")
    row=rows[0];need(row["frequency"]=="M" and row["unit"]=="persons","legacy identity")
    old={month(d):float(v) for d,v in zip(row["dates"],row["values"])}
    need(None not in old and len(old)==len(row["dates"])>=36,"invalid legacy months")
    raw,final=fetch(PAGE);soup=BeautifulSoup(raw,"html.parser")
    print("PAYE_PAGE",final,"HEADINGS",[(h.name,h.get_text(" ",strip=True)) for h in soup.find_all(["h2","h3","h4","h5"])][:70])
    print("PAYE_DOWNLOAD_LINKS",[(a.get_text(" ",strip=True),a["href"]) for a in soup.find_all("a",href=True) if "csv" in a["href"].lower() or "dataset" in a["href"].lower()][:60])
    headings=[h for h in soup.find_all(["h2","h3","h4","h5"]) if "figure 1:" in h.get_text(" ",strip=True).casefold() and "payrolled employees" in h.get_text(" ",strip=True).casefold()]
    need(len(headings)==1,"missing unique payrolled employee Figure 1")
    links=[]
    for el in headings[0].next_elements:
        if getattr(el,"name",None) in ("h2","h3") and "figure 2:" in el.get_text(" ",strip=True).casefold():break
        if getattr(el,"name",None)=="a" and el.get("href"):
            url=urljoin(final,el["href"]);q=parse_qs(urlsplit(url).query)
            if q.get("format")==["csv"] and urlsplit(url).hostname=="www.ons.gov.uk":links.append(url);break
    need(len(links)==1,"missing official chart CSV")
    raw,url=fetch(links[0]);data=list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    print("PAYE_CSV",url,json.dumps(data[:12]),json.dumps(data[-6:]))
    # Compare all numeric columns on the full shared history; do not assume flash column identity.
    for i in range(1,max(map(len,data))):
        obs={}
        for r in data:
            if len(r)<=i:continue
            d=month(r[0])
            if not d:continue
            try:v=float(r[i].strip().replace(",",""))
            except ValueError:continue
            if not math.isfinite(v) or v<=0:continue
            need(d not in obs,"duplicate month");obs[d]=v
        if not set(old)<=set(obs):continue
        errors=[abs(obs[d]-v) for d,v in old.items()]
        print("PAYE_OVERLAP",json.dumps({"column":i+1,"count":len(old),"exact":sum(e<=1 for e in errors),"median_abs":statistics.median(errors),"max_abs":max(errors),"new":{d:obs[d] for d in sorted(obs) if d>max(old)}}))
if __name__=="__main__":main()
