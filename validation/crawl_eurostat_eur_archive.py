#!/usr/bin/env python3
import json, re, html, urllib.parse, urllib.request, time
from pathlib import Path

OUT=Path("validation/pit_batch/eurostat/archive")
OUT.mkdir(parents=True, exist_ok=True)
BASE="https://ec.europa.eu/eurostat/en/web/euro-indicators/publications"
UA={"User-Agent":"Mozilla/5.0 GMFQ-PIT-archive/1.0"}

def get(url, timeout=120):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.read().decode("utf-8","replace")

def clean(s):
    s=re.sub(r"<script[\s\S]*?</script>"," ",s,flags=re.I)
    s=re.sub(r"<style[\s\S]*?</style>"," ",s,flags=re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",html.unescape(s)).strip()

base_html=get(BASE)
m=re.search(r"AssetPublisherPortlet_INSTANCE_([A-Za-z0-9]+)",base_html)
if not m:
    raise RuntimeError("Could not discover Eurostat publication AssetPublisher instance id")
inst=m.group(1)

def page_url(page,delta=100):
    q={
      f"_com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_{inst}_cur":str(page),
      f"_com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_{inst}_delta":str(delta),
      "p_p_id":f"com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_{inst}",
      "p_p_lifecycle":"0","p_p_mode":"view","p_p_state":"normal","p_r_p_resetCur":"false"
    }
    return BASE+"?"+urllib.parse.urlencode(q)

seen={}
target_patterns={
 "retail":re.compile(r"volume of retail trade",re.I),
 "employment":re.compile(r"gdp.*employment|employment.*gdp",re.I)
}

# Crawl provider archive pages in large batches; stop after all links are older than 2020.
for p in range(1,80):
    u=page_url(p)
    txt=get(u)
    links=re.findall(r'href=["\']([^"\']*products-euro-indicators[^"\']*)["\'][^>]*>([\s\S]*?)</a>',txt,re.I)
    year_hits=[]
    new_count=0
    for href,label_html in links:
        href=html.unescape(href)
        if href.startswith("/"): href="https://ec.europa.eu"+href
        elif href.startswith("http"): pass
        else: href=urllib.parse.urljoin(BASE,href)
        label=clean(label_html)
        code=re.search(r"(\d{1,2})-(\d{8})-([A-Za-z]{2})",href)
        year=None
        if code:
            year=int(code.group(2)[4:8]); year_hits.append(year)
        kinds=[k for k,pat in target_patterns.items() if pat.search(label)]
        if kinds and href not in seen:
            seen[href]={"url":href,"title":label,"kinds":kinds,"year":year}
            new_count+=1
    print("page",p,"links",len(links),"new targets",new_count,"years",min(year_hits) if year_hits else None,max(year_hits) if year_hits else None)
    if year_hits and max(year_hits)<2020:
        break
    time.sleep(0.15)

targets=[x for x in seen.values() if x.get("year") is None or 2020<=x["year"]<=2026]
targets.sort(key=lambda x:(x.get("year") or 0,x["url"]))

# Verify each target and capture publication metadata / whether key source tables are present.
for n,x in enumerate(targets):
    try:
        page=get(x["url"])
        text=clean(page)
        rm=re.search(r"Release date:\s*([0-9]{1,2}\s+[A-Za-z]+\s+20\d{2})",text,re.I)
        x["release_date_text"]=rm.group(1) if rm else None
        x["has_sts_trtu_m"]="sts_trtu_m" in text.lower()
        x["has_namq_10_pe"]="namq_10_pe" in text.lower()
        x["mentions_thousand_persons"]=bool(re.search(r"thousand persons|thousands of persons",text,re.I))
        x["verified_title_match"]=bool(target_patterns["retail"].search(text) if "retail" in x["kinds"] else target_patterns["employment"].search(text))
    except Exception as e:
        x["fetch_error"]=repr(e)
    if n%25==0: print("verified",n,"of",len(targets))
    time.sleep(0.10)

report={
 "schema":"GMFQ_EUROSTAT_ARCHIVE_MANIFEST_V1",
 "created_at":"2026-10-02",
 "provider":"Eurostat",
 "source":BASE,
 "asset_publisher_instance":inst,
 "window":"2020-2026",
 "targets":targets,
 "qa":{
   "total":len(targets),
   "retail":sum("retail" in x["kinds"] for x in targets),
   "employment":sum("employment" in x["kinds"] for x in targets),
   "retail_with_sts_trtu_m":sum("retail" in x["kinds"] and x.get("has_sts_trtu_m") for x in targets),
   "employment_with_namq_10_pe":sum("employment" in x["kinds"] and x.get("has_namq_10_pe") for x in targets),
   "fetch_errors":sum("fetch_error" in x for x in targets)
 },
 "next_action":"Use verified retail release pages to extract first-published euro-area volume indices. Employment pages require a separate value-level extractor if NAMQ_10_PE levels are not embedded."
}
(OUT/"EUROSTAT_ARCHIVE_MANIFEST_V1_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report["qa"],indent=2))
