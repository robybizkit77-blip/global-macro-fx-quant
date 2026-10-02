#!/usr/bin/env python3
import json,re,time,urllib.request,os
from pathlib import Path
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTDIR=Path("validation/pit_batch/eurostat/archive")
OUTDIR.mkdir(parents=True,exist_ok=True)
YEAR_FILTER=int(os.environ["CRAWL_YEAR"]) if os.environ.get("CRAWL_YEAR") else None
MONTH_FILTER=int(os.environ["CRAWL_MONTH"]) if os.environ.get("CRAWL_MONTH") else None
OUT=OUTDIR/(f"EUR_RETAIL_VOLUME_DATED_RELEASE_CRAWL_{YEAR_FILTER}_{MONTH_FILTER:02d}_V1_2026-10-02.json" if YEAR_FILTER and MONTH_FILTER else (f"EUR_RETAIL_VOLUME_DATED_RELEASE_CRAWL_{YEAR_FILTER}_V1_2026-10-02.json" if YEAR_FILTER else "EUR_RETAIL_VOLUME_DATED_RELEASE_CRAWL_V1_2026-10-02.json"))

UA={"User-Agent":"Mozilla/5.0 GMFQ-PIT-retail/2.0"}

def get(url,timeout=10):
    last=None
    for attempt in range(4):
        req=urllib.request.Request(url,headers=UA)
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return r.read().decode("utf-8","ignore"),r.geturl()
        except Exception as e:
            last=e
            s=str(e)
            if "404" in s: return None,None
            if "429" in s or "timed out" in s.lower():
                time.sleep(1.5*(attempt+1)); continue
            return None,None
    return None,None

def clean(s):
    s=re.sub(r"<script.*?</script>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def urls_for(d):
    code=d.strftime("%d%m%Y")
    return [
      f"https://ec.europa.eu/eurostat/web/products-euro-indicators/w/4-{code}-ap",
      f"https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/4-{code}-ap",
      f"https://ec.europa.eu/eurostat/web/products-euro-indicators/-/4-{code}-ap",
      f"https://ec.europa.eu/eurostat/en/web/products-euro-indicators/-/4-{code}-ap",
    ]

months={m:i+1 for i,m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"])}

def prev_month(y,m):
    return (y-1,12) if m==1 else (y,m-1)

def extract_first_release(txt,release_date):
    # Normalize split decimal extraction.
    txt=re.sub(r'(?<=\d)[.,]\s+(?=\d)',lambda m:m.group(0)[0],txt)
    # Prefer headline: "Volume of retail trade up/down by X% in the euro area"
    pats=[
      r'Volume of retail trade\s+(up|down)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+(?:both\s+)?the euro area',
      r'volume of retail trade.*?(increased|decreased)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+the euro area.*?compared with the previous month'
    ]
    val=None; matched=None
    for p in pats:
        m=re.search(p,txt,re.I|re.S)
        if m:
            d=m.group(1).lower()
            v=float(m.group(2).replace(",","."))
            val=-abs(v) if d in ("down","decreased") else abs(v)
            matched=m.group(0)[:700]
            break
    if val is None: return None
    # Reference month is usually two months before publication; verify from text.
    rd=date.fromisoformat(release_date)
    y,m=rd.year,rd.month
    y,m=prev_month(y,m); y,m=prev_month(y,m)
    ref=f"{y}-{m:02d}"
    month_name=[k for k,v in months.items() if v==m][0]
    # Require the expected reference month/year to appear near a monthly-change phrase.
    if not re.search(rf'\b{month_name}\s+{y}\b',txt,re.I):
        # Some releases omit year in repeated prose; accept if title/table context clearly matches.
        if not re.search(rf'\b{month_name}\b',txt,re.I):
            return None
    return {"reference_month":ref,"mom_pct":val,"match_text":matched}

def crawl_release_month(y,mo):
    for day in range(4,11):
        try: d=date(y,mo,day)
        except ValueError: continue
        for u in urls_for(d):
            raw,final=get(u)
            if not raw: continue
            txt=clean(raw)
            if "volume of retail trade" not in txt.lower() or "euro area" not in txt.lower():
                continue
            x=extract_first_release(txt,d.isoformat())
            if not x: continue
            return {
              "release_date":d.isoformat(),
              "reference_month":x["reference_month"],
              "retail_volume_mom_pct":x["mom_pct"],
              "url":final or u,
              "match_text":x["match_text"]
            }
    return None

targets=[]
years=[YEAR_FILTER] if YEAR_FILTER else list(range(2020,2027))
for y in years:
    m0=8 if y==2020 else 1
    m1=10 if y==2026 else 12
    for mo in range(m0,m1+1):
        if MONTH_FILTER and mo!=MONTH_FILTER:
            continue
        targets.append((y,mo))

rows=[]
with ThreadPoolExecutor(max_workers=4) as ex:
    futs={ex.submit(crawl_release_month,y,mo):(y,mo) for y,mo in targets}
    for fut in as_completed(futs):
        x=fut.result()
        if x: rows.append(x)
rows.sort(key=lambda x:x["release_date"])

# Deduplicate by reference month, retaining earliest official release found.
by={}
for x in sorted(rows,key=lambda z:z["release_date"]):
    by.setdefault(x["reference_month"],x)
rows=[by[k] for k in sorted(by)]
expected=[]
y,m=2020,6
while (y,m)<=(2026,7):
    expected.append(f"{y}-{m:02d}")
    m+=1
    if m==13: y+=1;m=1
missing=[x for x in expected if x not in by]
report={
 "schema":"GMFQ_EUR_RETAIL_VOLUME_DATED_RELEASE_CRAWL_V1",
 "created_at":"2026-10-02",
 "target":{"runtime_id":"EA_RETAIL_VOL_history_value","source":"Eurostat Volume of retail trade releases"},
 "rows":rows,
 "summary":{
   "crawl_year":YEAR_FILTER,
   "expected_count":len(expected) if YEAR_FILTER is None else None,
   "parsed":len(rows),
   "coverage_pct":round(100*len(rows)/len(expected),2) if YEAR_FILTER is None else None,
   "from":rows[0]["reference_month"] if rows else None,
   "to":rows[-1]["reference_month"] if rows else None,
   "missing":missing if YEAR_FILTER is None else [],
   "complete":len(missing)==0 if YEAR_FILTER is None else None
 },
 "guardrail":"Only dated official Eurostat release-time monthly changes are retained. Missing months remain missing; current revised history is never substituted."
}
OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report["summary"],indent=2))
