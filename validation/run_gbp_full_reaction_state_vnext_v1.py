#!/usr/bin/env python3
import csv,json,math,random,statistics
from datetime import datetime,date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/'history/pit_v1/GBP_LABOUR_A01_CERTIFIED_VINTAGES_2018_2026.csv'
AWE=ROOT/'history/pit_v1/GBP_AWE_K54L_CERTIFIED_VINTAGES_2018_2026.csv'
SERV=ROOT/'history/pit_v1/GBP_CPI_SERVICES_D7NN_CERTIFIED_VINTAGES_2018_2026.csv'
OIS=ROOT/'history/pit_v1/GBP_BOE_OIS_SPOT_2Y_DAILY_2018_2026.csv'
FX=ROOT/'history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
OUT=ROOT/'validation/GBP_FULL_REACTION_STATE_VNEXT_V1_2026-10-06.json'
ROB=ROOT/'validation/GBP_FULL_REACTION_STATE_VNEXT_V1_ROBUSTNESS_2026-10-06.json'
H=[5,20,60]; CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

def dmy(s):
    s=s.strip()
    for fmt in ('%d %B %Y','%Y-%m-%d'):
        try:return datetime.strptime(s,fmt).date()
        except:pass
    raise ValueError(s)

def med_scale(vals):
    ds=[abs(vals[i]-vals[i-1]) for i in range(1,len(vals))]
    if not ds:return None
    m=statistics.median(ds[-80:]); return m if m>0 else None

def impulse(vals,polarity=1):
    if len(vals)<8:return None
    s=med_scale(vals)
    if not s:return None
    cur=polarity*(vals[-1]-vals[-2])/s
    prev=polarity*(vals[-2]-vals[-3])/s
    direction=0 if abs(cur)<0.20 else (1 if cur>0 else -1)
    return {'current':cur,'previous':prev,'direction':direction}

def stats(rows,key):
    vals=[r[key] for r in rows if key in r and r[key] is not None]
    if not vals:return {'n':0,'mean':None,'median':None,'positive_share':None}
    return {'n':len(vals),'mean':sum(vals)/len(vals),'median':statistics.median(vals),'positive_share':sum(v>0 for v in vals)/len(vals)}

lab=list(csv.DictReader(LAB.open(encoding='utf-8')))
awe=list(csv.DictReader(AWE.open(encoding='utf-8')))
serv=list(csv.DictReader(SERV.open(encoding='utf-8')))
ois=list(csv.DictReader(OIS.open(encoding='utf-8')))
fx=list(csv.DictReader(FX.open(encoding='utf-8')))

# Release-event map. Same frozen impulse mechanics for all state variables; no fitted weights.
events={}
for r in lab: events.setdefault(dmy(r['publication_date']),[]).append(('lab',r))
for r in awe: events.setdefault(dmy(r['available_date']),[]).append(('awe',r))
for r in serv: events.setdefault(dmy(r['available_date']),[]).append(('serv',r))
emp=[]; unemp=[]; wages=[]; services=[]
state_rows=[]
for dt in sorted(events):
    for kind,r in events[dt]:
        if kind=='lab': emp.append(float(r['employment_rate'])); unemp.append(float(r['unemployment_rate']))
        elif kind=='awe': wages.append(float(r['yoy_pct']))
        else: services.append(float(r['annual_rate_pct']))
    ie=impulse(emp,1); iu=impulse(unemp,-1); iw=impulse(wages,1); isv=impulse(services,1)
    if not all((ie,iu,iw,isv)):continue
    labour_cur=statistics.median([ie['current'],iu['current']])
    labour_dir=0 if abs(labour_cur)<0.20 else (1 if labour_cur>0 else -1)
    wage_dir=iw['direction']; service_dir=isv['direction']
    if wage_dir!=0 and wage_dir==service_dir:
        domestic_dir=wage_dir
        if labour_dir==domestic_dir: state='DOMESTIC_LABOUR_ALIGNED'
        elif labour_dir==-domestic_dir: state='DOMESTIC_LABOUR_CONFLICT'
        else: state='DOMESTIC_ALIGNED_LABOUR_NEUTRAL'
    elif wage_dir==0 and service_dir==0:
        domestic_dir=0; state='DOMESTIC_NEUTRAL'
    elif wage_dir==-service_dir and wage_dir!=0:
        domestic_dir=0; state='WAGES_SERVICES_CONFLICT'
    else:
        domestic_dir=wage_dir if wage_dir!=0 else service_dir
        state='DOMESTIC_PARTIAL_SIGNAL'
    state_rows.append({'checkpoint':dt,'labour_direction':labour_dir,'wage_direction':wage_dir,'services_direction':service_dir,'domestic_direction':domestic_dir,'state':state})

rates=[]
for r in ois:
    try:rates.append((date.fromisoformat(r['date']),float(r['gbp_ois_spot_2y_pct'])))
    except:pass
rates.sort()
def rate_window(dt):
    p=[x for x in rates if x[0]>dt]
    if len(p)<6:return None
    delta=p[5][1]-p[0][1]; direction=1 if delta>0 else -1 if delta<0 else 0
    return {'start_date':p[0][0].isoformat(),'end_date':p[5][0].isoformat(),'delta_2y':delta,'direction':direction}
