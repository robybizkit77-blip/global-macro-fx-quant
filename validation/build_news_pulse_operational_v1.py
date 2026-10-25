#!/usr/bin/env python3
import json,re
from datetime import date,datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
OIS=ROOT/'live_data/sections/OIS_OPERATIONAL_VIEW.json'
MACRO=ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json'
OUT=ROOT/'live_data/sections/NEWS_PULSE_OPERATIONAL.json'
ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

def parse_asof(raw):
    s=str(raw or '')
    m=re.search(r'(20\d{2})-(\d{2})-(\d{2})',s)
    if m:return date(int(m.group(1)),int(m.group(2)),int(m.group(3)))
    m=re.search(r'(20\d{2})-(\d{2})',s)
    if m:return date(int(m.group(1)),int(m.group(2)),1)
    return None

def iso(d): return d.isoformat() if d else None

def ois_items(data):
    out=[]
    for ccy,row in (data.get('currencies') or {}).items():
        moves=[]
        for h in ('3m','6m','12m'):
            v=((row.get('horizons') or {}).get(h) or {}).get('change_1d_bp')
            if v is not None:moves.append((abs(float(v)),h,float(v)))
        if not moves: continue
        _,h,v=max(moves); hrow=(row.get('horizons') or {}).get(h) or {}; weekly=hrow.get('change_1w_bp')
        tone='più hawkish' if v>0 else 'più dovish' if v<0 else 'invariato'
        detail=f"Movimento 1D {v:+.1f} bp sul bucket {h.upper()}"+(f"; variazione 1W {float(weekly):+.1f} bp." if weekly is not None else '; riferimento 1W non disponibile.')
        out.append({'category':'OIS_REPRICING','ccy':ccy,'as_of':row.get('as_of'),'title':f'{ccy}: repricing OIS {tone} ({v:+.1f} bp {h.upper()} in 1D)','detail':detail,'quality':row.get('quality'),'confidence':row.get('confidence'),'source':row.get('source'),'importance':'HIGH' if abs(v)>=2 else 'MEDIUM','_date':parse_asof(row.get('as_of'))})
    return out

def macro_items(data):
    today=date.today();out=[]
    for ccy,row in (data.get('currencies') or {}).items():
        candidates=[]
        for layer in ('inflation','labour'):
            x=row.get(layer) or {}; d=parse_asof(x.get('as_of'))
            if d:candidates.append((d,layer,x))
        if not candidates: continue
        d,layer,x=max(candidates,key=lambda z:z[0])
        if (today-d).days>45: continue
        label=x.get('label') or layer.title(); val=x.get('latest_value'); direction=x.get('direction') or 'N/D'; acceleration=x.get('acceleration') or 'N/D'
        out.append({'category':'MACRO_UPDATE','ccy':ccy,'as_of':x.get('as_of'),'title':f'{ccy}: {label} {direction.lower()} · {acceleration.lower()}','detail':f"Ultimo valore {val}; percentile storico {x.get('percentile')}%; stato {x.get('temperature_label')}.",'quality':'CERTIFIED_MACRO_LAYER','confidence':'A','source':x.get('source'),'importance':'HIGH' if x.get('temperature_label') in ('MOLTO_CALDO','MOLTO_FREDDO') else 'MEDIUM','_date':d})
    return out

def stable_write(core, now=None):
    """Preserve content vintage while recording a separate successful daily check.

    The check stamp is refreshed at most once per Rome calendar date if the
    source content is identical, avoiding repeated commits and publication
    churn. No unchanged market signal is presented as newly generated.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware UTC check instant required")
    now = now.astimezone(timezone.utc)
    now_str = now.isoformat().replace('+00:00', 'Z')
    prior = None
    if OUT.exists():
        try:
            prior = json.loads(OUT.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            prior = None
    prior_core = dict(prior or {})
    prior_core.pop('generated_at_utc', None)
    prior_core.pop('last_checked_at_utc', None)
    content_changed = prior_core != core or not (prior or {}).get('generated_at_utc')
    generated = now_str if content_changed else prior['generated_at_utc']
    prev_check = (prior or {}).get('last_checked_at_utc')
    try:
        parsed = datetime.fromisoformat(prev_check.replace('Z', '+00:00'))
        prior_checked_today = (
            parsed.tzinfo is not None
            and parsed.astimezone(ZoneInfo('Europe/Rome')).date()
            == now.astimezone(ZoneInfo('Europe/Rome')).date()
            and parsed <= now
        )
    except (AttributeError, TypeError, ValueError):
        prior_checked_today = False
    checked = prev_check if (not content_changed and prior_checked_today) else now_str
    out = dict(core)
    out['generated_at_utc'] = generated
    out['last_checked_at_utc'] = checked
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return content_changed

def main():
    ois=json.loads(OIS.read_text(encoding='utf-8'));macro=json.loads(MACRO.read_text(encoding='utf-8'))
    items=ois_items(ois)+macro_items(macro)
    items.sort(key=lambda x:(x['_date'] or date.min,x['importance']=='HIGH',-ORDER.index(x['ccy']) if x['ccy'] in ORDER else 0),reverse=True)
    for x in items:x.pop('_date',None)
    items=items[:12]
    latest=max((parse_asof(x.get('as_of')) for x in items if parse_asof(x.get('as_of'))),default=None)
    core={'schema':'GMFQ_NEWS_PULSE_OPERATIONAL_V1','status':'ACTIVE_DETERMINISTIC_LAYERS','content_as_of':iso(latest),'scope':{'external_news_feed':'NOT_REQUIRED','inputs':['OIS_OPERATIONAL_VIEW','MACRO_THERMOMETER_DATA'],'claim':'LATEST_VALIDATED_SIGNALS_NOT_GENERIC_HEADLINES'},'items':items}
    changed=stable_write(core)
    print(json.dumps({'status':'PASS','changed':changed,'items':len(items),'content_as_of':iso(latest),'output':str(OUT.relative_to(ROOT))}))

if __name__=='__main__':main()
