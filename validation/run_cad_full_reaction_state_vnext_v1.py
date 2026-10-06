#!/usr/bin/env python3
import csv,json,math,statistics,urllib.request
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'history/pit_v1/CAD_CORE_INFLATION_FIRST_RELEASE_2017_2026.csv'
RATES_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/engine-freeze-v1-2026-10-02/validation/cad_rates_pit/CA_BOC_BENCHMARK_RATES_DAILY_2020_2026_V1.csv'
MACRO_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/engine-freeze-v1-2026-10-02/validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json'
FX=ROOT/'history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
OUT=ROOT/'validation/CAD_FULL_REACTION_STATE_VNEXT_V1_2026-10-06.json'
CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']; H=[5,20,60]

def fetch_text(url):
    with urllib.request.urlopen(url,timeout=60) as r:return r.read().decode('utf-8-sig')
macro=json.loads(fetch_text(MACRO_URL))
rr=list(csv.DictReader(fetch_text(RATES_URL).splitlines()))
fx=list(csv.DictReader(FX.open(encoding='utf-8')))
core=list(csv.DictReader(CORE.open(encoding='utf-8')))

def scale(vals):
    ds=[abs(vals[i]-vals[i-1]) for i in range(1,len(vals))]
    if not ds:return None
    m=statistics.median(ds[-80:]); return m if m>0 else None

def impulse(vals):
    if len(vals)<8:return None
    s=scale(vals)
    if not s:return None
    cur=(vals[-1]-vals[-2])/s; prev=(vals[-2]-vals[-3])/s
    direction=0 if abs(cur)<0.20 else (1 if cur>0 else -1)
    return {'current':cur,'previous':prev,'direction':direction}

# Build release-date inflation block from first-release YoY values; at each release use latest available value per measure.
series={k:[] for k in ['CPI_COMMON_YOY','CPI_MEDIAN_YOY','CPI_TRIM_YOY']}
release_events={}
for r in core:
    release_events.setdefault(r['release_date'],[]).append(r)
inf_states=[]
for rel in sorted(release_events):
    for r in release_events[rel]: series[r['series']].append(float(r['first_release_yoy_pct']))
    xs=[impulse(series[k]) for k in series]; xs=[x for x in xs if x]
    if not xs: continue
    cur=statistics.median(x['current'] for x in xs); prev=statistics.median(x['previous'] for x in xs)
    d=0 if abs(cur)<0.20 else (1 if cur>0 else -1)
    inf_states.append({'release_date':rel,'direction':d,'current':cur,'previous':prev,'n':len(xs)})

# Rates parse.
rdate=next(k for k in rr[0] if k.lower() in ('date','observation_date'))
y2=next(k for k in rr[0] if '2' in k.lower() and ('year' in k.lower() or '2y' in k.lower() or 'y2' in k.lower()))
rates=[]
for r in rr:
    try: rates.append((date.fromisoformat(r[rdate][:10]),float(r[y2])))
    except: pass
rates.sort()
def rate_state(dt):
    p=[x for x in rates if x[0]>dt]
    if len(p)<6:return None
    delta=p[5][1]-p[0][1]; d=1 if delta>0 else -1 if delta<0 else 0
    return {'direction':d,'delta_2y_5d':delta,'end_date':p[5][0].isoformat()}
fxdates=[date.fromisoformat(r['date']) for r in fx]
def next_idx(dt):
    for i,d in enumerate(fxdates):
        if d>dt:return i
    return None
def pairret(c,o,i0,i1):
    a=c+o;b=o+c
    if a in fx[i0] and fx[i0][a] and fx[i1][a]:return math.log(float(fx[i1][a])/float(fx[i0][a]))
    return -math.log(float(fx[i1][b])/float(fx[i0][b]))
def basket(i0,i1):return sum(pairret('CAD',o,i0,i1) for o in CCYS if o!='CAD')/7

def latest_inf(dt):
    xs=[x for x in inf_states if date.fromisoformat(x['release_date'])<=dt]
    return xs[-1] if xs else None

def stats(rows,key):
    vals=[r[key] for r in rows if key in r]
    if not vals:return {'n':0,'mean':None,'median':None}
    s=sorted(vals); n=len(s); med=s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
    return {'n':n,'mean':sum(vals)/n,'median':med,'positive_share':sum(v>0 for v in vals)/n}

rows=[]
for rec in macro['comparisons']:
    m=rec['first_release']; mp=m['macro_polarity']
    if mp not in (-1,1):continue
    dt=date.fromisoformat(rec['checkpoint']); inf=latest_inf(dt)
    if not inf or inf['direction'] not in (-1,0,1):continue
    rs=rate_state(dt)
    if not rs:continue
    # State architecture only; no optimized weighting.
    if inf['direction']==mp and mp!=0: cb_state='INFLATION_MACRO_ALIGNED'
    elif inf['direction']==0: cb_state='INFLATION_NEUTRAL_MACRO_DIRECTIONAL'
    elif inf['direction']==-mp: cb_state='INFLATION_MACRO_CONFLICT'
    else: cb_state='OTHER'
    i0=next_idx(date.fromisoformat(rs['end_date']))
    if i0 is None:continue
    e={'checkpoint':rec['checkpoint'],'growth_direction':m['growth_direction'],'labour_direction':m['labour_direction'],'macro_polarity':mp,'inflation_direction':inf['direction'],'inflation_release_date':inf['release_date'],'cb_state':cb_state,'rates_direction':rs['direction'],'delta_2y_5d':rs['delta_2y_5d'],'fx_entry_date':fx[i0]['date']}
    for h in H:
        if i0+h<len(fx):e[f'cad_basket_{h}d']=basket(i0,i0+h)
    rows.append(e)

groups={s:[r for r in rows if r['cb_state']==s] for s in sorted(set(r['cb_state'] for r in rows))}
rate_groups={s:[r for r in rows if ('SAME' if r['rates_direction']==r['macro_polarity'] else 'OPPOSITE' if r['rates_direction']==-r['macro_polarity'] else 'FLAT')==s] for s in ['SAME','OPPOSITE','FLAT']}
res={'schema':'GMFQ_CAD_FULL_REACTION_STATE_VNEXT_V1','status':'PASS_CORE_INFLATION_HEADLINE_PENDING','created_at':'2026-10-06','scope':'CAD frozen Growth+Labour PIT plus first-release BoC core inflation block -> BoC state -> observed 5-day 2Y repricing -> CAD basket. No fitted weights.','engine_baseline':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','modified':False},'inflation_block':{'series':['CPI_COMMON_YOY','CPI_MEDIAN_YOY','CPI_TRIM_YOY'],'construction':'frozen normalized impulse per series; median aggregation; 0.20 direction threshold','headline_cpi':'PENDING_SEPARATE_ARCHIVE_RECONSTRUCTION'},'guardrails':['no threshold tuning','no parameter fitting','states descriptive not trading gates','engine/live_data untouched'],'counts':{'events':len(rows),'by_cb_state':{k:len(v) for k,v in groups.items()}},'by_cb_state':{k:{f'{h}d':stats(v,f'cad_basket_{h}d') for h in H} for k,v in groups.items()},'by_rates_vs_macro':{k:{f'{h}d':stats(v,f'cad_basket_{h}d') for h in H} for k,v in rate_groups.items()},'rows':rows,'changes_engine_rules':False,'changes_live_data':False}
OUT.write_text(json.dumps(res,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'counts':res['counts'],'by_cb_state':res['by_cb_state']},indent=2))
