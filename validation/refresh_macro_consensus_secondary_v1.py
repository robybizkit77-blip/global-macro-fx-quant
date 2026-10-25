#!/usr/bin/env python3
import json
import re
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OFFICIAL=ROOT/'live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json'
OUT=ROOT/'live_data/sections/MACRO_CONSENSUS_SECONDARY_V1.json'

G8={'USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'}
ALIASES={
    'INFLATION':('inflation','consumer price','cpi','price index','prices'),
    'LABOUR':('employment','unemployment','labour','labor','jobless','payroll','claimant'),
    'LABOUR_COST':('employment cost','labour cost','labor cost','wages','earnings'),
    'GROWTH':('gdp','gross domestic product','growth'),
}
FEED='https://nfs.faireconomy.media/ff_calendar_thisweek.json'


def norm(s):
    return re.sub(r'[^a-z0-9]+',' ',str(s or '').lower()).strip()


def iso_day(raw):
    try:
        return datetime.fromisoformat(str(raw).replace('Z','+00:00')).date()
    except Exception:
        try:
            return date.fromisoformat(str(raw)[:10])
        except Exception:
            return None


def semantic_score(official,candidate):
    o=norm(official.get('title'))
    c=norm(candidate.get('event'))
    score=0
    if o and c and (o in c or c in o):
        score+=6
    owords={w for w in o.split() if len(w)>3}
    cwords=set(c.split())
    score+=min(5,len(owords & cwords))
    aliases=ALIASES.get(official.get('event_type'),())
    if any(a in c for a in aliases):
        score+=4
    return score



def series_compatible(official, candidate):
    """Fail closed unless the candidate represents the same geographic
    aggregate and economic series; a generic category/date match is unsafe.
    A whole-release title must not silently inherit a narrower subseries.
    """
    ccy = str(official.get('ccy') or '')
    o = norm(official.get('title'))
    c = norm(candidate.get('event'))
    if not o or not c:
        return False
    # EUR includes country-level events in third-party calendars, whereas the
    # official seed refers to the Euro AREA. French/German data are not peers.
    if ccy == 'EUR' and ('euro area' in o or 'eurozone' in o):
        if not ('euro area' in c or 'eurozone' in c):
            return False
        if any(country in c.split() for country in (
            'french', 'german', 'italian', 'spanish', 'dutch'
        )):
            return False
    if 'employment cost index' in o:
        return 'employment cost index' in c
    if 'consumer price index' in o or re.search(r'\bcpi\b', o):
        # "Import Prices", PPI and trimmed/core series are not headline CPI.
        # The official seed lacks a m/m vs y/y indicator: do not attach an
        # unexplained subseries consensus to the entire CPI release.
        if any(bad in c for bad in ('import prices', 'producer prices',
                                    'trimmed mean', 'core cpi', 'weighted median')):
            return False
        return ('consumer price index' in c or re.search(r'\bcpi\b', c)) and not (
            re.search(r'\b(m m|y y|q q)\b', c) and
            not any(m in o for m in ('m m', 'y y', 'q q'))
        )
    if 'preliminary flash gdp' in o:
        return 'gdp' in c and 'flash' in c
    if 'gross domestic product by industry' in o:
        return ccy == 'CAD' and (
            c.startswith('gdp m m') or
            'gross domestic product by industry' in c
        )
    if 'unemployment' in o:
        return 'unemployment rate' in c and 'change' not in c
    if 'labour force survey' in o:
        # The aggregate release contains multiple metrics. A provider's
        # unemployment-rate subseries needs its own explicit seed event.
        return 'labour force survey' in c
    # For remaining families, require substantially matching actual names;
    # synonyms such as "prices" or "employment" alone are insufficient.
    return len(o) >= 12 and (o in c or c in o)



