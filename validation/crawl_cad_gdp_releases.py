#!/usr/bin/env python3
import csv, json, re, time
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

START="https://www150.statcan.gc.ca/n1/daily-quotidien/260929/dq260929a-eng.htm"
OUT=Path("validation/cad_gdp_release_crawl")
OUT.mkdir(parents=True, exist_ok=True)
STATE=OUT/"CA_GDP_DATED_RELEASE_CRAWL_V1.json"
MAX_PAGES_PER_RUN=8

session=requests.Session()
session.headers.update({"User-Agent":"Mozilla/5.0 GMFQ-PIT-validation/1.0"})
MONTHS={m.lower():i for i,m in enumerate(
["January","February","March","April","May","June","July","August","September","October","November","December"],1)}

def get(url):
    last=None
    for attempt in range(4):
        try:
            r=session.get(url,timeout=(10,25))
            r.raise_for_status()
            return r.text
        except Exception as ex:
            last=ex
            time.sleep(2*(attempt+1))
    raise last

def parse_headline_value(text, month_name, year):
    # Prefer the official compact headline block:
    # "Real GDP by industry / Month YYYY / -0.2% / Image: decrease / (monthly change)".
    block=re.search(
        rf"Real GDP by industry\s+{re.escape(month_name)}\s*{year}\s*([+-]?\d+(?:\.\d+)?)%\s*(?:Image:\s*)?(increase|decrease)?\s*\(monthly change\)",
        text,re.I
    )
    if block:
        val=float(block.group(1))
        direction=(block.group(2) or "").lower()
        if direction=="decrease" and val>0:
            val=-val
        return val

    # Fallback for older archived layouts where the compact label is flattened differently.
    generic=re.search(
        rf"{re.escape(month_name)}\s*{year}\s*([+-]?\d+(?:\.\d+)?)%\s*(?:Image:\s*)?(increase|decrease)?\s*\(monthly change\)",
        text,re.I
    )
    if generic:
        val=float(generic.group(1))
        direction=(generic.group(2) or "").lower()
        if direction=="decrease" and val>0:
            val=-val
        return val

    segment=text[:6000]
    nm=re.search(
        r"Real gross domestic product \(GDP\).*?"
        r"(grew|increased|rose|expanded|edged up|decreased|declined|contracted|fell|edged down)\s*"
        r"(?:by\s*)?([0-9]+(?:\.[0-9]+)?)%",
        segment,re.I
    )
    if nm:
        val=float(nm.group(2))
        if nm.group(1).lower() in {"decreased","declined","contracted","fell","edged down"}:
            val=-val
        return val
    if re.search(r"Real gross domestic product \(GDP\).*?(?:was\s+)?essentially unchanged",segment,re.I):
        return 0.0
    return None

def parse_release(url, html):
    soup=BeautifulSoup(html,"html.parser")
    text=" ".join(soup.stripped_strings)
    h1=soup.find("h1")
    title=h1.get_text(" ",strip=True) if h1 else ""
    m=re.search(r"Gross domestic product by industry,\s*([A-Za-z]+)\s*(\d{4})",title,re.I)
    if not m:
        return None
    mon=m.group(1).lower(); year=int(m.group(2)); month=MONTHS.get(mon)
    if not month:
        return None
    ref=f"{year:04d}-{month:02d}"
    dm=re.search(r"Released:\s*(\d{4}-\d{2}-\d{2})",text)
    if dm:
        release_date=dm.group(1)
    else:
        um=re.search(r"/(\d{6})/",url)
        yy=int(um.group(1)[:2]) if um else None
        release_date=f"20{yy:02d}-{um.group(1)[2:4]}-{um.group(1)[4:6]}" if um else None

    val=parse_headline_value(text,m.group(1),year)

    prev=None
    for a in soup.find_all("a",href=True):
        label=" ".join(a.stripped_strings).lower()
        if "previous release" in label:
            prev=urljoin(url,a["href"])
            break
    return {
        "reference_month":ref,
        "release_date":release_date,
        "first_release_mom_pct":val,
        "url":url,
        "previous_url":prev
    }

rows=[]; next_url=START
if STATE.exists():
    try:
        old=json.loads(STATE.read_text(encoding="utf-8"))
        rows=old.get("rows",[])
        next_url=old.get("next_url") or None
    except Exception:
        pass

# Re-read previously materialized nulls with the current parser.
repaired=0
for i,row in enumerate(rows):
    if row.get("first_release_mom_pct") is not None or not row.get("url"):
        continue
    try:
        rec=parse_release(row["url"],get(row["url"]))
    except Exception:
        continue
    if rec and rec.get("reference_month")==row.get("reference_month") and rec.get("first_release_mom_pct") is not None:
        rows[i]=rec
        repaired+=1
    time.sleep(0.15)

seen={r["url"] for r in rows}
fetched=0; stop_reason=None
while next_url and next_url not in seen and fetched<MAX_PAGES_PER_RUN:
    try:
        html=get(next_url)
    except Exception as ex:
        stop_reason=f"FETCH_RETRY_EXHAUSTED: {type(ex).__name__}: {ex}"
        break
    rec=parse_release(next_url,html)
    if not rec:
        stop_reason="PARSE_FAILED"
        break
    rows.append(rec); seen.add(rec["url"]); fetched+=1
    next_url=rec["previous_url"]
    if rec["reference_month"]<="2021-12":
        next_url=None; stop_reason="TARGET_REACHED"; break
    time.sleep(0.25)

rows=sorted({r["reference_month"]:r for r in rows}.values(),key=lambda x:x["reference_month"])
report={
 "schema":"GMFQ_CA_GDP_DATED_RELEASE_CRAWL_V3_REPAIRABLE",
 "start_url":START,
 "next_url":next_url,
 "rows":rows,
 "summary":{
   "count":len(rows),
   "fetched_this_run":fetched,
   "repaired_nulls_this_run":repaired,
   "from":rows[0]["reference_month"] if rows else None,
   "to":rows[-1]["reference_month"] if rows else None,
   "missing_values":[x["reference_month"] for x in rows if x["first_release_mom_pct"] is None],
   "stop_reason":stop_reason or ("CHUNK_LIMIT" if fetched>=MAX_PAGES_PER_RUN else "COMPLETE"),
   "complete":next_url is None
 }
}
STATE.write_text(json.dumps(report,indent=2),encoding="utf-8")
with (OUT/"CA_GDP_DATED_RELEASE_CRAWL_V1.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["reference_month","release_date","first_release_mom_pct","url"])
    w.writeheader()
    for r in rows:
        w.writerow({k:r[k] for k in w.fieldnames})
print(json.dumps(report["summary"],indent=2))
