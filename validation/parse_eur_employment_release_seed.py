#!/usr/bin/env python3
import io,json,re,time,urllib.request
from pathlib import Path
from pypdf import PdfReader

SEED=Path("validation/pit_batch/eurostat/archive/EUR_EMPLOYMENT_OFFICIAL_RELEASE_SEED_V1_2026-10-02.json")
OUT=Path("validation/pit_batch/eurostat/archive/EUR_EMPLOYMENT_RELEASE_PARSE_PILOT_V1_2026-10-02.json")
seed=json.loads(SEED.read_text(encoding="utf-8"))

def fetch_bytes(url):
    last=None
    for attempt in range(5):
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GMFQ-validation/2.0"})
        try:
            with urllib.request.urlopen(req,timeout=30) as r:
                return r.read(), (r.headers.get("Content-Type") or "").lower()
        except Exception as e:
            last=e
            if "429" not in str(e):
                raise
            time.sleep(2*(attempt+1))
    raise last

def html_to_text(raw):
    s=raw.decode("utf-8","ignore")
    s=re.sub(r"<script.*?</script>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def pdf_to_text(raw):
    reader=PdfReader(io.BytesIO(raw))
    return re.sub(r"\s+"," "," ".join((p.extract_text() or "") for p in reader.pages)).strip()

def employment_contexts(txt, limit=4):
    out=[]
    for m in re.finditer(r'employ',txt,re.I):
        a=max(0,m.start()-220); b=min(len(txt),m.start()+520)
        sn=re.sub(r'\s+',' ',txt[a:b]).strip()
        if sn not in out:
            out.append(sn)
        if len(out)>=limit:
            break
    return out

def extract_qoq(txt):
    txt=re.sub(r'(?<=\d)[.,]\s+(?=\d)', lambda m: m.group(0)[0], txt)
    head=txt[:3500]
    m=re.search(r'GDP\s+(?:up|down|stable).*?employment\s+(up|down)\s+by\s+([+-]?\d+(?:[.,]\d+)?)%\s+in\s+(?:both\s+)?the euro area',head,re.I|re.S)
    if m:
        d=m.group(1).lower(); v=float(m.group(2).replace(",","."))
        return (-abs(v) if d=="down" else abs(v)),m.group(0)[:700]
    m=re.search(r'GDP\s+(?:up|down|stable).*?employment\s+(stable|unchanged)\s+in\s+(?:both\s+)?the euro area',head,re.I|re.S)
    if m:
        return 0.0,m.group(0)[:700]
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

rows=[]
for x in seed["releases"]:
    try:
        raw,ctype=fetch_bytes(x["url"])
        is_pdf=("pdf" in ctype) or raw[:4]==b"%PDF"
        txt=pdf_to_text(raw) if is_pdf else html_to_text(raw)
        val,matched=extract_qoq(txt)
        rows.append({
          **x,
          "fetch_ok":True,
          "content_type":ctype,
          "parsed_as":"pdf" if is_pdf else "html",
          "text_chars":len(txt),
          "employment_qoq_pct":val,
          "match_text":matched,
          "employment_contexts":[] if val is not None else employment_contexts(txt)
        })
    except Exception as e:
        rows.append({**x,"fetch_ok":False,"error":str(e),"employment_qoq_pct":None,"match_text":None})

ok=[r for r in rows if r.get("fetch_ok")]
parsed=[r for r in rows if r.get("employment_qoq_pct") is not None]
report={
 "schema":"GMFQ_EUR_EMPLOYMENT_RELEASE_PARSE_PILOT_V2",
 "created_at":"2026-10-02",
 "seed_count":len(rows),
 "fetch_ok":len(ok),
 "parsed_qoq":len(parsed),
 "coverage_pct":round(100*len(parsed)/len(rows),2) if rows else 0,
 "rows":rows,
 "status":"PARSER_VALIDATED_FULL" if len(parsed)==len(rows) else ("PARSER_VALIDATED_PARTIAL" if len(parsed)>=8 else "PARSER_NOT_YET_VALIDATED"),
 "guardrail":"Parsed q/q flash growth rates are release-time observables. Do not equate them mechanically to the runtime level series until the level-path transformation and parity test are completed."
}
OUT.write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"seed_count":len(rows),"fetch_ok":len(ok),"parsed_qoq":len(parsed),"coverage_pct":report["coverage_pct"],"status":report["status"]},indent=2))
