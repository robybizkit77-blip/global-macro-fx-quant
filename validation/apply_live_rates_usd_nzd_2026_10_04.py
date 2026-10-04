from pathlib import Path
import json

ROOT=Path('.')
SEC=ROOT/'live_data'/'sections'
rates_path=SEC/'NATIVE_RATES_DATA.json'
d_path=SEC/'D.json'
rates=json.loads(rates_path.read_text(encoding='utf-8'))
d=json.loads(d_path.read_text(encoding='utf-8'))

def upsert(series,date,value):
    if not isinstance(series,dict): return
    dates=series.setdefault('dates',[]); values=series.setdefault('values',[])
    if date in dates:
        i=dates.index(date); values[i]=value
    else:
        dates.append(date); values.append(value)
    series['last_date']=date; series['last_value']=value

def curve_state(chg2,chg10):
    if chg2>0 and chg10>0:
        return 'Bear steepening / long-end in rialzo più del front-end' if chg10>chg2 else 'Bear flattening / front-end in rialzo più del long-end'
    if chg2<0 and chg10<0:
        return 'Bull flattening / long-end in calo più del front-end' if chg10<chg2 else 'Bull steepening / front-end in calo più del long-end'
    return 'Movimento misto / curva da leggere per componenti'

updates={
 'USD':{
   'date':'2026-10-02','source':'U.S. Treasury Daily Par Yield Curve · 2 Oct 2026','quality':'FULL_CURRENT_OFFICIAL',
   'y2':4.83,'y10':5.28,'ref_date':'2026-09-25','ref_y2':4.81,'ref_y10':5.17
 },
 'NZD':{
   'date':'2026-10-01','source':'RBNZ B2 Wholesale interest rates · government bond close · 1 Oct 2026','quality':'FULL_CURRENT_OFFICIAL',
   'y2':3.89,'y10':5.10,'ref_date':'2026-09-25','ref_y2':3.93,'ref_y10':5.11
 }
}

audit={'schema':'GMFQ_LIVE_RATES_REFRESH_USD_NZD_V1','created_at':'2026-10-04','updates':{}}
for c,u in updates.items():
    r=rates[c]
    old={'date':r.get('date'),'y2':r.get('2Y'),'y10':r.get('10Y')}
    chg2=round((u['y2']-u['ref_y2'])*100,10)
    chg10=round((u['y10']-u['ref_y10'])*100,10)
    curve=round((u['y10']-u['y2'])*100,10)
    r['date']=u['date']; r['source']=u['source']; r['quality']=u['quality']
    r['2Y']=u['y2']; r['10Y']=u['y10']; r['curve_bp']=curve
    r['chg2_bp']=chg2; r['chg10_bp']=chg10; r['curve_state']=curve_state(chg2,chg10)
    upsert(r.get('history2'),u['date'],u['y2']); upsert(r.get('history10'),u['date'],u['y10'])
    if isinstance(r.get('tenors'),list):
        for t in r['tenors']:
            if t.get('tenor')=='2Y': t.update(value=u['y2'],date=u['date'])
            if t.get('tenor')=='10Y': t.update(value=u['y10'],date=u['date'])
    r['freshness_status']='CURRENT_OFFICIAL_SAME_BASIS'
    r['freshness_note']=f"Official same-basis 2Y/10Y updated through {u['date']}."
    r['weekly2_validation']={'end_date':u['date'],'end_value':u['y2'],'change_bp':chg2,'source':u['source'],'note':f"Same-basis change from {u['ref_date']} to {u['date']}."}
    if c in d.get('macro',{}):
        d['macro'][c]['rate2y']=u['y2']; d['macro'][c]['rate_status']='CURRENT'
    audit['updates'][c]={'old':old,'new':{'date':u['date'],'y2':u['y2'],'y10':u['y10'],'curve_bp':curve,'chg2_bp':chg2,'chg10_bp':chg10,'curve_state':r['curve_state']},'reference_date':u['ref_date'],'source':u['source']}

rates_path.write_text(json.dumps(rates,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
d_path.write_text(json.dumps(d,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
(ROOT/'validation'/'LIVE_RATES_USD_NZD_REFRESH_AUDIT_2026-10-04.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(audit))
