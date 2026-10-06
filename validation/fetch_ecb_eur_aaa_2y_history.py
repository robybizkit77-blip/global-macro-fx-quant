#!/usr/bin/env python3
import argparse, csv, io, json, math, urllib.parse, urllib.request
from pathlib import Path

SERIES_KEY='YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y'
DATA_KEY='B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y'
BASE='https://data-api.ecb.europa.eu/service/data/YC/'


def fetch(start,end):
    q=urllib.parse.urlencode({'startPeriod':start,'endPeriod':end,'format':'csvdata'})
    url=BASE+DATA_KEY+'?'+q
    req=urllib.request.Request(url,headers={'User-Agent':'GLOBAL-MACRO-FX-QUANT/1.0','Accept':'text/csv,*/*'})
    with urllib.request.urlopen(req,timeout=60) as r:
        raw=r.read().decode('utf-8-sig')
    rows=list(csv.DictReader(io.StringIO(raw)))
    out=[]
    for row in rows:
        d=row.get('TIME_PERIOD') or row.get('TIME_PERIOD_START') or row.get('Time period')
        v=row.get('OBS_VALUE') or row.get('Obs value') or row.get('OBSERVATION_VALUE')
        if not d or v in (None,''): continue
        try: fv=float(v)
        except: continue
        if math.isfinite(fv): out.append({'date':d[:10],'value':fv})
    out.sort(key=lambda x:x['date'])
    return url,out,rows[0].keys() if rows else []


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--start',default='2016-01-01')
    ap.add_argument('--end',default='2026-09-30')
    ap.add_argument('--output',required=True)
    ap.add_argument('--summary',required=True)
    a=ap.parse_args()
    url,obs,cols=fetch(a.start,a.end)
    if not obs: raise RuntimeError('ECB returned no observations; columns='+repr(list(cols)))
    by={x['date']:x['value'] for x in obs}
    anchor_date='2026-09-29'; anchor_expected=3.2105877756
    anchor_actual=by.get(anchor_date)
    anchor_error=None if anchor_actual is None else abs(anchor_actual-anchor_expected)
    series={
      'schema':'GMFQ_EUR_AAA_2Y_HISTORY_V1',
      'id':'EUR_ECB_AAA_SVENSSON_SPOT_2Y_HISTORY',
      'series_key':SERIES_KEY,
      'label':'EUR AAA Svensson spot 2Y',
      'category':'Rates','unit':'Percent per annum','frequency':'Daily - businessweek',
      'source':'ECB Data Portal · Financial market data - yield curve (YC)',
      'basis':'Euro area changing composition · EUR · ECB · nominal AAA government bonds · Svensson continuous-compounding yield-error minimisation · 2Y spot rate',
      'start':a.start,'end':a.end,'observations':obs
    }
    summary={
      'schema':'GMFQ_EUR_AAA_2Y_HISTORY_VALIDATION_V1','status':'PASS' if anchor_error is not None and anchor_error<=1e-8 and len(obs)>2000 else 'FAIL',
      'series_key':SERIES_KEY,'source_url':url,'observation_count':len(obs),
      'first_observation':obs[0]['date'],'last_observation':obs[-1]['date'],
      'anchor_date':anchor_date,'anchor_expected':anchor_expected,'anchor_actual':anchor_actual,'anchor_error':anchor_error,
      'same_basis_current_snapshot_match':anchor_error is not None and anchor_error<=1e-8,
      'history_spliced':False,'live_data_modified':False,'model_rules_modified':False,
      'rules_fingerprint_expected_unchanged':'3356baf0'
    }
    Path(a.output).write_text(json.dumps(series,ensure_ascii=False,indent=2))
    Path(a.summary).write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if summary['status']!='PASS': raise SystemExit(1)

if __name__=='__main__': main()
