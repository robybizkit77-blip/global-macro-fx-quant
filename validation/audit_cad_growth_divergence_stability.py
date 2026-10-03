#!/usr/bin/env python3
import json, math, statistics
from pathlib import Path

GDP=Path('validation/CA_GDP_FIRST_RELEASE_SERIES_FULL_2020_2026_V1.json')
RETAIL=Path('validation/cad_retail_volume_release_crawl/CA_RETAIL_VOLUME_DATED_RELEASE_CRAWL_V1.json')
PAYLOAD=Path('payload/part-01.txt')
OUT=Path('validation/CAD_GROWTH_DIVERGENCE_STABILITY_AUDIT_2026-10-03.json')

def extract_runtime_series(text, series_id):
    marker='{"id":"'+series_id+'"'; start=text.find(marker)
    if start<0: raise RuntimeError(series_id)
    depth=0; ins=False; esc=False
    for i in range(start,len(text)):
        ch=text[i]
        if ins:
            if esc: esc=False
            elif ch=='\\': esc=True
            elif ch=='"': ins=False
        else:
            if ch=='"': ins=True
            elif ch=='{': depth+=1
            elif ch=='}':
                depth-=1
                if depth==0: return json.loads(text[start:i+1])
    raise RuntimeError('unterminated')

def scale(vals):
    diffs=[abs(vals[i]-vals[i-1]) for i in range(1,len(vals))]
    return statistics.median(diffs[-80:]) if diffs else None

def impulse(vals):
    vals=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
    if len(vals)<8:return None
    s=scale(vals)
    if not s or s<=0:return None
    cur=(vals[-1]-vals[-2])/s; prev=(vals[-2]-vals[-3])/s
    d=0 if abs(cur)<0.2 else (1 if cur>0 else -1)
    return {'current':cur,'previous':prev,'direction':d}

def chain(rows, anchor):
    out={}; lvl=float(anchor)
    for r in sorted(rows,key=lambda x:x['reference_month']):
        v=r.get('first_release_mom_pct')
        if v is None: continue
        lvl*=1+float(v)/100
        out[r['reference_month']]=lvl
    return out

gdp=json.loads(GDP.read_text()); ret=json.loads(RETAIL.read_text()); p=PAYLOAD.read_text()
rg=extract_runtime_series(p,'CA_REAL_GDP_M_history_value'); rr=extract_runtime_series(p,'CA_RETAIL_VOLUME_history_value')
rgm=dict(zip(rg['dates'],map(float,rg['values']))); rrm=dict(zip(rr['dates'],map(float,rr['values'])))
fgm=chain(gdp['rows'],rgm['2020-04']); frm=chain(ret['rows'],rrm['2020-04'])
grel={r['reference_month']:r['release_date'] for r in gdp['rows']}; rrel={r['reference_month']:r['release_date'] for r in ret['rows']}
events=sorted(set([r['release_date'] for r in gdp['rows']]+[r['release_date'] for r in ret['rows']]))
rows=[]
for cp in events:
    gm=sorted([m for m,d in grel.items() if d<=cp and m in fgm and m in rgm]); rm=sorted([m for m,d in rrel.items() if d<=cp and m in frm and m in rrm])
    if not gm or not rm: continue
    fi_g=impulse([fgm[m] for m in gm]); fi_r=impulse([frm[m] for m in rm]); rv_g=impulse([rgm[m] for m in gm]); rv_r=impulse([rrm[m] for m in rm])
    if not all([fi_g,fi_r,rv_g,rv_r]): continue
    def block(a,b):
        cur=statistics.median([a['current'],b['current']]); d=0 if abs(cur)<0.2 else (1 if cur>0 else -1)
        return {'current':cur,'direction':d}
    fb=block(fi_g,fi_r); rb=block(rv_g,rv_r)
    diverge_first=fi_g['direction']!=0 and fi_r['direction']!=0 and fi_g['direction']!=fi_r['direction']
    diverge_rev=rv_g['direction']!=0 and rv_r['direction']!=0 and rv_g['direction']!=rv_r['direction']
    rows.append({'checkpoint':cp,'first_divergence':diverge_first,'revised_divergence':diverge_rev,'first_block_direction':fb['direction'],'revised_block_direction':rb['direction'],'block_direction_changed':fb['direction']!=rb['direction'],'first_abs_block_current':abs(fb['current']),'revised_abs_block_current':abs(rb['current'])})

first_div=[x for x in rows if x['first_divergence']]; first_align=[x for x in rows if not x['first_divergence']]
near=lambda x: x['first_abs_block_current']<0.4
report={
 'schema':'GMFQ_CAD_GROWTH_DIVERGENCE_STABILITY_AUDIT_V1',
 'engine_ref':'engine-freeze-v1-2026-10-02',
 'threshold_direction':0.2,
 'totals':{'checkpoints':len(rows),'first_release_divergence_checkpoints':len(first_div),'first_release_divergence_pct':round(100*len(first_div)/len(rows),2),'aligned_checkpoints':len(first_align)},
 'stability':{
  'direction_changes_when_divergent':sum(x['block_direction_changed'] for x in first_div),
  'direction_change_pct_when_divergent':round(100*sum(x['block_direction_changed'] for x in first_div)/len(first_div),2) if first_div else None,
  'direction_changes_when_aligned':sum(x['block_direction_changed'] for x in first_align),
  'direction_change_pct_when_aligned':round(100*sum(x['block_direction_changed'] for x in first_align)/len(first_align),2) if first_align else None,
  'near_threshold_when_divergent':sum(near(x) for x in first_div),
  'near_threshold_pct_when_divergent':round(100*sum(near(x) for x in first_div)/len(first_div),2) if first_div else None
 },
 'examples_divergent_changes':[x['checkpoint'] for x in first_div if x['block_direction_changed']][:20],
 'interpretation':{'no_model_change':'Descriptive audit only; no threshold/weight changes.'}
}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
