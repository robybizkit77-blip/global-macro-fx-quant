#!/usr/bin/env python3
import json,re,urllib.request,urllib.error
from pathlib import Path
from datetime import date,timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

OUT=Path("validation/pit_batch/eurostat/archive")
OUT.mkdir(parents=True,exist_ok=True)

START=date(2020,7,1)
END=date(2026,9,30)
UA={"User-Agent":"Mozilla/5.0 GMFQ-validation/2.0"}

# Quarterly GDP/employment Eurostat releases cluster in these months.
TARGET_MONTHS={2,3,5,6,8,9,11,12}
MAX_WORKERS=18

def clean(s):
    s=re.sub(r"<script.*?</script>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    s=s.replace("&nbsp;"," ").replace("&amp;","&")
    return re.sub(r"\s+"," ",s).strip()

def fetch_one(item):
    d,url=item
    req=urllib.request.Request(url,headers=UA)
    try:
        with urllib.request.urlopen(req,timeout=8) as r:
            if r.status!=200:
                return None
            html=r.read().decode("utf-8","ignore")
    except Exception:
        return None
    txt=clean(html)
    low=txt.lower()
    if "employment" not in low or "euro area" not in low:
        return None
    if not any(x in low for x in ["gdp","gross domestic product","persons employed"]):
        return None
    k=low.find("employment")
    return {
      "release_date":d.isoformat(),
      "url":url,
      "title_window":txt[:500],
      "employment_window":txt[max(0,k-1200):k+5000]
    }

tasks=[]
d=START
while d<=END:
    if d.month in TARGET_MONTHS and d.weekday()<5 and 4<=d.day<=20:
        ds=d.strftime("%d%m%Y")
        for prefix in [
          "https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-",
          "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/-/2-",
          "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-",
          "https://ec.europa.eu/eurostat/web/products-euro-indicators/-/3-",
          "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/-/3-",
          "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/3-",
        ]:
            tasks.append((d,f"{prefix}{ds}-ap"))
    d+=timedelta(days=1)

hits=[]
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    futs=[ex.submit(fetch_one,t) for t in tasks]
    for fut in as_completed(futs):
        h=fut.result()
        if h:
            hits.append(h)
            print("HIT",h["release_date"],h["url"])

# Deduplicate same publication date, preferring the first valid canonical page.
dedup={}
for h in sorted(hits,key=lambda x:(x["release_date"],x["url"])):
    dedup.setdefault(h["release_date"],h)
hits=[dedup[k] for k in sorted(dedup)]

report={
 "schema":"GMFQ_EUR_EMPLOYMENT_RELEASE_FINDER_V2",
 "created_at":"2026-10-02",
 "target":{
   "runtime_id":"EA_EMPLOYMENT_history_value",
   "dataset":"NAMQ_10_PE",
   "unit":"THS_PER",
   "s_adj":"SCA",
   "na_item":"EMP_DC",
   "composition_rule":"EA20 through 2025-Q4; EA21 from 2026-Q1"
 },
 "search_window":{"start":START.isoformat(),"end":END.isoformat()},
 "search_method":{
   "quarterly_release_months":sorted(TARGET_MONTHS),
   "day_window":"04-20 weekdays",
   "candidate_urls":len(tasks),
   "parallel_workers":MAX_WORKERS
 },
 "qa":{"releases_found":len(hits)},
 "hits":hits,
 "status":"RELEASE_ARCHIVE_DISCOVERED" if hits else "NO_RELEASES_FOUND",
 "guardrail":"Finder output is discovery evidence only. Do not mark PIT_READY until first-release values are parsed, mapped to reference quarters, and QA-checked against dated official releases."
}
(OUT/"EUROSTAT_EMPLOYMENT_RELEASE_FINDER_V1_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"candidate_urls":len(tasks),**report["qa"]},indent=2))
