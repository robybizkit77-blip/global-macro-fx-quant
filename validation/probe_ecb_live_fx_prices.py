from pathlib import Path
import csv,io,json,urllib.request
from datetime import date,timedelta

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
        x={'date':ds,'EUR':1.0}; x.update({c:m[c] for c in CCYS}); common.append(x)
if not common: raise RuntimeError('No common ECB fixing found')
latest=common[-1]
prices=D.get('prices') or []
if not prices: raise RuntimeError('D.prices missing')
last=prices[-1]
report={
 'schema':'GMFQ_ECB_LIVE_FX_PRICE_PROBE_V1','created_at':'2026-10-04','source':url,
 'runtime_priceAsOf':D.get('priceAsOf'),'runtime_last_row':last,
 'ecb_latest_common_fixing':latest,'ecb_common_fixing_count':len(common),
 'needs_refresh':str(D.get('priceAsOf'))!=latest['date'],
 'pairs':{}
}
pairs=D.get('pairs') or []
def cross(row,pair):
    a,b=pair.split('/')
    return float(row[b])/float(row[a])
for p in pairs:
    try:
        old=cross(last,p); new=cross(latest,p)
        report['pairs'][p]={'runtime':old,'ecb_latest':new,'change_pct':(new/old-1)*100}
    except Exception: pass
(ROOT/'validation'/'ECB_LIVE_FX_PRICE_PROBE_2026-10-04.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'runtime_priceAsOf':report['runtime_priceAsOf'],'latest':latest['date'],'needs_refresh':report['needs_refresh'],'common':len(common)},ensure_ascii=False))
