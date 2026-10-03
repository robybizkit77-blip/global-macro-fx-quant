from pathlib import Path
import json

needle='EURCAD'
hits=[]
for root in [Path('payload'), Path('history'), Path('validation')]:
    if not root.exists():
        continue
    for p in root.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in {'.txt','.js','.json','.csv','.html'}:
            continue
        try:
            text=p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        pos=text.find(needle)
        if pos>=0:
            hits.append({
                'path': str(p),
                'offset': pos,
                'snippet': text[max(0,pos-1200):pos+2400]
            })
            if len(hits)>=12:
                break
    if len(hits)>=12:
        break
out={'needle':needle,'hits':hits}
Path('validation/EURCAD_PRICE_LOCATOR_2026-10-03.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'hits':len(hits),'locations':[(h['path'],h['offset']) for h in hits]},indent=2))
