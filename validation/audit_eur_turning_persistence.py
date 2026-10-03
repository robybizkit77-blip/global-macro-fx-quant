#!/usr/bin/env python3
import json, math, statistics, re
from pathlib import Path

TH=0.20
SRC=Path('validation/pit_batch/eurostat/EUROSTAT_PIT_READY_V1_2026-10-02.json')
EMP=Path('validation/pit_batch/eurostat/archive/EUR_EMPLOYMENT_DATED_RELEASE_CRAWL_V1_2026-10-02.json')
PAYLOAD=Path('payload/part-01.txt')
OUT=Path('validation/EUR_TURNING_PERSISTENCE_AUDIT_2026-10-03.json')

POL={'EA_IP_history_value':1,'EA_UNEMP_history_value':-1,'EA_EMPLOYMENT_history_value':1}
CAT={'EA_IP_history_value':'Growth','EA_UNEMP_history_value':'Labour','EA_EMPLOYMENT_history_value':'Labour'}

def pick(row,prefix):
    ks=[k for k in row if k.startswith(prefix)]
    preferred=[k for k in ks if k.endswith('_level') or k.endswith('_value')]
    for k in preferred+ks:
        v=row.get(k)
        if isinstance(v,(int,float)) and math.isfinite(float(v)): return float(v)
    return None

def impulse(vals,polarity=1):
    vals=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
    if len(vals)<8:return None
    diffs=[abs(vals[i]-vals[i-1]) for i in range(max(1,len(vals)-80),len(vals))]
    if not diffs:return None
    scale=statistics.median(diffs)
    if not scale or scale<=0:return None
    cur=(vals[-1]-vals[-2])*polarity/scale
    prev=(vals[-2]-vals[-3])*polarity/scale
    direction=0 if abs(cur)<TH else (1 if cur>0 else -1)
    ps=0 if prev==0 else (1 if prev>0 else -1)
    return {'current':cur,'previous':prev,'direction':direction,'turning':bool(ps!=0 and direction!=0 and ps!=direction)}

def block(states):
    xs=[x for x in states if x]
    if not xs:return None
    cur=statistics.median([x['current'] for x in xs]); prev=statistics.median([x['previous'] for x in xs])
    d=0 if abs(cur)<TH else (1 if cur>0 else -1)
    ps=0 if prev==0 else (1 if prev>0 else -1)
    return {'current':cur,'previous':prev,'direction':d,'turning':bool(ps!=0 and d!=0 and ps!=d),'n':len(xs)}

def macro(g,l):
    if not g or not l:return None
    s=g['direction']+l['direction']
    return {'polarity':0 if s==0 else (1 if s>0 else -1),'turning':bool(g['turning'] or l['turning'])}

base=json.loads(SRC.read_text())
series=base['series']
rows={}
for sid in ['EA_IP_history_value','EA_UNEMP_history_value']:
    rr=[]
    for r in series[sid].get('rows',[]):
        fv=pick(r,'first_release'); rv=pick(r,'current_revised')
        d=r.get('first_release_date') or r.get('release_date')
        o=r.get('observation_month') or r.get('reference_month') or r.get('period')
        if fv is not None and rv is not None and d and o:
            rr.append({'release_date':d,'obs':o,'first':fv,'revised':rv})
    rows[sid]=sorted(rr,key=lambda x:(x['release_date'],x['obs']))

# Employment: official first-release q/q path compounded. Revised runtime level extracted from payload.
emp=json.loads(EMP.read_text())['rows']
first_level=100.0
first_map=[]
for r in sorted(emp,key=lambda x:x['reference_quarter']):
    first_level*=1.0+float(r['employment_qoq_pct'])/100.0
    first_map.append({'release_date':r['release_date'],'obs':r['reference_quarter'],'first':first_level})

text=PAYLOAD.read_text()
m=re.search(r'EA_EMPLOYMENT_history_value\s*:\s*\[(.*?)\]\s*,',text,re.S)
if not m: raise SystemExit('EA_EMPLOYMENT_history_value not found in payload')
rev_pairs=re.findall(r'\[\s*["\'](20\d{2}-Q[1-4])["\']\s*,\s*(-?\d+(?:\.\d+)?)\s*\]',m.group(1))
rev={q:float(v) for q,v in rev_pairs}
rows['EA_EMPLOYMENT_history_value']=sorted([{**r,'revised':rev[r['obs']]} for r in first_map if r['obs'] in rev],key=lambda x:(x['release_date'],x['obs']))

events=sorted(set(r['release_date'] for rr in rows.values() for r in rr))
replay=[]
for cp in events:
    fs={}; rs={}
    for sid,rr in rows.items():
        avail=[r for r in rr if r['release_date']<=cp]
        fs[sid]=impulse([r['first'] for r in avail],POL[sid]) if avail else None
        rs[sid]=impulse([r['revised'] for r in avail],POL[sid]) if avail else None
    fg=block([fs.get(s) for s in fs if CAT[s]=='Growth']); fl=block([fs.get(s) for s in fs if CAT[s]=='Labour'])
    rg=block([rs.get(s) for s in rs if CAT[s]=='Growth']); rl=block([rs.get(s) for s in rs if CAT[s]=='Labour'])
    fm=macro(fg,fl); rm=macro(rg,rl)
    if fm and rm: replay.append({'checkpoint':cp,'first':fm,'revised':rm})

# Focus on first-release turning signals that disagree with revised history at that same checkpoint (fragile turning).
fragile=[]
for i,x in enumerate(replay[:-1]):
    if x['first']['turning'] and x['first']['turning']!=x['revised']['turning']:
        nxt=replay[i+1]
        fragile.append({
            'checkpoint':x['checkpoint'],
            'next_checkpoint':nxt['checkpoint'],
            'first_polarity':x['first']['polarity'],
            'next_first_turning':nxt['first']['turning'],
            'next_first_polarity':nxt['first']['polarity'],
            'turning_persists_next':bool(nxt['first']['turning']),
            'macro_polarity_changes_next':bool(nxt['first']['polarity']!=x['first']['polarity'])
        })

n=len(fragile); pers=sum(x['turning_persists_next'] for x in fragile); flips=sum(x['macro_polarity_changes_next'] for x in fragile)
report={
 'schema':'GMFQ_EUR_TURNING_PERSISTENCE_AUDIT_V1',
 'engine_ref':'engine-freeze-v1-2026-10-02','rules_fingerprint':'3356baf0','threshold_direction':TH,
 'eligible_pit_core':['EA_IP_history_value','EA_UNEMP_history_value','EA_EMPLOYMENT_history_value'],
 'summary':{
   'usable_macro_checkpoints':len(replay),
   'fragile_first_release_turning_cases_with_next_checkpoint':n,
   'turning_persists_next':pers,
   'turning_persists_next_pct':round(100*pers/n,2) if n else None,
   'turning_reverts_next':n-pers,
   'turning_reverts_next_pct':round(100*(n-pers)/n,2) if n else None,
   'macro_polarity_changes_next':flips,
   'macro_polarity_changes_next_pct':round(100*flips/n,2) if n else None
 },
 'cases':fragile,
 'limitations':[
  'EUR PIT coverage remains partial: Retail volume and negotiated wages are withheld and excluded.',
  'Employment first-release path is compounded from official flash q/q growth; normalized impulse is scale-invariant.',
  'This is a descriptive persistence audit, not a trading backtest.'
 ],
 'interpretation_guardrail':'Do not alter model weights, thresholds, or turning rules from this partial EUR PIT sample.',
 'no_model_change':True
}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['summary'],indent=2))
