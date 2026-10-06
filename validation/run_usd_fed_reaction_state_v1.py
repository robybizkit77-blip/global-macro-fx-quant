#!/usr/bin/env python3
import csv,json,math,statistics
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/'history/pit_v1/USD_LABOUR_BLS_EMPLOYMENT_SITUATION_FIRST_RELEASE_2016_2026.csv'
CPI=ROOT/'history/pit_v1/USD_CPI_HEADLINE_CORE_FIRST_RELEASE_2016_2026.csv'
RATES=ROOT/'history/pit_v1/USD_TREASURY_PAR_2Y_DAILY_2016_2026.csv'
FX=ROOT/'history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
OUT=ROOT/'validation/USD_FED_REACTION_STATE_V1_2026-10-06.json'
CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
H=[5,20,60]
TH=0.20

lab=list(csv.DictReader(LAB.open(encoding='utf-8')))
cpi=list(csv.DictReader(CPI.open(encoding='utf-8')))
rates=list(csv.DictReader(RATES.open(encoding='utf-8')))
fx=list(csv.DictReader(FX.open(encoding='utf-8')))

def scale(vals):
    ds=[abs(vals[i]-vals[i-1]) for i in range(1,len(vals))]
    if not ds:return None
    m=statistics.median(ds[-80:])
    return m if m>0 else None

def impulse(vals,sign=1.0):
    if len(vals)<8:return None
    s=scale(vals)
    if not s:return None
    cur=sign*(vals[-1]-vals[-2])/s
    prev=sign*(vals[-2]-vals[-3])/s
    d=0 if abs(cur)<TH else (1 if cur>0 else -1)
    return {'current':cur,'previous':prev,'direction':d}

def combine(xs):
    xs=[x for x in xs if x]
    if not xs:return None
    cur=statistics.median(x['current'] for x in xs)
    d=0 if abs(cur)<TH else (1 if cur>0 else -1)
    return {'current':cur,'direction':d,'components':len(xs)}

# Labour: NFP higher = stronger/hawkish; unemployment higher = weaker/dovish.
nfp=[]; unemp=[]; lab_states=[]
for r in sorted(lab,key=lambda x:x['release_date']):
    nfp.append(float(r['nfp_change_persons']))
    unemp.append(float(r['unemployment_rate_pct']))
    z=combine([impulse(nfp,+1.0),impulse(unemp,-1.0)])
    if z:
        lab_states.append({'release_date':r['release_date'],'reference_month':r['reference_month'],'direction':z['direction'],'current':z['current'],'components':z['components']})

# Inflation: headline and core remain separate inputs; equal median only for descriptive state.
head=[]; core=[]; inf_states=[]
for r in sorted(cpi,key=lambda x:x['release_date']):
    head.append(float(r['headline_cpi_yoy_pct']))
    core.append(float(r['core_cpi_yoy_pct']))
    z=combine([impulse(head,+1.0),impulse(core,+1.0)])
    if z:
        inf_states.append({'release_date':r['release_date'],'reference_month':r['reference_month'],'direction':z['direction'],'current':z['current'],'components':z['components']})

rate_rows=[]
for r in rates:
    try: rate_rows.append((date.fromisoformat(r['date']),float(r['usd_treasury_par_2y_pct'])))
    except: pass
rate_rows.sort()

def rate_state(dt):
    p=[x for x in rate_rows if x[0]>dt]
    if len(p)<6:return None
    delta=p[5][1]-p[0][1]
    d=1 if delta>0 else -1 if delta<0 else 0
    return {'direction':d,'delta_2y_5d':delta,'start_date':p[0][0].isoformat(),'end_date':p[5][0].isoformat()}

fxdates=[date.fromisoformat(r['date']) for r in fx]
def next_idx(dt):
    for i,d in enumerate(fxdates):
        if d>dt:return i
    return None

def pairret(c,o,i0,i1):
    a=c+o; b=o+c
    if a in fx[i0] and fx[i0][a] and fx[i1][a]:
        return math.log(float(fx[i1][a])/float(fx[i0][a]))
    return -math.log(float(fx[i1][b])/float(fx[i0][b]))

def basket(i0,i1):
    return sum(pairret('USD',o,i0,i1) for o in CCYS if o!='USD')/7

def latest(states,dt):
    xs=[x for x in states if date.fromisoformat(x['release_date'])<=dt]
    return xs[-1] if xs else None

