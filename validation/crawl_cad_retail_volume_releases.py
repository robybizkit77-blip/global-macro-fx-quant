#!/usr/bin/env python3
# Trigger-ready resumable crawler. Final catch-up
import csv, json, re, time
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

START="https://www150.statcan.gc.ca/n1/daily-quotidien/260924/dq260924a-eng.htm"
OUT=Path("validation/cad_retail_volume_release_crawl")
OUT.mkdir(parents=True, exist_ok=True)
STATE=OUT/"CA_RETAIL_VOLUME_DATED_RELEASE_CRAWL_V1.json"
MAX_PAGES_PER_RUN=64
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

def volume_change(text, month_name):
    # The wording changes across vintages. Require the reference month in the
    # sentence so quarterly/YTD comparisons cannot be mistaken for monthly data.
    verbs=r"(increased|decreased|rose|fell|declined|grew|edged up|edged down|were up|were down|was up|was down)"
    stems=[
        r"In volume terms,\\s*retail sales\\s+",
        r"In volume terms,\\s*sales\\s+",
        r"Retail sales in volume terms\\s+"
    ]
    neg={"decreased","fell","declined","edged down","were down","was down"}
    for stem in stems:
        pat=rf"{stem}{verbs}\\s+(?:by\\s*)?([0-9]+(?:\\.[0-9]+)?)%\\s+in\\s+{re.escape(month_name)}"
        m=re.search(pat,text,re.I)
        if m:
            val=float(m.group(2))
            if m.group(1).lower() in neg:
                val=-val
            return val
    unchanged=[
        rf"In volume terms,\\s*retail sales\\s+(?:were|was|remained)?\\s*(?:relatively |essentially )?unchanged\\s+in\\s+{re.escape(month_name)}",
        rf"In volume terms,\\s*sales\\s+(?:were|was|remained)?\\s*(?:relatively |essentially )?unchanged\\s+in\\s+{re.escape(month_name)}"
    ]
    if any(re.search(p,text,re.I) for p in unchanged):
        return 0.0
    return None

def parse_release(url, html):
    soup=BeautifulSoup(html,"html.parser")
    text=" ".join(soup.stripped_strings)
    h1=soup.find("h1")
    title=h1.get_text(" ",strip=True) if h1 else ""
    m=re.search(r"Retail trade,\s*([A-Za-z]+)\s*(\d{4})",title,re.I)
    if not m:
        return None
    month_name=m.group(1)
    mon=MONTHS.get(month_name.lower()); year=int(m.group(2))
    if not mon:
        return None
    ref=f"{year:04d}-{mon:02d}"
    dm=re.search(r"Released:\s*(\d{4}-\d{2}-\d{2})",text)
    if dm:
        release_date=dm.group(1)
    else:
        um=re.search(r"/(\d{6})/",url)
        release_date=f"20{um.group(1)[:2]}-{um.group(1)[2:4]}-{um.group(1)[4:6]}" if um else None

    val=volume_change(text,month_name)

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

# Re-read all materialized observations with the latest parser. This repairs
# nulls and also corrects older false-positive parses caused by wording changes.
repaired=0
corrected=0
for i,row in enumerate(rows):
    if not row.get("url"):
        continue
    try:
        rec=parse_release(row["url"],get(row["url"]))
    except Exception:
        continue
    if rec and rec.get("reference_month")==row.get("reference_month") and rec.get("first_release_mom_pct") is not None:
        old=row.get("first_release_mom_pct")
        new=rec.get("first_release_mom_pct")
        if old is None:
            repaired+=1
        elif abs(float(old)-float(new))>1e-12:
            corrected+=1
        rows[i]=rec
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
    if rec["reference_month"]<=TARGET:
        next_url=None; stop_reason="TARGET_REACHED"; break
    time.sleep(0.25)

rows=sorted({r["reference_month"]:r for r in rows}.values(),key=lambda x:x["reference_month"])
report={
 "schema":"GMFQ_CA_RETAIL_VOLUME_DATED_RELEASE_CRAWL_V1",
 "runtime_id":"CA_RETAIL_VOLUME_history_value",
 "official_measure":"Retail sales in volume terms, seasonally adjusted, chained 2017 dollars",
 "official_table":"20-10-0067-01",
 "start_url":START,
 "target_reference_month":TARGET,
 "next_url":next_url,
 "rows":rows,
 "summary":{
   "count":len(rows),
   "fetched_this_run":fetched,
   "repaired_nulls_this_run":repaired,
   "corrected_values_this_run":corrected,
   "from":rows[0]["reference_month"] if rows else None,
   "to":rows[-1]["reference_month"] if rows else None,
   "missing_values":[x["reference_month"] for x in rows if x["first_release_mom_pct"] is None],
   "stop_reason":stop_reason or ("CHUNK_LIMIT" if fetched>=MAX_PAGES_PER_RUN else "COMPLETE"),
   "complete":next_url is None
 }
}
STATE.write_text(json.dumps(report,indent=2),encoding="utf-8")
with (OUT/"CA_RETAIL_VOLUME_DATED_RELEASE_CRAWL_V1.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["reference_month","release_date","first_release_mom_pct","url"])
    w.writeheader()
    for r in rows:
        w.writerow({k:r[k] for k in w.fieldnames})
print(json.dumps(report["summary"],indent=2))
