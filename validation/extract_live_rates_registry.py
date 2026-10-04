from pathlib import Path
import json

src=Path('live_data/sections/NATIVE_RATES_DATA.json')
data=json.loads(src.read_text(encoding='utf-8'))
out={'schema':'GMFQ_LIVE_RATES_REGISTRY_V1','created_at':'2026-10-04','currencies':{}}
for c in ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']:
    d=data.get(c,{})
    h2=d.get('history2') or {}
    h10=d.get('history10') or {}
    out['currencies'][c]={
        'date':d.get('date'),
        'source':d.get('source'),
        'quality':d.get('quality'),
        'y2':d.get('2Y'),
        'y10':d.get('10Y'),
        'curve_bp':d.get('curve_bp'),
        'chg2_bp':d.get('chg2_bp'),
        'chg10_bp':d.get('chg10_bp'),
        'curve_state':d.get('curve_state'),
        'history2_last_date':h2.get('last_date') or ((h2.get('dates') or [None])[-1]),
        'history10_last_date':h10.get('last_date') or ((h10.get('dates') or [None])[-1]),
        'history2_len':len(h2.get('values') or []),
        'history10_len':len(h10.get('values') or []),
        'freshness_status':d.get('freshness_status'),
        'history_status':d.get('history_status')
    }
Path('validation/LIVE_RATES_REGISTRY_2026-10-04.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
