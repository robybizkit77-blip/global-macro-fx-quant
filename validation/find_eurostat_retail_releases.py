#!/usr/bin/env python3
import json,re,html as htmlmod,urllib.request,urllib.parse,time,http.cookiejar
from pathlib import Path

OUT=Path("validation/pit_batch/eurostat/archive")
OUT.mkdir(parents=True,exist_ok=True)
BASE="https://ec.europa.eu/eurostat/news/euro-indicators"
MAX_PAGES=100

jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders=[("User-Agent","Mozilla/5.0 GMFQ-PIT-retail-index/4.0")]

def fetch(url,timeout=20):
    for attempt in range(4):
        try:
            with opener.open(url,timeout=timeout) as r:
                if r.status!=200: return None
                return r.read().decode("utf-8","ignore")
        except Exception as e:
            if "429" in str(e) or "timed out" in str(e).lower() or "403" in str(e):
                time.sleep(1.5*(attempt+1))
                continue
            return None
    return None

def clean(s):
    s=re.sub(r"<script.*?</script>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    s=htmlmod.unescape(s)
    return re.sub(r"\s+"," ",s).strip()

def abs_url(href,base=BASE):
    href=htmlmod.unescape(href)
    return urllib.parse.urljoin(base,href)

def extract_release_links(raw,page_no):
    out=[]
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',raw,flags=re.S|re.I):
        href=m.group(1); title=clean(m.group(2))
        if "volume of retail trade" in title.lower():
            out.append({"title":title,"url":abs_url(href),"search_page":page_no})
    return out

def next_page_url(raw):
    # Follow Eurostat's own tokenized/session-bound Next link rather than
    # synthesizing pagination parameters.
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',raw,flags=re.S|re.I):
        label=clean(m.group(2)).lower()
        if label=="next":
            return abs_url(m.group(1))
    return None

raw=fetch(BASE)
if not raw:
    raise SystemExit("Unable to fetch initial Eurostat Euro indicators page")

cands=[]
seen_pages=set()
url=BASE
pages_scanned=0
for page_no in range(1,MAX_PAGES+1):
    if url in seen_pages: break
    seen_pages.add(url)
    if page_no>1:
        raw=fetch(url)
        if not raw: break
    pages_scanned+=1
    cands.extend(extract_release_links(raw,page_no))
    nxt=next_page_url(raw)
    if not nxt: break
    url=nxt

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
for x in cands:
    h=parse_release(x)
    if h: hits.append(h)
hits.sort(key=lambda x:x["release_date"])

report={
 "schema":"GMFQ_EUROSTAT_RETAIL_RELEASE_FINDER_V3",
 "created_at":"2026-10-02",
 "runtime_id":"EA_RETAIL_VOL_history_value",
 "window":"2020-08 to 2026-10",
 "method":"Cookie-preserving crawl of Eurostat Euro indicators pages following the site's own tokenized Next links; retain only 'Volume of retail trade' release links, then parse those exact pages.",
 "qa":{
   "index_pages_scanned":pages_scanned,
   "candidate_release_links":len(cands),
   "releases_in_window":len(hits),
   "parsed_mom":sum(x["retail_volume_mom_pct"] is not None for x in hits),
   "sts_trtu_m_verified":sum(x["source_dataset_sts_trtu_m"] for x in hits)
 },
 "hits":hits,
 "status":"INDEX_DISCOVERY_COMPLETE" if hits else "NO_RELEASES_FOUND"
}
(OUT/"EUROSTAT_RETAIL_RELEASE_FINDER_V3_2026-10-02.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report["qa"],indent=2))
