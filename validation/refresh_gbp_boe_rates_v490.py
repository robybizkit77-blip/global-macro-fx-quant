from pathlib import Path
import io,json,urllib.request,zipfile,openpyxl,datetime

ROOT=Path('.')
rp=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
dp=ROOT/'live_data'/'sections'/'D.json'
rates=json.loads(rp.read_text(encoding='utf-8'))
d=json.loads(dp.read_text(encoding='utf-8'))

url='https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip'
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0'})
raw=urllib.request.urlopen(req,timeout=60).read()
z=zipfile.ZipFile(io.BytesIO(raw))
name='GLC Nominal daily data current month.xlsx'
wb=openpyxl.load_workbook(io.BytesIO(z.read(name)),data_only=True,read_only=True)
ws=wb['4. spot curve']
rows=list(ws.iter_rows(values_only=True))

# Find maturity row (years) and the closest 2Y / 10Y columns.
years_idx=None
for i,row in enumerate(rows[:20]):
    if row and str(row[0]).strip().lower()=='years:':
        years_idx=i; break
if years_idx is None: raise RuntimeError('BoE years row not found')
years=list(rows[years_idx])
def nearest_col(target):
    best=None
    for j,v in enumerate(years[1:],start=1):
        if isinstance(v,(int,float)):
            err=abs(float(v)-target)
            if best is None or err<best[0]: best=(err,j,float(v))
    if best is None or best[0]>0.01: raise RuntimeError(f'BoE maturity {target}Y not found')
    return best[1]
c2=nearest_col(2.0); c10=nearest_col(10.0)

obs=[]
for row in rows[years_idx+1:]:
    if not row or len(row)<=max(c2,c10): continue
    dt=row[0]
    if isinstance(dt,datetime.datetime): dd=dt.date()
    elif isinstance(dt,datetime.date): dd=dt
    else: continue
    v2=row[c2]; v10=row[c10]
    if isinstance(v2,(int,float)) and isinstance(v10,(int,float)):
        obs.append((dd,float(v2),float(v10)))
if not obs: raise RuntimeError('BoE nominal spot observations missing')
obs.sort(key=lambda x:x[0])
dd,y2,y10=obs[-1]
iso=dd.isoformat()
r=rates['GBP']

def norm(s): return str(s).replace('/','-')
def upsert(hist,date,value):
    dates=[norm(x) for x in hist.get('dates',[])]
    values=list(hist.get('values',[]))
    if date in dates: values[dates.index(date)]=value
    else:
        dates.append(date); values.append(value)
        pairs=sorted(zip(dates,values),key=lambda x:x[0]); dates=[x[0] for x in pairs]; values=[x[1] for x in pairs]
    hist['dates']=dates; hist['values']=values; hist['last_date']=dates[-1]; hist['last_value']=values[-1]

def ref_point(hist,target):
    cutoff=datetime.date.fromisoformat(target)-datetime.timedelta(days=7)
    pts=[]
    for ds,val in zip(hist.get('dates',[]),hist.get('values',[])):
        try: d0=datetime.date.fromisoformat(norm(ds))
        except: continue
        if d0<=cutoff: pts.append((d0,float(val)))
    if not pts: raise RuntimeError('GBP weekly reference missing')
    return max(pts,key=lambda x:x[0])

ref2=ref_point(r['history2'],iso); ref10=ref_point(r['history10'],iso)
chg2=(y2-ref2[1])*100; chg10=(y10-ref10[1])*100
curve=(y10-y2)*100
if chg2>0 and chg10>0:
    state='Bear steepening' if chg10>chg2 else 'Bear flattening'
elif chg2<0 and chg10<0:
    state='Bull flattening' if chg10<chg2 else 'Bull steepening'
else:
    state='Movimento misto'

upsert(r['history2'],iso,y2); upsert(r['history10'],iso,y10)
r.update({
    'date':iso,
    'source':'Bank of England · UK nominal government zero-coupon spot curve · official latest yield curve data',
    'quality':'FULL_CURRENT_OFFICIAL',
    '2Y':y2,'10Y':y10,
    'curve_bp':round(curve,1),
    'chg2_bp':round(chg2,1),'chg10_bp':round(chg10,1),
    'curve_state':state,
    'freshness_status':'CURRENT_OFFICIAL_SAME_BASIS'
})
for t in r.get('tenors',[]):
    if t.get('tenor')=='2Y': t.update(value=y2,date=iso)
    if t.get('tenor')=='10Y': t.update(value=y10,date=iso)
if d.get('macro',{}).get('GBP') is not None:
    d['macro']['GBP']['rate2y']=y2; d['macro']['GBP']['rate_status']='CURRENT'

rp.write_text(json.dumps(rates,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
dp.write_text(json.dumps(d,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
report={
    'schema':'GMFQ_GBP_BOE_RATES_REFRESH_V1','as_of':iso,'source':url,
    'workbook':name,'sheet':'4. spot curve','y2':y2,'y10':y10,
    'curve_bp':round(curve,1),'weekly_reference_2y':ref2[0].isoformat(),'weekly_reference_10y':ref10[0].isoformat(),
    'chg2_bp':round(chg2,1),'chg10_bp':round(chg10,1),'curve_state':state,'same_basis':True
}
(ROOT/'validation/JV_GBP_BOE_RATES_REFRESH_2026-10-04.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
