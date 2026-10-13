#!/usr/bin/env python3
import json
import urllib.parse
import urllib.request

BASE='https://www.stat-search.boj.or.jp/api/v1/getDataCode'
QUERIES=[
    ('MD02','MAM1NAM3M3MO'),
    ('MD11','DLCLAEDBLTTO'),
]

def main():
    out=[]
    for db,code in QUERIES:
        qs=urllib.parse.urlencode({
            'format':'json','lang':'en','db':db,
            'startDate':'202601','endDate':'202608','code':code,
        })
        url=BASE+'?'+qs
        req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0','Accept':'application/json'})
        with urllib.request.urlopen(req,timeout=45) as r:
            raw=r.read().decode('utf-8-sig')
            ct=r.headers.get('Content-Type','')
        try:
            parsed=json.loads(raw)
        except Exception as e:
            raise SystemExit(f'BOJ API non-JSON response db={db} code={code} ct={ct} sample={raw[:1200]!r}: {e}')
        out.append({'db':db,'code':code,'url':url,'content_type':ct,'payload':parsed})
    print(json.dumps({'schema':'GMFQ_BOJ_LIQUIDITY_API_PROBE_V1','queries':out},indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
