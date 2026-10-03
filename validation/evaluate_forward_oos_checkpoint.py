#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, io, json, sys, urllib.parse, urllib.request
from datetime import date, timedelta
from pathlib import Path

T0_PATH=Path('validation/CANONICAL_ENGINE_OOS_T0_V3_2026-10-01.json')
FREEZE_SHA='ff52198a75cc67f7dae96fc2bbf65623f170791c'
FINGERPRINT='3356baf0'
CCYS=['USD','GBP','JPY','CHF','CAD','AUD','NZD']


def load_json(path):
    return json.loads(Path(path).read_text())


def fetch_ecb(currency:str,start:date,end:date):
    # ECB Data Portal: foreign-exchange reference rate, currency units per EUR.
    key=f'D.{currency}.EUR.SP00.A'
    qs=urllib.parse.urlencode({'startPeriod':start.isoformat(),'endPeriod':end.isoformat(),'format':'csvdata'})
    url=f'https://data-api.ecb.europa.eu/service/data/EXR/{key}?{qs}'
    req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-OOS-Evaluator/1.0'})
    with urllib.request.urlopen(req,timeout=30) as r:
        text=r.read().decode('utf-8-sig')
    rows=[]
    for row in csv.DictReader(io.StringIO(text)):
        t=row.get('TIME_PERIOD') or row.get('TIME PERIOD')
        v=row.get('OBS_VALUE') or row.get('OBS VALUE')
        if not t or v in (None,''): continue
        try: rows.append((date.fromisoformat(t),float(v)))
        except Exception: continue
    return sorted(rows)


def first_common_fixing(target:date, max_days:int=10):
    end=target+timedelta(days=max_days)
    series={c:fetch_ecb(c,target,end) for c in CCYS}
    maps={c:dict(v) for c,v in series.items()}
    common=None
    for i in range(max_days+1):
        d=target+timedelta(days=i)
        if all(d in maps[c] for c in CCYS):
            common=d; break
    if common is None:
        return None,{},series
    rates={'EUR':1.0}
    for c in CCYS: rates[c]=maps[c][common]
    return common,rates,series


def cross_price(pair:str,rates:dict[str,float]):
    a,b=pair.split('/')
    # ECB rates are currency units per EUR. Cross A/B = B-per-EUR / A-per-EUR.
    return rates[b]/rates[a]


def smoke_test_ecb():
    target=date(2026,9,30)
    fixing_date,rates,series=first_common_fixing(target,max_days=3)
    missing=[c for c in CCYS if not series.get(c)]
    invalid=[c for c,v in rates.items() if not isinstance(v,(int,float)) or v<=0]
    if fixing_date is None or missing or invalid or len(rates)!=8:
        print(json.dumps({'status':'ECB_SMOKE_FAIL','target':target.isoformat(),'fixing_date':fixing_date.isoformat() if fixing_date else None,'missing_series':missing,'invalid_rates':invalid,'currencies':sorted(rates)},indent=2))
        return 2
    # Sanity-check the same cross formula used by the evaluator.
    sample=cross_price('EUR/USD',rates)
    if sample<=0:
        print(json.dumps({'status':'ECB_SMOKE_FAIL','reason':'invalid sample cross'},indent=2)); return 2
    print(json.dumps({'status':'ECB_SMOKE_PASS','target':target.isoformat(),'fixing_date':fixing_date.isoformat(),'currencies':sorted(rates),'sample_EURUSD':sample},indent=2))
    return 0


def evaluate(label:str, today:date):
    t0=load_json(T0_PATH)
    if t0.get('rules_fingerprint')!=FINGERPRINT:
        raise SystemExit('Fingerprint mismatch: canonical T0 changed')
    cp=t0['checkpoints'][label]
    target=date.fromisoformat(cp['evaluation_date'])
    out=Path(f"validation/FORWARD_OOS_{label}_EVALUATION_{target.isoformat()}.json")
    if out.exists():
        existing=load_json(out)
        if existing.get('status')=='EVALUATED':
            print(json.dumps({'status':'ALREADY_EVALUATED','path':str(out)},indent=2)); return 0
    if today<target:
        print(json.dumps({'status':'WAITING','checkpoint':label,'evaluation_date':target.isoformat(),'today':today.isoformat()},indent=2)); return 0
    fixing_date,rates,_=first_common_fixing(target)
    if fixing_date is None:
        print(json.dumps({'status':'WAITING_FOR_ECB_FIXING','checkpoint':label,'evaluation_date':target.isoformat()},indent=2)); return 0
    results=[]
    for pair,p in t0['pairs'].items():
        favored=p.get('favored')
        anchor=p.get('anchor_price')
        if not isinstance(anchor,(int,float)) or anchor<=0: continue
        px=cross_price(pair,rates)
        ret=(px/anchor-1.0)*100.0
        eligible=favored in pair.split('/')
        hit=None
        if eligible:
            base,quote=pair.split('/')
            hit=(ret>0) if favored==base else (ret<0)
        results.append({'pair':pair,'favored':favored,'quality':p.get('quality'),'anchor_price':anchor,'evaluation_price':px,'return_pct':ret,'eligible':eligible,'hit':hit})
    eligible=[r for r in results if r['eligible']]
    hits=[r for r in eligible if r['hit'] is True]
    by_quality={}
    for r in eligible:
        q=r['quality'] or 'UNKNOWN'
        z=by_quality.setdefault(q,{'n':0,'hits':0})
        z['n']+=1; z['hits']+=int(bool(r['hit']))
    for z in by_quality.values(): z['hit_rate_pct']=round(100*z['hits']/z['n'],2) if z['n'] else None
    report={
      'schema':'GMFQ_FORWARD_OOS_CHECKPOINT_EVALUATION_V1',
      'status':'EVALUATED','checkpoint':label,'evaluation_target':target.isoformat(),
      'fixing_date_used':fixing_date.isoformat(),'price_source':'ECB euro foreign exchange reference rates',
      't0_effective_date':t0['t0_effective_date'],'t0_source_main_sha':t0.get('source_main_sha'),
      'engine_freeze_sha':FREEZE_SHA,'rules_fingerprint':FINGERPRINT,
      'evaluation_rule':t0['evaluation_rule'],
      'summary':{'eligible_pairs':len(eligible),'hits':len(hits),'hit_rate_pct':round(100*len(hits)/len(eligible),2) if eligible else None,'by_quality':by_quality},
      'rates_currency_units_per_eur':rates,'pair_results':results,
      'guardrails':['No rule/threshold tuning','No use of data after the first common ECB fixing on/after the checkpoint date','Pairs without a canonical favored side are excluded from hit-rate scoring','Evaluation artifact is validation-only and does not modify runtime/model logic']
    }
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':'EVALUATED','path':str(out),'fixing_date':fixing_date.isoformat(),'summary':report['summary']},indent=2))
    return 0

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--checkpoint',choices=['1W','4W','12W'])
    ap.add_argument('--today',help='Override current date YYYY-MM-DD for deterministic dry-runs')
    ap.add_argument('--smoke-test-ecb',action='store_true',help='Test the real ECB feed on a historical fixing without creating an OOS artifact')
    a=ap.parse_args()
    if a.smoke_test_ecb:
        sys.exit(smoke_test_ecb())
    if not a.checkpoint:
        ap.error('--checkpoint is required unless --smoke-test-ecb is used')
    today=date.fromisoformat(a.today) if a.today else date.today()
    sys.exit(evaluate(a.checkpoint,today))
