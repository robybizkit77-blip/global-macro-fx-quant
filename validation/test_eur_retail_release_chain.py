#!/usr/bin/env python3
import io,json,re,urllib.request,html as htmlmod,urllib.parse
from pypdf import PdfReader

URL="https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/4-06022024-ap"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 GMFQ-retail-download-diagnostic/1.0"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); ctype=(r.headers.get("Content-Type") or "").lower(); final=r.geturl()
s=raw.decode("utf-8","ignore")
anchors=[]
for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',s,flags=re.S|re.I):
    href=htmlmod.unescape(m.group(1)); label=re.sub(r"<[^>]+>"," ",m.group(2)); label=re.sub(r"\s+"," ",htmlmod.unescape(label)).strip()
    if "download" in label.lower() or "pdf" in href.lower() or "documents/" in href.lower():
        anchors.append({"label":label,"href":urllib.parse.urljoin(final,href)})
print(json.dumps({"url":final,"ctype":ctype,"anchors":anchors[:30]},indent=2))
