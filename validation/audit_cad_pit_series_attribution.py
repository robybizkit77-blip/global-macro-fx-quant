#!/usr/bin/env python3
import json, math, statistics
from pathlib import Path

GDP=Path('validation/CA_GDP_FIRST_RELEASE_SERIES_FULL_2020_2026_V1.json')
RETAIL=Path('validation/cad_retail_volume_release_crawl/CA_RETAIL_VOLUME_DATED_RELEASE_CRAWL_V1.json')
LFS=Path('validation/cad_lfs_release_crawl/CA_LFS_DATED_RELEASE_CRAWL_V1.json')
PAYLOAD=Path('payload/part-01.txt')
OUT=Path('validation/CAD_PIT_REVISION_SERIES_ATTRIBUTION_2026-10-03.json')

def extract_runtime_series(text, series_id):
    marker='{"id":"'+series_id+'"'; start=text.find(marker)
    if start<0: raise RuntimeError(series_id)
    depth=0; instr=False; esc=False
    for i in range(start,len(text)):
        ch=text[i]
        if instr:
            if esc: esc=False
            elif ch=='\\': esc=True
            elif ch=='"': instr=False
        else:
            if ch=='"': instr=True
            elif ch=='{': depth+=1
            elif ch=='}':
                depth-=1
                if depth==0: return json.loads(text[start:i+1])
    raise RuntimeError('unterminated')

def scale(vals):
    vals=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
    ds=[abs(vals[i]-vals[i-1]) for i in range(1,len(vals))]
    if not ds: return None
    m=statistics.median(ds)
    return m if m>0 and math.isfinite(m) else None

def state(vals, polarity=1):
    vals=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
    if len(vals)<8: return None
    s=scale(vals[-80:])
    if not s: return None
    cur=(vals[-1]-vals[-2])*polarity/s
    prev=(vals[-2]-vals[-3])*polarity/s
    d=0 if abs(cur)<0.20 else (1 if cur>0 else -1)
    acc=cur-prev
    ad=0 if abs(acc)<0.20 else (1 if acc>0 else -1)
    ps=0 if prev==0 else (1 if prev>0 else -1)
    turn=(ps!=0 and d!=0 and ps!=d)
    return {'direction':d,'turning':turn,'accelDir':ad}

def chain(rows, anchor):
    out={}; level=float(anchor)
    for r in sorted(rows,key=lambda x:x['reference_month']):
        v=r.get('first_release_mom_pct')
        if v is None: continue
        level*=1+float(v)/100
        out[r['reference_month']]=level
    return out

payload=PAYLOAD.read_text()
series_ids={
 'GDP':'CA_REAL_GDP_M_history_value',
 'Retail':'CA_RETAIL_VOLUME_history_value',
 'Employment':'CA_EMPLOYMENT_history_value',
 'Unemployment':'CA_UNEMP_RATE_history_value'
}
runtime={k:extract_runtime_series(payload,v) for k,v in series_ids.items()}
rmap={k:dict(zip(v['dates'],map(float,v['values']))) for k,v in runtime.items()}

# Growth series
gdp=json.loads(GDP.read_text()); retail=json.loads(RETAIL.read_text())
gdp_first=chain(gdp['rows'],rmap['GDP']['2020-04'])
ret_first=chain(retail['rows'],rmap['Retail']['2020-04'])
gdp_release={r['reference_month']:r['release_date'] for r in gdp['rows']}
ret_release={r['reference_month']:r['release_date'] for r in retail['rows']}

def per_series_growth(name, first_map, rel_map):
    rows=[]
    for cp in sorted(set(rel_map.values())):
        months=sorted(m for m,d in rel_map.items() if d<=cp and m in first_map and m in rmap[name])
        if not months: continue
        a=state([first_map[m] for m in months])
        b=state([rmap[name][m] for m in months])
        if not a or not b: continue
        rows.append((cp,a,b))
    return rows

growth_rows={
 'GDP':per_series_growth('GDP',gdp_first,gdp_release),
 'Retail':per_series_growth('Retail',ret_first,ret_release)
}

# Labour series, common monthly LFS releases
lfs=json.loads(LFS.read_text())
first_emp=[]; first_un=[]; rev_emp=[]; rev_un=[]
lab_rows={'Employment':[],'Unemployment':[]}
for r in sorted(lfs['rows'],key=lambda x:x['release_date']):
    m=r['reference_month']
    if m not in rmap['Employment'] or m not in rmap['Unemployment']: continue
    first_emp.append(float(r['employment_first_release_thousands']))
    first_un.append(float(r['unemployment_rate_first_release_pct']))
    rev_emp.append(rmap['Employment'][m]); rev_un.append(rmap['Unemployment'][m])
    pairs=[('Employment',first_emp,rev_emp,1),('Unemployment',first_un,rev_un,-1)]
    for name,a_vals,b_vals,pol in pairs:
        a=state(a_vals,pol); b=state(b_vals,pol)
        if a and b: lab_rows[name].append((r['release_date'],a,b))

all_rows={**growth_rows,**lab_rows}
summary={}
for name,rows in all_rows.items():
    d=[cp for cp,a,b in rows if a['direction']!=b['direction']]
    t=[cp for cp,a,b in rows if a['turning']!=b['turning']]
    ac=[cp for cp,a,b in rows if a['accelDir']!=b['accelDir']]
    summary[name]={
      'checkpoints':len(rows),
      'direction_changes':len(d),
      'direction_change_pct':round(100*len(d)/len(rows),2) if rows else None,
      'turning_changes':len(t),
      'turning_change_pct':round(100*len(t)/len(rows),2) if rows else None,
      'acceleration_direction_changes':len(ac),
      'acceleration_direction_change_pct':round(100*len(ac)/len(rows),2) if rows else None,
      'direction_change_checkpoints':d
    }

rank=sorted(summary,key=lambda k:(summary[k]['direction_change_pct'] or 0),reverse=True)
report={
 'schema':'GMFQ_CAD_PIT_REVISION_SERIES_ATTRIBUTION_V1',
 'engine_ref':'engine-freeze-v1-2026-10-02',
 'rules_fingerprint':'3356baf0',
 'series':summary,
 'direction_revision_sensitivity_rank':rank,
 'interpretation':{
   'scope':'Descriptive series-level PIT vs revised sensitivity using frozen v9.3 normalizedSeriesImpulse thresholds.',
   'no_model_change':'Do not change weights or thresholds from this audit.'
 }
}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
