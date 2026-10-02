#!/usr/bin/env python3
import json,re,html as htmlmod,urllib.request,urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

OUT=Path("validation/pit_batch/eurostat/archive")
OUT.mkdir(parents=True,exist_ok=True)
UA={"User-Agent":"Mozilla/5.0 GMFQ-validation/3.0"}
BASE="https://ec.europa.eu/eurostat/news/euro-indicators"
MAX_WORKERS=16
PAGE_SIZE=50
MAX_PAGES=100

def fetch(url,timeout=12):
    req=urllib.request.Request(url,headers=UA)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            if r.status!=200: return None
            return r.read().decode("utf-8","ignore")
    except Exception:
        return None

def clean(s):
    s=re.sub(r"<script.*?</script>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    s=htmlmod.unescape(s)
    return re.sub(r"\s+"," ",s).strip()

def search_url(page):
    q={
      "_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action":"search",
      "_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection":"CAT_PREREL",
      "_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber":str(page),
      "_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize":str(PAGE_SIZE),
      "_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_sort":"lastUpdateDate"
    }
    return BASE+"?"+urllib.parse.urlencode(q)

def parse_search_page(page):
    url=search_url(page)
    raw=fetch(url)
    if not raw: return []
    # Capture anchors and nearby text; Eurostat result titles are regular links.
    out=[]
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',raw,flags=re.S|re.I):
        href=htmlmod.unescape(m.group(1))
        title=clean(m.group(2))
        low=title.lower()
        if "gdp" in low and "employment" in low:
            if href.startswith("/"):
                href="https://ec.europa.eu"+href
            if href.startswith("http"):
                out.append({"title":title,"url":href,"search_page":page})
    return out

cands=[]
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    futs={ex.submit(parse_search_page,p):p for p in range(1,MAX_PAGES+1)}
    for fut in as_completed(futs):
        cands.extend(fut.result())

# Deduplicate URLs.
uniq={}
for x in cands:
    uniq[x["url"]]=x
cands=list(uniq.values())

def parse_release(x):
    raw=fetch(x["url"])
    if not raw: return None
    txt=clean(raw)
    low=txt.lower()
    if "gdp" not in low or "employment" not in low or "euro area" not in low:
        return None
    # Publication date from visible release header.
    dm=re.search(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',txt,re.I)
    if not dm: return None
    months={m:i+1 for i,m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"])}
    release_date=f"{dm.group(3)}-{months[dm.group(2).title()]:02d}-{int(dm.group(1)):02d}"
    if not ("2020-07-01" <= release_date <= "2026-09-30"):
        return None
    # Keep only releases that explicitly describe GDP/employment estimates.
    if "employment" not in low:
        return None
    k=low.find("employment")
    # Extract reference-quarter phrase when available.
    qm=re.search(r'(first|second|third|fourth) quarter of (20\d{2})',txt,re.I)
    qmap={"first":"Q1","second":"Q2","third":"Q3","fourth":"Q4"}
    refq=f"{qm.group(2)}-{qmap[qm.group(1).lower()]}" if qm else None
    return {
      "release_date":release_date,
      "reference_quarter":refq,
      "url":x["url"],
      "title":x["title"],
      "release_kind":"flash" if "flash estimate" in low[:2500] else ("regular" if "main aggregates" in low[:2500] else "other"),
      "employment_window":txt[max(0,k-1200):k+6500]
    }

hits=[]
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    futs=[ex.submit(parse_release,x) for x in cands]
    for fut in as_completed(futs):
        h=fut.result()
        if h: hits.append(h)

hits.sort(key=lambda x:(x["release_date"],x["url"]))
# Dedup same dated release/url after multilingual/search aliases.
ded=[]
seen=set()
for h in hits:
    key=(h["release_date"],h["reference_quarter"],h["release_kind"])
    if key in seen: continue
    seen.add(key); ded.append(h)
hits=ded

report={
 "schema":"GMFQ_EUR_EMPLOYMENT_RELEASE_FINDER_V3",
 "created_at":"2026-10-02",
 "target":{
   "runtime_id":"EA_EMPLOYMENT_history_value",
   "dataset":"NAMQ_10_PE","unit":"THS_PER","s_adj":"SCA","na_item":"EMP_DC",
   "composition_rule":"EA20 through 2025-Q4; EA21 from 2026-Q1"
 },
 "search_method":{
   "source":"Eurostat Euro indicators search index",
   "pages_scanned":MAX_PAGES,
   "page_size":PAGE_SIZE,
   "candidate_title_links":len(cands),
   "parallel_workers":MAX_WORKERS
 },
 "qa":{
   "releases_found":len(hits),
   "reference_quarters":len(set(x["reference_quarter"] for x in hits if x["reference_quarter"])),
   "flash":sum(x["release_kind"]=="flash" for x in hits),
   "regular":sum(x["release_kind"]=="regular" for x in hits)
 },
 "hits":hits,
 "status":"RELEASE_ARCHIVE_DISCOVERED" if hits else "NO_RELEASES_FOUND",
 "guardrail":"Discovery only. PIT_READY requires extracting first-publication employment observations or growth rates, mapping them to reference quarters, and validating publication dates. Do not substitute current revised history."
}
(OUT/"EUROSTAT_EMPLOYMENT_RELEASE_FINDER_V1_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"candidates":len(cands),**report["qa"]},indent=2))