def fetch_calendar():
    req=urllib.request.Request(FEED,headers={
        'User-Agent':'GMFQ/1.0 (+https://github.com/robybizkit77-blip/global-macro-fx-quant)',
        'Accept':'application/json'
    })
    with urllib.request.urlopen(req,timeout=30) as r:
        payload=json.loads(r.read().decode('utf-8'))
    if not isinstance(payload,list):
        raise RuntimeError('unexpected Fair Economy calendar payload')
    out=[]
    for row in payload:
        ccy=str(row.get('country') or row.get('currency') or '').upper().strip()
        d=iso_day(row.get('date'))
        if ccy not in G8 or not d:
            continue
        out.append({
            'currency':ccy,
            'event':row.get('title') or row.get('event'),
            'date':d.isoformat(),
            'previous':row.get('previous') or None,
            'consensus':row.get('forecast') or None,
            'impact':row.get('impact') or None,
            'source_url':row.get('url') or None,
        })
    if not out:
        raise RuntimeError('Fair Economy feed returned no G8 rows')
    return out


def main():
    official=json.loads(OFFICIAL.read_text(encoding='utf-8')).get('events',[])
    today=date.today()
    try:
        provider_rows=fetch_calendar()
    except Exception as exc:
        print(json.dumps({'status':'PROVIDER_FETCH_FAILED','provider':'FOREX_FACTORY_FAIR_ECONOMY_WEEKLY','error':str(exc),'changed':False,'output':str(OUT.relative_to(ROOT))}))
        raise

    by_ccy={ccy:[] for ccy in G8}
    for row in provider_rows:
        by_ccy[row['currency']].append(row)

    rows=[]
    for e in official:
        d=iso_day(e.get('date'))
        ccy=e.get('ccy')
        if ccy not in G8 or not d or d<today:
            continue
        best=None; best_rank=None; best_gap=None
        for cand in by_ccy.get(ccy,[]):
            cd=iso_day(cand.get('date'))
            if not cd:
                continue
            gap=abs((cd-d).days)
            if gap>1:
                continue
            if not series_compatible(e, cand):
                continue
            sem=semantic_score(e,cand)
            if sem<4:
                continue
            rank=(10 if gap==0 else 6)+sem
            if best_rank is None or rank>best_rank:
                best_rank=rank; best=cand; best_gap=gap
        if not best:
            continue

        consensus=best.get('consensus')
        previous=best.get('previous')
        if consensus in (None,'') and previous in (None,''):
            continue

        event_key='|'.join([str(e.get('ccy','')),str(e.get('date','')),str(e.get('event_type','')),str(e.get('title',''))])
        status='AVAILABLE' if consensus not in (None,'') else 'PREVIOUS_ONLY'
        rows.append({
            'event_key':event_key,
            'ccy':ccy,
            'official_date':e.get('date'),
            'official_title':e.get('title'),
            'event_type':e.get('event_type'),
            'status':status,
            'consensus':consensus if consensus not in ('',None) else None,
            'previous':previous if previous not in ('',None) else None,
            'unit':None,
            'impact':best.get('impact') or None,
            'provider':'FOREX_FACTORY_FAIR_ECONOMY_WEEKLY',
            'provider_event':best.get('event'),
            'provider_country':None,
            'provider_date':best.get('date'),
            'provider_url':best.get('source_url'),
            'confidence_grade':'B' if best_gap==0 else 'C',
            'date_match_gap_days':best_gap,
            'official_date_overridden':False,
            'actual_ignored_for_pre_release_consensus':True
        })

    status='ACTIVE_PARTIAL' if rows else 'PROVIDER_ACTIVE_NO_MATCHED_VALUES'
    out={
        'schema':'GMFQ_MACRO_CONSENSUS_SECONDARY_V1',
        'status':status,
        'provider':'FOREX_FACTORY_FAIR_ECONOMY_WEEKLY',
        'provider_endpoint':FEED,
        'provider_field':'forecast',
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
            'official_calendar_remains_primary':True,
            'public_json_secondary_source':True,
            'weekly_feed_scope':True
        }
    }
    old=OUT.read_text(encoding='utf-8') if OUT.exists() else ''
    new=json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    changed=old!=new
    if changed:
        OUT.write_text(new,encoding='utf-8')
    print(json.dumps({'status':'PASS','provider':'FOREX_FACTORY_FAIR_ECONOMY_WEEKLY','changed':changed,'provider_rows':len(provider_rows),'matched_events':len(rows),'consensus_available':sum(r['status']=='AVAILABLE' for r in rows),'output':str(OUT.relative_to(ROOT))}))


if __name__=='__main__':
    main()
