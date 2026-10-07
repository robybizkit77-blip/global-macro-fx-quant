import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SRC=ROOT.parent/'live_data'/'sections'/'NATIVE_LIQ_DATA.json'
OUT=ROOT/'LIQUIDITY_COMPACT_PAYLOAD_V1_2026-10-07.json'

def series_read(x):
    if not isinstance(x,dict):
        return {'status':'UNAVAILABLE','direction':None,'last_date':None}
    vals=x.get('values') or []
    dates=x.get('dates') or []
    if len(vals)<2:
        return {'status':'INSUFFICIENT_HISTORY','direction':None,'last_date':x.get('last_date') or (dates[-1] if dates else None)}
    a,b=vals[-2],vals[-1]
    if a is None or b is None:
        direction=None
    elif b>a:
        direction='UP'
    elif b<a:
        direction='DOWN'
    else:
        direction='FLAT'
    return {
        'status':'AVAILABLE',
        'direction':direction,
        'last_date':x.get('last_date') or (dates[-1] if dates else None),
        'label':x.get('label')
    }

data=json.loads(SRC.read_text())
out={
 'schema':'GMFQ_LIQUIDITY_COMPACT_PAYLOAD_V1',
 'status':'RESEARCH_ONLY_CONTEXT_NOT_PROMOTED',
 'purpose':'Compact liquidity/credit context by currency. Descriptive only; not an FX directional score or gate.',
 'currencies':{},
 'guards':{
   'universal_score':False,
   'fx_directional_override':False,
   'trade_signal':False,
   'changes_engine_rules':False,
   'changes_live_data':False,
   'production_promotion':False
 }
}
for c in ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']:
    d=data.get(c) or {}
    comps={k:series_read(d.get(k)) for k in ('liquidity','money','credit')}
    dirs=[v['direction'] for v in comps.values() if v['status']=='AVAILABLE' and v['direction'] in ('UP','DOWN')]
    if not dirs:
        read='WITHHELD'
    elif all(x=='UP' for x in dirs):
        read='ESPANSIONE'
    elif all(x=='DOWN' for x in dirs):
        read='CONTRAZIONE'
    else:
        read='MISTA'
    out['currencies'][c]={
      'currency':c,
      'source_status':d.get('status','UNKNOWN'),
      'context_read':read,
      'components':comps,
      'note_it':'Contesto di liquidità/credito: non modifica automaticamente il bias macro o FX.'
    }
OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({c:v['context_read'] for c,v in out['currencies'].items()},ensure_ascii=False))
