#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VAL=ROOT/'validation'
RATES=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
REGISTRY=VAL/'RATES_SOURCE_ADAPTERS_V1_2026-10-05.json'
OUT=VAL/'RATES_UNIFIED_AUDIT_OUTPUT.json'


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


def main()->int:
    rates=json.loads(RATES.read_text())
    reg=json.loads(REGISTRY.read_text())
    out={
      'schema':'GMFQ_RATES_UNIFIED_AUDIT_V1',
      'status':'PASS',
      'policy':reg['policy'],
      'currencies':{},
      'summary':{}
    }
    failures=[]

    # USD + JPY: official Treasury and Japan MoF adapters.
    uj=load_module('rates_usd_jpy',VAL/'fetch_rates_usd_jpy.py')
    for c,src in [('USD',uj.parse_treasury(uj.fetch(uj.TREASURY_URL))),('JPY',uj.parse_mof(uj.fetch(uj.MOF_URL)))]:
        state=compare(rates[c],src['date'],src['2Y'],src['10Y'])
        out['currencies'][c]={
          'state':state,'coverage_mode':'LIVE_FETCH','authority':src['authority'],
          'official':{'date':src['date'],'2Y':src['2Y'],'10Y':src['10Y']},
          'current':{'date':rates[c]['date'],'2Y':rates[c]['2Y'],'10Y':rates[c]['10Y']}
        }
        if state in {'SOURCE_OLDER_THAN_CURRENT','SAME_DATE_VALUE_MISMATCH'}: failures.append(c)

    # EUR + GBP: ECB AAA Svensson curve and BoE nominal government zero-coupon spot curve.
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

    # CAD: Bank of Canada Valet benchmark Government of Canada bond yields.
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

    # AUD: official RBA F2 CSV, same-day official 2Y/10Y pair by stable series IDs.
    aud=load_module('rates_aud',VAL/'fetch_rates_aud.py')
    a=aud.latest()
    state=compare(rates['AUD'],a['date'],a['2Y'],a['10Y'])
    out['currencies']['AUD']={
      'state':state,'coverage_mode':'LIVE_FETCH','authority':a['authority'],
      'official':{'date':a['date'],'2Y':a['2Y'],'10Y':a['10Y'],'series_2Y':a['series_2Y'],'series_10Y':a['series_10Y']},
      'current':{'date':rates['AUD']['date'],'2Y':rates['AUD']['2Y'],'10Y':rates['AUD']['10Y']},
      'publication_cadence':a['publication_cadence']
    }
    if state in {'SOURCE_OLDER_THAN_CURRENT','SAME_DATE_VALUE_MISMATCH'}: failures.append('AUD')

    # NZD remains an official-source-lag assertion because the RBNZ B2 public page/XLSX
    # returns HTTP 403 to GitHub-hosted runners. Never substitute a secondary source.
    meta=reg['currencies']['NZD']
    expected=meta['current_snapshot']
    state='NO_CHANGE' if str(rates['NZD']['date']) == expected else 'CURRENT_SNAPSHOT_REGISTRY_MISMATCH'
    out['currencies']['NZD']={
      'state':state,'coverage_mode':'OFFICIAL_SOURCE_LAG_ASSERTION','authority':meta['authority'],
      'official_contract_snapshot':expected,
      'current':{'date':rates['NZD']['date'],'2Y':rates['NZD']['2Y'],'10Y':rates['NZD']['10Y']},
      'reason':meta.get('reason'),
      'runner_access':'RBNZ B2 official page and canonical XLSX return HTTP 403 to GitHub-hosted runner; no secondary fallback permitted'
    }
    if state != 'NO_CHANGE': failures.append('NZD')

    # CHF is intentionally WITHHELD until the official SNB same-basis export works again.
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
      'cadence_or_lag_assertion_count':sum(v['coverage_mode'] in {'OFFICIAL_CADENCE_ASSERTION','OFFICIAL_SOURCE_LAG_ASSERTION'} for v in out['currencies'].values()),
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
