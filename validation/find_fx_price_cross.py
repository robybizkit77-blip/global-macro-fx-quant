from pathlib import Path
import json,re
p=Path('history/MACRO_SERIES_2016_2026_RUNTIME_ARCHIVE_2026-10-01.js')
text=p.read_text(encoding='utf-8',errors='ignore')
needles=['EURUSD','USDCAD','EUR_CAD','EUR/CAD','ECB']
out={}
for n in needles:
    hits=[]
    for m in re.finditer(re.escape(n),text,re.I):
        a=max(0,m.start()-1000); b=min(len(text),m.end()+2000)
        hits.append({'offset':m.start(),'snippet':text[a:b]})
        if len(hits)>=5: break
    out[n]=hits
Path('validation/FX_PRICE_CROSS_LOCATOR_2026-10-03.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print({k:len(v) for k,v in out.items()})
