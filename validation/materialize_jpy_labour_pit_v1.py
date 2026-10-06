#!/usr/bin/env python3
import csv, io, json, re, time, urllib.request
from datetime import date, datetime
from pathlib import Path
from pypdf import PdfReader

START=(2018,1); END=(2026,8)
URL='https://www.stat.go.jp/data/roudou/rireki/tsuki/pdf/{yyyymm}.pdf'
OUT=Path('history/pit_v1/JPY_LABOUR_LFS_FIRST_RELEASE_2018_2026.csv')
EVID=Path('validation/JPY_LABOUR_PIT_ACTIVATION_V1_2026-10-06.json')
UA='GMFQ-PIT-validation/1.0'

def era_to_iso(era,y,m,d):
    yy=1 if y=='元' else int(y)
    year=(1988+yy) if era=='平成' else (2018+yy)
    return date(year,int(m),int(d)).isoformat()

def fetch(month):
    u=URL.format(yyyymm=month.replace('-',''))
    req=urllib.request.Request(u,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=40) as r: raw=r.read()
    text='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages[:8])
    md=re.search(r'(平成|令和)\s*(元|\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日',text)
    if not md: raise ValueError('release date not found')
    rd=era_to_iso(*md.groups())
    sec=text
    for marker in ('季節調整値でみた結果の概要','季節調整値でみた結果'):
        i=text.find(marker)
        if i>=0: sec=text[i:]; break
    ur=None
    for p in [r'完全失業率(?:（季節調整値）)?\s*(?:は|：|:)\s*([0-9]+(?:\.[0-9]+)?)\s*[％%]',r'完全失業率[^\n]{0,80}?([0-9]+(?:\.[0-9]+)?)\s*[％%]']:
        q=re.search(p,sec)
        if q: ur=float(q.group(1)); break
    emp=None
    for p in [r'就業者数\s*(?:は|：|:)\s*([0-9]{4})\s*万人',r'就業者\s+([0-9]{4})\s+(?:[-−+]?\d+)']:
        q=re.search(p,sec)
        if q: emp=int(q.group(1)); break
    if ur is None or emp is None: raise ValueError(f'labour fields missing ur={ur} emp={emp}')
    return {'release_date':rd,'release_time_jst':'08:30','release_timezone':'Asia/Tokyo','availability_timestamp_jst':rd+'T08:30:00+09:00','reference_month':month,'unemployment_rate_sa_pct':ur,'employed_sa_10k':emp,'source_url':u,'pit_status':'READY_FIRST_RELEASE'}

def months():
    out=[]; y,m=START
    while (y,m)<=END:
        out.append(f'{y:04d}-{m:02d}'); m+=1
        if m==13:y+=1;m=1
    return out

def main():
    rows=[]; errors=[]
    for m in months():
        try: rows.append(fetch(m))
        except Exception as e: errors.append({'reference_month':m,'error':str(e)})
        time.sleep(.08)
    expected=months(); got=[r['reference_month'] for r in rows]
    missing=sorted(set(expected)-set(got)); dup=sorted({x for x in got if got.count(x)>1})
    status='PASS' if not errors and not missing and not dup and len(rows)==len(expected) else 'FAIL'
    ev={'schema':'GMFQ_JPY_LABOUR_PIT_ACTIVATION_V1','status':status,'coverage':{'start':expected[0],'end':expected[-1],'expected_months':len(expected),'materialized_months':len(rows)},'errors':errors,'missing':missing,'duplicates':dup,'event_time_policy':'Official standard Basic Tabulation release time 08:30 JST; release date from each archived preliminary PDF.','revised_history_fallback_used':False,'pit_active_labour':status=='PASS','full_jpy_macro_ready':False,'reason_full_macro_not_ready':'JPY Growth still requires two independently validated PIT first-release series.','changes_engine_rules':False,'changes_live_data':False}
    EVID.write_text(json.dumps(ev,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    if status!='PASS': print(json.dumps(ev,indent=2,ensure_ascii=False)); raise SystemExit(1)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(json.dumps(ev,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
