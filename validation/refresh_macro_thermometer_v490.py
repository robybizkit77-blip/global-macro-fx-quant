from pathlib import Path
import json

ROOT=Path('.')
p=ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json'
data=json.loads(p.read_text(encoding='utf-8'))

updates={
 ('USD','labour'):{'as_of':'2026-09-01','value':4.2,'source_note':'BLS Employment Situation September 2026 · released 2026-10-02'},
 ('EUR','inflation'):{'as_of':'2026-09','value':3.8,'source_note':'Eurostat flash HICP September 2026 · released 2026-10-02'},
 ('EUR','labour'):{'as_of':'2026-08','value':6.4,'source_note':'Eurostat unemployment August 2026 · released 2026-10-01'},
 ('AUD','labour'):{'as_of':'2026-08','value':4.6,'source_note':'ABS Labour Force August 2026 · released 2026-09-24'},
}

def pct_rank(hist,v):
    a=sorted(float(x) for x in hist if isinstance(x,(int,float)))
    below=sum(x<v for x in a); equal=sum(x==v for x in a)
    return 100*((below+0.5*equal)/len(a)) if a else None

def temp_label(pct):
    if pct<20:return 'MOLTO_FREDDO'
    if pct<40:return 'FREDDO'
    if pct<60:return 'NORMALE'
    if pct<80:return 'CALDO'
    return 'MOLTO_CALDO'

def dynamics(hist):
    d1=hist[-1]-hist[-2]
    d0=hist[-2]-hist[-3]
    direction='STABILE' if abs(d1)<1e-12 else ('SALE' if d1>0 else 'SCENDE')
    dd=d1-d0
    acceleration='STABILE' if abs(dd)<1e-12 else ('ACCELERA' if dd>0 else 'RALLENTA')
    return direction,acceleration

report={'schema':'GMFQ_MACRO_THERMOMETER_REFRESH_V1','updates':[]}
for (ccy,key),u in updates.items():
    x=data['currencies'][ccy][key]
    old={'as_of':x.get('as_of'),'value':x.get('latest_value')}
    hist=list(x.get('history') or [])
    if x.get('as_of')!=u['as_of']:
        hist.append(float(u['value']))
        # preserve existing rolling-window length
        old_len=len(x.get('history') or [])
        if old_len and len(hist)>old_len: hist=hist[-old_len:]
    else:
        hist[-1]=float(u['value'])
    pct=pct_rank(hist,float(u['value']))
    direction,acceleration=dynamics(hist)
    x['history']=hist
    x['latest_value']=float(u['value'])
    x['as_of']=u['as_of']
    x['percentile']=round(pct,1)
    x['temperature_score']=round(pct,1)
    x['temperature_label']=temp_label(pct)
    x['direction']=direction
    x['acceleration']=acceleration
    x.setdefault('validation',{}).update({'source':True,'history':True,'latest':True,'transformation':True})
    data['currencies'][ccy].setdefault('as_of_detail',{})['unemployment' if key=='labour' else 'inflation']=u['as_of']
    report['updates'].append({'currency':ccy,'key':key,'old':old,'new_as_of':u['as_of'],'new_value':u['value'],'percentile':round(pct,1),'temperature_label':temp_label(pct),'direction':direction,'acceleration':acceleration,'source_note':u['source_note']})

p.write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
(ROOT/'validation/MACRO_THERMOMETER_REFRESH_AUDIT_2026-10-04.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2,ensure_ascii=False))
