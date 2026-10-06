#!/usr/bin/env python3
import io,json,re,urllib.request
from pypdf import PdfReader

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
ANCHORS=['2018-12','2019-03','2020-03','2023-01']

def urls(month):
    y,m=map(int,month.split('-')); yy=str(y)[2:]; mm=f'{m:02d}'; stem=f'{yy}{mm}juchu-1.pdf'
    if y<=2019:return [f'https://www.esri.cao.go.jp/jp/stat/juchu/{stem}']
    return [f'https://www.esri.cao.go.jp/jp/stat/juchu/{y}/{stem}',f'https://www.esri.cao.go.jp/jp/stat/juchu/{stem}']

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/pdf,*/*','Accept-Language':'ja,en-US;q=0.9,en;q=0.8'})
    with urllib.request.urlopen(req,timeout=30) as r:return r.read(),getattr(r,'status',200)

def norm(s): return s.translate(str.maketrans('０１２３４５６７８９．％','0123456789.%'))

def parse(month):
    last=None
    for u in urls(month):
        try: raw,status=get(u); last=(u,raw,status); break
        except Exception as e:last=(u,str(e),None)
    if not last or last[2]!=200: raise RuntimeError(last[1] if last else 'no url')
    u,raw,status=last
    text='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages[:6]); z=norm(text)
    md=re.search(r'(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日[^\n]{0,80}?(\d{1,2})\s*[:：]\s*(\d{2})\s*公表',z)
    if not md:
        md=re.search(r'(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',z)
    patterns=[
      r'船舶・電力を除く民需[^。\n]{0,200}?前月比\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*(増|減)',
      r'船舶・電力を除く民需[^。\n]{0,200}?同\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*(増|減)'
    ]
    val=None
    for p in patterns:
        m=re.search(p,z)
        if m: val=float(m.group(1))*(1 if m.group(2)=='増' else -1); break
    if not md or val is None: raise ValueError(f'parse failure date={bool(md)} value={val}')
    rd=f'{int(md.group(1)):04d}-{int(md.group(2)):02d}-{int(md.group(3)):02d}'
    rt=(f'{int(md.group(4)):02d}:{int(md.group(5)):02d}' if md.lastindex and md.lastindex>=5 else None)
    return {'reference_month':month,'release_date':rd,'release_time_jst':rt,'core_private_orders_sa_mom_pct':val,'source_url':u,'http_status':status}

def main():
    rows=[];errors=[]
    for m in ANCHORS:
        try:rows.append(parse(m))
        except Exception as e:errors.append({'reference_month':m,'error':str(e)})
    out={'schema':'GMFQ_JPY_MACHINERY_ORDERS_PIT_FEASIBILITY_V1','status':'PASS' if not errors and len(rows)==len(ANCHORS) else 'FAIL','source':'Cabinet Office ESRI contemporaneous Machinery Orders report PDFs','series':'Private-sector machinery orders excluding ships and electric power, SA m/m','rows':rows,'errors':errors,'release_time_policy':'Timestamp parsed directly from contemporaneous official report PDF where present; no revised-history substitution','revised_history_fallback_used':False,'pit_activation':False}
    print(json.dumps(out,indent=2,ensure_ascii=False))
    if out['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
