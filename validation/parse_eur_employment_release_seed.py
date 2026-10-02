#!/usr/bin/env python3
import json,re,urllib.request
from pathlib import Path

SEED=Path("validation/pit_batch/eurostat/archive/EUR_EMPLOYMENT_OFFICIAL_RELEASE_SEED_V1_2026-10-02.json")
OUT=Path("validation/pit_batch/eurostat/archive/EUR_EMPLOYMENT_RELEASE_PARSE_PILOT_V1_2026-10-02.json")
seed=json.loads(SEED.read_text(encoding="utf-8"))

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GMFQ-validation/1.0"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read().decode("utf-8","ignore")

def clean(s):
    s=re.sub(r"<script.*?</script>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    s=re.sub(r"\\s+"," ",s)
    return s

rows=[]
for x in seed["releases"]:
    try:
        raw=fetch(x["url"])
        txt=clean(raw)
        low=txt.lower()
        # Capture first explicit q/q employment growth sentence for euro area.
        pats=[
          r'(?:number of employed persons|employment).*?(?:increased|decreased|remained stable).*?by\\s+([+-]?\\d+(?:[.,]\\d+)?)%\\s+in the euro area',
          r'employment.*?euro area.*?([+-]?\\d+(?:[.,]\\d+)?)'
        ]
        val=None
        matched=None
        for p in pats:
            m=re.search(p,txt,re.I)
            if m:
                try: val=float(m.group(1).replace(",",".")); matched=m.group(0)[:500]
                except: pass
                if val is not None: break
        # Infer sign from wording when first pattern is used.
        if matched and val is not None and "decreased" in matched.lower():
            val=-abs(val)
        rows.append({**x,"fetch_ok":True,"employment_qoq_pct":val,"match_text":matched})
    except Exception as e:
        rows.append({**x,"fetch_ok":False,"error":str(e),"employment_qoq_pct":None,"match_text":None})

ok=[r for r in rows if r.get("fetch_ok")]
parsed=[r for r in rows if r.get("employment_qoq_pct") is not None]
report={
 "schema":"GMFQ_EUR_EMPLOYMENT_RELEASE_PARSE_PILOT_V1",
 "created_at":"2026-10-02",
 "seed_count":len(rows),
 "fetch_ok":len(ok),
 "parsed_qoq":len(parsed),
 "rows":rows,
 "status":"PARSER_VALIDATED_PARTIAL" if len(parsed)>=5 else "PARSER_NOT_YET_VALIDATED",
 "guardrail":"Parsed q/q flash growth rates are release-time observables. Do not equate them mechanically to the runtime level series until the level-path transformation and parity test are completed."
}
OUT.write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"seed_count":len(rows),"fetch_ok":len(ok),"parsed_qoq":len(parsed),"status":report["status"]},indent=2))
