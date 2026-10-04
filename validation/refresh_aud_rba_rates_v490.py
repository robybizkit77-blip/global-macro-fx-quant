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

# Rebuild the recent tail from the same official RBA F2 source so level and weekly change are same-basis.
for d0,v2,v10 in obs[-30:]:
    ds=d0.isoformat(); upsert(r['history2'],ds,v2); upsert(r['history10'],ds,v10)

cutoff=dd-datetime.timedelta(days=7)
refs=[x for x in obs if x[0]<=cutoff]
if not refs: raise RuntimeError('RBA F2 weekly reference missing')
ref=refs[-1]
ref_date,ref2,ref10=ref
chg2=(y2-ref2)*100; chg10=(y10-ref10)*100
curve=(y10-y2)*100
if chg2>0 and chg10>0:
    state='Bear steepening' if chg10>chg2 else 'Bear flattening'
elif chg2<0 and chg10<0:
    state='Bull flattening' if chg10<chg2 else 'Bull steepening'
else:
    state='Movimento misto'

r.update({
    'date':iso,
    'source':'Reserve Bank of Australia · F2 Capital Market Yields – Government Bonds – Daily',
    'quality':'FULL_CURRENT_OFFICIAL',
    '2Y':y2,'10Y':y10,
    'curve_bp':round(curve,1),'chg2_bp':round(chg2,1),'chg10_bp':round(chg10,1),
    'curve_state':state,'freshness_status':'CURRENT_OFFICIAL_SAME_BASIS',
    'history_status':'FULL_HISTORY_RECENT_TAIL_RBA_F2'
})
for t in r.get('tenors',[]):
    if t.get('tenor')=='2Y': t.update(value=y2,date=iso)
    if t.get('tenor')=='10Y': t.update(value=y10,date=iso)
if d.get('macro',{}).get('AUD') is not None:
    d['macro']['AUD']['rate2y']=y2; d['macro']['AUD']['rate_status']='CURRENT'

rp.write_text(json.dumps(rates,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
dp.write_text(json.dumps(d,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
report={
    'schema':'GMFQ_AUD_RBA_RATES_REFRESH_V2','as_of':iso,'source':url,
    'series_2y':'FCMYGBAG2D','series_10y':'FCMYGBAG10D','y2':y2,'y10':y10,
    'curve_bp':round(curve,1),'weekly_reference_2y':ref_date.isoformat(),'weekly_reference_10y':ref_date.isoformat(),
    'weekly_reference_y2':ref2,'weekly_reference_y10':ref10,
    'chg2_bp':round(chg2,1),'chg10_bp':round(chg10,1),'curve_state':state,'same_basis':True,
    'recent_tail_rows_synced':min(30,len(obs))
}
(ROOT/'validation/JV_AUD_RBA_RATES_REFRESH_2026-10-04.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
