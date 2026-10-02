#!/usr/bin/env python3
import io,json,re,urllib.request
from pypdf import PdfReader

URL="https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/4-06022024-ap"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 GMFQ-retail-format-diagnostic/1.0"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); ctype=(r.headers.get("Content-Type") or "").lower(); final=r.geturl()
if raw[:4]==b"%PDF" or "pdf" in ctype:
    rd=PdfReader(io.BytesIO(raw))
    txt=" ".join((p.extract_text() or "") for p in rd.pages)
else:
    txt=raw.decode("utf-8","ignore")
    txt=re.sub(r"<script.*?</script>"," ",txt,flags=re.S|re.I)
    txt=re.sub(r"<style.*?</style>"," ",txt,flags=re.S|re.I)
    txt=re.sub(r"<[^>]+>"," ",txt)
txt=re.sub(r"\s+"," ",txt).strip()
contexts=[]
for pat in ["Revisions","revised","News Release","December 2023","January 2024","retail trade"]:
    m=re.search(pat,txt,re.I)
    contexts.append({"pattern":pat,"found":bool(m),"context":txt[max(0,m.start()-600):m.start()+1400] if m else None})
print(json.dumps({"url":final,"ctype":ctype,"chars":len(txt),"head":txt[:1200],"contexts":contexts},indent=2))
