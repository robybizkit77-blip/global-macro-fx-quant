from pathlib import Path
import csv, io, json, urllib.request, time
from datetime import datetime, timedelta

ROOT=Path('.')
rates_path=ROOT/'live_data/sections/NATIVE_RATES_DATA.json'
d_path=ROOT/'live_data/sections/D.json'
rates=json.loads(rates_path.read_text())
d=json.loads(d_path.read_text())

BASE='https://data-api.ecb.europa.eu/service/data/YC/'
KEYS={
    '2Y':'B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y',
    '10Y':'B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y',
}

def fetch_series(key):
    url=f'{BASE}{key}?startPeriod=2026-09-22&endPeriod=2026-10-04&format=csvdata'
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0','Accept':'text/csv'})
            raw=urllib.request.urlopen(req,timeout=30).read().decode('utf-8-sig')
            rows=list(csv.DictReader(io.StringIO(raw)))
            out={r['TIME_PERIOD']:float(r['OBS_VALUE']) for r in rows if r.get('TIME_PERIOD') and r.get('OBS_VALUE') not in (None,'')}
            if not out: raise RuntimeError('ECB series empty')
            return out,url
        except Exception as e:
            last=e; time.sleep(3*(attempt+1))
    raise RuntimeError(f'ECB fetch failed {key}: {last!r}')

s2,url2=fetch_series(KEYS['2Y'])
s10,url10=fetch_series(KEYS['10Y'])
common=sorted(set(s2)&set(s10))
if not common: raise RuntimeError('No common ECB AAA 2Y/10Y date')
iso=common[-1]
y2=s2[iso]; y10=s10[iso]
r=rates['EUR']

def norm(s): return str(s).replace('/','-')
def upsert(series,date,value):
    dates=[norm(x) for x in series.get('dates',[])]
    values=list(series.get('values',[]))
    if date in dates: values[dates.index(date)]=value
    else:
        dates.append(date); values.append(value)
        pairs=sorted(zip(dates,values),key=lambda x:x[0]); dates=[x[0] for x in pairs]; values=[x[1] for x in pairs]
    series['dates']=dates; series['values']=values; series['last_date']=date; series['last_value']=value

def ref_point(series,target_date):
    td=datetime.fromisoformat(target_date); cutoff=td-timedelta(days=7)
    pts=[]
    for ds,val in zip(series.get('dates',[]),series.get('values',[])):
        try: dt=datetime.fromisoformat(norm(ds))
        except: continue
        if dt<=cutoff: pts.append((dt,float(val)))
    if not pts: raise RuntimeError('weekly reference missing')
    return max(pts,key=lambda x:x[0])

ref2=ref_point(r['history2'],iso); ref10=ref_point(r['history10'],iso)
chg2=(y2-ref2[1])*100; chg10=(y10-ref10[1])*100
curve=(y10-y2)*100
if chg2>0 and chg10>0: state='Bear steepening' if chg10>chg2 else 'Bear flattening'
elif chg2<0 and chg10<0: state='Bull steepening' if chg10<chg2 else 'Bull flattening'
else: state='Movimento misto'

r.update({
    'date':iso,
    'source':'ECB AAA Svensson spot curve · official ECB Data Portal',
    'quality':'FULL_CURRENT_OFFICIAL',
    '2Y':y2,
    '10Y':y10,
    'curve_bp':round(curve,1),
    'chg2_bp':round(chg2,1),
    'chg10_bp':round(chg10,1),
    'curve_state':state,
    'freshness_status':'CURRENT_OFFICIAL_SAME_BASIS'
})
for t in r.get('tenors',[]):
    if t.get('tenor')=='2Y': t.update(value=y2,date=iso)
    if t.get('tenor')=='10Y': t.update(value=y10,date=iso)
upsert(r['history2'],iso,y2); upsert(r['history10'],iso,y10)
if d.get('macro',{}).get('EUR') is not None:
    d['macro']['EUR']['rate2y']=y2

rates_path.write_text(json.dumps(rates,separators=(',',':'),ensure_ascii=False))
d_path.write_text(json.dumps(d,separators=(',',':'),ensure_ascii=False))
report={
    'schema':'GMFQ_EUR_ECB_AAA_RATES_REFRESH_V1',
    'as_of':iso,
    'source_2y':url2,
    'source_10y':url10,
    'y2':y2,
    'y10':y10,
    'curve_bp':round(curve,1),
    'weekly_reference_2y':ref2[0].date().isoformat(),
    'weekly_reference_10y':ref10[0].date().isoformat(),
    'chg2_bp':round(chg2,1),
    'chg10_bp':round(chg10,1),
    'curve_state':state,
    'same_basis':True
}
(ROOT/'validation/JV_EUR_ECB_AAA_RATES_REFRESH_2026-10-04.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
