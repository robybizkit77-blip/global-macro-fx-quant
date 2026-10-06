#!/usr/bin/env python3
import csv, json, hashlib
from pathlib import Path
ROOT=Path('.')
H=ROOT/'history/pit_v1'
ENGINE='ff52198a75cc67f7dae96fc2bbf65623f170791c'; RULES='3356baf0'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    market=json.loads((H/'MARKET_HISTORY_MANIFEST.json').read_text())
    mask=json.loads((H/'MACRO_ELIGIBILITY_MASK.json').read_text())
    bundle=json.loads((H/'BACKTEST_DATASET_MANIFEST.json').read_text())
    fx=H/'FX_G8_DAILY_ECB_2016_2026.csv'; er=H/'EUR_RATES_2Y_10Y_ECB_SAME_BASIS_2016_2026.csv'
    assert market['status']=='MATERIALIZED'
    assert market['frozen_engine_commit']==ENGINE and market['rules_fingerprint']==RULES
    assert sha(fx)==market['fx']['sha256']; assert sha(er)==market['eur_rates']['sha256']
    with fx.open() as f: fxrows=list(csv.DictReader(f))
    with er.open() as f: erows=list(csv.DictReader(f))
    assert len(fxrows)==2754 and len(fxrows[0])==29
    assert fxrows[0]['date']=='2016-01-04' and fxrows[-1]['date']=='2026-10-05'
    assert len(erows)==2746 and erows[0]['date']=='2016-01-04' and erows[-1]['date']=='2026-10-05'
    assert mask['currencies']['CAD']['status']=='ELIGIBLE_CORE'
    assert mask['currencies']['EUR']['status']=='ELIGIBLE_PARTIAL'
    assert mask['currencies']['USD']['status']=='ELIGIBLE_GROWTH_ONLY_LABOUR_WITHHELD'
    assert mask['currencies']['GBP']['status']=='ELIGIBLE_LABOUR_ONLY_FROM_ONS_A01_VINTAGES'
    assert mask['currencies']['JPY']['status']=='WITHHELD_PENDING_EVENT_TIME_POLICY'
    for c in ('AUD','NZD','CHF'): assert mask['currencies'][c]['status']=='WITHHELD_HISTORICAL_PIT'
    assert bundle['market_history_bundle_sha256']==market['dataset_bundle_sha256']
    assert bundle['macro_eligibility_mask_sha256']==mask['mask_sha256']
    assert bundle['frozen_engine_commit']==ENGINE and bundle['rules_fingerprint']==RULES
    assert bundle['threshold_tuning_allowed'] is False and bundle['backtest_started'] is False
    out={'schema':'GMFQ_PRE_BACKTEST_MINIMUM_DATASET_INTEGRITY_V1','status':'PASS','market_bundle_sha256':market['dataset_bundle_sha256'],'macro_mask_sha256':mask['mask_sha256'],'dataset_manifest_sha256':bundle['dataset_manifest_sha256'],'fx_rows':len(fxrows),'eur_rates_rows':len(erows),'eligible_macro_currencies':['CAD','EUR','USD','GBP'],'withheld_macro_currencies':['JPY','AUD','NZD','CHF'],'frozen_engine_commit':ENGINE,'rules_fingerprint':RULES,'backtest_started':False}
    print(json.dumps(out,indent=2))
    Path('validation/PRE_BACKTEST_MINIMUM_DATASET_INTEGRITY_2026-10-06.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__': main()
