from pathlib import Path
import json

s=json.loads(Path('live_data/sections/MACRO_SERIES.json').read_text(encoding='utf-8'))
d=json.loads(Path('live_data/sections/D.json').read_text(encoding='utf-8'))
out={'schema':'GMFQ_MACRO_CORE_REGISTRY_V2','created_at':'2026-10-04','currencies':{},'currency_macro':{}}
for c,arr in s.items():
    rows=[]
    if isinstance(arr,list):
        for v in arr:
            if not isinstance(v,dict): continue
            dates=v.get('dates') or []
            vals=v.get('values') or []
            rows.append({
                'id':v.get('id'),'label':v.get('label'),'category':v.get('category'),
                'last_date':dates[-1] if dates else v.get('last_date') or v.get('date') or v.get('as_of'),
                'last_value':vals[-1] if vals else v.get('last_value') or v.get('value') or v.get('latest'),
                'n':len(vals),'unit':v.get('unit'),'frequency':v.get('frequency'),'source_file':v.get('source_file')
            })
    out['currencies'][c]=rows
for c in ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']:
    m=(d.get('macro') or {}).get(c,{})
    keep={k:m.get(k) for k in ['macro','macro_score','macro_status','macro_dir','macro_accel','macro_turn','growth','labour','inflation','gdp','unemployment','rate2y','as_of','date'] if k in m}
    out['currency_macro'][c]=keep
Path('validation/MACRO_CORE_REGISTRY_2026-10-04.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({c:[(x['id'],x['category'],x['last_date']) for x in rows] for c,rows in out['currencies'].items()},indent=2,ensure_ascii=False))
