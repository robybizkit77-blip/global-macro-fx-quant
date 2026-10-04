from pathlib import Path
import csv,io,json,urllib.request,datetime

ROOT=Path('.')
rp=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
dp=ROOT/'live_data'/'sections'/'D.json'
rates=json.loads(rp.read_text(encoding='utf-8'))
d=json.loads(dp.read_text(encoding='utf-8'))

url='https://www.rba.gov.au/statistics/tables/csv/f2-data.csv'
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0'})
raw=urllib.request.urlopen(req,timeout=60).read().decode('utf-8-sig',errors='replace')
rows=list(csv.reader(io.StringIO(raw)))
# Columns are fixed by title row: date, 2Y, 3Y, 5Y, 10Y, indexed10Y.
obs=[]
for row in rows[11:]:
    if len(row)<5: continue
    try: dd=datetime.datetime.strptime(row[0].strip(),'%d-%b-%Y').date()
    except: continue
    try: y2=float(row[1]); y10=float(row[4])
    except: continue
    obs.append((dd,y2,y10))
if not obs: raise RuntimeError('RBA F2 no valid 2Y/10Y observations')
obs.sort(key=lambda x:x[0])
dd,y2,y10=obs[-1]; iso=dd.isoformat()
r=rates['AUD']

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
    if not pts: raise RuntimeError('AUD weekly reference missing')
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
    'source':'Reserve Bank of Australia · F2 Capital Market Yields – Government Bonds – Daily',
    'quality':'FULL_CURRENT_OFFICIAL',
    '2Y':y2,'10Y':y10,
    'curve_bp':round(curve,1),'chg2_bp':round(chg2,1),'chg10_bp':round(chg10,1),
    'curve_state':state,'freshness_status':'CURRENT_OFFICIAL_SAME_BASIS'
})
for t in r.get('tenors',[]):
    if t.get('tenor')=='2Y': t.update(value=y2,date=iso)
    if t.get('tenor')=='10Y': t.update(value=y10,date=iso)
if d.get('macro',{}).get('AUD') is not None:
    d['macro']['AUD']['rate2y']=y2; d['macro']['AUD']['rate_status']='CURRENT'

rp.write_text(json.dumps(rates,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
dp.write_text(json.dumps(d,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
report={
    'schema':'GMFQ_AUD_RBA_RATES_REFRESH_V1','as_of':iso,'source':url,
    'series_2y':'FCMYGBAG2D','series_10y':'FCMYGBAG10D','y2':y2,'y10':y10,
    'curve_bp':round(curve,1),'weekly_reference_2y':ref2[0].isoformat(),'weekly_reference_10y':ref10[0].isoformat(),
    'chg2_bp':round(chg2,1),'chg10_bp':round(chg10,1),'curve_state':state,'same_basis':True
}
(ROOT/'validation/JV_AUD_RBA_RATES_REFRESH_2026-10-04.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
