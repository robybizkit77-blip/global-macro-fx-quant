#!/usr/bin/env python3
import csv, io, json, zipfile, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'history/pit_v1/CAD_CORE_INFLATION_FIRST_RELEASE_2017_2026.csv'
OUT=ROOT/'history/pit_v1/CAD_HEADLINE_CPI_FIRST_RELEASE_2017_2026.csv'
AUDIT=ROOT/'validation/CAD_HEADLINE_CPI_PIT_MATERIALIZATION_2026-10-06.json'
URL='https://www150.statcan.gc.ca/n1/en/tbl/csv/18100004-eng.zip'

# Exact CPI release dates. Through 2026-03, inherit the common monthly CPI release date
# from the certified real-time core table. Post-discontinuation bridge is seeded from
# contemporaneous The Daily releases verified separately.
release={}
with CORE.open(newline='',encoding='utf-8') as f:
    for r in csv.DictReader(f):
        release.setdefault(r['reference_month'], r['release_date'])
release.update({
    '2026-04':'2026-05-19',
    '2026-05':'2026-06-22',
    '2026-06':'2026-07-20',
    '2026-07':'2026-08-17',
    '2026-08':'2026-09-14',
})

with urllib.request.urlopen(URL, timeout=90) as resp:
    data=resp.read()
with zipfile.ZipFile(io.BytesIO(data)) as z:
    name=next(n for n in z.namelist() if n.lower().endswith('.csv') and 'meta' not in n.lower())
    with z.open(name) as bf:
        text=io.TextIOWrapper(bf, encoding='utf-8-sig')
        rows=list(csv.DictReader(text))

# Official all-items, Canada, not seasonally adjusted index. The raw CPI is not revised.
series=[]
for r in rows:
    ref=r.get('REF_DATE','')[:7]
    if ref < '2016-01' or ref > '2026-08':
        continue
    geo=(r.get('GEO') or '').strip()
    prod=(r.get('Products and product groups') or r.get('Products and product group') or '').strip()
    uom=(r.get('UOM') or '').strip()
    if geo!='Canada':
        continue
    if prod!='All-items':
        continue
    if '2002=100' not in uom:
        continue
    try: val=float(r['VALUE'])
    except Exception: continue
    series.append((ref,val))
# De-duplicate if table contains repeated identical coordinates.
vals={}
for ref,val in series:
    vals[ref]=val

out=[]
for ref in sorted(k for k in vals if '2017-01' <= k <= '2026-08'):
    y,m=map(int,ref.split('-'))
    prev=f'{y-1:04d}-{m:02d}'
    if prev not in vals or ref not in release:
        continue
    yoy=(vals[ref]/vals[prev]-1.0)*100.0
    out.append({
        'reference_month':ref,
        'release_date':release[ref],
        'series':'CPI_HEADLINE_YOY',
        'first_release_yoy_pct':f'{yoy:.6f}',
        'all_items_index':f'{vals[ref]:.1f}',
        'source_table':'18-10-0004-01',
        'pit_basis':'official unadjusted CPI is non-revisable; availability date is contemporaneous CPI release date',
    })

if len(out) < 110:
    raise RuntimeError(f'Insufficient headline CPI coverage: {len(out)} rows')
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)

audit={
 'schema':'GMFQ_CAD_HEADLINE_CPI_PIT_MATERIALIZATION_V1','status':'PASS','created_at':'2026-10-06',
 'source':{'provider':'Statistics Canada','table':'18-10-0004-01','url':URL},
 'method':'All-items Canada not-seasonally-adjusted CPI; official raw CPI is not revised. YoY computed from official index levels. Availability dates inherit certified monthly CPI release dates from core real-time table through 2026-03 and contemporaneous The Daily dates for 2026-04..2026-08.',
 'coverage':{'rows':len(out),'first_reference_month':out[0]['reference_month'],'last_reference_month':out[-1]['reference_month']},
 'release_date_bridge':{'core_table_through':'2026-03','daily_seed':{k:v for k,v in release.items() if k>='2026-04'}},
 'guardrails':['unadjusted headline CPI only','no seasonally adjusted series','no revised substitution issue because official raw CPI is final','no threshold tuning','audit/materialization only'],
 'changes_engine_rules':False,'changes_live_data':False
}
AUDIT.write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
print(json.dumps(audit,indent=2))
