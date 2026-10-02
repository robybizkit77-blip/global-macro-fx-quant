#!/usr/bin/env python3
import io,json,re,time,urllib.request,urllib.parse,html as htmlmod
from pathlib import Path
from pypdf import PdfReader

OUT=Path("validation/pit_batch/eurostat/archive/EUR_RETAIL_VOLUME_CHAIN_PIT_V1_2026-10-02.json")
SEED="https://ec.europa.eu/eurostat/web/products-euro-indicators/w/4-04092026-ap"
UA={"User-Agent":"Mozilla/5.0 GMFQ-retail-chain/6.0"}
MONTHS="January February March April May June July August September October November December".split()
MM={m:i+1 for i,m in enumerate(MONTHS)}

def fetch(url,tries=5,timeout=15):
    for attempt in range(tries):
        req=urllib.request.Request(url,headers=UA)
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return r.read(),(r.headers.get("Content-Type") or "").lower(),r.geturl()
        except Exception:
            time.sleep(1.0*(attempt+1))
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
        low=t2.lower()
        if "volume of retail trade" in low or "retail trade volume" in low:
            return t2,f2 or u
    return None,None

def parse_release_date(txt):
    m=re.search(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',txt,re.I)
    if not m: return None
    return f"{m.group(3)}-{MM[m.group(2).title()]:02d}-{int(m.group(1)):02d}"

def parse_reference_month(txt):
    pats=[
      r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\s+compared with',
      r'In\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2}),',
    ]
    for p in pats:
        m=re.search(p,txt,re.I)
        if m:
            return f"{m.group(2)}-{MM[m.group(1).title()]:02d}"
    return None

def parse_mom(txt):
    txt=re.sub(r'(?<=\d)[.,]\s+(?=\d)',lambda m:m.group(0)[0],txt)
    # Headline stable/unchanged must win before any broad narrative fallback.
    for p in [
      r'Volume of retail trade\s+(?:remained\s+)?stable\s+in\s+(?:both\s+)?(?:the\s+)?euro area',
      r'retail trade volume\s+(?:remained\s+)?stable\s+in\s+(?:both\s+)?(?:the\s+)?euro area',
      r'Volume of retail trade\s+unchanged\s+in\s+(?:both\s+)?(?:the\s+)?euro area'
    ]:
        m=re.search(p,txt,re.I)
        if m: return 0.0,m.group(0)
    # Exact headline directional wording.
    m=re.search(r'Volume of retail trade\s+(up|down)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+(?:both\s+)?(?:the\s+)?euro area',txt,re.I)
    if m:
        d=m.group(1).lower(); v=float(m.group(2).replace(",","."))
        return (-abs(v) if d=="down" else abs(v)),m.group(0)[:700]
    # Narrative fallbacks are deliberately bounded so they cannot jump from the
    # release title to a later country/EU sentence and capture the wrong number.
    pats=[
      r'volume of retail trade.{0,500}?(increased|decreased|rose|fell)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+(?:the\s+)?euro area.{0,250}?compared with',
      r'seasonally adjusted (?:volume of )?retail trade(?: volume)?\s+(increased|decreased|rose|fell)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+(?:the\s+)?euro area'
    ]
    for p in pats:
        m=re.search(p,txt,re.I|re.S)
        if not m: continue
        d=m.group(1).lower()
        v=float(m.group(2).replace(",","."))
        return (-abs(v) if d in ("down","decreased","fell") else abs(v)),m.group(0)[:700]
    return None,None

def previous_release_date(txt):
    pats=[
      r'Compared with the data issued in the News Release of\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',
      r'[Dd]ata of previous months have been revised compared to those issued in the News Release of\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',
      r'revised compared to the News Release of\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',
      r'News Release\s+\d+/\d+\s+of\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',
      r'News Release[^.]{0,100}?of\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})'
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
    # Two complete passes protect the deterministic chain from transient Eurostat timeouts.
    for _pass in range(2):
        for u in candidates(ds):
            raw,ctype,final=fetch(u,tries=4,timeout=15)
            if raw is None: continue
            try:
                txt=textify(raw,ctype)
            except Exception:
                continue
            low=txt.lower()
            if "volume of retail trade" in low or "retail trade volume" in low:
                return raw,ctype,final or u,txt
        time.sleep(2)
    return None,None,None,None

def build_report(rows):
    valid=[x for x in rows if x.get("reference_month") and x.get("retail_volume_mom_pct") is not None]
    by={x["reference_month"]:x for x in valid}
    expected=[]
    y,m=2020,6
    while (y,m)<=(2026,7):
        expected.append(f"{y}-{m:02d}")
        m+=1
        if m==13:
            y+=1;m=1
    missing=[x for x in expected if x not in by]
    return {
      "schema":"GMFQ_EUR_RETAIL_VOLUME_CHAIN_PIT_V1",
      "created_at":"2026-10-02",
      "source":"Eurostat official Volume of retail trade releases",
      "method":"Backward deterministic chain with persistent checkpoints. Each release identifies the preceding News Release date in its revisions section; transient fetch failures do not discard completed history.",
      "rows":rows,
      "summary":{
        "chain_rows":len(rows),
        "expected_months":len(expected),
        "parsed_months":len(by),
        "coverage_pct":round(100*len(by)/len(expected),2),
        "from":min(by) if by else None,
        "to":max(by) if by else None,
        "missing":missing,
        "complete":len(missing)==0,
        "terminal_error":rows[-1].get("error") if rows else None
      },
      "guardrail":"No current revised retail history is substituted. Every retained monthly change comes from its dated Eurostat release."
    }

def save_progress(rows):
    report=build_report(rows)
    OUT.write_text(json.dumps(report,indent=2)+"\n")
    return report

# Resume from the oldest successfully parsed checkpoint if a partial chain exists.
rows=[]
resume_date=None
if OUT.exists():
    try:
        old=json.loads(OUT.read_text())
        rows=[]
        for x in old.get("rows",[]):
            if not (x.get("reference_month") and x.get("retail_volume_mom_pct") is not None):
                continue
            # Sanitize rows produced by the older permissive parser: if the
            # captured text itself says the headline was stable, the correct
            # release-time monthly change is mechanically 0.0.
            mt=(x.get("match_text") or "").lower()
            if "stable" in mt or "unchanged" in mt:
                x["retail_volume_mom_pct"]=0.0
                x["parser_sanitized_v6"]=True
            rows.append(x)
        if rows and old.get("summary",{}).get("complete") is not True:
            resume_date=rows[-1].get("previous_release_date")
    except Exception:
        rows=[]
        resume_date=None

if resume_date:
    raw,ctype,final,txt=load_candidate(resume_date)
    url=final or (candidates(resume_date)[0] if resume_date else SEED)
else:
    raw,ctype,final=fetch(SEED)
    txt=textify(raw,ctype) if raw else None
    url=SEED

guard=0
while txt and guard<90:
    guard+=1
    rd=parse_release_date(txt)
    ref=parse_reference_month(txt)
    val,matched=parse_mom(txt)
    pd,pm=previous_release_date(txt)
    pdf_url=None
    if not ref or not pd:
        extra,pdf_url=download_pdf_text(raw,ctype,final or url)
        if extra:
            combo=txt+" "+extra
            ref=parse_reference_month(combo) or ref
            if val is None:
                val,matched=parse_mom(combo)
            pd2,pm2=previous_release_date(combo)
            pd=pd2 or pd
            pm=pm2 or pm
    # Avoid duplicating a checkpoint already present after a retry/resume.
    if not any(x.get("release_date")==rd for x in rows):
        rows.append({
          "release_date":rd,
          "reference_month":ref,
          "retail_volume_mom_pct":val,
          "url":final or url,
          "pdf_url":pdf_url,
          "content_type":ctype,
          "match_text":matched,
          "previous_release_date":pd,
          "previous_match":pm
        })
    save_progress(rows)
    if ref and ref<="2020-06":
        break
    if not pd:
        rows.append({"release_date":rd,"reference_month":None,"retail_volume_mom_pct":None,"url":final or url,"error":"PREVIOUS_RELEASE_DATE_NOT_PARSED"})
        save_progress(rows)
        break
    raw2,ctype2,final2,txt2=load_candidate(pd)
    if raw2 is None:
        rows.append({
          "release_date":pd,
          "reference_month":None,
          "retail_volume_mom_pct":None,
          "url":None,
          "error":"PREVIOUS_RELEASE_URL_NOT_RESOLVED_TRANSIENT_OR_PATTERN"
        })
        save_progress(rows)
        break
    raw,ctype,final,txt=raw2,ctype2,final2,txt2
    url=final2 or url
    time.sleep(.2)

report=save_progress(rows)
print(json.dumps(report["summary"],indent=2))
