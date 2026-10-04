from pathlib import Path
import json

s=json.loads(Path('live_data/sections/MACRO_SERIES.json').read_text(encoding='utf-8'))
d=json.loads(Path('live_data/sections/D.json').read_text(encoding='utf-8'))
out={'schema':'GMFQ_MACRO_CORE_REGISTRY_V1','created_at':'2026-10-04','series':{},'currency_macro':{}}
for k,v in s.items():
    if not isinstance(v,dict): continue
    dates=v.get('dates') or []
    vals=v.get('values') or []
    out['series'][k]={
        'last_date':dates[-1] if dates else v.get('date') or v.get('as_of'),
        'last_value':vals[-1] if vals else v.get('value') or v.get('latest'),
        'n':len(vals),
        'label':v.get('label'),
        'source':v.get('source'),
        'frequency':v.get('frequency'),
        'keys':list(v.keys())[:15]
    }
for c in ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']:
    m=(d.get('macro') or {}).get(c,{})
    keep={k:m.get(k) for k in ['macro','macro_score','macro_status','macro_dir','macro_accel','macro_turn','growth','labour','inflation','gdp','unemployment','rate2y','as_of','date'] if k in m}
    out['currency_macro'][c]=keep
Path('validation/MACRO_CORE_REGISTRY_2026-10-04.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({'series_count':len(out['series']),'currency_macro':out['currency_macro']},indent=2,ensure_ascii=False))
