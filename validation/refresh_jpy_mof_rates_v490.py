from pathlib import Path
import csv, json, urllib.request
from datetime import datetime, timedelta

ROOT=Path('.')
rates_path=ROOT/'live_data/sections/NATIVE_RATES_DATA.json'
d_path=ROOT/'live_data/sections/D.json'
rates=json.loads(rates_path.read_text())
d=json.loads(d_path.read_text())

url='https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv'
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0'})
raw=urllib.request.urlopen(req,timeout=30).read()
rows=list(csv.reader(raw.decode('cp932').splitlines()))
header=rows[1]
target='2026/10/1'
row=next((r for r in rows if r and r[0]==target),None)
if row is None: raise RuntimeError('MOF target row missing')
idx={k:i for i,k in enumerate(header)}
y2=float(row[idx['2Y']]); y10=float(row[idx['10Y']])
iso='2026-10-01'
r=rates['JPY']

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
elif chg2<0 and chg10<0: state='Bull steepening' if chg2<chg10 else 'Bull flattening'
else: state='Movimento misto'

r.update({'date':iso,'source':'Japan Ministry of Finance · JGB Interest Rate · 1 Oct 2026','quality':'FULL_CURRENT_OFFICIAL','2Y':y2,'10Y':y10,'curve_bp':round(curve,1),'chg2_bp':round(chg2,1),'chg10_bp':round(chg10,1),'curve_state':state,'freshness_status':'CURRENT_OFFICIAL'})
for t in r.get('tenors',[]):
    if t.get('tenor')=='2Y': t.update(value=y2,date=iso)
    if t.get('tenor')=='10Y': t.update(value=y10,date=iso)
upsert(r['history2'],iso,y2); upsert(r['history10'],iso,y10)
if d.get('macro',{}).get('JPY') is not None:
    d['macro']['JPY']['rate2y']=y2

rates_path.write_text(json.dumps(rates,separators=(',',':'),ensure_ascii=False))
d_path.write_text(json.dumps(d,separators=(',',':'),ensure_ascii=False))
report={'schema':'GMFQ_JPY_MOF_RATES_REFRESH_V1','as_of':iso,'source':url,'y2':y2,'y10':y10,'curve_bp':round(curve,1),'weekly_reference_2y':ref2[0].date().isoformat(),'weekly_reference_10y':ref10[0].date().isoformat(),'chg2_bp':round(chg2,1),'chg10_bp':round(chg10,1),'curve_state':state}
(ROOT/'validation/JV_JPY_MOF_RATES_REFRESH_2026-10-04.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
