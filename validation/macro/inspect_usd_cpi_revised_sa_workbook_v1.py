#!/usr/bin/env python3
from __future__ import annotations
import argparse, io, json, pathlib, urllib.request, zipfile, xml.etree.ElementTree as ET

# Inspect exact workbook rows before designing any monthly-vintage reconstruction.
UA="Mozilla/5.0 (compatible; GLOBAL-MACRO-FX-QUANT/1.0; research validation)"
NS={'a':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','p':'http://schemas.openxmlformats.org/package/2006/relationships'}
BASE='https://www.bls.gov/cpi/tables/seasonal-adjustment/revised-seasonally-adjusted-indexes-{year}.xlsx'


def fetch(year:int)->bytes:
    req=urllib.request.Request(BASE.format(year=year),headers={'User-Agent':UA,'Connection':'close'})
    with urllib.request.urlopen(req,timeout=30) as r:return r.read()

def shared(z):
    if 'xl/sharedStrings.xml' not in z.namelist(): return []
    root=ET.fromstring(z.read('xl/sharedStrings.xml')); out=[]
    for si in root.findall('a:si',NS): out.append(''.join(t.text or '' for t in si.iter('{%s}t'%NS['a'])))
    return out

def sheets(z):
    wb=ET.fromstring(z.read('xl/workbook.xml')); rel=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    relmap={x.attrib['Id']:x.attrib['Target'] for x in rel}
    out=[]
    for s in wb.find('a:sheets',NS):
        rid=s.attrib['{%s}id'%NS['r']]; target=relmap[rid]
        if target.startswith('/'): path=target.lstrip('/')
        else: path='xl/'+target.lstrip('/')
        out.append((s.attrib['name'],path))
    return out

def cell_value(c,ss):
    typ=c.attrib.get('t'); v=c.find('a:v',NS)
    if typ=='inlineStr':
        isel=c.find('a:is',NS); return ''.join(t.text or '' for t in isel.iter('{%s}t'%NS['a'])) if isel is not None else ''
    if v is None:return ''
    raw=v.text or ''
    if typ=='s':
        try:return ss[int(raw)]
        except:return raw
    return raw

def inspect(year:int):
    raw=fetch(year); z=zipfile.ZipFile(io.BytesIO(raw)); ss=shared(z); hits=[]; sheet_meta=[]
    for name,path in sheets(z):
        root=ET.fromstring(z.read(path)); rows=root.findall('.//a:sheetData/a:row',NS); sheet_meta.append({'name':name,'rows':len(rows)})
        decoded=[]
        for row in rows:
            vals=[]
            for c in row.findall('a:c',NS): vals.append({'ref':c.attrib.get('r'),'value':cell_value(c,ss)})
            decoded.append((int(row.attrib.get('r','0')),vals))
        for i,(rn,vals) in enumerate(decoded):
            joined=' | '.join(str(x['value']) for x in vals)
            if 'CUSR0000SA0' in joined:
                lo=max(0,i-3); hi=min(len(decoded),i+5)
                hits.append({'sheet':name,'row':rn,'context':[{'row':rr,'cells':vv} for rr,vv in decoded[lo:hi]]})
    return {'year':year,'url':BASE.format(year=year),'sheets':sheet_meta,'canonical_hits':hits}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--years',nargs='+',type=int,default=[2017,2018,2024,2025]); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    out={'schema':'GMFQ_USD_CPI_REVISED_SA_WORKBOOK_INSPECTION_V1','results':[inspect(y) for y in a.years],'certification_implied':False}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps(out,indent=2,sort_keys=True))
if __name__=='__main__':main()
