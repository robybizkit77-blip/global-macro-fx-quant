#!/usr/bin/env python3
import csv, io, json, re, time, urllib.request
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from pypdf import PdfReader

ITA_START=(2018,1); ITA_END=(2023,7)
GDP_START_YEAR=2018; GDP_END_YEAR=2023; GDP_END_Q=2
OUT_ITA=Path('history/pit_v1/JPY_GROWTH_ITA_FIRST_RELEASE_2018_2023.csv')
OUT_GDP=Path('history/pit_v1/JPY_GROWTH_GDP_FIRST_PRELIM_2018_2023.csv')
EVID=Path('validation/JPY_GROWTH_GDP_ITA_PIT_ACTIVATION_V1_2026-10-06.json')
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
ITA='https://www.meti.go.jp/statistics/tyo/sanzi/result/pdf/ITA_press_{yyyymm}j.pdf'
ESRI='https://www.esri.cao.go.jp'

def request(url,accept='*/*',referer=None):
    h={'User-Agent':UA,'Accept':accept,'Accept-Language':'ja,en-US;q=0.9,en;q=0.8'}
    if referer:h['Referer']=referer
    with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=45) as r:
        return r.read(),getattr(r,'status',200)

def months(start,end):
    out=[];y,m=start
    while (y,m)<=end:
        out.append(f'{y:04d}-{m:02d}');m+=1
        if m==13:y+=1;m=1
    return out

def norm(s): return s.translate(str.maketrans('０１２３４５６７８９．','0123456789.'))
def parse_jp_date(text):
    z=norm(text)
    m=re.search(r'(2\s*0\s*\d\s*\d)\s*年\s*(\d(?:\s*\d)?)\s*月\s*(\d(?:\s*\d)?)\s*日',z)
    if not m:return None
    y=int(re.sub(r'\s+','',m.group(1)));mo=int(re.sub(r'\s+','',m.group(2)));d=int(re.sub(r'\s+','',m.group(3)))
    return date(y,mo,d).isoformat()
def parse_ita_idx(text):
    z=norm(text)
    for p in [r'第3次産業活動指数は[、,\s]*([0-9]{2,3}(?:\.[0-9]+)?)',r'第３次産業活動指数は[、,\s]*([0-9]{2,3}(?:\.[0-9]+)?)',r'Tertiary\s*Industry[^\n]{0,80}?([0-9]{2,3}(?:\.[0-9]+)?)']:
        m=re.search(p,z,re.I)
        if m:return float(m.group(1))
    return None

def parse_ita(month):
    u=ITA.format(yyyymm=month.replace('-',''))
    raw,status=request(u,'application/pdf,*/*;q=0.8','https://www.meti.go.jp/statistics/tyo/sanzi/')
    text='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages[:4])
    rd=parse_jp_date(text);idx=parse_ita_idx(text)
    if rd is None or idx is None: raise ValueError(f'ITA parse failure date={rd} idx={idx}')
    return {'reference_month':month,'release_date':rd,'release_time_jst':'13:30','availability_timestamp_jst':rd+'T13:30:00+09:00','ita_sa_index':idx,'source_url':u,'pit_status':'READY_FIRST_RELEASE'}

def parse_date_text(s):
    s=re.sub(r'\s+',' ',s).strip().replace('Sept.','Sep').replace('Sept','Sep').replace('March.','Mar').replace('February.','Feb').replace('August.','Aug').replace('November.','Nov').replace('December.','Dec')
    s=s.replace('Jan.','Jan').replace('Feb.','Feb').replace('Mar.','Mar').replace('Apr.','Apr').replace('Jun.','Jun').replace('Jul.','Jul').replace('Aug.','Aug').replace('Sep.','Sep').replace('Oct.','Oct').replace('Nov.','Nov').replace('Dec.','Dec')
    for fmt in ('%B %d, %Y','%b %d, %Y','%B %d %Y','%b %d %Y'):
        try:return datetime.strptime(s,fmt).date().isoformat()
        except:pass
    return None

def gdp_release_map(year):
    u=f'{ESRI}/en/sna/data/sokuhou/files/{year}/toukei_{year}.html'
    raw,_=request(u,'text/html,*/*')
    soup=BeautifulSoup(raw.decode('utf-8','replace'),'html.parser')
    out={}
    for tr in soup.find_all('tr'):
        txt=' '.join(tr.stripped_strings)
        if 'First preliminary' not in txt and 'First Preliminary' not in txt and 'The First preliminary' not in txt and 'The First Preliminary' not in txt: continue
        a=tr.find('a',href=re.compile(r'qe\d{3}/gdemenuea\.html$'))
        if not a: continue
        m=re.search(r'qe(\d{2})([1-4])/gdemenuea\.html$',a.get('href',''))
        if not m: continue
        q=int(m.group(2));
        first_td=tr.find('td'); rd=parse_date_text(' '.join(first_td.stripped_strings)) if first_td else None
        if rd: out[q]={'release_date':rd,'page_url':urljoin(u,a['href'])}
    return out

