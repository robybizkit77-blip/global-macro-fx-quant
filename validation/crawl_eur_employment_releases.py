#!/usr/bin/env python3
import io,json,re,time,urllib.request
from pathlib import Path
from datetime import date,timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pypdf import PdfReader

OUTDIR=Path("validation/pit_batch/eurostat/archive")
OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"EUR_EMPLOYMENT_DATED_RELEASE_CRAWL_V1_2026-10-02.json"

def fetch_bytes(url):
    last=None
    for attempt in range(4):
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GMFQ-validation/4.0"})
        try:
            with urllib.request.urlopen(req,timeout=25) as r:
                return r.read(), (r.headers.get("Content-Type") or "").lower(), r.geturl()
        except Exception as e:
            last=e
            s=str(e)
            if "404" in s:
                return None,None,None
            if "429" in s or "timed out" in s.lower():
                time.sleep(1.5*(attempt+1))
                continue
            return None,None,None
    return None,None,None

def html_to_text(raw):
    s=raw.decode("utf-8","ignore")
    s=re.sub(r"<script.*?</script>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def pdf_to_text(raw):
    reader=PdfReader(io.BytesIO(raw))
    return re.sub(r"\s+"," "," ".join((p.extract_text() or "") for p in reader.pages)).strip()

def extract_qoq(txt):
    txt=re.sub(r'(?<=\d)[.,]\s+(?=\d)', lambda m: m.group(0)[0], txt)
    head=txt[:3500]
    # Headline is the cleanest flash-release value.
    m=re.search(r'GDP\s+(?:up|down|stable).*?employment\s+(up|down)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+(?:both\s+)?the euro area',head,re.I|re.S)
    if m:
        d=m.group(1).lower(); v=float(m.group(2).replace(",","."))
        return (-abs(v) if d=="down" else abs(v)),m.group(0)[:700]
    m=re.search(r'GDP\s+(?:up|down|stable).*?employment\s+(stable|unchanged)\s+in\s+(?:both\s+)?the euro area',head,re.I|re.S)
    if m:
        return 0.0,m.group(0)[:700]
    # Narrative fallback requires explicit previous-quarter context and euro-area value.
    pats=[
      r'(?:number of employed persons|employment)\s+(increased|decreased)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+(?:both\s+)?the euro area.*?compared with the previous quarter',
      r'(?:number of employed persons|employment)\s+(remained stable|was stable|remained unchanged)\s+in\s+(?:both\s+)?the euro area.*?compared with the previous quarter'
    ]
    for p in pats:
        m=re.search(p,txt,re.I|re.S)
        if not m: continue
        d=m.group(1).lower()
        if "stable" in d or "unchanged" in d:
            return 0.0,m.group(0)[:700]
        v=float(m.group(2).replace(",","."))
        return (-abs(v) if d=="decreased" else abs(v)),m.group(0)[:700]
    return None,None

def quarter_label(y,q):
    return f"{y}-Q{q}"

def expected_release_window(y,q):
    # Eurostat employment flash: Q1 May, Q2 Aug, Q3 Nov, Q4 following Feb.
    if q==1: return date(y,5,12),date(y,5,18)
    if q==2: return date(y,8,12),date(y,8,18)
    if q==3: return date(y,11,12),date(y,11,18)
    return date(y+1,2,12),date(y+1,2,18)

# Verified seed URLs override discovery and reduce requests.
seed_path=OUTDIR/"EUR_EMPLOYMENT_OFFICIAL_RELEASE_SEED_V1_2026-10-02.json"
seed={}
if seed_path.exists():
    sj=json.loads(seed_path.read_text())
    for x in sj.get("releases",[]):
        if x.get("kind")=="flash":
            seed[x["reference_quarter"]]=x

def crawl_one(y,q):
    ref=quarter_label(y,q)
    candidates=[]
    if ref in seed:
        candidates.append((seed[ref]["release_date"],seed[ref]["url"],"seed"))
    a,b=expected_release_window(y,q)
    d=a
    while d<=b:
        dd=d.strftime("%d%m%Y")
        ds=d.isoformat()
        candidates.append((ds,f"https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-{dd}-ap","scan"))
        d+=timedelta(days=1)
    seen=set()
    for ds,url,mode in candidates:
        if url in seen: continue
        seen.add(url)
        raw,ctype,final=fetch_bytes(url)
        if raw is None: continue
        try:
            is_pdf=("pdf" in (ctype or "")) or raw[:4]==b"%PDF"
            txt=pdf_to_text(raw) if is_pdf else html_to_text(raw)
        except Exception:
            continue
        low=txt.lower()
        if "employment" not in low or "euro area" not in low: continue
        qwords={1:"first",2:"second",3:"third",4:"fourth"}
        if not re.search(rf'{qwords[q]} quarter of {y}',txt,re.I): continue
        val,matched=extract_qoq(txt)
        if val is None: continue
        return {
          "reference_quarter":ref,
          "release_date":ds,
          "employment_qoq_pct":val,
          "url":final or url,
          "discovery":mode,
          "match_text":matched
        }
    return {
      "reference_quarter":ref,
      "release_date":None,
      "employment_qoq_pct":None,
      "url":None,
      "discovery":"missing"
    }

targets=[]
for y in range(2020,2027):
    for q in range(1,5):
        ref=quarter_label(y,q)
        if "2020-Q2" <= ref <= "2026-Q2":
            targets.append((y,q))

rows=[]
with ThreadPoolExecutor(max_workers=3) as ex:
    futs={ex.submit(crawl_one,y,q):(y,q) for y,q in targets}
    for fut in as_completed(futs):
        rows.append(fut.result())
rows.sort(key=lambda x:x["reference_quarter"])

valid=[x for x in rows if x["employment_qoq_pct"] is not None]
report={
 "schema":"GMFQ_EUR_EMPLOYMENT_DATED_RELEASE_CRAWL_V1",
 "created_at":"2026-10-02",
 "target":{"runtime_id":"EA_EMPLOYMENT_history_value","source":"Eurostat GDP and employment flash estimates"},
 "rows":rows,
 "summary":{
   "count":len(rows),
   "parsed":len(valid),
   "coverage_pct":round(100*len(valid)/len(rows),2) if rows else 0,
   "from":rows[0]["reference_quarter"] if rows else None,
   "to":rows[-1]["reference_quarter"] if rows else None,
   "missing":[x["reference_quarter"] for x in rows if x["employment_qoq_pct"] is None],
   "complete":len(valid)==len(rows)
 },
 "guardrail":"Only dated Eurostat first-publication q/q employment growth is stored. Current revised levels are never substituted for missing releases."
}
OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report["summary"],indent=2))
