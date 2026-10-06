#!/usr/bin/env python3
import csv, io, json, math, urllib.request
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FX=ROOT/'history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
OUT=ROOT/'validation/CAD_REACTION_FUNCTION_STATE_REPLAY_VNEXT_V1_2026-10-06.json'
LAB_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/engine-freeze-v1-2026-10-02/validation/PIT_SIGNAL_SENSITIVITY_CA_LABOUR_FULL_2020_2026_V1_2026-10-02.json'
RATES_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/engine-freeze-v1-2026-10-02/validation/cad_rates_pit/CA_BOC_BENCHMARK_RATES_DAILY_2020_2026_V1.csv'
CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
H=[5,20,60]

with urllib.request.urlopen(LAB_URL,timeout=30) as r:
    lab=json.load(r)
with urllib.request.urlopen(RATES_URL,timeout=30) as r:
    rr=list(csv.DictReader(io.StringIO(r.read().decode('utf-8'))))
with FX.open(newline='',encoding='utf-8') as f:
    fx=list(csv.DictReader(f))

rdate=next(k for k in rr[0] if k.lower() in ('date','observation_date'))
y2_candidates=[k for k in rr[0] if '2' in k.lower() and ('year' in k.lower() or 'y2' in k.lower() or '2y' in k.lower())]
if not y2_candidates:
    raise RuntimeError(f'2Y column not found; columns={list(rr[0])}')
y2col=y2_candidates[0]
rate_rows=[]
for r in rr:
    try:
        rate_rows.append((date.fromisoformat(r[rdate][:10]),float(r[y2col])))
    except Exception:
        pass
rate_rows.sort()
if not rate_rows:
    raise RuntimeError('No usable rate rows')

fxdates=[date.fromisoformat(r['date']) for r in fx]
def next_fx_idx(dt):
    for i,d in enumerate(fxdates):
        if d>dt:
            return i
    return None

def pair_log_return(ccy,other,i0,i1):
    direct=ccy+other; inverse=other+ccy
    if direct in fx[i0] and fx[i0][direct] and fx[i1][direct]:
        return math.log(float(fx[i1][direct])/float(fx[i0][direct]))
    if inverse in fx[i0] and fx[i0][inverse] and fx[i1][inverse]:
        return -math.log(float(fx[i1][inverse])/float(fx[i0][inverse]))
    raise KeyError((ccy,other))

def basket_return(i0,i1):
    vals=[pair_log_return('CAD',o,i0,i1) for o in CCYS if o!='CAD']
    return sum(vals)/len(vals)

def rate_window(rel,days=5):
    post=[x for x in rate_rows if x[0]>rel]
    if len(post)<days+1:
        return None
    start=post[0]; end=post[days]
    delta=end[1]-start[1]
    sign=1 if delta>0 else -1 if delta<0 else 0
    return {'start_date':start[0].isoformat(),'end_date':end[0].isoformat(),'start_2y':start[1],'end_2y':end[1],'delta_2y':delta,'direction':sign}

def stats(rows,h):
    vals=[x[f'signed_{h}d'] for x in rows if f'signed_{h}d' in x]
    if not vals:
        return {'n':0,'hit_rate':None,'mean':None,'median':None}
    s=sorted(vals); n=len(vals)
    med=s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
    return {'n':n,'hit_rate':sum(v>0 for v in vals)/n,'mean':sum(vals)/n,'median':med}

rows=[]
for rec in lab['comparisons']:
    if not rec.get('both_series_ready'):
        continue
    d=rec['first_release'].get('direction')
    if d not in (-1,1):
        continue
    rel=date.fromisoformat(rec['checkpoint'])
    rw=rate_window(rel,5)
    if not rw:
        continue
    if rw['direction']==0:
        market_state='RATES_FLAT'
    elif rw['direction']==d:
        market_state='CONVERGENT'
    else:
        market_state='DIVERGENT'
    i0=next_fx_idx(date.fromisoformat(rw['end_date']))
    if i0 is None:
        continue
    e={'checkpoint':rec['checkpoint'],'labour_direction':d,
       'cb_interpretation':'HAWKISH_PRESSURE' if d>0 else 'DOVISH_PRESSURE',
       'market_repricing':rw,'state':market_state,'fx_entry_date':fx[i0]['date']}
    for h in H:
        i1=i0+h
        if i1<len(fx):
            e[f'signed_{h}d']=d*basket_return(i0,i1)
    rows.append(e)

groups={g:[x for x in rows if x['state']==g] for g in ['CONVERGENT','DIVERGENT','RATES_FLAT']}
result={
 'schema':'GMFQ_CAD_REACTION_FUNCTION_STATE_REPLAY_VNEXT_V1','status':'PASS','created_at':'2026-10-06',
 'scope':'Diagnostic vNext state replay for CAD: frozen first-release Labour -> BoC interpretation -> observed 5-market-day 2Y repricing -> FX outcomes. Rates are state, never a filter.',
 'engine_baseline':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','modified':False},
 'input_provenance':{'labour':LAB_URL,'rates':RATES_URL,'fx':str(FX.relative_to(ROOT))},
 'method':{'labour_signal':'unchanged frozen PIT Labour direction','cb_interpretation':'direct employment relevance under BoC reaction-function map','rates_window_market_days':5,'rates_role':'observed repricing state, not confirmation gate','fx_entry':'first ECB FX reference day after rates window','horizons_days':H,'threshold_tuning':False,'parameter_fitting':False},
 'counts':{'events':len(rows),**{k:len(v) for k,v in groups.items()}},
 'all':{f'{h}d':stats(rows,h) for h in H},
 'by_state':{k:{f'{h}d':stats(v,h) for h in H} for k,v in groups.items()},
 'rows':rows,
 'interpretation_rule':'Convergence/divergence is explanatory state only. No state is promoted, discarded, or reweighted from these results.',
 'changes_engine_rules':False,'changes_live_data':False
}
OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({'counts':result['counts'],'by_state':result['by_state']},indent=2))