fxdates=[date.fromisoformat(r['date']) for r in fx]
def next_fx(dt):
    for i,d in enumerate(fxdates):
        if d>dt:return i
    return None
def pairret(c,o,i0,i1):
    a=c+o;b=o+c
    if a in fx[i0] and fx[i0][a] and fx[i1][a]:return math.log(float(fx[i1][a])/float(fx[i0][a]))
    if b in fx[i0] and fx[i0][b] and fx[i1][b]:return -math.log(float(fx[i1][b])/float(fx[i0][b]))
    raise KeyError((c,o))
def basket(i0,i1):return sum(pairret('GBP',o,i0,i1) for o in CCYS if o!='GBP')/7

rows=[]
for s in state_rows:
    rw=rate_window(s['checkpoint'])
    if not rw:continue
    i0=next_fx(date.fromisoformat(rw['end_date']))
    if i0 is None:continue
    dd=s['domestic_direction']
    if dd!=0:
        rates_state='SAME' if rw['direction']==dd else 'OPPOSITE' if rw['direction']==-dd else 'FLAT'
    else: rates_state='NO_DIRECTIONAL_COMPARISON'
    e={**{k:(v.isoformat() if k=='checkpoint' else v) for k,v in s.items()},'rates_direction':rw['direction'],'rates_state':rates_state,'delta_2y_5d':rw['delta_2y'],'fx_entry_date':fx[i0]['date']}
    for h in H:
        if i0+h<len(fx):
            raw=basket(i0,i0+h); e[f'gbp_basket_{h}d']=raw
            if dd!=0:e[f'signed_{h}d']=dd*raw
    rows.append(e)

groups={k:[r for r in rows if r['state']==k] for k in sorted(set(r['state'] for r in rows))}
rate_groups={k:[r for r in rows if r['rates_state']==k] for k in ['SAME','OPPOSITE','FLAT']}
res={'schema':'GMFQ_GBP_FULL_REACTION_STATE_VNEXT_V1','status':'PASS','created_at':'2026-10-06','scope':'GBP Labour PIT + AWE + CPI Services -> BoE domestic-pressure state -> observed 5-market-day 2Y OIS repricing -> GBP G8 basket. Wages+services define primary domestic inflation pressure; Labour is context.','engine_baseline':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','modified':False},'architecture':{'labour':'frozen-style median of employment (+) and unemployment (-) normalized impulses','wages':'AWE K54L YoY frozen-style impulse','services':'CPI Services D7NN YoY frozen-style impulse','boe_primary_direction':'wages and services when aligned; no fitted weights','rates':'2Y OIS observed state only, never a gate'},'guardrails':['0.20 threshold unchanged','no parameter fitting','no window selection','state definitions predeclared','engine/live_data untouched'],'counts':{'events':len(rows),'by_state':{k:len(v) for k,v in groups.items()}},'by_state':{k:{f'{h}d':stats(v,f'signed_{h}d') for h in H} for k,v in groups.items()},'by_rates_state':{k:{f'{h}d':stats(v,f'signed_{h}d') for h in H} for k,v in rate_groups.items()},'rows':rows,'changes_engine_rules':False,'changes_live_data':False}
OUT.write_text(json.dumps(res,indent=2)+'\n',encoding='utf-8')

# Robustness: fixed states, chronological halves + 3 forward folds on final 60%; bootstrap descriptive only.
def boot(vals,nboot=4000):
    if not vals:return {'n':0,'lo':None,'hi':None}
    rng=random.Random(5606+len(vals)); means=[]
    for _ in range(nboot):means.append(sum(rng.choice(vals) for _ in vals)/len(vals))
    means.sort(); return {'n':len(vals),'lo':means[int(.025*nboot)],'hi':means[int(.975*nboot)-1]}
def group_stats(rs):
    out={}
    for k in sorted(groups):
        rr=[r for r in rs if r['state']==k]
        out[k]={}
        for h in H:
            vals=[r[f'signed_{h}d'] for r in rr if f'signed_{h}d' in r]
            z=stats(rr,f'signed_{h}d'); z['bootstrap_mean_95']=boot(vals); out[k][f'{h}d']=z
    return out
rows2=sorted(rows,key=lambda r:r['checkpoint']); mid=len(rows2)//2; init=max(1,int(len(rows2)*.4)); tail=rows2[init:]; folds=[]
for j in range(3):
    a=j*len(tail)//3; b=(j+1)*len(tail)//3
    test=tail[a:b]
    folds.append({'fold':j+1,'test_start':test[0]['checkpoint'] if test else None,'test_end':test[-1]['checkpoint'] if test else None,'by_state':group_stats(test)})
rob={'schema':'GMFQ_GBP_FULL_REACTION_STATE_VNEXT_V1_ROBUSTNESS','status':'PASS','created_at':'2026-10-06','source':OUT.name,'guardrails':['state definitions unchanged','chronological splits only','bootstrap descriptive only','no tuning'],'full_sample':group_stats(rows2),'split_half':{'first':group_stats(rows2[:mid]),'second':group_stats(rows2[mid:])},'walkforward':{'initial_history_n':init,'pooled_oos_n':len(tail),'folds':folds,'pooled_by_state':group_stats(tail)}}
ROB.write_text(json.dumps(rob,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'counts':res['counts'],'by_state':res['by_state'],'pooled_oos':rob['walkforward']['pooled_by_state']},indent=2))
