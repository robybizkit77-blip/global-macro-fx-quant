#!/usr/bin/env python3
import io,json,re,urllib.request,time
from pypdf import PdfReader

SEED="https://ec.europa.eu/eurostat/web/products-euro-indicators/w/4-04092026-ap"
UA={"User-Agent":"Mozilla/5.0 GMFQ-retail-chain/2.0"}
MONTHS="January February March April May June July August September October November December".split()
MM={m:i+1 for i,m in enumerate(MONTHS)}

def fetch(url):
    req=urllib.request.Request(url,headers=UA)
    try:
        with urllib.request.urlopen(req,timeout=15) as r:
            return r.read(),(r.headers.get("Content-Type") or "").lower(),r.geturl()
    except Exception:
        return None,None,None

def textify(raw,ctype):
    if raw[:4]==b"%PDF" or "pdf" in ctype:
        rd=PdfReader(io.BytesIO(raw))
        return re.sub(r"\s+"," "," ".join((p.extract_text() or "") for p in rd.pages)).strip()
    s=raw.decode("utf-8","ignore")
    s=re.sub(r"<script.*?</script>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def previous_release_date(txt):
    pats=[
      r'revised compared to those issued in the News Release of\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',
      r'revised compared to the News Release of\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',
      r'News Release\s+\d+/\d+\s+of\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})'
    ]
    for p in pats:
        m=re.search(p,txt,re.I)
        if m:
            return f"{m.group(3)}-{MM[m.group(2).title()]:02d}-{int(m.group(1)):02d}",m.group(0)
    return None,None

def candidates(ds):
    y,m,d=ds.split("-"); code=f"{d}{m}{y}"
    bases=[
      "https://ec.europa.eu/eurostat/web/products-euro-indicators/w/",
      "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/",
      "https://ec.europa.eu/eurostat/web/products-euro-indicators/-/",
      "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/-/",
    ]
    return [f"{b}4-{code}-{s}" for b in bases for s in ("ap","bp")]

rows=[]
url=SEED
for step in range(8):
    raw,ctype,final=fetch(url)
    if raw is None:
        rows.append({"step":step,"url":url,"fetch_ok":False}); break
    txt=textify(raw,ctype)
    pd,pm=previous_release_date(txt)
    rows.append({"step":step,"url":final or url,"fetch_ok":True,"content_type":ctype,"text_chars":len(txt),"previous_date":pd,"previous_match":pm,"head":txt[:350]})
    if not pd: break
    found=None
    for u in candidates(pd):
        r2,c2,f2=fetch(u)
        if r2 is None: continue
        t2=textify(r2,c2)
        if "volume of retail trade" in t2.lower() or "retail trade volume" in t2.lower():
            found=f2 or u; break
    if not found:
        rows.append({"step":step+1,"target_date":pd,"candidate_fetch_found":False}); break
    url=found
    time.sleep(.1)

print(json.dumps(rows,indent=2))
