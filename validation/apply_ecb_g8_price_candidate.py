#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
PART = ROOT / 'payload' / 'part-15.txt'


def js_num(x):
    return format(float(x), '.10g')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--apply', action='store_true')
    args=ap.parse_args()

    c=json.loads(pathlib.Path(args.candidate).read_text(encoding='utf-8'))
    if c.get('schema')!='GMFQ_ECB_G8_PRICE_CANDIDATE_V1' or c.get('status')!='CANDIDATE_OFFICIAL':
        raise SystemExit('invalid Price candidate schema/status')
    if c.get('base')!='EUR' or c.get('pair_count')!=28:
        raise SystemExit('invalid Price candidate base/pair_count')
    as_of=c['as_of']
    compact=as_of.replace('-','')
    r=c['rates']
    required=('EUR','USD','GBP','JPY','CHF','CAD','AUD','NZD')
    if set(r) != set(required):
        raise SystemExit(f'candidate currencies mismatch: {sorted(r)}')
    if float(r['EUR']) != 1.0 or any(float(r[k])<=0 for k in required):
        raise SystemExit('candidate rates invalid')

    text=PART.read_text(encoding='utf-8')
    pattern=r'<script id="gmfq-price-ecb-\d{8}">.*?</script>'
    matches=re.findall(pattern,text,flags=re.S)
    if len(matches)!=1:
        raise SystemExit(f'expected exactly one existing ECB Price overlay, got {len(matches)}')

    replacement=f'''<script id="gmfq-price-ecb-{compact}">
(function(){{
  'use strict';
  try{{
    const row={{
      Date:'{as_of}',
      EUR:1,
      USD:{js_num(r['USD'])},
      GBP:{js_num(r['GBP'])},
      JPY:{js_num(r['JPY'])},
      CHF:{js_num(r['CHF'])},
      CAD:{js_num(r['CAD'])},
      AUD:{js_num(r['AUD'])},
      NZD:{js_num(r['NZD'])}
    }};
    if(typeof D==='undefined' || !Array.isArray(D.prices)) throw new Error('PRICE_DATA_MISSING');
    const i=D.prices.findIndex(x=>x?.Date===row.Date);
    if(i>=0) D.prices[i]=Object.assign({{}},D.prices[i],row);
    else D.prices.push(row);
    D.prices.sort((a,b)=>String(a.Date).localeCompare(String(b.Date)));
    if(window.DATA_FRESHNESS_REGISTRY){{
      window.DATA_FRESHNESS_REGISTRY.audit_date='{as_of}';
      window.DATA_FRESHNESS_REGISTRY.PRICE={{as_of:'{as_of}',status:'CURRENT_OFFICIAL',source:'ECB euro foreign exchange reference rates'}};
    }}
    if(window.FINAL_SOURCE_POLICY_AUDIT){{
      if(window.FINAL_SOURCE_POLICY_AUDIT.PRICE) Object.assign(window.FINAL_SOURCE_POLICY_AUDIT.PRICE,{{current_as_of:'{as_of}',source:'ECB euro foreign exchange reference rates',policy:'AUTO_UPDATE_PRIMARY',fallback:'LAST_VALID_STALE'}});
      if(window.FINAL_SOURCE_POLICY_AUDIT.price) Object.assign(window.FINAL_SOURCE_POLICY_AUDIT.price,{{current_as_of:'{as_of}',source:'ECB euro foreign exchange reference rates',policy:'AUTO_UPDATE_PRIMARY',fallback:'LAST_VALID_STALE'}});
    }}
    if(window.PRODUCTION_PRICE_COT_LIQ_AUDIT?.price){{
      Object.assign(window.PRODUCTION_PRICE_COT_LIQ_AUDIT.price,{{status:'CURRENT_OFFICIAL',current_as_of:'{as_of}',action:'CURRENT'}});
    }}
    window.GMFQ_ECB_PRICE_AUDIT={{status:'PASS',as_of:'{as_of}',source:'ECB euro foreign exchange reference rates',row:{{...row}},pair_count:Array.isArray(D.pairs)?D.pairs.length:null,rule:'All 28 G8 crosses are derived from one official ECB EUR-base fixing row; no intraday mixing.'}};
    try{{ if(typeof stableModelRefresh==='function') stableModelRefresh(); }}catch(e){{}}
    try{{ if(typeof rebuildCanonicalState==='function') rebuildCanonicalState(); }}catch(e){{}}
    try{{ if(typeof syncCoreFreshnessRegistryFromLive==='function') syncCoreFreshnessRegistryFromLive(); }}catch(e){{}}
    document.documentElement.setAttribute('data-ecb-price-audit','PASS');
    document.documentElement.setAttribute('data-price-asof','{as_of}');
  }}catch(e){{
    window.GMFQ_ECB_PRICE_AUDIT={{status:'FAIL',error:String(e?.message||e)}};
    document.documentElement.setAttribute('data-ecb-price-audit','FAIL');
  }}
}})();
</script>'''
    new,n=re.subn(pattern,replacement,text,count=1,flags=re.S)
    if n != 1:
        raise SystemExit('Price overlay replacement failed')
    changed = new != text
    result={
        'schema':'GMFQ_ECB_G8_PRICE_APPLY_RECEIPT_V1',
        'status':'UPDATE_AVAILABLE' if changed else 'NO_CHANGE',
        'as_of':as_of,
        'changed_file':'payload/part-15.txt' if changed else None,
        'applied':bool(args.apply and changed),
        'publication_performed':False,
    }
    if args.apply and changed:
        PART.write_text(new,encoding='utf-8')
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=='__main__':
    main()
