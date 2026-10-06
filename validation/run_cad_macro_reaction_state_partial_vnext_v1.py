#!/usr/bin/env python3
import csv,json,math,urllib.request
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MACRO_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/engine-freeze-v1-2026-10-02/validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json'
RATES_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/engine-freeze-v1-2026-10-02/validation/cad_rates_pit/CA_BOC_BENCHMARK_RATES_DAILY_2020_2026_V1.csv'
FX=ROOT/'history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
OUT=ROOT/'validation/CAD_MACRO_REACTION_STATE_PARTIAL_VNEXT_V1_2026-10-06.json'
CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']; H=[5,20,60]
macro=json.load(urllib.request.urlopen(MACRO_URL))
rr=list(csv.DictReader(urllib.request.urlopen(RATES_URL).read().decode().splitlines()))
fx=list(csv.DictReader(FX.open(encoding='utf-8')))
rdate=next(k for k in rr[0] if k.lower() in ('date','observation_date'))
y2=next(k for k in rr[0] if '2' in k.lower() and ('year' in k.lower() or '2y' in k.lower() or 'y2' in k.lower()))
rates=[]
for r in rr:
    try: rates.append((date.fromisoformat(r[rdate][:10]),float(r[y2])))
    except: pass
rates.sort(); fxdates=[date.fromisoformat(r['date']) for r in fx]
def nidx(dt):
    for i,d in enumerate(fxdates):
        if d>dt:return i

def pret(c,o,a,b):
    x=c+o; y=o+c
    if x in fx[a] and fx[a][x] and fx[b][x]: return math.log(float(fx[b][x])/float(fx[a][x]))
    return -math.log(float(fx[b][y])/float(fx[a][y]))
def basket(a,b): return sum(pret('CAD',o,a,b) for o in CCYS if o!='CAD')/7
def rstate(rel,sign):
    p=[x for x in rates if x[0]>rel]
    if len(p)<6:return None
    d=p[5][1]-p[0][1]; rs=1 if d>0 else -1 if d<0 else 0
    state='RATES_FLAT' if rs==0 else ('CONVERGENT' if rs==sign else 'DIVERGENT')
    return p[5][0],state,d
rows=[]
for r in macro['comparisons']:
    fr=r['first_release']; s=fr.get('macro_polarity')
    if s not in (-1,1): continue
    rel=date.fromisoformat(r['checkpoint']); z=rstate(rel,s)
    if not z: continue
    end,state,delta=z; i=nidx(end)
    if i is None: continue
    e={'checkpoint':r['checkpoint'],'growth_direction':fr['growth_direction'],'labour_direction':fr['labour_direction'],'macro_polarity':s,'macro_alignment':fr['alignment'],'inflation_state':'WITHHELD_HISTORICAL_PIT','cb_interpretation':'HAWKISH_PRESSURE' if s>0 else 'DOVISH_PRESSURE','rates_state':state,'delta_2y_5d':delta,'fx_entry_date':fx[i]['date']}
    for h in H:
        if i+h<len(fx):e[f'signed_{h}d']=s*basket(i,i+h)
    rows.append(e)
def stats(xs,h):
    v=[r[f'signed_{h}d'] for r in xs if f'signed_{h}d' in r]; n=len(v)
    if not n:return {'n':0,'hit_rate':None,'mean':None,'median':None}
    q=sorted(v); med=q[n//2] if n%2 else (q[n//2-1]+q[n//2])/2
    return {'n':n,'hit_rate':sum(x>0 for x in v)/n,'mean':sum(v)/n,'median':med}
groups={k:[r for r in rows if r['rates_state']==k] for k in ['CONVERGENT','DIVERGENT','RATES_FLAT']}
out={'schema':'GMFQ_CAD_MACRO_REACTION_STATE_PARTIAL_VNEXT_V1','status':'PASS_PARTIAL_INFLATION_WITHHELD','created_at':'2026-10-06','scope':'CAD Growth+Labour PIT macro state -> BoC interpretation -> observed 5-day 2Y repricing -> CAD basket. Inflation historical first-release PIT unavailable and explicitly WITHHELD.','engine_baseline':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','modified':False},'method':{'macro_signal':'frozen sign(Growth.direction + Labour.direction)','inflation':'WITHHELD_HISTORICAL_PIT','rates_role':'observed state, not filter','rates_window_market_days':5,'fx_entry':'first ECB FX reference day after rates window','threshold_tuning':False,'parameter_fitting':False},'counts':{'events':len(rows),**{k:len(v) for k,v in groups.items()}},'all':{f'{h}d':stats(rows,h) for h in H},'by_rates_state':{k:{f'{h}d':stats(v,h) for h in H} for k,v in groups.items()},'rows':rows,'changes_engine_rules':False,'changes_live_data':False}
OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':out['status'],'counts':out['counts'],'by_rates_state':out['by_rates_state']},indent=2))
