#!/usr/bin/env python3
import csv, io, json, zipfile, urllib.request
from pathlib import Path
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]
OUT_CSV=ROOT/'history/pit_v1/CAD_CORE_INFLATION_FIRST_RELEASE_2017_2026.csv'
OUT_AUDIT=ROOT/'validation/CAD_CORE_INFLATION_PIT_MATERIALIZATION_2026-10-06.json'
URL='https://www150.statcan.gc.ca/n1/en/tbl/csv/18100259-eng.zip'

with urllib.request.urlopen(URL, timeout=60) as r:
    data=r.read()
with zipfile.ZipFile(io.BytesIO(data)) as z:
    names=[n for n in z.namelist() if n.lower().endswith('.csv') and 'MetaData' not in n]
    if not names:
        raise RuntimeError('No CSV found in StatCan ZIP')
    raw=z.read(names[0]).decode('utf-8-sig')
rows=list(csv.DictReader(io.StringIO(raw)))
if not rows:
    raise RuntimeError('Empty StatCan table')

cols=rows[0].keys()
# Expected cube fields include REF_DATE, Release, Alternative measures, VALUE.
need=['REF_DATE','Release','Alternative measures','VALUE']
missing=[c for c in need if c not in cols]
if missing:
    raise RuntimeError(f'Missing expected columns: {missing}; got={list(cols)}')

measure_map={
    'CPI-common':'CPI_COMMON_YOY',
    'CPI-median':'CPI_MEDIAN_YOY',
    'CPI-trim':'CPI_TRIM_YOY',
}
parsed=[]
for r in rows:
    label=r['Alternative measures']
    code=None
    for key,val in measure_map.items():
        if key.lower() in label.lower() and 'year-over-year' in label.lower():
            code=val; break
    if not code: continue
    if not r['VALUE']: continue
    try:
        ref=r['REF_DATE'][:7]
        rel=datetime.strptime(r['Release'].strip(),'%B %d, %Y').date().isoformat()
        val=float(r['VALUE'])
    except Exception:
        continue
    parsed.append((code,ref,rel,val,label))

# Earliest official release carrying a value for each measure/reference month = first observable vintage.
first={}
for code,ref,rel,val,label in sorted(parsed,key=lambda x:(x[0],x[1],x[2])):
    first.setdefault((code,ref),(rel,val,label))

out=[]
for (code,ref),(rel,val,label) in sorted(first.items(), key=lambda x:(x[0][1],x[0][0])):
    if ref<'2017-01': continue
    out.append({'reference_month':ref,'release_date':rel,'series':code,'first_release_yoy_pct':val,'source_table':'18-10-0259-01','source_label':label})

OUT_CSV.parent.mkdir(parents=True,exist_ok=True)
with OUT_CSV.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['reference_month','release_date','series','first_release_yoy_pct','source_table','source_label'])
    w.writeheader(); w.writerows(out)

by={k:0 for k in measure_map.values()}
for r in out: by[r['series']]+=1
refs=[r['reference_month'] for r in out]
audit={
 'schema':'GMFQ_CAD_CORE_INFLATION_PIT_MATERIALIZATION_V1',
 'status':'PASS' if out else 'FAIL',
 'created_at':'2026-10-06',
 'source':{'provider':'Statistics Canada','table':'18-10-0259-01','url':URL,'purpose':'historical real-time releases of Bank of Canada core CPI measures'},
 'method':'For each core measure and reference month, retain the earliest official release date in the real-time table carrying a non-null YoY value. No current revised-history substitution.',
 'coverage':{'rows':len(out),'by_series':by,'first_reference_month':min(refs) if refs else None,'last_reference_month':max(refs) if refs else None},
 'guardrails':['first observable vintage only','no revised substitution','no threshold tuning','audit/materialization only'],
 'headline_cpi_status':'SEPARATE_DAILY_ARCHIVE_RECONSTRUCTION_REQUIRED',
 'post_apr_2026_note':'StatCan discontinued updates to table 18-10-0259-01 from April 2026; subsequent first-release values must be taken from contemporaneous CPI Daily Table 4.',
}
OUT_AUDIT.write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
print(json.dumps(audit,indent=2))
