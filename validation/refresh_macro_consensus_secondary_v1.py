#!/usr/bin/env python3
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OFFICIAL=ROOT/'live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json'
OUT=ROOT/'live_data/sections/MACRO_CONSENSUS_SECONDARY_V1.json'

COUNTRIES={
    'USD':'united states','EUR':'euro area','GBP':'united kingdom','JPY':'japan',
    'CHF':'switzerland','CAD':'canada','AUD':'australia','NZD':'new zealand'
}
ALIASES={
    'INFLATION':('inflation','consumer price','cpi'),
    'LABOUR':('employment','unemployment','labour','labor','jobless'),
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
    c=norm(' '.join([str(candidate.get('Event') or ''),str(candidate.get('Category') or '')]))
    score=0
    if o and (o in c or c in o): score+=6
    owords={w for w in o.split() if len(w)>3}
    cwords=set(c.split())
    score+=min(5,len(owords & cwords))
    aliases=ALIASES.get(official.get('event_type'),())
    if any(a in c for a in aliases): score+=4
    return score

def fetch_country(country,key):
    q=urllib.parse.quote(country,safe='')
    url=f'https://api.tradingeconomics.com/calendar/country/{q}?c={urllib.parse.quote(key,safe=":")}&f=json'
    req=urllib.request.Request(url,headers={'User-Agent':'GMFQ/1.0 consensus-secondary'})
    with urllib.request.urlopen(req,timeout=25) as r:
        payload=json.loads(r.read().decode('utf-8'))
    if not isinstance(payload,list): raise RuntimeError(f'unexpected provider payload for {country}')
    return payload

def main():
    key=os.environ.get('TRADING_ECONOMICS_API_KEY','').strip()
    if not key:
        print(json.dumps({'status':'NO_PROVIDER_CREDENTIALS','changed':False,'output':str(OUT.relative_to(ROOT))}))
        return
    official=json.loads(OFFICIAL.read_text(encoding='utf-8')).get('events',[])
    today=date.today()
    rows=[]
    cache={}
    for ccy,country in COUNTRIES.items():
        try: cache[ccy]=fetch_country(country,key)
        except Exception as exc:
            cache[ccy]=[]
            print(f'WARN provider {ccy}: {exc}')
    for e in official:
        d=iso_day(e.get('date'))
        if not d or d<today: continue
        best=None; best_tuple=None
        for cand in cache.get(e.get('ccy'),[]):
            cd=iso_day(cand.get('Date'))
            if not cd: continue
            gap=abs((cd-d).days)
            if gap>1: continue
            sem=semantic_score(e,cand)
            if sem<4: continue
            rank=(10 if gap==0 else 6)+sem
            if best_tuple is None or rank>best_tuple:
                best_tuple=rank; best=cand
        event_key='|'.join([str(e.get('ccy','')),str(e.get('date','')),str(e.get('event_type','')),str(e.get('title',''))])
        if not best: continue
        forecast=best.get('Forecast')
        previous=best.get('Previous')
        if forecast in (None,'') and previous in (None,''): continue
        provider_day=iso_day(best.get('Date'))
        gap=abs((provider_day-d).days) if provider_day else 99
        status='AVAILABLE' if forecast not in (None,'') else 'PREVIOUS_ONLY'
        rows.append({
            'event_key':event_key,
            'ccy':e.get('ccy'),'official_date':e.get('date'),'official_title':e.get('title'),'event_type':e.get('event_type'),
            'status':status,'consensus':forecast if forecast not in ('',None) else None,
            'previous':previous if previous not in ('',None) else None,
            'unit':best.get('Unit') or None,'provider':'TRADING_ECONOMICS','provider_event':best.get('Event'),
            'provider_category':best.get('Category'),'provider_date_utc':best.get('Date'),'provider_last_update':best.get('LastUpdate'),
            'confidence_grade':'B' if gap==0 else 'C','date_match_gap_days':gap,
            'official_date_overridden':False,'teforecast_used':False
        })
    status='ACTIVE_PARTIAL' if rows else 'PROVIDER_ACTIVE_NO_MATCHED_VALUES'
    out={
        'schema':'GMFQ_MACRO_CONSENSUS_SECONDARY_V1','status':status,'provider':'TRADING_ECONOMICS',
        'provider_field':'Forecast','provider_model_field_excluded':'TEForecast',
        'generated_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'events':rows,
        'rules':{'never_promote_to_official':True,'never_fill_missing_with_zero':True,'never_change_release_date':True,
                 'context_only':True,'core_score_impact':0,'forecast_field_is_consensus_only':True,
                 'teforecast_is_never_used_as_consensus':True}
    }
    old=OUT.read_text(encoding='utf-8') if OUT.exists() else ''
    new=json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    changed=old!=new
    if changed: OUT.write_text(new,encoding='utf-8')
    print(json.dumps({'status':'PASS','changed':changed,'matched_events':len(rows),'consensus_available':sum(r['status']=='AVAILABLE' for r in rows),'output':str(OUT.relative_to(ROOT))}))

if __name__=='__main__': main()
