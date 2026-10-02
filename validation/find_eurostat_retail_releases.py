#!/usr/bin/env python3
import json, re, urllib.request, urllib.error, calendar, time
from pathlib import Path
from datetime import date

OUT=Path("validation/pit_batch/eurostat/archive")
OUT.mkdir(parents=True, exist_ok=True)
UA={"User-Agent":"Mozilla/5.0 GMFQ-PIT-retail/1.0"}

def get(url, timeout=40):
    req=urllib.request.Request(url,headers=UA)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            if r.status!=200: return None
            return r.read().decode("utf-8","replace")
    except Exception:
        return None

def strip_tags(s):
    s=re.sub(r"<script[\s\S]*?</script>"," ",s,flags=re.I)
    s=re.sub(r"<style[\s\S]*?</style>"," ",s,flags=re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    s=s.replace("&nbsp;"," ")
    return re.sub(r"\s+"," ",s)

def candidates(d):
    code=d.strftime("%d%m%Y")
    return [
      f"https://ec.europa.eu/eurostat/en/web/products-euro-indicators/-/4-{code}-ap",
      f"https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/4-{code}-ap",
      f"https://ec.europa.eu/eurostat/web/products-euro-indicators/-/4-{code}-ap",
      f"https://ec.europa.eu/eurostat/web/products-euro-indicators/w/4-{code}-ap"
    ]

hits=[]
# Retail Euro-indicator releases normally occur early each month.
# Probe days 1-10, 2020-08 through 2026-09. This avoids relying on the Liferay archive index.
for y in range(2020,2027):
    m0=8 if y==2020 else 1
    m1=9 if y==2026 else 12
    for m in range(m0,m1+1):
        found=None
        for day in range(1,11):
            try: d=date(y,m,day)
            except ValueError: continue
            for u in candidates(d):
                h=get(u)
                if not h: continue
                t=strip_tags(h)
                if re.search(r"Volume of retail trade",t,re.I) and re.search(r"Source dataset:\s*sts_trtu_m",t,re.I):
                    found={"release_date":d.isoformat(),"url":u,"text":t}
                    break
            if found: break
        if found:
            t=found.pop("text")
            found["title_match"]=re.search(r"Volume of retail trade[^<]{0,180}",t,re.I).group(0)[:180] if re.search(r"Volume of retail trade[^<]{0,180}",t,re.I) else None
            # Capture a compact window around the seasonally adjusted indices table.
            marker=re.search(r"Volume of retail trade,\s*calendar and seasonally adjusted indices",t,re.I)
            if marker:
                window=t[marker.start():marker.start()+4500]
                found["table_text_window"]=window
                found["has_euro_area_row"]=bool(re.search(r"Euro area\s+[-0-9. ]+",window,re.I))
            else:
                found["table_text_window"]=None
                found["has_euro_area_row"]=False
            hits.append(found)
            print("FOUND",found["release_date"],found["url"])
        else:
            print("MISS",y,m)
        time.sleep(.05)

report={
 "schema":"GMFQ_EUROSTAT_RETAIL_RELEASE_FINDER_V1",
 "created_at":"2026-10-02",
 "runtime_id":"EA_RETAIL_VOL_history_value",
 "window":"2020-08 to 2026-09",
 "method":"Probe official Eurostat Euro-indicator product-code URLs on days 1-10 of each month; retain only pages whose text identifies Volume of retail trade and source dataset sts_trtu_m.",
 "hits":hits,
 "qa":{
   "releases_found":len(hits),
   "with_index_table_window":sum(bool(x.get("table_text_window")) for x in hits),
   "with_euro_area_row":sum(bool(x.get("has_euro_area_row")) for x in hits)
 }
}
(OUT/"EUROSTAT_RETAIL_RELEASE_FINDER_V1_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report["qa"],indent=2))
