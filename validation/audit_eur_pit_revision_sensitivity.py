#!/usr/bin/env python3
import json, math, statistics
from pathlib import Path

SRC=Path('validation/pit_batch/eurostat/EUROSTAT_PIT_READY_V1_2026-10-02.json')
OUT=Path('validation/EUR_PIT_REVISION_SENSITIVITY_AUDIT_2026-10-03.json')
TH=0.20
POL={'EA_IP_history_value':1,'EA_UNEMP_history_value':-1,'EA_EMPLOYMENT_history_value':1}
CAT={'EA_IP_history_value':'Growth','EA_UNEMP_history_value':'Labour','EA_EMPLOYMENT_history_value':'Labour'}

def pick(row, prefix):
    ks=[k for k in row if k.startswith(prefix)]
    preferred=[k for k in ks if k.endswith('_level') or k.endswith('_value')]
    for k in preferred+ks:
        v=row.get(k)
        if isinstance(v,(int,float)) and math.isfinite(float(v)):
            return float(v),k
    return None,None

def datekey(row):
    return row.get('first_release_date') or row.get('release_date')

def obskey(row):
    return row.get('observation_month') or row.get('observation_quarter') or row.get('reference_month') or row.get('period')

def impulse(vals, polarity=1):
    vals=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
    if len(vals)<8:return None
    diffs=[abs(vals[i]-vals[i-1]) for i in range(max(1,len(vals)-80),len(vals))]
    diffs=[x for x in diffs if math.isfinite(x)]
    if not diffs:return None
    scale=statistics.median(diffs)
    if not scale or scale<=0:return None
    cur=(vals[-1]-vals[-2])*polarity/scale
    prev=(vals[-2]-vals[-3])*polarity/scale
    direction=0 if abs(cur)<TH else (1 if cur>0 else -1)
    accel=cur-prev
    accel_dir=0 if abs(accel)<TH else (1 if accel>0 else -1)
    prev_sign=0 if prev==0 else (1 if prev>0 else -1)
    turning=(prev_sign!=0 and direction!=0 and prev_sign!=direction)
    return {'current':cur,'previous':prev,'direction':direction,'accelDir':accel_dir,'turning':turning}

def block(states):
    xs=[x for x in states if x]
    if not xs:return None
    cur=statistics.median([x['current'] for x in xs]); prev=statistics.median([x['previous'] for x in xs])
    d=0 if abs(cur)<TH else (1 if cur>0 else -1)
    a=cur-prev; ad=0 if abs(a)<TH else (1 if a>0 else -1)
    ps=0 if prev==0 else (1 if prev>0 else -1)
    return {'current':cur,'previous':prev,'direction':d,'accelDir':ad,'turning':(ps!=0 and d!=0 and ps!=d),'n':len(xs)}

def macro(g,l):
    if not g or not l:return None
    s=g['direction']+l['direction']
    return {'polarity':0 if s==0 else (1 if s>0 else -1),'turning':bool(g['turning'] or l['turning'])}

data=json.loads(SRC.read_text())
series=data['series']
selected={k:series[k] for k in POL if k in series}
# Normalize rows and retain only rows with both PIT and revised values and release date.
rows={}
field_map={}
for sid,s in selected.items():
    rr=[]
    for r in s.get('rows',[]):
        fv,fk=pick(r,'first_release')
        rv,rk=pick(r,'current_revised')
        d=datekey(r); o=obskey(r)
        if fv is None or rv is None or not d or not o: continue
        rr.append({'release_date':d,'obs':o,'first':fv,'revised':rv})
        field_map[sid]={'first':fk,'revised':rk}
    rows[sid]=sorted(rr,key=lambda x:(x['release_date'],x['obs']))

events=sorted(set(r['release_date'] for rr in rows.values() for r in rr))
comparisons=[]
for cp in events:
    fs={}; rs={}; counts={}
    for sid,rr in rows.items():
        avail=[r for r in rr if r['release_date']<=cp]
        if not avail: continue
        fs[sid]=impulse([r['first'] for r in avail],POL[sid])
        rs[sid]=impulse([r['revised'] for r in avail],POL[sid])
        counts[sid]=len(avail)
    fg=block([fs.get(s) for s in fs if CAT[s]=='Growth']); fl=block([fs.get(s) for s in fs if CAT[s]=='Labour'])
    rg=block([rs.get(s) for s in rs if CAT[s]=='Growth']); rl=block([rs.get(s) for s in rs if CAT[s]=='Labour'])
    fm=macro(fg,fl); rm=macro(rg,rl)
    comparisons.append({'checkpoint':cp,'first_release':{'growth':fg,'labour':fl,'macro':fm},'current_revised':{'growth':rg,'labour':rl,'macro':rm},'counts':counts})

usable=[x for x in comparisons if x['first_release']['macro'] and x['current_revised']['macro']]
def changed(path):
    a,b=path
    out=[]
    for x in usable:
        p=x['first_release'][a]; q=x['current_revised'][a]
        if p and q and p[b]!=q[b]:out.append(x['checkpoint'])
    return out

gd=changed(('growth','direction')); ld=changed(('labour','direction')); mp=changed(('macro','polarity')); mt=changed(('macro','turning'))
report={'schema':'GMFQ_EUR_PIT_REVISION_SENSITIVITY_AUDIT_V1','engine_ref':'engine-freeze-v1-2026-10-02','rules_fingerprint':'3356baf0','threshold_direction':TH,'source':str(SRC),'eligible_series':list(selected),'field_map':field_map,'coverage':{k:{'rows':len(v),'from':v[0]['release_date'] if v else None,'to':v[-1]['release_date'] if v else None} for k,v in rows.items()},'summary':{'event_checkpoints':len(comparisons),'usable_macro_checkpoints':len(usable),'growth_direction_changes':len(gd),'growth_direction_change_pct':round(100*len(gd)/len(usable),2) if usable else None,'labour_direction_changes':len(ld),'labour_direction_change_pct':round(100*len(ld)/len(usable),2) if usable else None,'macro_polarity_changes':len(mp),'macro_polarity_change_pct':round(100*len(mp)/len(usable),2) if usable else None,'macro_turning_changes':len(mt),'macro_turning_change_pct':round(100*len(mt)/len(usable),2) if usable else None},'changed_checkpoints':{'growth':gd,'labour':ld,'macro_polarity':mp,'macro_turning':mt},'limitations':['EUR PIT coverage is partial: Retail volume and negotiated wages are withheld and excluded.','This audit tests the eligible PIT Macro Core only; it is not a full FX-engine backtest.'],'no_model_change':True}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['summary'],indent=2))
