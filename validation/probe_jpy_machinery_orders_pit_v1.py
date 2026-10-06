#!/usr/bin/env python3
import json,re,urllib.request
from bs4 import BeautifulSoup

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
ANCHORS=['2018-12','2019-03','2020-03','2023-01']

def urls(month):
    y,m=map(int,month.split('-')); yy=str(y)[2:]; mm=f'{m:02d}'; stem=f'{yy}{mm}juchu'
    if y<=2019:
        return [f'https://www.esri.cao.go.jp/jp/stat/juchu/{stem}.html']
    return [f'https://www.esri.cao.go.jp/jp/stat/juchu/{y}/{stem}.html',f'https://www.esri.cao.go.jp/jp/stat/juchu/{stem}.html']

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'ja,en-US;q=0.9,en;q=0.8'})
    with urllib.request.urlopen(req,timeout=30) as r:return r.read().decode('utf-8','replace'),getattr(r,'status',200)

def parse(month):
    last=None
    for u in urls(month):
        try:
            raw,status=get(u); last=(u,raw,status); break
        except Exception as e:last=(u,str(e),None)
    if not last or last[2]!=200: raise RuntimeError(last[1] if last else 'no url')
    u,raw,status=last; text=' '.join(BeautifulSoup(raw,'html.parser').stripped_strings)
    md=re.search(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日',text)
    # core machinery orders: private-sector excluding ships and electric power, MoM SA
    patterns=[
      r'船舶・電力を除く民需[^。]{0,120}?前月比\s*([0-9]+(?:\.[0-9]+)?)%\s*(増|減)',
      r'「船舶・電力を除く民需」[^。]{0,160}?同\s*([0-9]+(?:\.[0-9]+)?)%\s*(増|減)'
    ]
    val=None
    for p in patterns:
        m=re.search(p,text)
        if m:
            val=float(m.group(1))*(1 if m.group(2)=='増' else -1);break
    if not md or val is None: raise ValueError(f'parse failure date={bool(md)} value={val}')
    rd=f'{int(md.group(1)):04d}-{int(md.group(2)):02d}-{int(md.group(3)):02d}'
    return {'reference_month':month,'release_date':rd,'core_private_orders_sa_mom_pct':val,'source_url':u,'http_status':status}

def main():
    rows=[];errors=[]
    for m in ANCHORS:
        try:rows.append(parse(m))
        except Exception as e:errors.append({'reference_month':m,'error':str(e)})
    out={'schema':'GMFQ_JPY_MACHINERY_ORDERS_PIT_FEASIBILITY_V1','status':'PASS' if not errors and len(rows)==len(ANCHORS) else 'FAIL','source':'Cabinet Office ESRI Machinery Orders contemporaneous monthly result pages','series':'Private-sector machinery orders excluding ships and electric power, SA m/m','rows':rows,'errors':errors,'release_time_policy':'Official release time to be certified from contemporaneous report PDF before activation','revised_history_fallback_used':False,'pit_activation':False}
    print(json.dumps(out,indent=2,ensure_ascii=False))
    if out['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
