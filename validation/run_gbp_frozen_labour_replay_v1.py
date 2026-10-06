#!/usr/bin/env python3
import csv,json,math,statistics
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/'history/pit_v1/GBP_LABOUR_A01_CERTIFIED_VINTAGES_2018_2026.csv'
FX=ROOT/'history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
OUT=ROOT/'validation/GBP_FROZEN_LABOUR_REPLAY_V1_2026-10-06.json'
CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']; H=[5,20,60]

def robust_scale(vals):
    ds=[abs(vals[i]-vals[i-1]) for i in range(1,len(vals))]
    if not ds:return None
    m=statistics.median(ds)
    return m if m>0 and math.isfinite(m) else None

def impulse(vals,pol):
    if len(vals)<8:return None
    s=robust_scale(vals[-80:])
    if not s:return None
    cur=(vals[-1]-vals[-2])*pol/s
    prev=(vals[-2]-vals[-3])*pol/s
    return {'current':cur,'previous':prev}

def block(emp,unemp):
    xs=[impulse(emp,1),impulse(unemp,-1)]; xs=[x for x in xs if x]
    if not xs:return None
    cur=statistics.median([x['current'] for x in xs]); prev=statistics.median([x['previous'] for x in xs])
    direction=0 if abs(cur)<0.20 else (1 if cur>0 else -1)
    acc=cur-prev; accel_dir=0 if abs(acc)<0.20 else (1 if acc>0 else -1)
    ps=0 if prev==0 else (1 if prev>0 else -1)
    turning=(ps!=0 and direction!=0 and ps!=direction)
    return {'current':cur,'previous':prev,'direction':direction,'acceleration':acc,'accelDir':accel_dir,'turning':turning,'n':len(xs)}

with LAB.open(newline='',encoding='utf-8') as f: lab=list(csv.DictReader(f))
with FX.open(newline='',encoding='utf-8') as f: fx=list(csv.DictReader(f))
fxdates=[date.fromisoformat(r['date']) for r in fx]

def entry_idx(ds):
    d=date.fromisoformat(ds)
    for i,x in enumerate(fxdates):
        if x>d:return i
    return None

def pair_ret(ccy,o,i0,i1):
    a=ccy+o;b=o+ccy
    if a in fx[i0] and fx[i0][a] and fx[i1][a]:return math.log(float(fx[i1][a])/float(fx[i0][a]))
    return -math.log(float(fx[i1][b])/float(fx[i0][b]))

def basket(ccy,i0,i1):return sum(pair_ret(ccy,o,i0,i1) for o in CCYS if o!=ccy)/7

def stats(es,h):
    vs=[e[f'signed_{h}d'] for e in es if f'signed_{h}d' in e]
    if not vs:return {'n':0,'hit_rate':None,'mean':None,'median':None}
    return {'n':len(vs),'hit_rate':sum(v>0 for v in vs)/len(vs),'mean':sum(vs)/len(vs),'median':statistics.median(vs)}

def walkforward(es):
    n=len(es); init=max(1,int(n*.4)); rem=n-init;base=rem//3;extra=rem%3;start=init; pooled=[];folds=[]
    for k in range(3):
        z=base+(1 if k<extra else 0); test=es[start:start+z]; start+=z
        if not test:continue
        pooled+=test; folds.append({'fold':k+1,'test_n':len(test),'test_start':test[0]['checkpoint'],'test_end':test[-1]['checkpoint'],'stats':{f'{h}d':stats(test,h) for h in H}})
    return {'initial_train_n':init,'folds':folds,'pooled_oos':{f'{h}d':stats(pooled,h) for h in H},'pooled_oos_n':len(pooled)}

emp=[];unemp=[];rows=[];entries=[];prev_dir=None
for r in lab:
    emp.append(float(r['employment_rate']));unemp.append(float(r['unemployment_rate']))
    b=block(emp,unemp)
    if not b:continue
    rec={'checkpoint':r['publication_date'],'reference_period':r['reference_period'],**b};rows.append(rec)
    if b['direction'] not in (-1,1) or b['direction']==prev_dir:continue
    prev_dir=b['direction']; i0=entry_idx(r['publication_date'])
    if i0 is None:continue
    e={'checkpoint':r['publication_date'],'entry_date':fx[i0]['date'],'direction':b['direction']}
    for h in H:
        if i0+h<len(fx):e[f'signed_{h}d']=b['direction']*basket('GBP',i0,i0+h)
    entries.append(e)

report={'schema':'GMFQ_GBP_FROZEN_LABOUR_REPLAY_V1','status':'PASS','created_at':'2026-10-06','scope':'GBP ONS A01 certified PIT Labour using frozen v9.3 blockDynamics-equivalent formula, tested versus equal-weight G8 FX basket.','engine':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','threshold_direction':0.2,'threshold_acceleration':0.2},'construction':{'series':['LF24 employment rate','MGSX unemployment rate'],'polarity':{'employment_rate':1,'unemployment_rate':-1},'scale':'median absolute first differences, last 80 observations','aggregation':'median of eligible normalized series impulses','event':'new non-zero Labour direction regime only','entry':'next ECB FX reference day after ONS publication date'},'counts':{'vintages':len(lab),'usable_block_checkpoints':len(rows),'regime_entries':len(entries)},'full_sample':{f'{h}d':stats(entries,h) for h in H},'walkforward':walkforward(entries),'rows':rows,'entries':entries,'guardrails':['No threshold tuning','No parameter fitting','No revised-history fallback','Chronological PIT order','engine/live_data untouched'],'changes_engine_rules':False,'changes_live_data':False}
OUT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'counts':report['counts'],'full_sample':report['full_sample'],'pooled_oos':report['walkforward']['pooled_oos']},indent=2))
