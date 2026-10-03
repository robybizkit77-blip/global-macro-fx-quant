#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
from datetime import date

OUT=Path('validation/PIT_MACRO_REPLAY_V1_2026-10-03.json')

def load(p): return json.loads(Path(p).read_text())
def med(a):
    a=[x for x in a if isinstance(x,(int,float)) and math.isfinite(x)]
    return statistics.median(a) if a else None
def scale(vals):
    diffs=[abs(vals[i]-vals[i-1]) for i in range(1,len(vals)) if math.isfinite(vals[i]) and math.isfinite(vals[i-1])]
    m=med(diffs)
    return m if m and m>0 else None
def impulse(vals,pol):
    vals=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
    if len(vals)<8: return None
    s=scale(vals[-80:])
    if not s: return None
    d0=(vals[-1]-vals[-2])*pol/s
    d1=(vals[-2]-vals[-3])*pol/s
    return {'current':d0,'previous':d1}
def block(series_vals):
    imps=[]
    for vals,pol in series_vals:
        z=impulse(vals,pol)
        if z: imps.append(z)
    if not imps: return None
    cur=med([z['current'] for z in imps]); prev=med([z['previous'] for z in imps])
    if cur is None or prev is None: return None
    direction=0 if abs(cur)<0.20 else (1 if cur>0 else -1)
    acc=cur-prev; accel=0 if abs(acc)<0.20 else (1 if acc>0 else -1)
    turning=(prev!=0 and direction!=0 and (1 if prev>0 else -1)!=direction)
    return {'direction':direction,'speed':abs(cur),'acceleration':acc,'accelDir':accel,'turning':turning,'n':len(imps)}
def synth_from_growth(rows,date_key,val_key):
    lvl=100.0; out=[]
    for r in sorted(rows,key=lambda x:x[date_key]):
        v=r.get(val_key)
        if v is None: continue
        lvl*=1+float(v)/100.0
        out.append({'release_date':r['release_date'] if 'release_date' in r else r.get('first_release_date'),'value':lvl})
    return out
def vals_asof(series,cp): return [r['value'] for r in series if r['release_date'] and r['release_date']<=cp]
def replay(series_by_block):
    cps=sorted({r['release_date'] for block_map in series_by_block.values() for s in block_map.values() for r in s['rows'] if r.get('release_date')})
    out=[]
    for cp in cps:
        row={'checkpoint':cp,'blocks':{}}
        for b,ss in series_by_block.items():
            row['blocks'][b]=block([(vals_asof(s['rows'],cp),s['pol']) for s in ss.values()])
        g=row['blocks'].get('Crescita'); l=row['blocks'].get('Lavoro')
        if g and l:
            sm=g['direction']+l['direction']; pol=0 if sm==0 else (1 if sm>0 else -1)
            row['macro_polarity']=pol
            row['macro_turning']=bool(g.get('turning') or l.get('turning'))
        else:
            row['macro_polarity']=None; row['macro_turning']=None
        out.append(row)
    return out

# USD
ind=load('validation/pit_batch/fed_g17/FED_G17_INDPRO_PIT_BATCH_READY_V1_2026-10-02.json')['rows']
ind_rows=[{'release_date':r['release_date'],'value':float(r['initial_index_level'])} for r in ind]
bea=load('validation/pit_batch/bea/BEA_PIO_PIT_BATCH_V1_2026-10-03.json')['rows']
pi_rows=synth_from_growth([r for r in bea if r.get('personal_income_first_release_mom_pct') is not None],'observation_month','personal_income_first_release_mom_pct')
new=load('validation/pit_batch/census/CENSUS_M3_NEWORDER_PIT_BATCH_V1_2026-10-03.json')['rows']
new_rows=[{'release_date':r['release_date'],'value':float(r['neworder_first_release_millions_sa'])} for r in new if r.get('neworder_first_release_millions_sa') is not None]
usd=replay({'Crescita':{
 'US_INDPRO_history_value':{'pol':1,'rows':ind_rows},
 'US_PI_history_PI':{'pol':1,'rows':pi_rows},
 'US_NEWORDER_history_NEWORDER':{'pol':1,'rows':new_rows},
}})

# EUR
eur0=load('validation/pit_batch/eurostat/EUROSTAT_PIT_READY_V1_2026-10-02.json')['series']
ip_rows=[{'release_date':r['first_release_date'],'value':float(r['first_release_synth_level'])} for r in eur0['EA_IP_history_value']['rows']]
un_rows=[{'release_date':r['first_release_date'],'value':float(r['first_release_value'])} for r in eur0['EA_UNEMP_history_value']['rows']]
emp=load('validation/pit_batch/eurostat/archive/EUR_EMPLOYMENT_DATED_RELEASE_CRAWL_V1_2026-10-02.json')['rows']
emp_rows=synth_from_growth(emp,'reference_quarter','employment_qoq_pct')
eur=replay({'Crescita':{'EA_IP_history_value':{'pol':1,'rows':ip_rows}},'Lavoro':{
 'EA_UNEMP_history_value':{'pol':-1,'rows':un_rows},
 'EA_EMPLOYMENT_history_value':{'pol':1,'rows':emp_rows},
}})

# CAD: reuse already-validated v9.3-equivalent first-release macro replay
cad_src=load('validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json')
cad=[]
for r in cad_src['comparisons']:
    fr=r['first_release']
    cad.append({'checkpoint':r['checkpoint'],'blocks':{
        'Crescita':{'direction':fr.get('growth_direction')},
        'Lavoro':{'direction':fr.get('labour_direction')},
    },'macro_polarity':fr.get('macro_polarity'),'macro_turning':fr.get('turning_present')})

def summ(rows):
    usable=[r for r in rows if any(v is not None for v in r.get('blocks',{}).values())]
    macro=[r for r in rows if r.get('macro_polarity') is not None]
    turns=[r['checkpoint'] for r in rows if r.get('macro_turning')]
    return {'checkpoints':len(rows),'usable_checkpoints':len(usable),'macro_complete_checkpoints':len(macro),'macro_turning_count':len(turns),'last_checkpoint':rows[-1]['checkpoint'] if rows else None,'last_state':rows[-1] if rows else None}

payload={
 'schema':'GMFQ_PIT_MACRO_REPLAY_V1','created_at':date.today().isoformat(),
 'engine':{'model_rules_version':'9.3-pair-attention-hierarchy','rules_fingerprint':'3356baf0','threshold_direction':0.20,'threshold_acceleration':0.20,'scale':'median absolute first differences, last 80 observations','minimum_observations':8},
 'guardrails':['PIT/first-release observations only','No revised-history fallback','Withheld currencies produce no replay vote','USD macro overall withheld because Labour is unavailable'],
 'currencies':{
   'USD':{'status':'PIT_GROWTH_ONLY','replay':usd,'summary':summ(usd)},
   'EUR':{'status':'PIT_MACRO_CORE_READY','replay':eur,'summary':summ(eur)},
   'CAD':{'status':'PIT_MACRO_CORE_READY_REUSED_VALIDATED_V93','replay':cad,'summary':summ(cad)},
   'GBP':{'status':'WITHHELD_PIT'},'JPY':{'status':'WITHHELD_PIT'},'CHF':{'status':'WITHHELD_PIT'},'AUD':{'status':'WITHHELD_PIT'},'NZD':{'status':'WITHHELD_PIT'}
 }
}
OUT.write_text(json.dumps(payload,indent=2)+"\n")
print(json.dumps({k:v.get('summary',{'status':v['status']}) for k,v in payload['currencies'].items()},indent=2))
