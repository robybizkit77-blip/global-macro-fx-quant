#!/usr/bin/env python3
import json,re,time,urllib.request,urllib.error
from pathlib import Path
from datetime import date,timedelta

OUT=Path("validation/pit_batch/eurostat/archive")
OUT.mkdir(parents=True,exist_ok=True)

START=date(2020,7,1)
END=date(2026,9,30)
UA={"User-Agent":"Mozilla/5.0 GMFQ-validation/1.0"}

# Candidate Eurostat release slugs/patterns used for GDP + employment releases.
slugs=["2","2-","3","4"]
phrases=[
  "gdp and employment",
  "employment",
  "persons employed",
  "number of employed persons",
  "employment up",
  "employment down"
]

def fetch(url):
    req=urllib.request.Request(url,headers=UA)
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            return r.status,r.read().decode("utf-8","ignore")
    except urllib.error.HTTPError as e:
        return e.code,""
    except Exception:
        return None,""

def clean(s):
    s=re.sub(r"<script.*?</script>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    s=s.replace("&nbsp;"," ").replace("&amp;","&")
    return re.sub(r"\s+"," ",s).strip()

hits=[]
d=START
while d<=END:
    # Euro-indicator publication dates are weekdays and generally early/mid month.
    if d.weekday()<5 and d.day<=20:
        ds=d.strftime("%d%m%Y")
        urls=[
          f"https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-{ds}-ap",
          f"https://ec.europa.eu/eurostat/en/web/products-euro-indicators/-/2-{ds}-ap",
          f"https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-{ds}-ap",
          f"https://ec.europa.eu/eurostat/web/products-euro-indicators/-/3-{ds}-ap",
          f"https://ec.europa.eu/eurostat/en/web/products-euro-indicators/-/3-{ds}-ap",
          f"https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/3-{ds}-ap",
        ]
        seen=False
        for url in urls:
            status,html=fetch(url)
            if status!=200 or not html:
                continue
            txt=clean(html)
            low=txt.lower()
            if "employment" not in low:
                continue
            if not any(x in low for x in ["gdp","gross domestic product","persons employed"]):
                continue
            # Require euro-area aggregate context and quarterly wording/table.
            if "euro area" not in low:
                continue
            title=txt[:500]
            # Capture a compact window around first employment mention.
            k=low.find("employment")
            window=txt[max(0,k-1200):k+5000]
            hits.append({
              "release_date":d.isoformat(),
              "url":url,
              "title_window":title,
              "employment_window":window
            })
            seen=True
            break
        if seen:
            print("HIT",d.isoformat(),hits[-1]["url"])
    d+=timedelta(days=1)

# Deduplicate same release date.
dedup={}
for h in hits:
    dedup[h["release_date"]]=h
hits=[dedup[k] for k in sorted(dedup)]

report={
 "schema":"GMFQ_EUR_EMPLOYMENT_RELEASE_FINDER_V1",
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
 "qa":{"releases_found":len(hits)},
 "hits":hits,
 "status":"RELEASE_ARCHIVE_DISCOVERED" if hits else "NO_RELEASES_FOUND",
 "guardrail":"Finder output is discovery evidence only. Do not mark PIT_READY until first-release values are parsed, mapped to reference quarters, and QA-checked against dated official releases."
}
(OUT/"EUROSTAT_EMPLOYMENT_RELEASE_FINDER_V1_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report["qa"],indent=2))
