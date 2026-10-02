#!/usr/bin/env python3
import io,json,re,time,urllib.request,urllib.parse,html as htmlmod
from pathlib import Path
from pypdf import PdfReader

OUT=Path("validation/pit_batch/eurostat/archive/EUR_RETAIL_VOLUME_CHAIN_PIT_V1_2026-10-02.json")
SEED="https://ec.europa.eu/eurostat/web/products-euro-indicators/w/4-04092026-ap"
UA={"User-Agent":"Mozilla/5.0 GMFQ-retail-chain/3.0"}
MONTHS="January February March April May June July August September October November December".split()
MM={m:i+1 for i,m in enumerate(MONTHS)}

def fetch(url,tries=2,timeout=8):
    last=None
    for attempt in range(tries):
        req=urllib.request.Request(url,headers=UA)
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return r.read(),(r.headers.get("Content-Type") or "").lower(),r.geturl()
        except Exception as e:
            last=e
            time.sleep(0.5*(attempt+1))
    return None,None,None

def textify(raw,ctype):
    if raw[:4]==b"%PDF" or "pdf" in (ctype or ""):
        rd=PdfReader(io.BytesIO(raw))
        return re.sub(r"\s+"," "," ".join((p.extract_text() or "") for p in rd.pages)).strip()
    s=raw.decode("utf-8","ignore")
    s=re.sub(r"<script.*?</script>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def download_pdf_text(raw,ctype,final):
    if raw is None or "html" not in (ctype or ""):
        return None,None
    s=raw.decode("utf-8","ignore")
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',s,flags=re.S|re.I):
        href=htmlmod.unescape(m.group(1))
        label=re.sub(r"<[^>]+>"," ",m.group(2))
        label=re.sub(r"\s+"," ",htmlmod.unescape(label)).strip().lower()
        if label!="download" and ".pdf" not in href.lower():
            continue
        u=urllib.parse.urljoin(final,href)
        r2,c2,f2=fetch(u)
        if r2 is None:
            continue
        try:
            t2=textify(r2,c2)
        except Exception:
            continue
        if "volume of retail trade" in t2.lower() or "retail trade volume" in t2.lower():
            return t2,f2 or u
    return None,None

def parse_release_date(txt):
    m=re.search(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',txt,re.I)
    if not m: return None
    return f"{m.group(3)}-{MM[m.group(2).title()]:02d}-{int(m.group(1)):02d}"

def parse_reference_month(txt):
    m=re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\s+compared with',txt,re.I)
    if not m: return None
    return f"{m.group(2)}-{MM[m.group(1).title()]:02d}"

def parse_mom(txt):
    txt=re.sub(r'(?<=\d)[.,]\s+(?=\d)',lambda m:m.group(0)[0],txt)
    pats=[
      r'Volume of retail trade\s+(up|down)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+(?:both\s+)?(?:the\s+)?euro area',
      r'volume of retail trade.*?(increased|decreased|rose|fell)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+(?:the\s+)?euro area.*?compared with',
      r'seasonally adjusted (?:volume of )?retail trade(?: volume)?\s+(increased|decreased|rose|fell)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+(?:the\s+)?euro area'
    ]
    for p in pats:
        m=re.search(p,txt,re.I|re.S)
        if not m: continue
        d=m.group(1).lower()
        v=float(m.group(2).replace(",","."))
        return (-abs(v) if d in ("down","decreased","fell") else abs(v)),m.group(0)[:700]
    stable=[
      r'Volume of retail trade\s+(?:remained\s+)?stable\s+in\s+(?:the\s+)?euro area',
      r'retail trade volume\s+(?:remained\s+)?stable\s+in\s+(?:the\s+)?euro area'
    ]
    for p in stable:
        m=re.search(p,txt,re.I)
        if m: return 0.0,m.group(0)
    return None,None

def previous_release_date(txt):
    pats=[
      r'Compared with the data issued in the News Release of\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',
      r'[Dd]ata of previous months have been revised compared to those issued in the News Release of\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',
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

def load_candidate(ds):
    for u in candidates(ds):
        raw,ctype,final=fetch(u)
        if raw is None: continue
        try: txt=textify(raw,ctype)
        except Exception: continue
        low=txt.lower()
        if "volume of retail trade" in low or "retail trade volume" in low:
            return raw,ctype,final or u,txt
    return None,None,None,None

def save_progress(rows):
    report=save_progress(rows)
print(json.dumps(report["summary"],indent=2))
