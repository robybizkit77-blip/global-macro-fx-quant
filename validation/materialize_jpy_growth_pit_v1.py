#!/usr/bin/env python3
import csv, io, json, re, time, urllib.request
from datetime import date
from pathlib import Path
from pypdf import PdfReader

START=(2018,1); END=(2023,7)
OUT=Path('history/pit_v1/JPY_GROWTH_IIP_ITA_FIRST_RELEASE_2018_2023.csv')
EVID=Path('validation/JPY_GROWTH_PIT_ACTIVATION_V1_2026-10-06.json')
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
MONTH_NAMES={1:'January',2:'February',3:'March',4:'April',5:'May',6:'June',7:'July',8:'August',9:'September',10:'October',11:'November',12:'December'}
IIP='https://www.meti.go.jp/english/statistics/tyo/iip/b2015_{yyyymm}se.html'
ITA='https://www.meti.go.jp/statistics/tyo/sanzi/result/pdf/ITA_press_{yyyymm}j.pdf'

def months():
    out=[];y,m=START
    while (y,m)<=END:
        out.append(f'{y:04d}-{m:02d}');m+=1
        if m==13:y+=1;m=1
    return out

def req(url,accept='*/*',referer=None):
    h={'User-Agent':UA,'Accept':accept,'Accept-Language':'ja,en-US;q=0.9,en;q=0.8','Cache-Control':'no-cache'}
    if referer:h['Referer']=referer
    with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=40) as r:
        return r.read(),getattr(r,'status',200)

def parse_iip(month):
    y,m=map(int,month.split('-'));u=IIP.format(yyyymm=month.replace('-',''))
    raw,status=req(u,'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8','https://www.meti.go.jp/english/statistics/tyo/iip/')
    text=raw.decode('utf-8','replace');text=re.sub(r'<[^>]+>',' ',text);text=re.sub(r'&nbsp;|&#160;',' ',text);text=re.sub(r'\s+',' ',text)
    mn=MONTH_NAMES[m]
    rel=re.search(rf'Preliminary\s+report\s+for\s+{mn}\s+{y}\s*\(released\s+at\s+(\d{{1,2}}:\d{{2}}),\s+([A-Za-z]+)\s+(\d{{1,2}}),\s+(\d{{4}})\)',text,re.I)
    prod=re.search(r'Production\s+([0-9]+(?:\.[0-9]+)?)\s+[-+0-9.]',text,re.I)
    if not rel or not prod: raise ValueError(f'IIP parse failure rel={bool(rel)} prod={bool(prod)}')
    rev={v:k for k,v in MONTH_NAMES.items()};rd=f"{int(rel.group(4)):04d}-{rev[rel.group(2).capitalize()]:02d}-{int(rel.group(3)):02d}"
    return {'release_date':rd,'release_time_jst':rel.group(1).zfill(5),'iip_production_sa_index':float(prod.group(1)),'iip_source_url':u,'iip_http_status':status}

def normalize_digits(s): return s.translate(str.maketrans('０１２３４５６７８９．','0123456789.'))
def parse_jp_date(text):
    z=normalize_digits(text);m=re.search(r'(2\s*0\s*\d\s*\d)\s*年\s*(\d(?:\s*\d)?)\s*月\s*(\d(?:\s*\d)?)\s*日',z)
    if not m:return None
    yy=int(re.sub(r'\s+','',m.group(1)));mm=int(re.sub(r'\s+','',m.group(2)));dd=int(re.sub(r'\s+','',m.group(3)));return date(yy,mm,dd).isoformat()
def parse_ita_index(text):
    z=normalize_digits(text)
    for p in [r'第3次産業活動指数は[、,\s]*([0-9]{2,3}(?:\.[0-9]+)?)',r'第３次産業活動指数は[、,\s]*([0-9]{2,3}(?:\.[0-9]+)?)',r'Tertiary\s*Industry[^\n]{0,80}?([0-9]{2,3}(?:\.[0-9]+)?)']:
        m=re.search(p,z,re.I)
        if m:return float(m.group(1))
    return None

def parse_ita(month):
    u=ITA.format(yyyymm=month.replace('-',''));raw,status=req(u,'application/pdf,*/*;q=0.8','https://www.meti.go.jp/statistics/tyo/sanzi/')
    text='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages[:4]);rd=parse_jp_date(text);idx=parse_ita_index(text)
    if rd is None or idx is None: raise ValueError(f'ITA parse failure date={rd} idx={idx}')
    return {'release_date':rd,'release_time_jst':'13:30','ita_sa_index':idx,'ita_source_url':u,'ita_http_status':status}

def main():
    rows=[];errors=[]
    for month in months():
        try:
            a=parse_iip(month);b=parse_ita(month)
            rows.append({'reference_month':month,'iip_release_date':a['release_date'],'iip_release_time_jst':a['release_time_jst'],'iip_availability_timestamp_jst':a['release_date']+'T'+a['release_time_jst']+':00+09:00','iip_production_sa_index':a['iip_production_sa_index'],'iip_source_url':a['iip_source_url'],'ita_release_date':b['release_date'],'ita_release_time_jst':b['release_time_jst'],'ita_availability_timestamp_jst':b['release_date']+'T13:30:00+09:00','ita_sa_index':b['ita_sa_index'],'ita_source_url':b['ita_source_url'],'pit_status':'READY_FIRST_RELEASE'})
        except Exception as e: errors.append({'reference_month':month,'error':str(e)})
        time.sleep(.08)
    exp=months();got=[r['reference_month'] for r in rows];missing=sorted(set(exp)-set(got));dup=sorted({x for x in got if got.count(x)>1})
    status='PASS' if not errors and not missing and not dup and len(rows)==len(exp) else 'FAIL'
    ev={'schema':'GMFQ_JPY_GROWTH_PIT_ACTIVATION_V1','status':status,'coverage':{'start':exp[0],'end':exp[-1],'expected_months':len(exp),'materialized_months':len(rows)},'series':['METI IIP seasonally adjusted Production index','METI Tertiary Industry Activity seasonally adjusted index'],'event_time_policy':{'IIP':'timestamp embedded in archived METI preliminary report; expected standard 08:50 JST','ITA':'official METI release-time policy 13:30 JST since report for March 2015'},'errors':errors,'missing':missing,'duplicates':dup,'revised_history_fallback_used':False,'growth_block_series_count':2,'pit_active_growth':status=='PASS','common_with_jpy_labour_through':'2023-07','changes_engine_rules':False,'changes_live_data':False}
    EVID.write_text(json.dumps(ev,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    if status!='PASS': print(json.dumps(ev,indent=2,ensure_ascii=False)); raise SystemExit(1)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(ev,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
