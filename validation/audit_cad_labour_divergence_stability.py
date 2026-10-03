#!/usr/bin/env python3
import json, math, statistics
from pathlib import Path

LFS=Path('validation/cad_lfs_release_crawl/CA_LFS_DATED_RELEASE_CRAWL_V1.json')
PAYLOAD=Path('payload/part-01.txt')
OUT=Path('validation/CAD_LABOUR_DIVERGENCE_STABILITY_AUDIT_2026-10-03.json')
TH=0.20

def extract_runtime_series(text, series_id):
    marker='{"id":"'+series_id+'"'
    start=text.find(marker)
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
    diffs=[abs(vals[i]-vals[i-1]) for i in range(1,len(vals))]
    if not diffs:return None
    m=statistics.median(diffs[-80:]); return m if m>0 else None

def impulse(vals,polarity):
    if len(vals)<8:return None
    s=scale(vals)
    if not s:return None
    cur=(vals[-1]-vals[-2])*polarity/s
    prev=(vals[-2]-vals[-3])*polarity/s
    return cur,prev

def direction(x):
    return 0 if abs(x)<TH else (1 if x>0 else -1)

lfs=json.loads(LFS.read_text())
payload=PAYLOAD.read_text()
remp=extract_runtime_series(payload,'CA_EMPLOYMENT_history_value')
runemp=extract_runtime_series(payload,'CA_UNEMP_RATE_history_value')
remp_map=dict(zip(remp['dates'],map(float,remp['values'])))
runemp_map=dict(zip(runemp['dates'],map(float,runemp['values'])))

fe=[]; fu=[]; re=[]; ru=[]
rows=[]
for r in sorted(lfs['rows'],key=lambda x:x['release_date']):
    m=r['reference_month']
    if m not in remp_map or m not in runemp_map: continue
    fe.append(float(r['employment_first_release_thousands']))
    fu.append(float(r['unemployment_rate_first_release_pct']))
    re.append(remp_map[m]); ru.append(runemp_map[m])
    ie=impulse(fe,1); iu=impulse(fu,-1); rie=impulse(re,1); riu=impulse(ru,-1)
    if not all([ie,iu,rie,riu]): continue
    de,du=direction(ie[0]),direction(iu[0])
    divergence=(de!=0 and du!=0 and de!=du)
    first_cur=statistics.median([ie[0],iu[0]])
    revised_cur=statistics.median([rie[0],riu[0]])
    first_dir=direction(first_cur); revised_dir=direction(revised_cur)
    near=abs(first_cur)<0.40
    rows.append({'checkpoint':r['release_date'],'divergence':divergence,'first_block_direction':first_dir,'revised_block_direction':revised_dir,'direction_changed':first_dir!=revised_dir,'near_threshold':near})

div=[x for x in rows if x['divergence']]
aln=[x for x in rows if not x['divergence']]
report={
 'schema':'GMFQ_CAD_LABOUR_DIVERGENCE_STABILITY_AUDIT_V1',
 'engine_ref':'engine-freeze-v1-2026-10-02','threshold_direction':TH,
 'totals':{'checkpoints':len(rows),'first_release_divergence_checkpoints':len(div),'first_release_divergence_pct':round(100*len(div)/len(rows),2) if rows else None,'aligned_checkpoints':len(aln)},
 'stability':{
  'direction_changes_when_divergent':sum(x['direction_changed'] for x in div),
  'direction_change_pct_when_divergent':round(100*sum(x['direction_changed'] for x in div)/len(div),2) if div else None,
  'direction_changes_when_aligned':sum(x['direction_changed'] for x in aln),
  'direction_change_pct_when_aligned':round(100*sum(x['direction_changed'] for x in aln)/len(aln),2) if aln else None,
  'near_threshold_when_divergent':sum(x['near_threshold'] for x in div),
  'near_threshold_pct_when_divergent':round(100*sum(x['near_threshold'] for x in div)/len(div),2) if div else None},
 'examples_divergent_changes':[x['checkpoint'] for x in div if x['direction_changed']][:24],
 'interpretation':{'no_model_change':'Descriptive audit only; no threshold/weight changes.'}}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
