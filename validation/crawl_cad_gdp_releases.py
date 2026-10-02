#!/usr/bin/env python3
import csv, json, re, time
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

START="https://www150.statcan.gc.ca/n1/daily-quotidien/260929/dq260929a-eng.htm"
OUT=Path("validation/cad_gdp_release_crawl")
OUT.mkdir(parents=True, exist_ok=True)

session=requests.Session()
session.headers.update({"User-Agent":"Mozilla/5.0 GMFQ-PIT-validation/1.0"})

MONTHS={m.lower():i for i,m in enumerate(
["January","February","March","April","May","June","July","August","September","October","November","December"],1)}

def get(url):
    r=session.get(url,timeout=30)
    r.raise_for_status()
    return r.text

def parse_release(url, html):
    soup=BeautifulSoup(html,"html.parser")
    text=" ".join(soup.stripped_strings)
    h1=soup.find("h1")
    title=h1.get_text(" ",strip=True) if h1 else ""
    m=re.search(r"Gross domestic product by industry,\s*([A-Za-z]+)\s*(\d{4})",title,re.I)
    if not m:
        return None
    mon=m.group(1).lower(); year=int(m.group(2))
    month=MONTHS.get(mon)
    if not month: return None
    ref=f"{year:04d}-{month:02d}"

    dm=re.search(r"Released:\s*(\d{4}-\d{2}-\d{2})",text)
    if dm:
        release_date=dm.group(1)
    else:
        dm=re.search(r"Released at .*?,\s*[A-Za-z]+,\s*([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",text)
        if dm:
            release_date=f"{int(dm.group(3)):04d}-{MONTHS[dm.group(1).lower()]:02d}-{int(dm.group(2)):02d}"
        else:
            # URL date YYMMDD
            um=re.search(r"/(\d{6})/",url)
            yy=int(um.group(1)[:2]); release_date=f"20{yy:02d}-{um.group(1)[2:4]}-{um.group(1)[4:6]}" if um else None

    # Prefer the compact headline block: reference month followed by monthly change.
    # Fall back to first narrative sentence.
    pat=rf"{re.escape(m.group(1))}\s*{year}\s*([+-]?\d+(?:\.\d+)?)%\s*(?:Image:\s*(increase|decrease))?\s*\(monthly change\)"
    hm=re.search(pat,text,re.I)
    if hm:
        val=float(hm.group(1))
        direction=(hm.group(2) or "").lower()
        if direction=="decrease" and val>0: val=-val
    else:
        # Handles "grew 0.4%", "declined 0.2%", "edged down 0.1%",
        # and "was essentially unchanged".
        segment=text[:4000]
        nm=re.search(r"Real gross domestic product \(GDP\).*?(grew|increased|rose|expanded|edged up|decreased|declined|contracted|fell|edged down)\s*(?:by\s*)?([0-9]+(?:\.[0-9]+)?)%",segment,re.I)
        if nm:
            val=float(nm.group(2))
            if nm.group(1).lower() in {"decreased","declined","contracted","fell","edged down"}: val=-val
        elif re.search(r"Real gross domestic product \(GDP\).*?essentially unchanged",segment,re.I):
            val=0.0
        else:
            val=None

    prev=None
    for a in soup.find_all("a",href=True):
        label=" ".join(a.stripped_strings).lower()
        if "previous release" in label:
            prev=urljoin(url,a["href"]); break

    # Sometimes nav label is not directly on the anchor; search nearby href by URL form.
    if not prev:
        for a in soup.find_all("a",href=True):
            href=a["href"]
            if "daily-quotidien" in href and re.search(r"dq\d{6}[a-z]-eng\.htm",href):
                label=" ".join(a.stripped_strings).lower()
                if "previous" in label:
                    prev=urljoin(url,href); break

    return {"reference_month":ref,"release_date":release_date,"first_release_mom_pct":val,"url":url,"previous_url":prev}

rows=[]; seen=set(); url=START
while url and url not in seen and len(rows)<100:
    seen.add(url)
    html=get(url)
    rec=parse_release(url,html)
    if not rec:
        break
    rows.append(rec)
    if rec["reference_month"]<="2021-12":
        break
    url=rec["previous_url"]
    time.sleep(0.15)

rows=sorted(rows,key=lambda x:x["reference_month"])
report={
 "schema":"GMFQ_CA_GDP_DATED_RELEASE_CRAWL_V1",
 "start_url":START,
 "rows":rows,
 "summary":{
   "count":len(rows),
   "from":rows[0]["reference_month"] if rows else None,
   "to":rows[-1]["reference_month"] if rows else None,
   "missing_values":[x["reference_month"] for x in rows if x["first_release_mom_pct"] is None],
   "broken_previous_links":[x["reference_month"] for x in rows[:-1] if not x["previous_url"]]
 }
}
(OUT/"CA_GDP_DATED_RELEASE_CRAWL_V1.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
with (OUT/"CA_GDP_DATED_RELEASE_CRAWL_V1.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["reference_month","release_date","first_release_mom_pct","url"])
    w.writeheader()
    for r in rows:
        w.writerow({k:r[k] for k in w.fieldnames})
print(json.dumps(report["summary"],indent=2))
