from pathlib import Path
import json,urllib.request,datetime

ROOT=Path('.')
rp=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
dp=ROOT/'live_data'/'sections'/'D.json'
rates=json.loads(rp.read_text(encoding='utf-8'))
d=json.loads(dp.read_text(encoding='utf-8'))

base='https://data.snb.ch/api/cube/rendeiduebd'
url=base+'/data/json/en?dimSel=D0(CHF),D1(2J,10J)&fromDate=2026-09-01&toDate=2026-10-04'
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0','Accept':'application/json'})
obj=json.loads(urllib.request.urlopen(req,timeout=60).read().decode('utf-8-sig'))
series={}
for ts in obj.get('timeseries',[]):
    key=ts.get('metadata',{}).get('key','')
    if '{CHF,2J}' in key: series['2Y']={x['date']:float(x['value']) for x in ts.get('values',[]) if x.get('value') is not None}
    if '{CHF,10J}' in key: series['10Y']={x['date']:float(x['value']) for x in ts.get('values',[]) if x.get('value') is not None}
if set(series)!= {'2Y','10Y'}: raise RuntimeError('SNB CHF 2Y/10Y series missing')
common=sorted(set(series['2Y']) & set(series['10Y']))
if not common: raise RuntimeError('SNB CHF no common date')
iso=common[-1]; y2=series['2Y'][iso]; y10=series['10Y'][iso]
r=rates['CHF']

def norm(s): return str(s).replace('/','-')
def upsert(hist,date,value):
    dates=[norm(x) for x in hist.get('dates',[])]
    values=list(hist.get('values',[]))
    if date in dates: values[dates.index(date)]=value
    else:
        dates.append(date); values.append(value)
    pairs=sorted(zip(dates,values),key=lambda x:x[0]); dates=[x[0] for x in pairs]; values=[x[1] for x in pairs]
    hist['dates']=dates; hist['values']=values; hist['last_date']=dates[-1]; hist['last_value']=values[-1]

# Sync recent official same-basis tail.
for ds in common[-30:]:
    upsert(r['history2'],ds,series['2Y'][ds]); upsert(r['history10'],ds,series['10Y'][ds])

target=datetime.date.fromisoformat(iso)-datetime.timedelta(days=7)
refs=[ds for ds in common if datetime.date.fromisoformat(ds)<=target]
if not refs: raise RuntimeError('SNB CHF weekly reference missing')
ref=refs[-1]; ref2=series['2Y'][ref]; ref10=series['10Y'][ref]
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
    'source':'Swiss National Bank · spot interest rates on Swiss Confederation bonds · rendeiduebd',
    'quality':'FULL_CURRENT_OFFICIAL',
    '2Y':y2,'10Y':y10,
    'curve_bp':round(curve,1),'chg2_bp':round(chg2,1),'chg10_bp':round(chg10,1),
    'curve_state':state,'freshness_status':'CURRENT_OFFICIAL_SAME_BASIS',
    'history_status':'FULL_HISTORY_RECENT_TAIL_SNB'
})
for t in r.get('tenors',[]):
    if t.get('tenor')=='2Y': t.update(value=y2,date=iso)
    if t.get('tenor')=='10Y': t.update(value=y10,date=iso)
if d.get('macro',{}).get('CHF') is not None:
    d['macro']['CHF']['rate2y']=y2; d['macro']['CHF']['rate_status']='CURRENT'

rp.write_text(json.dumps(rates,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
dp.write_text(json.dumps(d,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
report={
    'schema':'GMFQ_CHF_SNB_RATES_REFRESH_V1','as_of':iso,'source':url,
    'series_2y':'EPB@SNB.rendeiduebd{CHF,2J}','series_10y':'EPB@SNB.rendeiduebd{CHF,10J}',
    'y2':y2,'y10':y10,'curve_bp':round(curve,1),
    'weekly_reference_2y':ref,'weekly_reference_10y':ref,'weekly_reference_y2':ref2,'weekly_reference_y10':ref10,
    'chg2_bp':round(chg2,1),'chg10_bp':round(chg10,1),'curve_state':state,'same_basis':True,
    'recent_tail_rows_synced':min(30,len(common))
}
(ROOT/'validation/JV_CHF_SNB_RATES_REFRESH_2026-10-04.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
