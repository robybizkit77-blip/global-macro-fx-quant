from pathlib import Path
import io, json, urllib.request, zipfile, openpyxl, datetime

ROOT=Path('.')
URL='https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip'
req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0'})
raw=urllib.request.urlopen(req,timeout=60).read()
z=zipfile.ZipFile(io.BytesIO(raw))
name='GLC Nominal daily data current month.xlsx'
wb=openpyxl.load_workbook(io.BytesIO(z.read(name)),data_only=True,read_only=True)
ws=wb['4. spot curve']
rows=[list(r) for r in ws.iter_rows(values_only=True)]
years_i=None
for i,row in enumerate(rows):
    if row and str(row[0]).strip().lower()=='years:':
        years_i=i; break
if years_i is None: raise RuntimeError('years row not found')
years=rows[years_i]

def nearest_col(target):
    best=None
    for j,v in enumerate(years[1:],start=1):
        try: x=float(v)
        except: continue
        d=abs(x-target)
        if best is None or d<best[0]: best=(d,j,x)
    if best is None: raise RuntimeError(f'no maturity near {target}')
    if best[0]>0.02: raise RuntimeError(f'maturity mismatch target {target}: {best}')
    return best[1],best[2]

c2,m2=nearest_col(2.0); c10,m10=nearest_col(10.0)
obs=[]
for row in rows[years_i+1:]:
    if not row: continue
    d=row[0]
    if isinstance(d,datetime.datetime): d=d.date()
    elif isinstance(d,datetime.date): pass
    else: continue
    if c2>=len(row) or c10>=len(row): continue
    try: y2=float(row[c2]); y10=float(row[c10])
    except: continue
    obs.append((d.isoformat(),y2,y10))
if not obs: raise RuntimeError('no dated observations')
obs.sort()
last=obs[-1]
out={
  'schema':'GMFQ_BOE_GBP_RATES_EXTRACT_V2',
  'source':URL,
  'workbook':name,
  'sheet':'4. spot curve',
  'maturity_2y_column':c2,
  'maturity_2y_years':m2,
  'maturity_10y_column':c10,
  'maturity_10y_years':m10,
  'latest':{'date':last[0],'2Y':last[1],'10Y':last[2]},
  'tail':[{'date':d,'2Y':a,'10Y':b} for d,a,b in obs[-10:]]
}
(ROOT/'validation/BOE_GBP_RATES_EXTRACT_2026-10-04.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
