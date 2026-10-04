from pathlib import Path
import json

src=Path('live_data/sections/MACRO_THERMOMETER_DATA.json')
data=json.loads(src.read_text(encoding='utf-8'))
out={'schema':'GMFQ_LIVE_MACRO_REGISTRY_V1','created_at':'2026-10-04','currencies':{}}
for c in ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']:
    d=(data.get('currencies') or {}).get(c,{})
    row={'status':d.get('status'),'inflation':{},'labour':{}}
    for k in ['inflation','labour']:
        x=d.get(k) or {}
        row[k]={
            'series_id':x.get('series_id'),
            'source':x.get('source'),
            'frequency':x.get('frequency'),
            'transformation':x.get('transformation'),
            'as_of':x.get('as_of'),
            'latest_value':x.get('latest_value'),
            'direction':x.get('direction'),
            'acceleration':x.get('acceleration'),
            'validation':x.get('validation'),
            'history_len':len(x.get('history') or [])
        }
    out['currencies'][c]=row
Path('validation/LIVE_MACRO_REGISTRY_2026-10-04.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(out,indent=2,ensure_ascii=False))
