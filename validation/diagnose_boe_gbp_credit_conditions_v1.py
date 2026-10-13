#!/usr/bin/env python3
import io, json, re, urllib.request, zipfile
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

URL='https://www.bankofengland.co.uk/-/media/boe/files/credit-conditions-survey/2026/ccs-2026-q3-annex.xlsx'
RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
RELNS={'p':'http://schemas.openxmlformats.org/package/2006/relationships'}
TARGET='availability of credit provided to the corporate sector overall'


def colnum(ref):
    n=0
    for c in re.match(r'([A-Z]+)', ref).group(1): n=n*26+ord(c)-64
    return n

def fetch_bytes():
    req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as r: return r.read()

def parse_xlsx(data):
    z=zipfile.ZipFile(io.BytesIO(data))
    shared=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        root=ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in root.findall('m:si',NS):
            shared.append(''.join(t.text or '' for t in si.iterfind('.//m:t',NS)))
    wb=ET.fromstring(z.read('xl/workbook.xml'))
    rel=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    relmap={x.attrib['Id']:x.attrib['Target'] for x in rel.findall('p:Relationship',RELNS)}
    out={}
    for s in wb.find('m:sheets',NS):
        name=s.attrib['name']; rid=s.attrib['{'+NS['r']+'}id']
        target=relmap[rid]
        path='xl/'+target.lstrip('/') if not target.startswith('xl/') else target
        root=ET.fromstring(z.read(path))
        rows=[]
        for row in root.findall('.//m:sheetData/m:row',NS):
            vals={}
            for c in row.findall('m:c',NS):
                ref=c.attrib['r']; typ=c.attrib.get('t'); v=c.find('m:v',NS)
                if typ=='inlineStr':
                    txt=''.join(t.text or '' for t in c.iterfind('.//m:t',NS))
                elif v is None: txt=''
                elif typ=='s': txt=shared[int(v.text)]
                else: txt=v.text or ''
                vals[colnum(ref)]=txt
            rows.append((int(row.attrib['r']), vals))
        out[name]=rows
    return out

def norm(s): return re.sub(r'\s+',' ',str(s)).strip().lower()

def qkey_from_value(s):
    txt=str(s).strip()
    m=re.search(r'(20\d{2}).*?q([1-4])', txt, re.I)
    if m:
        return f'{int(m.group(1)):04d}-Q{int(m.group(2))}'
    try:
        serial=float(txt)
    except ValueError:
        return None
    if not (30000 <= serial <= 60000):
        return None
    d=datetime(1899,12,30)+timedelta(days=serial)
    q=(d.month-1)//3+1
    return f'{d.year:04d}-Q{q}'

def main():
    runtime=json.loads(RUNTIME.read_text())['GBP']['conditions']
    book=parse_xlsx(fetch_bytes())
    hits=[]
    for sheet,rows in book.items():
        for idx,vals in rows:
            joined=' | '.join(str(v) for _,v in sorted(vals.items()))
            if TARGET in norm(joined) and 'past three months' in norm(joined):
                hits.append((sheet,idx,vals))
    candidates=[]
    for sheet,idx,vals in hits:
        rows=book[sheet]
        q_by_col={}
        debug_headers=[]
        for rno,rowvals in rows:
            if rno >= idx: break
            if idx-rno>12: continue
            debug_headers.append({'row':rno,'values':rowvals})
            for col,val in rowvals.items():
                q=qkey_from_value(val)
                if q: q_by_col[col]=q
        obs=[]
        for col,val in sorted(vals.items()):
            if col not in q_by_col: continue
            try: num=float(val)
            except: continue
            obs.append({'date':q_by_col[col],'value':num})
        rmap={d:float(v) for d,v in zip(runtime['dates'],runtime['values'])}
        smap={x['date']:x['value'] for x in obs}
        overlap=sorted(set(rmap)&set(smap))
        exact=sum(abs(rmap[d]-smap[d])<1e-9 for d in overlap)
        diffs=[abs(rmap[d]-smap[d]) for d in overlap]
        candidates.append({'sheet':sheet,'row':idx,'observations':obs,'header_quarters':q_by_col,'debug_headers':debug_headers,'overlap':len(overlap),'exact':exact,'exact_ratio':exact/len(overlap) if overlap else 0.0,'mae':sum(diffs)/len(diffs) if diffs else None,'max_abs_diff':max(diffs) if diffs else None,'mismatches':[{'date':d,'runtime':rmap[d],'source':smap[d]} for d in overlap if abs(rmap[d]-smap[d])>=1e-9][:20]})
    best=max(candidates,key=lambda x:(x['exact_ratio'],x['overlap']),default=None)
    out={'schema':'GMFQ_LIQUIDITY_GBP_CCS_DIAGNOSTIC_V1','source':{'publisher':'Bank of England','release':'2026 Q3','url':URL,'target_question':'How has the availability of credit provided to the corporate sector overall changed?','response_horizon':'Past three months'},'runtime':{'lane':'GBP.conditions','count':len(runtime['dates']),'last_date':runtime['dates'][-1],'last_value':runtime['values'][-1]},'candidate_count':len(candidates),'candidates':candidates,'best_candidate':best,'runtime_match_certified':bool(best and best['overlap']>=12 and best['exact_ratio']==1.0),'automation_ready':False,'promotion_performed':False,'runtime_mutated':False,'publication_performed':False}
    print(json.dumps(out,indent=2))
if __name__=='__main__': main()
