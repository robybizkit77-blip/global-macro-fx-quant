#!/usr/bin/env python3
import json
from datetime import date, datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OIS=ROOT/'live_data/sections/OIS_OPERATIONAL_VIEW.json'
MACRO=ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json'
OUT=ROOT/'live_data/sections/NEWS_PULSE_OPERATIONAL.json'
ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

def parse_asof(raw):
    s=str(raw or '')
    import re
    m=re.search(r'(20\d{2})-(\d{2})-(\d{2})',s)
    if m:
        return date(int(m.group(1)),int(m.group(2)),int(m.group(3)))
    m=re.search(r'(20\d{2})-(\d{2})',s)
    if m:
        return date(int(m.group(1)),int(m.group(2)),1)
    return None

def iso(d): return d.isoformat() if d else None

def ois_items(data):
    out=[]
    for ccy,row in (data.get('currencies') or {}).items():
        moves=[]
        for h in ('3m','6m','12m'):
            v=((row.get('horizons') or {}).get(h) or {}).get('change_1d_bp')
            if v is not None:
                moves.append((abs(float(v)),h,float(v)))
        if not moves:
            continue
        _,h,v=max(moves)
        hrow=(row.get('horizons') or {}).get(h) or {}
        weekly=hrow.get('change_1w_bp')
        tone='più hawkish' if v>0 else 'più dovish' if v<0 else 'invariato'
        title=f'{ccy}: repricing OIS {tone} ({v:+.1f} bp {h.upper()} in 1D)'
        detail=f"Movimento 1D {v:+.1f} bp sul bucket {h.upper()}"
        if weekly is not None:
            detail+=f"; variazione 1W {float(weekly):+.1f} bp."
        else:
            detail+='; riferimento 1W non disponibile.'
        out.append({
            'category':'OIS_REPRICING','ccy':ccy,'as_of':row.get('as_of'),'title':title,
            'detail':detail,'quality':row.get('quality'),'confidence':row.get('confidence'),
            'source':row.get('source'),'importance':'HIGH' if abs(v)>=2 else 'MEDIUM',
            '_date':parse_asof(row.get('as_of'))
        })
    return out

def macro_items(data):
    today=date.today(); out=[]
    for ccy,row in (data.get('currencies') or {}).items():
        candidates=[]
        for layer in ('inflation','labour'):
            x=row.get(layer) or {}
            d=parse_asof(x.get('as_of'))
            if d:
                candidates.append((d,layer,x))
        if not candidates:
            continue
        d,layer,x=max(candidates,key=lambda z:z[0])
        if (today-d).days>45:
            continue
        label=x.get('label') or layer.title()
        val=x.get('latest_value')
        direction=x.get('direction') or 'N/D'
        acceleration=x.get('acceleration') or 'N/D'
        title=f'{ccy}: {label} {direction.lower()} · {acceleration.lower()}'
        detail=f"Ultimo valore {val}; percentile storico {x.get('percentile')}%; stato {x.get('temperature_label')}."
        out.append({
            'category':'MACRO_UPDATE','ccy':ccy,'as_of':x.get('as_of'),'title':title,'detail':detail,
            'quality':'CERTIFIED_MACRO_LAYER','confidence':'A','source':x.get('source'),
            'importance':'HIGH' if x.get('temperature_label') in ('MOLTO_CALDO','MOLTO_FREDDO') else 'MEDIUM',
            '_date':d
        })
    return out

def main():
    ois=json.loads(OIS.read_text(encoding='utf-8'))
    macro=json.loads(MACRO.read_text(encoding='utf-8'))
    items=ois_items(ois)+macro_items(macro)
    items.sort(key=lambda x:(x['_date'] or date.min, x['importance']=='HIGH', -ORDER.index(x['ccy']) if x['ccy'] in ORDER else 0), reverse=True)
    for x in items:
        x.pop('_date',None)
    items=items[:12]
    latest=max((parse_asof(x.get('as_of')) for x in items if parse_asof(x.get('as_of'))), default=None)
    out={
        'schema':'GMFQ_NEWS_PULSE_OPERATIONAL_V1',
        'status':'ACTIVE_DETERMINISTIC_LAYERS',
        'generated_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'content_as_of':iso(latest),
        'scope':{
            'external_news_feed':'NOT_REQUIRED',
            'inputs':['OIS_OPERATIONAL_VIEW','MACRO_THERMOMETER_DATA'],
            'claim':'LATEST_VALIDATED_SIGNALS_NOT_GENERIC_HEADLINES'
        },
        'items':items
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','items':len(items),'content_as_of':iso(latest),'output':str(OUT.relative_to(ROOT))}))

if __name__=='__main__': main()
