#!/usr/bin/env python3
import csv, json, math, urllib.request
from bisect import bisect_right
from pathlib import Path

REPLAY_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/staging-usd-pit-readiness-2026-10-03/validation/PIT_MACRO_REPLAY_V1_2026-10-03.json'
PRICE_PATH=Path('history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv')
MANIFEST_PATH=Path('history/pit_v1/BACKTEST_DATASET_MANIFEST.json')
OUT=Path('validation/PIT_MACRO_PRICE_BACKTEST_V1_2026-10-06.json')
PAIR='EURCAD'
HORIZONS=(5,20,60)

def load_json_url(url):
    req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-PIT-backtest/1.0'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))

def metrics(xs):
    if not xs: return {'n':0,'hit_rate':None,'mean_signed_return':None,'median_signed_return':None}
    ys=sorted(xs); n=len(xs)
    return {'n':n,'hit_rate':sum(x>0 for x in xs)/n,'mean_signed_return':sum(xs)/n,'median_signed_return':ys[n//2] if n%2 else (ys[n//2-1]+ys[n//2])/2}

def main():
    manifest=json.loads(MANIFEST_PATH.read_text())
    assert manifest['frozen_engine_commit']=='ff52198a75cc67f7dae96fc2bbf65623f170791c'
    assert manifest['rules_fingerprint']=='3356baf0'
    assert manifest['threshold_tuning_allowed'] is False
    replay=load_json_url(REPLAY_URL)
    assert replay['engine']['rules_fingerprint']=='3356baf0'
    eur={x['checkpoint']:x for x in replay['currencies']['EUR']['replay']}
    cad={x['checkpoint']:x for x in replay['currencies']['CAD']['replay']}
    common=sorted(set(eur)&set(cad))
    rows=[]
    with PRICE_PATH.open(newline='',encoding='utf-8') as f:
        for r in csv.DictReader(f): rows.append((r['date'],float(r[PAIR])))
    dates=[d for d,_ in rows]
    prices=[p for _,p in rows]
    samples=[]
    for cp in common:
        ep=eur[cp].get('macro_polarity'); cpv=cad[cp].get('macro_polarity')
        if ep not in (-1,1) or cpv not in (-1,1) or ep==cpv: continue
        direction=1 if ep>cpv else -1
        i=bisect_right(dates,cp)  # conservative: first ECB reference observation strictly after checkpoint
        if i>=len(rows): continue
        rec={'checkpoint':cp,'entry_date':dates[i],'direction':direction,'eur_polarity':ep,'cad_polarity':cpv,'entry_price':prices[i]}
        for h in HORIZONS:
            if i+h<len(rows):
                raw=prices[i+h]/prices[i]-1.0
                rec[f'return_{h}d']=raw
                rec[f'signed_return_{h}d']=direction*raw
        samples.append(rec)
    regime=[]; last=None
    for s in samples:
        if s['direction']!=last:
            regime.append(s); last=s['direction']
    stats_all={}; stats_regime={}
    for h in HORIZONS:
        k=f'signed_return_{h}d'
        stats_all[f'{h}d']=metrics([s[k] for s in samples if k in s])
        stats_regime[f'{h}d']=metrics([s[k] for s in regime if k in s])
    out={
      'schema':'GMFQ_PIT_MACRO_PRICE_BACKTEST_V1','created_at':'2026-10-06','status':'PASS',
      'scope':'Frozen v9.3 PIT Macro block only; EUR vs CAD because both have full PIT Growth+Labour macro votes. This is not a full 28-pair all-layer engine backtest.',
      'engine':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','threshold_tuning':False},
      'dataset_manifest_sha256':manifest['dataset_manifest_sha256'],
      'price_pair':PAIR,'entry_policy':'First ECB daily reference observation strictly after macro checkpoint date.',
      'signal_rule':'Long EURCAD when EUR macro polarity=+1 and CAD=-1; short when EUR=-1 and CAD=+1; no trade otherwise.',
      'checkpoint_count_common':len(common),'signal_checkpoint_count':len(samples),'regime_entry_count':len(regime),
      'stats_all_signal_checkpoints':stats_all,'stats_regime_entries_only':stats_regime,
      'samples':samples,'regime_entries':regime,
      'guardrails':['PIT replay artifact only','No revised-history fallback','No threshold tuning','Withheld currencies excluded','Conservative next-reference-price entry'],
      'changes_live_data':False,'changes_engine_rules':False,'changes_oos_baseline':False
    }
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:out[k] for k in ['status','checkpoint_count_common','signal_checkpoint_count','regime_entry_count','stats_all_signal_checkpoints','stats_regime_entries_only']},indent=2))

if __name__=='__main__': main()