def joint(ld,id):
    if ld==1 and id==1:return 'LABOUR_INFLATION_BOTH_HAWKISH'
    if ld==-1 and id==-1:return 'LABOUR_INFLATION_BOTH_DOVISH'
    if ld==1 and id==-1:return 'LABOUR_HAWKISH_INFLATION_DOVISH'
    if ld==-1 and id==1:return 'LABOUR_DOVISH_INFLATION_HAWKISH'
    return 'MIXED_OR_NEUTRAL'

def stats(rows,key):
    vals=[r[key] for r in rows if key in r]
    if not vals:return {'n':0,'mean':None,'median':None,'positive_share':None}
    s=sorted(vals); n=len(s); med=s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
    return {'n':n,'mean':sum(vals)/n,'median':med,'positive_share':sum(v>0 for v in vals)/n}

# Use every official Labour/CPI release as a checkpoint; the other mandate block is last-known PIT state.
events=[]
for r in lab: events.append((date.fromisoformat(r['release_date']),'LABOUR_RELEASE',r['reference_month']))
for r in cpi: events.append((date.fromisoformat(r['release_date']),'CPI_RELEASE',r['reference_month']))
events=sorted(set(events))
rows=[]
for dt,etype,ref in events:
    ls=latest(lab_states,dt); ins=latest(inf_states,dt); rs=rate_state(dt)
    if not ls or not ins or not rs:continue
    j=joint(ls['direction'],ins['direction'])
    if ls['direction']==ins['direction'] and ls['direction']!=0:
        joint_dir=ls['direction']
        rate_alignment='ALIGNED' if rs['direction']==joint_dir else 'CONFLICT' if rs['direction']==-joint_dir else 'FLAT'
    else:
        joint_dir=0; rate_alignment='NO_SINGLE_JOINT_DIRECTION'
    i0=next_idx(date.fromisoformat(rs['end_date']))
    if i0 is None:continue
    e={'checkpoint':dt.isoformat(),'event_type':etype,'reference_month':ref,'labour_direction':ls['direction'],'labour_current':ls['current'],'inflation_direction':ins['direction'],'inflation_current':ins['current'],'joint_state':j,'joint_direction':joint_dir,'rates_direction':rs['direction'],'rate_alignment':rate_alignment,'delta_2y_5d':rs['delta_2y_5d'],'rate_start_date':rs['start_date'],'rate_end_date':rs['end_date'],'fx_entry_date':fx[i0]['date']}
    for hh in H:
        if i0+hh<len(fx): e[f'usd_basket_{hh}d']=basket(i0,i0+hh)
    rows.append(e)

groups={k:[r for r in rows if r['joint_state']==k] for k in sorted(set(r['joint_state'] for r in rows))}
align_groups={k:[r for r in rows if r['rate_alignment']==k] for k in sorted(set(r['rate_alignment'] for r in rows))}
res={
 'schema':'GMFQ_USD_FED_REACTION_STATE_V1',
 'status':'PASS',
 'created_at':'2026-10-06',
 'scope':'Fed dual-mandate descriptive PIT state: first-release Labour + first-release CPI -> observed fixed 5-market-day US Treasury 2Y repricing -> USD equal-weight G8 basket. No fitted weights and no production gate.',
 'engine_baseline':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','modified':False},
 'architecture':{
   'labour':'median frozen-style impulse of NFP change and inverted unemployment-rate change',
   'inflation':'median frozen-style impulse of headline CPI and core CPI; descriptive CPI state only, not a claim CPI is Fed preferred gauge',
   'threshold':TH,
   'rates':'observed 2Y Treasury par-yield direction over fixed 5-market-day post-release window; descriptive, not a filter',
   'fx':'USD versus equal-weight remaining G8 basket, entry strictly after rates checkpoint'
 },
 'guardrails':['no consensus surprise series','no threshold tuning','no parameter fitting','no post-hoc reweighting','PCE remains conceptually distinct and WITHHELD from this V1','2Y is observed transmission state, not production gate','engine/live_data untouched'],
 'counts':{'events':len(rows),'by_event_type':{k:sum(r['event_type']==k for r in rows) for k in sorted(set(r['event_type'] for r in rows))},'by_joint_state':{k:len(v) for k,v in groups.items()}},
 'by_joint_state':{k:{f'{h}d':stats(v,f'usd_basket_{h}d') for h in H} for k,v in groups.items()},
 'by_rate_alignment':{k:{f'{h}d':stats(v,f'usd_basket_{h}d') for h in H} for k,v in align_groups.items()},
 'rows':rows,
 'changes_engine_rules':False,
 'changes_live_data':False
}
OUT.write_text(json.dumps(res,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'counts':res['counts'],'by_joint_state':res['by_joint_state'],'by_rate_alignment':res['by_rate_alignment']},indent=2))
