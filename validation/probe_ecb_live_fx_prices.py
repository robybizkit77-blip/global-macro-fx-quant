from pathlib import Path
import csv,io,json,urllib.request
from datetime import date

ROOT=Path('.')
D=json.loads((ROOT/'live_data'/'sections'/'D.json').read_text(encoding='utf-8'))
CCYS=['USD','GBP','JPY','CHF','CAD','AUD','NZD']
start=(date(2026,9,25)).isoformat(); end=(date(2026,10,4)).isoformat()
series='+'.join(CCYS)
url=f'https://data-api.ecb.europa.eu/service/data/EXR/D.{series}.EUR.SP00.A?startPeriod={start}&endPeriod={end}&format=csvdata'
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0','Accept':'text/csv'})
raw=urllib.request.urlopen(req,timeout=45).read().decode('utf-8-sig',errors='replace')
rdr=csv.DictReader(io.StringIO(raw))
by_date={}
for r in rdr:
    c=(r.get('CURRENCY') or r.get('CURRENCY_DENOM') or '').strip()
    ds=(r.get('TIME_PERIOD') or '').strip()
    vs=(r.get('OBS_VALUE') or '').strip()
    if c not in CCYS or not ds or not vs: continue
    try:v=float(vs)
    except:continue
    by_date.setdefault(ds,{})[c]=v
common=[]
for ds,m in sorted(by_date.items()):
    if all(c in m for c in CCYS):
        x={'Date':ds,'EUR':1.0}; x.update({c:m[c] for c in CCYS}); common.append(x)
if not common: raise RuntimeError('No common ECB fixing found')
latest=common[-1]
prices=D.get('prices') or []
if not prices: raise RuntimeError('D.prices missing')
last=prices[-1]

def pair_names():
    ps=D.get('pairStates') or {}
    if isinstance(ps,dict) and ps:return sorted(ps)
    raw=D.get('pairs') or []
    out=[]
    for x in raw:
        if isinstance(x,str):out.append(x)
        elif isinstance(x,dict):
            p=x.get('pair') or x.get('symbol') or x.get('name')
            if p:out.append(p)
    return sorted(set(out))
def cross(row,pair):
    a,b=pair.split('/')
    return float(row[b])/float(row[a])

pairs=pair_names(); states=D.get('pairStates') or {}
report={
 'schema':'GMFQ_ECB_LIVE_FX_PRICE_PROBE_V2','created_at':'2026-10-04','source':url,
 'runtime_priceAsOf':D.get('priceAsOf'),'runtime_last_row':last,
 'ecb_latest_common_fixing':latest,'ecb_common_fixing_count':len(common),
 'ecb_common_fixings':common,
 'needs_refresh':str(D.get('priceAsOf'))!=latest['Date'],
 'd_top_level_keys':sorted(D.keys()),
 'prices_count':len(prices),'prices_tail':prices[-7:],
 'pairs_count':len(pairs),'pair_names':pairs,
 'pairStates_type':type(states).__name__,
 'pairState_samples':{p:states.get(p) for p in pairs[:3]} if isinstance(states,dict) else None,
 'pairs':{}
}
for p in pairs:
    try:
        old=cross(last,p); new=cross(latest,p)
        st=states.get(p,{}) if isinstance(states,dict) else {}
        report['pairs'][p]={'runtime':old,'ecb_latest':new,'change_pct':(new/old-1)*100,'stored_price_layer':(st.get('layers') or {}).get('price') if isinstance(st,dict) else None}
    except Exception as e:
        report['pairs'][p]={'error':str(e)}
(ROOT/'validation'/'ECB_LIVE_FX_PRICE_PROBE_2026-10-04.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'runtime_priceAsOf':report['runtime_priceAsOf'],'latest':latest['Date'],'needs_refresh':report['needs_refresh'],'common':len(common),'pairs':len(pairs)},ensure_ascii=False))
