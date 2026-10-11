#!/usr/bin/env python3
"""Read-only transport probe for official SECO-ALV monthly labour-market PDFs.

Goal: determine whether the migrated official secoalv.admin.ch archive is a
stable GitHub-runner route for period-specific first-release CHF labour
artifacts. This does not certify CHF.labour and intentionally probes only a
small set of known official monthly releases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import time
import urllib.request
from urllib.error import HTTPError, URLError

UA='global-macro-fx-quant/chf-labour-secoalv-route-discovery-v1'
PROBES=[
    {
        'reference_month':'2019-02',
        'url':'https://www.secoalv.admin.ch/dam/secoalv/de/dokumente/publikationen/amstat/2019/Die%20Lage%20auf%20dem%20Arbeitsmarkt%20im%20Februar%202019.pdf.download.pdf/PRESSEDOK1902_D.pdf',
    },
    {
        'reference_month':'2020-01',
        'url':'https://www.secoalv.admin.ch/dam/secoalv/de/dokumente/publikationen/amstat/2020/die_lage_auf_dem_arbeitsmarkt_im_januar_2020.pdf.download.pdf/PRESSEDOK2001_D.pdf',
    },
    {
        'reference_month':'2021-01',
        'url':'https://www.secoalv.admin.ch/dam/secoalv/de/dokumente/publikationen/amstat/2021/die_lage_auf_dem_arbeitsmarkt_im_januar_2021.pdf.download.pdf/PRESSEDOK2101_D.pdf',
    },
    {
        'reference_month':'2022-01',
        'url':'https://www.secoalv.admin.ch/dam/secoalv/de/dokumente/publikationen/amstat/2022/die_lage_auf_dem_arbeitsmarkt_im_januar_2022.pdf.download.pdf/PRESSEDOK2201_D.pdf',
    },
]
TRANSIENT={429,500,502,503,504}


def fetch(url:str)->tuple[bytes,str,int]:
    last=None
    for attempt in range(1,5):
        req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/pdf,*/*;q=0.8','Connection':'close'})
        try:
            with urllib.request.urlopen(req,timeout=60) as r:
                return r.read(),r.geturl(),r.status
        except HTTPError as exc:
            last=exc
            if exc.code not in TRANSIENT or attempt==4: raise
        except URLError as exc:
            last=exc
            if attempt==4: raise
        time.sleep((2,5,10)[attempt-1])
    raise RuntimeError(repr(last))


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); args=ap.parse_args()
    rows=[]; errors=[]
    for probe in PROBES:
        try:
            raw,final,status=fetch(probe['url'])
            rows.append({
                **probe,
                'http_status':status,
                'final_url':final,
                'is_pdf':raw.startswith(b'%PDF'),
                'bytes':len(raw),
                'sha256':hashlib.sha256(raw).hexdigest(),
            })
        except Exception as exc:
            errors.append({'reference_month':probe['reference_month'],'url':probe['url'],'error':repr(exc)})
            break
    status='DISCOVERY_PASS' if not errors and len(rows)==len(PROBES) and all(r['is_pdf'] and r['bytes']>10000 for r in rows) else 'DISCOVERY_FAIL'
    out={
        'schema':'GMFQ_CHF_LABOUR_SECOALV_ROUTE_DISCOVERY_V1',
        'status':status,
        'authority':'State Secretariat for Economic Affairs (SECO) / Arbeitslosenversicherung official archive',
        'purpose':'Transport viability only; no historical certification implied.',
        'probes':rows,
        'errors':errors,
        'invariants':{
            'official_domain_only':True,
            'period_specific_artifacts':True,
            'production_write':False,
            'changes_live_data':False,
            'changes_engine_rules':False,
        },
    }
    semantic={**out,'probes':[{k:v for k,v in row.items() if k!='sha256'} for row in rows]}
    out['semantic_sha256']=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':status,'probes':[{k:v for k,v in r.items() if k not in ('url','final_url')} for r in rows],'errors':errors,'semantic_sha256':out['semantic_sha256']},indent=2))
    return 0 if status=='DISCOVERY_PASS' else 2

if __name__=='__main__': raise SystemExit(main())
