#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,io,json,pathlib,urllib.request
from copy import deepcopy

ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
URL='https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_{tenor}?startPeriod=2026-09-25&format=csvdata'
UA='Mozilla/5.0 GMFQ-rates-updater/1.0'

def fetch(tenor:str):
    req=urllib.request.Request(URL.format(tenor=tenor),headers={'User-Agent':UA,'Accept':'text/csv,*/*'})
    with urllib.request.urlopen(req,timeout=60) as r:
        raw=r.read().decode('utf-8-sig','replace')
    found=[]
    for row in csv.DictReader(io.StringIO(raw)):
        d=row.get('TIME_PERIOD') or row.get('TIME PERIOD') or row.get('time_period')
        v=row.get('OBS_VALUE') or row.get('OBS VALUE') or row.get('obs_value')
        if not d or v in (None,''): continue
        try: found.append((str(d)[:10],float(v)))
        except: pass
    if not found: raise SystemExit(f'ECB {tenor}: no parsable observations')
    return max(found,key=lambda x:x[0])

def state(d2:float,d10:float)->str:
    if d2<0 and d10<0:
        return 'Bull flattening' if d10<d2 else 'Bull steepening'
    if d2>0 and d10>0:
        return 'Bear steepening' if d10>d2 else 'Bear flattening'
    return 'Movimento misto'

def append_history(h:dict,date:str,value:float)->None:
    dates=h.get('dates'); values=h.get('values')
    if not isinstance(dates,list) or not isinstance(values,list) or len(dates)!=len(values):
        raise SystemExit('EUR history structure malformed')
    if date in dates:
        i=dates.index(date)
        if abs(float(values[i])-value)>1e-10:
            raise SystemExit(f'Existing history value mismatch for {date}')
    else:
        if dates and date<str(dates[-1]): raise SystemExit('Refusing non-monotonic history append')
        dates.append(date); values.append(value)
    h['last_date']=date; h['last_value']=value

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True); a=ap.parse_args()
    data=json.loads(SRC.read_text()); eur=deepcopy(data['EUR'])
    d2,y2=fetch('2Y'); d10,y10=fetch('10Y')
    if d2!=d10: raise SystemExit(f'ECB tenor date mismatch: {d2} vs {d10}')
    date=d2; old_date=str(eur['date']); old2=float(eur['2Y']); old10=float(eur['10Y'])
    if date<old_date: raise SystemExit(f'Official ECB latest {date} older than runtime {old_date}')
    if date==old_date:
        if abs(y2-old2)>1e-10 or abs(y10-old10)>1e-10:
            raise SystemExit('Same-date ECB values differ from runtime')
        result={'status':'NO_CHANGE','date':date,'2Y':y2,'10Y':y10}
        pathlib.Path(a.output).write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False)+'\n')
        print(json.dumps(result,indent=2)); return 0

    d2bp=(y2-old2)*100; d10bp=(y10-old10)*100
    eur['date']=date
    eur['source']=f'ECB AAA Svensson spot curve · official ECB Data Portal · {date}'
    eur['quality']='FULL_CURRENT_OFFICIAL'
    eur['2Y']=y2; eur['10Y']=y10
    eur['curve_bp']=round((y10-y2)*100,1)
    eur['chg2_bp']=round(d2bp,1); eur['chg10_bp']=round(d10bp,1)
    eur['curve_state']=state(d2bp,d10bp)
    for t in eur.get('tenors',[]):
        if t.get('tenor')=='2Y': t.update(value=y2,date=date)
        elif t.get('tenor')=='10Y': t.update(value=y10,date=date)
    append_history(eur['history2'],date,y2); append_history(eur['history10'],date,y10)
    eur['freshness_status']='CURRENT_OFFICIAL_SAME_BASIS'
    eur['freshness_note']=f'Official ECB AAA same-basis 2Y/10Y updated through {date}.'
    if 'history_note' in eur:
        eur['history_note']=f'Legacy history-basis flag retained; validated current same-basis ECB tail updated through {date}.'
    data['EUR']=eur
    pathlib.Path(a.output).write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False)+'\n')
    print(json.dumps({'status':'UPDATED','currency':'EUR','from_date':old_date,'to_date':date,'old_2Y':old2,'new_2Y':y2,'old_10Y':old10,'new_10Y':y10,'chg2_bp':eur['chg2_bp'],'chg10_bp':eur['chg10_bp'],'curve_bp':eur['curve_bp'],'curve_state':eur['curve_state']},indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
