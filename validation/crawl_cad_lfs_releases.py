#!/usr/bin/env python3
import csv, json, re, time
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

START="https://www150.statcan.gc.ca/n1/daily-quotidien/260904/dq260904a-eng.htm"
OUT=Path("validation/cad_lfs_release_crawl")
OUT.mkdir(parents=True, exist_ok=True)
STATE=OUT/"CA_LFS_DATED_RELEASE_CRAWL_V1.json"
MAX_PAGES_PER_RUN=90
TARGET="2020-05"

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

def parse_release(url,html):
    soup=BeautifulSoup(html,"html.parser")
    text=" ".join(soup.stripped_strings)
    h1=soup.find("h1")
    title=h1.get_text(" ",strip=True) if h1 else ""
    m=re.search(r"Labour Force Survey,\s*([A-Za-z]+)\s*(\d{4})",title,re.I)
    if not m: return None
    month_name=m.group(1); year=int(m.group(2))
    mon=MONTHS.get(month_name.lower())
    if not mon: return None
    ref=f"{year:04d}-{mon:02d}"

    dm=re.search(r"Released:\s*(\d{4}-\d{2}-\d{2})",text)
    if dm: release_date=dm.group(1)
    else:
        um=re.search(r"/(\d{6})/",url)
        release_date=f"20{um.group(1)[:2]}-{um.group(1)[2:4]}-{um.group(1)[4:6]}" if um else None

    # Top Canada cards. Historical pages use "Employment"; newer pages
    # may use "Employment level".
    emp=None
    em=re.search(
        rf"Employment(?: level)?\s*[—-]\s*Canada\s*([0-9][0-9,]*)\s*{re.escape(month_name)}\s*{year}",
        text,re.I
    )
    if em:
        emp=float(em.group(1).replace(",",""))/1000.0

    unemp=None
    um=re.search(
        rf"Unemployment rate\s*[—-]\s*Canada\s*([0-9]+(?:\.[0-9]+)?)%\s*{re.escape(month_name)}\s*{year}",
        text,re.I
    )
    if um:
        unemp=float(um.group(1))

    prev=None
    for a in soup.find_all("a",href=True):
        label=" ".join(a.stripped_strings).lower()
        if "previous release" in label:
            prev=urljoin(url,a["href"]); break

    return {
      "reference_month":ref,
      "release_date":release_date,
      "employment_first_release_thousands":emp,
      "unemployment_rate_first_release_pct":unemp,
      "url":url,
      "previous_url":prev
    }

rows=[]; next_url=START
if STATE.exists():
    try:
        old=json.loads(STATE.read_text())
        rows=old.get("rows",[])
        next_url=old.get("next_url") or None
    except Exception:
        pass

# Reparse all existing observations with the current parser.
repaired_emp=0; repaired_unemp=0; corrected=0
for i,row in enumerate(rows):
    if not row.get("url"): continue
    try:
        rec=parse_release(row["url"],get(row["url"]))
    except Exception:
        continue
    if not rec or rec["reference_month"]!=row["reference_month"]: continue
    if row.get("employment_first_release_thousands") is None and rec.get("employment_first_release_thousands") is not None:
        repaired_emp+=1
    if row.get("unemployment_rate_first_release_pct") is None and rec.get("unemployment_rate_first_release_pct") is not None:
        repaired_unemp+=1
    for k in ("employment_first_release_thousands","unemployment_rate_first_release_pct"):
        a=row.get(k); b=rec.get(k)
        if a is not None and b is not None and abs(float(a)-float(b))>1e-12:
            corrected+=1
    if rec.get("employment_first_release_thousands") is not None or rec.get("unemployment_rate_first_release_pct") is not None:
        rows[i]=rec
    time.sleep(0.10)

seen={r["url"] for r in rows}
fetched=0; stop_reason=None
while next_url and next_url not in seen and fetched<MAX_PAGES_PER_RUN:
    try:
        rec=parse_release(next_url,get(next_url))
    except Exception as ex:
        stop_reason=f"FETCH_RETRY_EXHAUSTED: {type(ex).__name__}: {ex}"
        break
    if not rec:
        stop_reason="PARSE_FAILED"; break
    rows.append(rec); seen.add(rec["url"]); fetched+=1
    next_url=rec["previous_url"]
    if rec["reference_month"]<=TARGET:
        next_url=None; stop_reason="TARGET_REACHED"; break
    time.sleep(0.20)

rows=sorted({r["reference_month"]:r for r in rows}.values(),key=lambda x:x["reference_month"])
missing_emp=[r["reference_month"] for r in rows if r["employment_first_release_thousands"] is None]
missing_unemp=[r["reference_month"] for r in rows if r["unemployment_rate_first_release_pct"] is None]
report={
 "schema":"GMFQ_CA_LFS_DATED_RELEASE_CRAWL_V1",
 "runtime_ids":["CA_EMPLOYMENT_history_value","CA_UNEMP_RATE_history_value"],
 "official_table":"14-10-0287-01",
 "start_url":START,
 "target_reference_month":TARGET,
 "next_url":next_url,
 "rows":rows,
 "summary":{
   "count":len(rows),"fetched_this_run":fetched,
   "repaired_employment_this_run":repaired_emp,
   "repaired_unemployment_this_run":repaired_unemp,
   "corrected_values_this_run":corrected,
   "from":rows[0]["reference_month"] if rows else None,
   "to":rows[-1]["reference_month"] if rows else None,
   "missing_employment":missing_emp,
   "missing_unemployment":missing_unemp,
   "stop_reason":stop_reason or ("CHUNK_LIMIT" if fetched>=MAX_PAGES_PER_RUN else "COMPLETE"),
   "complete":next_url is None and not missing_emp and not missing_unemp
 }
}
STATE.write_text(json.dumps(report,indent=2)+"\n")
with (OUT/"CA_LFS_DATED_RELEASE_CRAWL_V1.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["reference_month","release_date","employment_first_release_thousands","unemployment_rate_first_release_pct","url"])
    w.writeheader()
    for r in rows: w.writerow({k:r[k] for k in w.fieldnames})
print(json.dumps(report["summary"],indent=2))
