from pathlib import Path
import csv,io,json,urllib.request
from datetime import date

ROOT=Path('.')
SEC=ROOT/'live_data'/'sections'
D=json.loads((SEC/'D.json').read_text(encoding='utf-8'))
CCYS=['USD','GBP','JPY','CHF','CAD','AUD','NZD']
start='2026-09-25'; end='2026-10-04'
url=f"https://data-api.ecb.europa.eu/service/data/EXR/D.{'+'.join(CCYS)}.EUR.SP00.A?startPeriod={start}&endPeriod={end}&format=csvdata"
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0','Accept':'text/csv'})
raw=urllib.request.urlopen(req,timeout=45).read().decode('utf-8-sig',errors='replace')
rdr=csv.DictReader(io.StringIO(raw))
by={}
for r in rdr:
    c=(r.get('CURRENCY') or r.get('CURRENCY_DENOM') or '').strip()
    ds=(r.get('TIME_PERIOD') or '').strip(); vs=(r.get('OBS_VALUE') or '').strip()
    if c not in CCYS or not ds or not vs: continue
    try:v=float(vs)
    except:continue
    by.setdefault(ds,{})[c]=v
common=[]
for ds,m in sorted(by.items()):
    if all(c in m for c in CCYS):
        row={'Date':ds,'EUR':1.0}; row.update({c:m[c] for c in CCYS}); common.append(row)
if not common: raise RuntimeError('No common ECB fixing')
prices=D.get('prices') or []
if len(prices)<21: raise RuntimeError('Insufficient price history')
old_asof=D.get('priceAsOf'); existing={str(x.get('Date')):x for x in prices if isinstance(x,dict) and x.get('Date')}
added=[]; replaced=[]
for row in common:
    ds=row['Date']
    if ds in existing:
        # Exact official overwrite for dates in probe window.
        if existing[ds] != row: replaced.append(ds)
    else: added.append(ds)
    existing[ds]=row
new_prices=[existing[k] for k in sorted(existing)]
latest=new_prices[-1]['Date']
if latest!=common[-1]['Date']: raise RuntimeError('Latest price is not latest common ECB fixing')
D['prices']=new_prices; D['priceAsOf']=latest

# Keep legacy stored price layers synchronized with the canonical historical rule.
# Runtime decision functions may derive price dynamically, but D.pairStates is also
# retained for compatibility and must not carry an obsolete price direction.
def cross(row,pair):
    a,b=pair.split('/'); return float(row[b])/float(row[a])
def direction(x): return 'FLAT' if abs(x)<0.20 else ('UP' if x>0 else 'DOWN')
last,w1,w4=new_prices[-1],new_prices[-6],new_prices[-21]
price_layer_changes=[]
states=D.get('pairStates') or {}
for pair,state in states.items():
    if not isinstance(state,dict) or '/' not in pair: continue
    r1=(cross(last,pair)/cross(w1,pair)-1)*100
    r4=(cross(last,pair)/cross(w4,pair)-1)*100
    d1,d4=direction(r1),direction(r4)
    old=(state.get('layers') or {}).get('price')
    if d1==d4 and d1!='FLAT': new=pair.split('/')[0] if d1=='UP' else pair.split('/')[1]
    else: new='MISTO'
    state.setdefault('layers',{})['price']=new
    if old!=new: price_layer_changes.append({'pair':pair,'old':old,'new':new,'r1_pct':round(r1,4),'r4_pct':round(r4,4)})

audit={
 'schema':'GMFQ_ECB_LIVE_FX_REFRESH_V1','created_at':'2026-10-04','source':url,
 'old_priceAsOf':old_asof,'new_priceAsOf':latest,'added_dates':added,'replaced_dates':replaced,
 'price_rows_before':len(prices),'price_rows_after':len(new_prices),
 'price_layer_changes':price_layer_changes,
 'latest_fixing':last
}
(SEC/'D.json').write_text(json.dumps(D,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
(ROOT/'validation'/'ECB_LIVE_FX_REFRESH_AUDIT_2026-10-04.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'old':old_asof,'new':latest,'added':added,'price_layer_changes':len(price_layer_changes)},ensure_ascii=False))
