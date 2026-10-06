#!/usr/bin/env python3
import csv,json,math,statistics,urllib.request
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FX=ROOT/'history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
OUT=ROOT/'validation/CAD_BOC_LABOUR_2Y_PAIRED_ATTRIBUTION_V1_2026-10-06.json'
LAB_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/engine-freeze-v1-2026-10-02/validation/PIT_SIGNAL_SENSITIVITY_CA_LABOUR_FULL_2020_2026_V1_2026-10-02.json'
RATES_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/engine-freeze-v1-2026-10-02/validation/PIT_REPLAY_CA_RATES_POLICY_2020_2026_V1_2026-10-02.json'
CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];H=[5,20,60]
def loadurl(u):
    with urllib.request.urlopen(u,timeout=60) as r:return json.load(r)
lab=loadurl(LAB_URL); rates=loadurl(RATES_URL)
with FX.open(newline='',encoding='utf-8') as f:fx=list(csv.DictReader(f))
fxdates=[date.fromisoformat(r['date']) for r in fx]
rr=sorted(rates['rows'],key=lambda x:x['date']); rdates=[date.fromisoformat(r['date']) for r in rr]
def first_gt(ds,arr):
    d=date.fromisoformat(ds)
    for i,x in enumerate(arr):
        if x>d:return i
    return None
def pair_ret(ccy,o,i0,i1):
    a=ccy+o;b=o+ccy
    if a in fx[i0] and fx[i0][a] and fx[i1][a]:return math.log(float(fx[i1][a])/float(fx[i0][a]))
    return -math.log(float(fx[i1][b])/float(fx[i0][b]))
def basket(i0,i1):return sum(pair_ret('CAD',o,i0,i1) for o in CCYS if o!='CAD')/7
def stats(es,h):
    vs=[e[f'signed_{h}d'] for e in es if f'signed_{h}d' in e]
    if not vs:return {'n':0,'hit_rate':None,'mean':None,'median':None}
    return {'n':len(vs),'hit_rate':sum(v>0 for v in vs)/len(vs),'mean':sum(vs)/len(vs),'median':statistics.median(vs)}
def wf(es):
    es=sorted(es,key=lambda x:x['checkpoint']);cut=int(len(es)*.4);test=es[cut:]
    return {'train_n':cut,'test_n':len(test),'test_start':test[0]['checkpoint'] if test else None,'test_end':test[-1]['checkpoint'] if test else None,'test_stats':{f'{h}d':stats(test,h) for h in H}}
all_events=[];confirmed=[];rejected=[]
for c in lab['comparisons']:
    d=c['first_release'].get('direction')
    if d not in (-1,1):continue
    ri=first_gt(c['checkpoint'],rdates)
    if ri is None or ri+5>=len(rr):continue
    y0=float(rr[ri]['y2']);y5=float(rr[ri+5]['y2']);chg=y5-y0
    conf=(chg*d)>0
    fi=first_gt(rr[ri+5]['date'],fxdates)
    if fi is None:continue
    e={'checkpoint':c['checkpoint'],'labour_direction':d,'rates_start':rr[ri]['date'],'rates_end':rr[ri+5]['date'],'y2_start':y0,'y2_end':y5,'y2_change':chg,'confirmed':conf,'fx_entry_date':fx[fi]['date']}
    for h in H:
        if fi+h<len(fx):e[f'signed_{h}d']=d*basket(fi,fi+h)
    all_events.append(e);(confirmed if conf else rejected).append(e)
report={'schema':'GMFQ_CAD_BOC_LABOUR_2Y_PAIRED_ATTRIBUTION_V1','status':'PASS','created_at':'2026-10-06','scope':'Frozen first-release CAD Labour block versus 5-market-day Canadian 2Y confirmation, same event universe and post-confirmation FX timing.','engine':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0'},'guardrails':['CAD Labour signal taken unchanged from frozen PIT sensitivity','5-market-day 2Y window predeclared to mirror GBP test','same post-confirmation FX timing for confirmed/rejected','no threshold tuning','no parameter fitting','engine/live_data untouched'],'counts':{'all':len(all_events),'confirmed':len(confirmed),'rejected':len(rejected)},'all':{'stats':{f'{h}d':stats(all_events,h) for h in H},'walkforward_reference':wf(all_events)},'confirmed':{'stats':{f'{h}d':stats(confirmed,h) for h in H},'walkforward_reference':wf(confirmed)},'rejected':{'stats':{f'{h}d':stats(rejected,h) for h in H},'walkforward_reference':wf(rejected)},'incremental_confirmation':{f'{h}d':{'confirmed_minus_rejected_hit_rate':stats(confirmed,h)['hit_rate']-stats(rejected,h)['hit_rate'],'confirmed_minus_rejected_mean':stats(confirmed,h)['mean']-stats(rejected,h)['mean']} for h in H},'assessment_policy':'Rates confirmation is useful only if confirmed events materially outperform rejected events and the effect persists in chronological holdout.','changes_engine_rules':False,'changes_live_data':False}
OUT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'counts':report['counts'],'confirmed':report['confirmed']['stats'],'rejected':report['rejected']['stats'],'incremental':report['incremental_confirmation']},indent=2))
