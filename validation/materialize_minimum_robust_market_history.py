#!/usr/bin/env python3
from __future__ import annotations
import csv, io, itertools, json, hashlib, math, urllib.request, zipfile
from datetime import date
from pathlib import Path

OUT=Path('history/pit_v1'); OUT.mkdir(parents=True,exist_ok=True)
G8=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
ECB_FX='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip'
ECB_YC='https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.{series}?format=csvdata&startPeriod=2016-01-01'
START=date(2016,1,1)

def get(url, accept=None):
    h={'User-Agent':'GMFQ-minimum-robust-PIT-materializer/1.0'}
    if accept: h['Accept']=accept
    with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=60) as r:
        return r.read()

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def materialize_fx():
    raw=get(ECB_FX,'application/zip,application/octet-stream,*/*;q=0.8')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name=[n for n in z.namelist() if n.lower().endswith('.csv')][0]
        rows=list(csv.DictReader(io.TextIOWrapper(z.open(name),encoding='utf-8-sig')))
    pairs=list(itertools.combinations(G8,2)); out=[]
    for row in rows:
        d=date.fromisoformat(row['Date'].strip())
        if d<START: continue
        q={'EUR':1.0}; ok=True
        for c in G8:
            if c=='EUR': continue
            try: v=float((row.get(c) or '').strip())
            except: ok=False; break
            if not(math.isfinite(v) and v>0): ok=False; break
            q[c]=v
        if not ok: continue
        r={'date':d.isoformat()}
        for a,b in pairs: r[a+b]=q[b]/q[a]
        out.append(r)
    out.sort(key=lambda x:x['date'])
    p=OUT/'FX_G8_DAILY_ECB_2016_2026.csv'
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['date']+[a+b for a,b in pairs]); w.writeheader(); w.writerows(out)
    assert len(out)>=2500 and len(out[-1])==29
    return {'path':str(p),'rows':len(out),'first':out[0]['date'],'last':out[-1]['date'],'sha256':sha(p),'source':ECB_FX,'event_time_policy':'ECB daily reference rate; use only after its publication date for forward-return measurement; not intraday executable price.'}

def fetch_curve(series):
    url=ECB_YC.format(series=series); raw=get(url).decode('utf-8-sig'); d={}
    for row in csv.DictReader(io.StringIO(raw)):
        ds=row.get('TIME_PERIOD') or row.get('TIME_PERIOD_START'); vs=row.get('OBS_VALUE')
        if not ds or vs in (None,''): continue
        try: dd=date.fromisoformat(ds[:10]); v=float(vs)
        except: continue
        if dd>=START and math.isfinite(v): d[dd.isoformat()]=v
    return url,d

def materialize_rates():
    u2,y2=fetch_curve('SR_2Y'); u10,y10=fetch_curve('SR_10Y'); common=sorted(set(y2)&set(y10))
    assert len(common)>=2500 and set(y2)==set(y10)
    p=OUT/'EUR_RATES_2Y_10Y_ECB_SAME_BASIS_2016_2026.csv'
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['date','eur_2y_pct','eur_10y_pct','curve_10y_minus_2y_pp']); w.writeheader()
        for d in common: w.writerow({'date':d,'eur_2y_pct':f'{y2[d]:.10f}','eur_10y_pct':f'{y10[d]:.10f}','curve_10y_minus_2y_pp':f'{(y10[d]-y2[d]):.10f}'})
    return {'path':str(p),'rows':len(common),'first':common[0],'last':common[-1],'sha256':sha(p),'source_2y':u2,'source_10y':u10,'basis':'ECB AAA euro-area central government bond zero-coupon spot curve, Svensson model, daily.'}

def main():
    fx=materialize_fx(); rates=materialize_rates()
    manifest={'schema':'GMFQ_MINIMUM_ROBUST_MARKET_HISTORY_V1','created_at':date.today().isoformat(),'status':'MATERIALIZED','fx':fx,'eur_rates':rates,'frozen_engine_commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','changes_live_data':False,'changes_engine_rules':False,'changes_oos_baseline':False,'backtest_started':False}
    canon=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode(); manifest['dataset_bundle_sha256']=hashlib.sha256(canon).hexdigest()
    mp=OUT/'MARKET_HISTORY_MANIFEST.json'; mp.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__': main()
