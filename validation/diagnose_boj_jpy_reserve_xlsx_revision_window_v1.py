#!/usr/bin/env python3
from __future__ import annotations
import io,json,urllib.request,zipfile,xml.etree.ElementTree as ET
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
BASE='https://www.boj.or.jp/en/statistics/boj/fm/juqf/juqf{month:02d}.xlsx'
NS={'a':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL_NS={'r':'http://schemas.openxmlformats.org/package/2006/relationships'}
DOC_REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-validation/1.0'})
 with urllib.request.urlopen(req,timeout=60) as r:return r.read()
def shared(z):
 p='xl/sharedStrings.xml'
 if p not in z.namelist():return []
 root=ET.fromstring(z.read(p)); return [''.join(t.text or '' for t in si.iterfind('.//a:t',NS)) for si in root.findall('a:si',NS)]
def cv(c,ss):
 typ=c.attrib.get('t')
 if typ=='inlineStr':return ''.join(t.text or '' for t in c.iterfind('.//a:t',NS))
 v=c.find('a:v',NS)
 if v is None or v.text is None:return None
 if typ=='s':
  try:return ss[int(v.text)]
  except Exception:return None
 if typ in {'str','e'}:return v.text
 try:return float(v.text)
 except ValueError:return v.text
def sheet_names(z):
 wb=ET.fromstring(z.read('xl/workbook.xml')); rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
 tg={r.attrib['Id']:r.attrib['Target'] for r in rels.findall('r:Relationship',REL_NS)}; out={}
 for s in wb.findall('a:sheets/a:sheet',NS):
  rid=s.attrib.get(f'{{{DOC_REL}}}id'); t=tg.get(rid,'')
  if not t:continue
  p=t.lstrip('/') if t.startswith('/') else (t if t.startswith('xl/') else 'xl/'+t.lstrip('./'))
  out[p]=s.attrib.get('name',p)
 return out
def exact_reserve_label(value):
 if not isinstance(value,str):return False
 parts=[' '.join(x.strip().lower().split()) for x in value.replace('\r','\n').split('\n') if x.strip()]
 return 'reserve balances' in parts
def reserve_row(body):
 with zipfile.ZipFile(io.BytesIO(body)) as z:
  ss=shared(z); names=sheet_names(z); candidates=[]
  for p in sorted(x for x in z.namelist() if x.startswith('xl/worksheets/sheet') and x.endswith('.xml')):
   root=ET.fromstring(z.read(p))
   for row in root.findall('.//a:sheetData/a:row',NS):
    vals=[]
    for c in row.findall('a:c',NS):
     v=cv(c,ss)
     if v is not None:vals.append((c.attrib.get('r'),v))
    if not any(exact_reserve_label(v) for _,v in vals):continue
    nums=[(ref,float(v)) for ref,v in vals if isinstance(v,(int,float))]
    if nums:candidates.append({'sheet':names.get(p,p),'row':int(row.attrib.get('r','0')),'values':nums,'raw':vals})
  if not candidates:raise RuntimeError('Exact Reserve balances row not found')
  candidates.sort(key=lambda x:(0 if 'final' in x['sheet'].lower() or '確報' in x['sheet'] else 1,x['row']))
  r=candidates[0]; ref,val=r['values'][0]
  return {'sheet':r['sheet'],'row':r['row'],'cell':ref,'value':val,'all_numeric':r['values'],'label_match':'EXACT_RESERVE_BALANCES'}
def runtime_2026():
 d=json.loads(RUNTIME.read_text(encoding='utf-8'))['JPY']['liquidity']
 return {str(dt)[:7]:float(v) for dt,v in zip(d['dates'],d['values']) if str(dt).startswith('2026-')}
def main():
 rt=runtime_2026(); rows=[]
 for m in range(1,9):
  key=f'2026-{m:02d}'; url=BASE.format(month=m)
  try:
   rr=reserve_row(fetch(url)); rv=rt.get(key); diff=None if rv is None else rv-rr['value']; pct=None if rv is None else diff/rr['value']*100
   rows.append({'month':key,'runtime':rv,'official':rr['value'],'diff':diff,'abs_diff':None if diff is None else abs(diff),'pct_diff':pct,'sheet':rr['sheet'],'row':rr['row'],'cell':rr['cell'],'label_match':rr['label_match'],'url':url})
  except Exception as e:rows.append({'month':key,'error':repr(e),'url':url})
 valid=[r for r in rows if r.get('runtime') is not None and r.get('official') is not None]
 out={'schema':'GMFQ_LIQUIDITY_JPY_RESERVE_XLSX_REVISION_WINDOW_V1','status':'DIAGNOSTIC_ONLY','rows':rows,'overlap':len(valid),'exact':sum(abs(r['diff'])<=1e-9 for r in valid),'mae':sum(r['abs_diff'] for r in valid)/len(valid) if valid else None,'max_abs_diff':max((r['abs_diff'] for r in valid),default=None),'max_abs_pct':max((abs(r['pct_diff']) for r in valid),default=None),'semantic_row_stable':bool(valid and all(r.get('label_match')=='EXACT_RESERVE_BALANCES' for r in valid)),'promotion_eligible':False,'runtime_mutated':False,'publication_performed':False}
 print(json.dumps(out,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
