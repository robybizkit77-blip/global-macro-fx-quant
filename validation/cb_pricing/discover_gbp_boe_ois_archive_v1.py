#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib, urllib.request, zipfile

URL='https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/oisddata.zip'
UA='GLOBAL-MACRO-FX-QUANT GBP CB pricing temporal PIT discovery v1'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    req=urllib.request.Request(URL,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=90) as r:
        raw=r.read()
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.zip') as f:
        f.write(raw); f.flush()
        with zipfile.ZipFile(f.name) as zf:
            files=[]
            for zi in zf.infolist():
                if zi.is_dir(): continue
                files.append({'name':zi.filename,'size':zi.file_size,'compressed_size':zi.compress_size})
    xlsx=[x for x in files if x['name'].lower().endswith('.xlsx')]
    out={
      'schema':'GMFQ_GBP_BOE_OIS_ARCHIVE_DISCOVERY_V1',
      'status':'DISCOVERY_ONLY',
      'authority':'Bank of England',
      'archive_url':URL,
      'archive_sha256':hashlib.sha256(raw).hexdigest(),
      'archive_size_bytes':len(raw),
      'xlsx_count':len(xlsx),
      'xlsx_files':xlsx,
      'changes_live_data':False,
      'changes_engine_rules':False,
      'production_write':False
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,indent=2))
if __name__=='__main__': main()
