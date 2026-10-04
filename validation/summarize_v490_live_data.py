from pathlib import Path
import json,re
ROOT=Path('.')
SEC=ROOT/'live_data'/'sections'
CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$')

def load(name): return json.loads((SEC/name).read_text(encoding='utf-8'))
def dates_in(x):
    out=[]
    def walk(v):
        if isinstance(v,dict):
            for k,z in v.items(): walk(k); walk(z)
        elif isinstance(v,list):
            for z in v: walk(z)
        elif isinstance(v,str) and DATE_RE.match(v): out.append(v)
    walk(x); return sorted(set(out))
def latest(x):
    d=dates_in(x); return d[-1] if d else None

d=load('D.json'); rates=load('NATIVE_RATES_DATA.json'); liq=load('NATIVE_LIQ_DATA.json'); cb=load('NATIVE_CB_DATA.json'); ois=load('OIS_DATA.json'); macro=load('MACRO_SERIES.json'); cot=load('V250_COT_CHART_DATA.json')
report={'schema':'GMFQ_V490_LIVE_DATA_STATUS_V1','created_at':'2026-10-04','dashboard':{'asOf':d.get('asOf'),'priceAsOf':d.get('priceAsOf'),'latest_date_anywhere':latest(d)},'currencies':{}}
for c in CCYS:
    r=rates.get(c,{}) if isinstance(rates,dict) else {}
    l=liq.get(c,{}) if isinstance(liq,dict) else {}
    b=cb.get(c,{}) if isinstance(cb,dict) else {}
    m=macro.get(c,{}) if isinstance(macro,dict) else {}
    ct=cot.get(c,{}) if isinstance(cot,dict) else {}
    oc=(ois.get('currencies') or {}).get(c,{}) if isinstance(ois,dict) else {}
    report['currencies'][c]={
      'rates':{'date':r.get('date') or latest(r),'latest_date':latest(r),'source':r.get('source'),'quality':r.get('quality'),'2Y':r.get('2Y'),'10Y':r.get('10Y'),'chg2_bp':r.get('chg2_bp'),'chg10_bp':r.get('chg10_bp')},
      'liquidity':{'latest_date':latest(l),'source':l.get('source') if isinstance(l,dict) else None,'quality':l.get('quality') if isinstance(l,dict) else None},
      'central_bank':{'latest_date':latest(b),'source':b.get('source') if isinstance(b,dict) else None,'quality':b.get('quality') if isinstance(b,dict) else None,'rate':b.get('rate') if isinstance(b,dict) else None},
      'ois':{'as_of':oc.get('as_of') if isinstance(oc,dict) else None,'latest_date':latest(oc),'status':oc.get('status') if isinstance(oc,dict) else None,'source':oc.get('source') if isinstance(oc,dict) else None,'quality':oc.get('quality') if isinstance(oc,dict) else None},
      'macro':{'latest_date':latest(m),'series_keys':sorted(m.keys()) if isinstance(m,dict) else None},
      'cot':{'latest_date':latest(ct)}
    }
report['ois_global_as_of']=ois.get('as_of') if isinstance(ois,dict) else None
report['staleness_order']=[]
for c in CCYS:
    for block in ('rates','liquidity','macro','cot'):
        dt=report['currencies'][c][block].get('latest_date')
        report['staleness_order'].append({'ccy':c,'block':block,'latest_date':dt})
report['staleness_order'].sort(key=lambda x:(x['latest_date'] or '0000-00-00',x['ccy'],x['block']))
(ROOT/'validation'/'LIVE_DATA_STATUS_2026-10-04.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'dashboard':report['dashboard'],'rates':{c:report['currencies'][c]['rates'] for c in CCYS},'ois_as_of':report['ois_global_as_of']},ensure_ascii=False))
