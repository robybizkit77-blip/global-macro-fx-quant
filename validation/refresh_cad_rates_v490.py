from pathlib import Path
import json,datetime
ROOT=Path('.')
rp=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
dp=ROOT/'live_data'/'sections'/'D.json'
rates=json.loads(rp.read_text(encoding='utf-8'))
d=json.loads(dp.read_text(encoding='utf-8'))
r=rates['CAD']
DATE='2026-10-01'; Y2=3.27; Y10=3.94

def upsert(hist,date,value):
    hist.setdefault('dates',[]); hist.setdefault('values',[])
    if date in hist['dates']:
        i=hist['dates'].index(date); hist['values'][i]=value
    else:
        hist['dates'].append(date); hist['values'].append(value)
    pairs=sorted(zip(hist['dates'],hist['values']))
    hist['dates']=[x for x,_ in pairs]; hist['values']=[v for _,v in pairs]
    hist['last_date']=hist['dates'][-1]; hist['last_value']=hist['values'][-1]

def weekly_change(hist,end_date,end_value):
    target=datetime.date.fromisoformat(end_date)-datetime.timedelta(days=7)
    pts=[]
    for dt,val in zip(hist.get('dates',[]),hist.get('values',[])):
        try: dd=datetime.date.fromisoformat(str(dt))
        except: continue
        if dd<=target: pts.append((dd,float(val)))
    if not pts: return None,None
    dd,val=max(pts,key=lambda x:x[0]); return (end_value-val)*100,dd.isoformat()

upsert(r['history2'],DATE,Y2); upsert(r['history10'],DATE,Y10)
chg2,ref2=weekly_change(r['history2'],DATE,Y2); chg10,ref10=weekly_change(r['history10'],DATE,Y10)
r.update({
 'date':DATE,
 'source':'Bank of Canada · selected benchmark Government of Canada bond yields · 1 Oct 2026',
 'quality':'FULL_CURRENT_OFFICIAL',
 '2Y':Y2,'10Y':Y10,
 'curve_bp':(Y10-Y2)*100,
 'chg2_bp':chg2,'chg10_bp':chg10,
 'curve_state':('Bear steepening' if chg2 is not None and chg10 is not None and chg2>0 and chg10>chg2 else
                'Bear flattening' if chg2 is not None and chg10 is not None and chg2>0 and chg10>0 else
                'Bull steepening' if chg2 is not None and chg10 is not None and chg2<0 and chg10<chg2 else
                'Bull flattening' if chg2 is not None and chg10 is not None and chg2<0 and chg10<0 else 'Curva aggiornata')
})
for t in r.get('tenors',[]):
    if t.get('tenor')=='2Y': t.update(value=Y2,date=DATE)
    if t.get('tenor')=='10Y': t.update(value=Y10,date=DATE)
r['freshness_status']='CURRENT_OFFICIAL'
r['freshness_note']='Official Bank of Canada benchmark 2Y/10Y updated through 1 Oct 2026.'
r['weekly2_validation']={'end_date':DATE,'end_value':Y2,'change_bp':chg2,'reference_date':ref2,'source':'Bank of Canada selected benchmark bond yields'}
if d.get('macro',{}).get('CAD') is not None:
    d['macro']['CAD']['rate2y']=Y2; d['macro']['CAD']['rate_status']='CURRENT'
rp.write_text(json.dumps(rates,separators=(',',':')),encoding='utf-8')
dp.write_text(json.dumps(d,separators=(',',':')),encoding='utf-8')
report={'schema':'GMFQ_CAD_RATES_REFRESH_V1','as_of':DATE,'source':'Bank of Canada selected benchmark Government of Canada bond yields','y2':Y2,'y10':Y10,'curve_bp':round((Y10-Y2)*100,3),'chg2_bp':chg2,'chg10_bp':chg10,'week_ref_2y':ref2,'week_ref_10y':ref10}
(ROOT/'validation'/'CAD_RATES_REFRESH_AUDIT_2026-10-04.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
