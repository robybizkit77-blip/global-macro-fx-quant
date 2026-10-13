#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

OUT=Path('validation/liquidity-jpy-reserve-xlsx-diagnostic.json')
BASE='https://www.boj.or.jp/en/statistics/boj/fm/juqf/juqf{month:02d}.xlsx'
TARGETS={'07':4020507.0,'08':3905822.0}
NS={'a':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL_NS={'r':'http://schemas.openxmlformats.org/package/2006/relationships'}
DOC_REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-validation/1.0'})
    with urllib.request.urlopen(req,timeout=60) as r:
        body=r.read()
    if len(body)<5000:
        raise SystemExit(f'BOJ workbook unexpectedly small: {len(body)} bytes')
    return body


def shared_strings(zf):
    path='xl/sharedStrings.xml'
    if path not in zf.namelist(): return []
    root=ET.fromstring(zf.read(path))
    return [''.join(t.text or '' for t in si.iterfind('.//a:t',NS)) for si in root.findall('a:si',NS)]


def cell_value(cell,shared):
    typ=cell.attrib.get('t')
    if typ=='inlineStr':
        return ''.join(t.text or '' for t in cell.iterfind('.//a:t',NS))
    v=cell.find('a:v',NS)
    if v is None or v.text is None: return None
    if typ=='s':
        try:return shared[int(v.text)]
        except Exception:return None
    if typ in {'str','e'}: return v.text
    try:return float(v.text)
    except ValueError:return v.text


def sheet_map(zf):
    wb=ET.fromstring(zf.read('xl/workbook.xml'))
    rels=ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
    targets={r.attrib['Id']:r.attrib['Target'] for r in rels.findall('r:Relationship',REL_NS)}
    out={}
    for s in wb.findall('a:sheets/a:sheet',NS):
        rid=s.attrib.get(f'{{{DOC_REL}}}id'); target=targets.get(rid,'')
        if not target: continue
        if target.startswith('/'): path=target.lstrip('/')
        elif target.startswith('xl/'): path=target
        else:path='xl/'+target.lstrip('./')
        out[path]=s.attrib.get('name',path)
    return out


def parse_workbook(body,target):
    hits=[]; nearest=[]
    with zipfile.ZipFile(io.BytesIO(body)) as zf:
        shared=shared_strings(zf); names=sheet_map(zf)
        for path in sorted(p for p in zf.namelist() if p.startswith('xl/worksheets/sheet') and p.endswith('.xml')):
            root=ET.fromstring(zf.read(path))
            for row in root.findall('.//a:sheetData/a:row',NS):
                rn=int(row.attrib.get('r','0') or 0); vals=[]
                for c in row.findall('a:c',NS):
                    val=cell_value(c,shared)
                    if val is not None: vals.append({'ref':c.attrib.get('r'),'value':val})
                for item in vals:
                    if not isinstance(item['value'],(int,float)): continue
                    val=float(item['value']); diff=abs(val-target)
                    rec={'sheet':names.get(path,path),'row':rn,'cell':item['ref'],'value':val,'abs_diff':diff,'row_values':vals}
                    if diff<=1e-9:hits.append(rec)
                    nearest.append(rec)
    nearest.sort(key=lambda x:x['abs_diff'])
    return hits,nearest[:10]


def main():
    report={'schema':'GMFQ_LIQUIDITY_JPY_RESERVE_XLSX_DIAGNOSTIC_V1','status':'DIAGNOSTIC_ONLY_NO_PROMOTION','files':{},'runtime_mutated':False,'publication_performed':False,'promotion_performed':False}
    for mm,target in TARGETS.items():
        url=BASE.format(month=int(mm))
        try:
            body=fetch(url); hits,nearest=parse_workbook(body,target)
            report['files'][mm]={'url':url,'target_runtime_value':target,'exact_hits':hits,'exact_hit_count':len(hits),'nearest':nearest}
        except Exception as exc:
            report['files'][mm]={'url':url,'target_runtime_value':target,'error':repr(exc)}
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
