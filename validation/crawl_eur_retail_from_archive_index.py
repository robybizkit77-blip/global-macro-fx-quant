#!/usr/bin/env python3
import json,re,html as htmlmod,time,urllib.request,urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed

OUT=Path("validation/pit_batch/eurostat/archive/EUR_RETAIL_VOLUME_DATED_RELEASE_CRAWL_V1_2026-10-02.json")
BASE="https://ec.europa.eu/eurostat/news/euro-indicators"
UA={"User-Agent":"Mozilla/5.0 GMFQ-PIT-retail-index/1.0"}
PAGE_SIZE=50
MAX_PAGES=95

def fetch(url,timeout=20):
    last=None
    for attempt in range(3):
        req=urllib.request.Request(url,headers=UA)
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return r.read().decode("utf-8","ignore"),r.geturl()
        except Exception as e:
            last=e
            if "429" in str(e) or "timed out" in str(e).lower():
                time.sleep(1.5*(attempt+1)); continue
            return None,None
    return None,None

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

def page_candidates(page):
    raw,_=fetch(search_url(page),timeout=25)
    if not raw:return []
    out=[]
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',raw,re.S|re.I):
        href=htmlmod.unescape(m.group(1)); title=clean(m.group(2))
        if "volume of retail trade" not in title.lower(): continue
        if href.startswith("/"): href="https://ec.europa.eu"+href
        if href.startswith("http"): out.append({"url":href,"title":title,"search_page":page})
    return out

cands=[]
with ThreadPoolExecutor(max_workers=10) as ex:
    futs=[ex.submit(page_candidates,p) for p in range(1,MAX_PAGES+1)]
    for fut in as_completed(futs): cands.extend(fut.result())
uniq={x["url"]:x for x in cands}
cands=list(uniq.values())

months={m:i+1 for i,m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"])}

def prev_month(y,m):
    return (y-1,12) if m==1 else (y,m-1)

def parse_release(x):
    raw,final=fetch(x["url"],timeout=25)
    if not raw:return None
    txt=clean(raw)
    dm=re.search(r'Release date:\s*(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',txt,re.I)
    if not dm:
        dm=re.search(r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b',txt,re.I)
    if not dm:return None
    rd=f"{dm.group(3)}-{months[dm.group(2).title()]:02d}-{int(dm.group(1)):02d}"
    if not ("2020-08-01"<=rd<="2026-09-30"):return None
    txt=re.sub(r'(?<=\d)[.,]\s+(?=\d)',lambda m:m.group(0)[0],txt)
    pats=[
      r'Volume of retail trade\s+(up|down)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+(?:both\s+)?the euro area',
      r'volume of retail trade.*?(increased|decreased|fell)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+the euro area.*?compared with'
    ]
    val=None;match=None
    for p in pats:
        m=re.search(p,txt,re.I|re.S)
        if m:
            d=m.group(1).lower();v=float(m.group(2).replace(",","."))
            val=-abs(v) if d in ("down","decreased","fell") else abs(v)
            match=m.group(0)[:600];break
    if val is None:return None
    y,mn=map(int,rd[:7].split("-"))
    y,mn=prev_month(y,mn);y,mn=prev_month(y,mn)
    ref=f"{y}-{mn:02d}"
    return {"release_date":rd,"reference_month":ref,"retail_volume_mom_pct":val,"url":final or x["url"],"title":x["title"],"match_text":match}

rows=[]
with ThreadPoolExecutor(max_workers=8) as ex:
    futs=[ex.submit(parse_release,x) for x in cands]
    for fut in as_completed(futs):
        z=fut.result()
        if z:rows.append(z)

by={}
for x in sorted(rows,key=lambda z:z["release_date"]):
    by.setdefault(x["reference_month"],x)
rows=[by[k] for k in sorted(by)]
expected=[];y,m=2020,6
while (y,m)<=(2026,7):
    expected.append(f"{y}-{m:02d}");m+=1
    if m==13:y+=1;m=1
missing=[x for x in expected if x not in by]
report={
 "schema":"GMFQ_EUR_RETAIL_VOLUME_DATED_RELEASE_CRAWL_V2_ARCHIVE_INDEX",
 "created_at":"2026-10-02",
 "target":{"runtime_id":"EA_RETAIL_VOL_history_value","source":"Eurostat Euro indicators archive index + official release pages"},
 "search":{"pages_scanned":MAX_PAGES,"page_size":PAGE_SIZE,"candidate_release_links":len(cands)},
 "rows":rows,
 "summary":{"expected_count":len(expected),"parsed":len(rows),"coverage_pct":round(100*len(rows)/len(expected),2),"from":rows[0]["reference_month"] if rows else None,"to":rows[-1]["reference_month"] if rows else None,"missing":missing,"complete":len(missing)==0},
 "guardrail":"Only dated official Eurostat release-time monthly changes are retained. Current revised history is never substituted."
}
OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({"search":report["search"],"summary":report["summary"]},indent=2))
