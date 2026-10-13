#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

OUT=Path('validation/liquidity-usd-bank-credit-h8-xml-diagnostic.json')
URL='https://www.federalreserve.gov/datadownload/Output.aspx?filetype=zip&rel=H8'
SERIES='B1001NCBA'


def fetch():
    req=urllib.request.Request(URL,headers={'User-Agent':'GMFQ-validation/1.0','Accept':'application/zip,application/octet-stream,*/*'})
    with urllib.request.urlopen(req,timeout=120) as r:body=r.read()
    if len(body)<1_000_000:raise SystemExit(f'H8 ZIP unexpectedly small: {len(body)}')
    return body


def main():
    body=fetch()
    hits=[]
    with zipfile.ZipFile(io.BytesIO(body)) as zf:
        names=zf.namelist()
        for name in names:
            if name.endswith('/'):
                continue
            raw=zf.read(name)
            pos=raw.find(SERIES.encode())
            if pos<0:
                continue
            start=max(0,pos-1200); end=min(len(raw),pos+5000)
            snippet=raw[start:end].decode('utf-8','replace')
            hits.append({'file':name,'file_size':len(raw),'series_offset':pos,'snippet':snippet})
            if len(hits)>=5:break
    report={
      'schema':'GMFQ_LIQUIDITY_USD_H8_XML_TRANSPORT_DIAGNOSTIC_V1',
      'status':'DIAGNOSTIC_ONLY_NO_PROMOTION',
      'source':{'publisher':'Federal Reserve Board','release':'H.8','series_id':SERIES,'url':URL,'transport':'official full-release SDMX/XML ZIP'},
      'zip_size':len(body),'zip_file_count':len(names),'series_hits':hits,'series_hit_count':len(hits),
      'transport_accessible':bool(hits),
      'runtime_mutated':False,'publication_performed':False,'promotion_performed':False
    }
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
