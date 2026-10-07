#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VAL=ROOT/'validation'
RATES=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
REGISTRY=VAL/'RATES_SOURCE_ADAPTERS_V1_2026-10-05.json'
OUT=VAL/'RATES_UNIFIED_AUDIT_OUTPUT.json'
NZD_MANUAL=VAL/'NZD_RATES_MANUAL_OFFICIAL_VERIFICATION_2026-10-07.json'


def load_module(name:str, path:Path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load {path}')
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def compare(cur:dict, official_date:str, y2:float, y10:float)->str:
    cd=str(cur.get('date'))
    if official_date < cd:
        return 'SOURCE_OLDER_THAN_CURRENT'
    if official_date == cd:
        if abs(float(cur['2Y'])-float(y2)) < 1e-9 and abs(float(cur['10Y'])-float(y10)) < 1e-9:
            return 'NO_CHANGE'
        return 'SAME_DATE_VALUE_MISMATCH'
    return 'UPDATE_AVAILABLE'


def manual_nzd_fallback(exc:Exception)->dict:
    if not NZD_MANUAL.exists():
        raise RuntimeError(f'RBNZ fetch failed and no manual official fallback exists: {exc}')
    m=json.loads(NZD_MANUAL.read_text())
    today=datetime.now(timezone.utc).date().isoformat()
    if m.get('schema')!='GMFQ_MANUAL_OFFICIAL_RATES_VERIFICATION_V1':
        raise RuntimeError('NZD manual fallback schema mismatch')
    if m.get('currency')!='NZD' or m.get('authority')!='Reserve Bank of New Zealand':
        raise RuntimeError('NZD manual fallback identity mismatch')
    if m.get('verified_on')!=today or m.get('expires_after')!=today:
        raise RuntimeError(f'NZD manual fallback expired/not valid today: verified={m.get("verified_on")} expires={m.get("expires_after")} today={today}')
    src=str(m.get('source_url') or '')
    if 'rbnz.govt.nz' not in src:
        raise RuntimeError('NZD manual fallback is not tied to official RBNZ URL')
    return {
      'date':str(m['official_date']), '2Y':float(m['2Y']), '10Y':float(m['10Y']),
      'authority':m['authority'], 'source':m['source'], 'source_url':src,
      'verification_note':m.get('verification_note'), 'fetch_error':repr(exc)
    }


def main()->int:
    rates=json.loads(RATES.read_text())
    reg=json.loads(REGISTRY.read_text())
    out={
      'schema':'GMFQ_RATES_UNIFIED_AUDIT_V2',
      'status':'PASS',
      'policy':reg['policy'],
      'currencies':{},
      'summary':{}
    }
    failures=[]

    uj=load_module('rates_usd_jpy',VAL/'fetch_rates_usd_jpy.py')
    for c,src in [('USD',uj.parse_treasury(uj.fetch(uj.TREASURY_URL))),('JPY',uj.parse_mof(uj.fetch(uj.MOF_URL)))]:
        state=compare(rates[c],src['date'],src['2Y'],src['10Y'])
        out['currencies'][c]={
          'state':state,'coverage_mode':'LIVE_FETCH','authority':src['authority'],
          'official':{'date':src['date'],'2Y':src['2Y'],'10Y':src['10Y']},
          'current':{'date':rates[c]['date'],'2Y':rates[c]['2Y'],'10Y':rates[c]['10Y']}
        }
        if state in {'SOURCE_OLDER_THAN_CURRENT','SAME_DATE_VALUE_MISMATCH'}: failures.append(c)

    eg=load_module('rates_eur_gbp',VAL/'fetch_rates_eur_gbp.py')
    e2=eg.ecb('SR_2Y'); e10=eg.ecb('SR_10Y')
    if e2[0] != e10[0]:
        raise RuntimeError(f'ECB same-day mismatch {e2[0]} vs {e10[0]}')
    state=compare(rates['EUR'],e2[0],e2[1],e10[1])
    out['currencies']['EUR']={
      'state':state,'coverage_mode':'LIVE_FETCH','authority':'European Central Bank',
      'official':{'date':e2[0],'2Y':e2[1],'10Y':e10[1]},
      'current':{'date':rates['EUR']['date'],'2Y':rates['EUR']['2Y'],'10Y':rates['EUR']['10Y']}
    }
    if state in {'SOURCE_OLDER_THAN_CURRENT','SAME_DATE_VALUE_MISMATCH'}: failures.append('EUR')

    b,_=eg.boe()
    state=compare(rates['GBP'],b[0],b[1],b[2])
    out['currencies']['GBP']={
      'state':state,'coverage_mode':'LIVE_FETCH','authority':'Bank of England',
      'official':{'date':b[0],'2Y':b[1],'10Y':b[2],'workbook':b[3],'sheet':b[4]},
      'current':{'date':rates['GBP']['date'],'2Y':rates['GBP']['2Y'],'10Y':rates['GBP']['10Y']}
    }
    if state in {'SOURCE_OLDER_THAN_CURRENT','SAME_DATE_VALUE_MISMATCH'}: failures.append('GBP')

    cad=load_module('rates_cad',VAL/'fetch_rates_cad.py')
    raw=cad.get_json(cad.URL)
    obs=[]
    for row in raw.get('observations',[]):
        d=row.get('d')
        try:
            y2=float(row[cad.SERIES_2Y]['v']); y10=float(row[cad.SERIES_10Y]['v'])
        except Exception:
            continue
        obs.append((d,y2,y10))
    if not obs: raise RuntimeError('CAD: no same-day 2Y/10Y observations')
    d,y2,y10=max(obs,key=lambda x:x[0])
    state=compare(rates['CAD'],d,y2,y10)
    out['currencies']['CAD']={
      'state':state,'coverage_mode':'LIVE_FETCH','authority':'Bank of Canada',
      'official':{'date':d,'2Y':y2,'10Y':y10},
      'current':{'date':rates['CAD']['date'],'2Y':rates['CAD']['2Y'],'10Y':rates['CAD']['10Y']}
    }
    if state in {'SOURCE_OLDER_THAN_CURRENT','SAME_DATE_VALUE_MISMATCH'}: failures.append('CAD')

    nz=load_module('rates_nzd',VAL/'fetch_rates_nzd.py')
    nmode='LIVE_FETCH'
    try:
        nsrc=nz.parse(nz.fetch())
    except Exception as exc:
        nsrc=manual_nzd_fallback(exc)
        nmode='MANUAL_OFFICIAL_VERIFICATION'
    state=compare(rates['NZD'],nsrc['date'],nsrc['2Y'],nsrc['10Y'])
    out['currencies']['NZD']={
      'state':state,'coverage_mode':nmode,'authority':nsrc['authority'],
      'official':{'date':nsrc['date'],'2Y':nsrc['2Y'],'10Y':nsrc['10Y']},
      'current':{'date':rates['NZD']['date'],'2Y':rates['NZD']['2Y'],'10Y':rates['NZD']['10Y']},
      'reason':('RBNZ B2 live official fetch.' if nmode=='LIVE_FETCH' else nsrc.get('verification_note')),
      'source_url':nsrc.get('source_url')
    }
    if state in {'SOURCE_OLDER_THAN_CURRENT','SAME_DATE_VALUE_MISMATCH'}: failures.append('NZD')

    meta=reg['currencies']['AUD']
    expected=meta['current_snapshot']
    state='NO_CHANGE' if str(rates['AUD']['date']) == expected else 'CURRENT_SNAPSHOT_REGISTRY_MISMATCH'
    out['currencies']['AUD']={
      'state':state,
      'coverage_mode':'OFFICIAL_CADENCE_ASSERTION',
      'authority':meta['authority'],
      'official_contract_snapshot':expected,
      'current':{'date':rates['AUD']['date'],'2Y':rates['AUD']['2Y'],'10Y':rates['AUD']['10Y']},
      'reason':meta.get('reason')
    }
    if state != 'NO_CHANGE': failures.append('AUD')

    chf=reg['currencies']['CHF']
    out['currencies']['CHF']={
      'state':'WITHHOLD',
      'coverage_mode':'SOURCE_EXPORT_BLOCKED',
      'authority':chf['authority'],
      'last_validated_snapshot':chf['last_validated_snapshot'],
      'current':{'date':rates['CHF']['date'],'2Y':rates['CHF']['2Y'],'10Y':rates['CHF']['10Y']},
      'reason':chf['reason']
    }

    states={c:v['state'] for c,v in out['currencies'].items()}
    out['summary']={
      'live_fetch_count':sum(v['coverage_mode']=='LIVE_FETCH' for v in out['currencies'].values()),
      'manual_official_verification_count':sum(v['coverage_mode']=='MANUAL_OFFICIAL_VERIFICATION' for v in out['currencies'].values()),
      'cadence_assertion_count':sum(v['coverage_mode']=='OFFICIAL_CADENCE_ASSERTION' for v in out['currencies'].values()),
      'withheld_count':sum(v['state']=='WITHHOLD' for v in out['currencies'].values()),
      'updates_available':[c for c,s in states.items() if s=='UPDATE_AVAILABLE'],
      'no_change':[c for c,s in states.items() if s=='NO_CHANGE'],
      'withheld':[c for c,s in states.items() if s=='WITHHOLD'],
      'failures':failures
    }
    if failures:
        out['status']='FAIL'
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(out,indent=2,ensure_ascii=False))
    return 2 if failures else 0

if __name__=='__main__':
    raise SystemExit(main())
