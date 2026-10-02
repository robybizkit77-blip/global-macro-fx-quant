#!/usr/bin/env python3
import json,re,html as htmlmod,urllib.request,urllib.parse,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed

OUT=Path("validation/pit_batch/eurostat/archive")
OUT.mkdir(parents=True,exist_ok=True)
BASE="https://ec.europa.eu/eurostat/news/euro-indicators"
MAX_PAGES=100
PAGE_SIZE=11
UA={"User-Agent":"Mozilla/5.0 GMFQ-PIT-retail-index/5.0"}

def fetch(url,timeout=15):
    req=urllib.request.Request(url,headers=UA)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                if r.status!=200: return None
                return r.read().decode("utf-8","ignore")
        except Exception as e:
            if "429" in str(e) or "timed out" in str(e).lower():
                time.sleep(1+attempt)
                continue
            return None
    return None

def clean(s):
    s=re.sub(r"<script.*?</script>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    s=htmlmod.unescape(s)
    return re.sub(r"\s+"," ",s).strip()

def page_url(page):
    q={
      "_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action":"search",
      "_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection":"CAT_PREREL",
      "_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber":str(page),
      "_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize":str(PAGE_SIZE),
      "_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_sort":"lastUpdateDate"
    }
    return BASE+"?"+urllib.parse.urlencode(q)

def parse_index(page):
    raw=fetch(page_url(page))
    if not raw: return []
    out=[]
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',raw,flags=re.S|re.I):
        href=htmlmod.unescape(m.group(1))
        title=clean(m.group(2))
        if "volume of retail trade" not in title.lower():
            continue
        href=urllib.parse.urljoin(BASE,href)
        out.append({"title":title,"url":href,"search_page":page})
    return out

cands=[]
with ThreadPoolExecutor(max_workers=10) as ex:
    futs={ex.submit(parse_index,p):p for p in range(1,MAX_PAGES+1)}
    for fut in as_completed(futs):
        cands.extend(fut.result())

uniq={}
for x in cands:
    uniq[x["url"]]=x
cands=list(uniq.values())

months={m:i+1 for i,m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"])}

def parse_release(x):
    raw=fetch(x["url"])
    if not raw: return None
    txt=clean(raw)
    low=txt.lower()
    if "volume of retail trade" not in low or "euro area" not in low:
        return None
    dm=re.search(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',txt,re.I)
    if not dm: return None
    release_date=f"{dm.group(3)}-{months[dm.group(2).title()]:02d}-{int(dm.group(1)):02d}"
    if not ("2020-08-01"<=release_date<="2026-10-31"):
        return None
    txt=re.sub(r'(?<=\d)[.,]\s+(?=\d)',lambda m:m.group(0)[0],txt)
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
    return {
      "release_date":release_date,
      "url":x["url"],
      "title":x["title"],
      "retail_volume_mom_pct":val,
      "match_text":matched,
      "source_dataset_sts_trtu_m":bool(re.search(r"Source dataset:\s*sts_trtu_m",txt,re.I))
    }

hits=[]
with ThreadPoolExecutor(max_workers=8) as ex:
    futs=[ex.submit(parse_release,x) for x in cands]
    for fut in as_completed(futs):
        h=fut.result()
        if h: hits.append(h)
hits.sort(key=lambda x:x["release_date"])

report={
 "schema":"GMFQ_EUROSTAT_RETAIL_RELEASE_FINDER_V4",
 "created_at":"2026-10-02",
 "runtime_id":"EA_RETAIL_VOL_history_value",
 "window":"2020-08 to 2026-10",
 "method":"Direct Eurostat search-index pagination using stable pageNumber/pageSize=11 parameters; retain exact 'Volume of retail trade' links, then parse only those official release pages.",
 "qa":{
   "index_pages_scanned":MAX_PAGES,
   "candidate_release_links":len(cands),
   "releases_in_window":len(hits),
   "parsed_mom":sum(x["retail_volume_mom_pct"] is not None for x in hits),
   "sts_trtu_m_verified":sum(x["source_dataset_sts_trtu_m"] for x in hits)
 },
 "hits":hits,
 "status":"INDEX_DISCOVERY_COMPLETE" if hits else "NO_RELEASES_FOUND"
}
(OUT/"EUROSTAT_RETAIL_RELEASE_FINDER_V4_2026-10-02.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report["qa"],indent=2))
