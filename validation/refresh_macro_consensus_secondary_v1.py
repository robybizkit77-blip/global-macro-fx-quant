#!/usr/bin/env python3
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OFFICIAL=ROOT/'live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json'
OUT=ROOT/'live_data/sections/MACRO_CONSENSUS_SECONDARY_V1.json'

G8={'USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'}
ALIASES={
    'INFLATION':('inflation','consumer price','cpi','price index','prices'),
    'LABOUR':('employment','unemployment','labour','labor','jobless','payroll'),
    'LABOUR_COST':('employment cost','labour cost','labor cost','wages','earnings'),
    'GROWTH':('gdp','gross domestic product','growth'),
}

def norm(s):
    return re.sub(r'[^a-z0-9]+',' ',str(s or '').lower()).strip()

def iso_day(raw):
    try:
        return datetime.fromisoformat(str(raw).replace('Z','+00:00')).date()
    except Exception:
        try: return date.fromisoformat(str(raw)[:10])
        except Exception: return None

def semantic_score(official,candidate):
    o=norm(official.get('title'))
    c=norm(candidate.get('event'))
    score=0
    if o and c and (o in c or c in o): score+=6
    owords={w for w in o.split() if len(w)>3}
    cwords=set(c.split())
    score+=min(5,len(owords & cwords))
    aliases=ALIASES.get(official.get('event_type'),())
    if any(a in c for a in aliases): score+=4
    return score

def fetch_calendar(key,start,end):
    params=urllib.parse.urlencode({'from':start.isoformat(),'to':end.isoformat(),'apikey':key})
    url=f'https://financialmodelingprep.com/stable/economic-calendar?{params}'
    req=urllib.request.Request(url,headers={'User-Agent':'GMFQ/1.0 consensus-secondary-fmp'})
    with urllib.request.urlopen(req,timeout=30) as r:
        payload=json.loads(r.read().decode('utf-8'))
    if not isinstance(payload,list):
        raise RuntimeError('unexpected FMP economic-calendar payload')
    return payload

def main():
    key=os.environ.get('FMP_API_KEY','').strip()
    if not key:
        print(json.dumps({'status':'NO_PROVIDER_CREDENTIALS','provider':'FMP','changed':False,'output':str(OUT.relative_to(ROOT))}))
        return

    official=json.loads(OFFICIAL.read_text(encoding='utf-8')).get('events',[])
    today=date.today()
    horizon=today+timedelta(days=90)
    try:
        provider_rows=fetch_calendar(key,today,horizon)
    except Exception as exc:
        print(json.dumps({'status':'PROVIDER_FETCH_FAILED','provider':'FMP','error':str(exc),'changed':False,'output':str(OUT.relative_to(ROOT))}))
        raise

    by_ccy={ccy:[] for ccy in G8}
    for row in provider_rows:
        ccy=str(row.get('currency') or '').upper().strip()
        if ccy in by_ccy:
            by_ccy[ccy].append(row)

    rows=[]
    for e in official:
        d=iso_day(e.get('date'))
        ccy=e.get('ccy')
        if ccy not in G8 or not d or d<today or d>horizon:
            continue
        best=None; best_rank=None; best_gap=None
        for cand in by_ccy.get(ccy,[]):
            cd=iso_day(cand.get('date'))
            if not cd:
                continue
            gap=abs((cd-d).days)
            if gap>1:
                continue
            sem=semantic_score(e,cand)
            if sem<4:
                continue
            rank=(10 if gap==0 else 6)+sem
            if best_rank is None or rank>best_rank:
                best_rank=rank; best=cand; best_gap=gap
        if not best:
            continue

        estimate=best.get('estimate')
        previous=best.get('previous')
        if estimate in (None,'') and previous in (None,''):
            continue

        event_key='|'.join([str(e.get('ccy','')),str(e.get('date','')),str(e.get('event_type','')),str(e.get('title',''))])
        status='AVAILABLE' if estimate not in (None,'') else 'PREVIOUS_ONLY'
        rows.append({
            'event_key':event_key,
            'ccy':ccy,
            'official_date':e.get('date'),
            'official_title':e.get('title'),
            'event_type':e.get('event_type'),
            'status':status,
            'consensus':estimate if estimate not in ('',None) else None,
            'previous':previous if previous not in ('',None) else None,
            'unit':best.get('unit') or None,
            'impact':best.get('impact') or None,
            'provider':'FMP',
            'provider_event':best.get('event'),
            'provider_country':best.get('country'),
            'provider_date':best.get('date'),
            'confidence_grade':'B' if best_gap==0 else 'C',
            'date_match_gap_days':best_gap,
            'official_date_overridden':False,
            'actual_ignored_for_pre_release_consensus':True
        })

    status='ACTIVE_PARTIAL' if rows else 'PROVIDER_ACTIVE_NO_MATCHED_VALUES'
    out={
        'schema':'GMFQ_MACRO_CONSENSUS_SECONDARY_V1',
        'status':status,
        'provider':'FMP',
        'provider_endpoint':'stable/economic-calendar',
        'provider_field':'estimate',
        'provider_previous_field':'previous',
        'generated_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'events':rows,
        'rules':{
            'never_promote_to_official':True,
            'never_fill_missing_with_zero':True,
            'never_change_release_date':True,
            'context_only':True,
            'core_score_impact':0,
            'estimate_field_is_consensus_only':True,
            'actual_not_used_as_pre_release_consensus':True,
            'official_calendar_remains_primary':True
        }
    }
    old=OUT.read_text(encoding='utf-8') if OUT.exists() else ''
    new=json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    changed=old!=new
    if changed:
        OUT.write_text(new,encoding='utf-8')
    print(json.dumps({'status':'PASS','provider':'FMP','changed':changed,'matched_events':len(rows),'consensus_available':sum(r['status']=='AVAILABLE' for r in rows),'output':str(OUT.relative_to(ROOT))}))

if __name__=='__main__':
    main()