def parse_float(s):
    try:return float(s.strip().replace(',',''))
    except:return None

def parse_gdp(year,q,meta):
    raw,_=request(meta['page_url'],'text/html,*/*')
    soup=BeautifulSoup(raw.decode('utf-8','replace'),'html.parser')
    target=None
    for a in soup.find_all('a',href=True):
        t=' '.join(a.stripped_strings)
        if 'Real, Seasonally Adjusted Series' in t and 'Quarter-to-Quarter' in t and a['href'].lower().endswith('.csv'):
            target=urljoin(meta['page_url'],a['href']); break
    if not target: raise ValueError('GDP real SA qoq CSV link not found')
    raw,_=request(target,'text/csv,*/*')
    text=None
    for enc in ('cp932','shift_jis','utf-8-sig','utf-8'):
        try:text=raw.decode(enc);break
        except:pass
    if text is None: raise ValueError('GDP CSV decode failed')
    latest=None
    for row in csv.reader(io.StringIO(text)):
        if len(row)<2:continue
        v=parse_float(row[1])
        if v is not None: latest=(row[0].strip(),v)
    if latest is None: raise ValueError('GDP latest qoq value not found')
    rq=f'{year}-Q{q}'
    return {'reference_quarter':rq,'release_date':meta['release_date'],'release_time_jst':'08:50','availability_timestamp_jst':meta['release_date']+'T08:50:00+09:00','real_gdp_sa_qoq_pct':latest[1],'source_page':meta['page_url'],'source_csv':target,'source_row_label':latest[0],'pit_status':'READY_FIRST_PRELIMINARY'}

def main():
    ita_rows=[];ita_err=[]
    for m in months(ITA_START,ITA_END):
        try:ita_rows.append(parse_ita(m))
        except Exception as e:ita_err.append({'reference_month':m,'error':str(e)})
        time.sleep(.12)
    gdp_rows=[];gdp_err=[]
    for y in range(GDP_START_YEAR,GDP_END_YEAR+1):
        try:rmap=gdp_release_map(y)
        except Exception as e:
            gdp_err.append({'year':y,'error':'archive '+str(e)});continue
        qmax=GDP_END_Q if y==GDP_END_YEAR else 4
        for q in range(1,qmax+1):
            try:
                if q not in rmap: raise ValueError('first preliminary release row not found')
                gdp_rows.append(parse_gdp(y,q,rmap[q]))
            except Exception as e:gdp_err.append({'reference_quarter':f'{y}-Q{q}','error':str(e)})
            time.sleep(.12)
    ita_expected=months(ITA_START,ITA_END);gdp_expected=sum((GDP_END_Q if y==GDP_END_YEAR else 4) for y in range(GDP_START_YEAR,GDP_END_YEAR+1))
    ita_ok=(not ita_err and len(ita_rows)==len(ita_expected));gdp_ok=(not gdp_err and len(gdp_rows)==gdp_expected)
    status='PASS' if ita_ok and gdp_ok else 'FAIL'
    ev={'schema':'GMFQ_JPY_GROWTH_GDP_ITA_PIT_ACTIVATION_V1','status':status,'series':['METI Tertiary Industry Activity SA index first-release','Cabinet Office ESRI Real GDP SA q/q first preliminary estimate'],'coverage':{'ita_start':ita_expected[0],'ita_end':ita_expected[-1],'ita_expected_months':len(ita_expected),'ita_materialized_months':len(ita_rows),'gdp_start':'2018-Q1','gdp_end':'2023-Q2','gdp_expected_quarters':gdp_expected,'gdp_materialized_quarters':len(gdp_rows)},'event_time_policy':{'ITA':'13:30 JST official METI policy','GDP':'08:50 JST official ESRI Quarterly Estimates release schedule'},'ita_errors':ita_err,'gdp_errors':gdp_err,'revised_history_fallback_used':False,'growth_block_series_count':2,'pit_active_growth':status=='PASS','common_with_jpy_labour_through':'2023-07','changes_engine_rules':False,'changes_live_data':False}
    EVID.write_text(json.dumps(ev,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    if status!='PASS': print(json.dumps(ev,indent=2,ensure_ascii=False));raise SystemExit(1)
    OUT_ITA.parent.mkdir(parents=True,exist_ok=True)
    for path,rows in ((OUT_ITA,ita_rows),(OUT_GDP,gdp_rows)):
        with path.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(ev,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
