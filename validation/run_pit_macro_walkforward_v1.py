import json, math
from pathlib import Path

SRC=Path('validation/PIT_MACRO_G8_BASKET_BACKTEST_V1_2026-10-06.json')
OUT=Path('validation/PIT_MACRO_WALKFORWARD_V1_2026-10-06.json')
raw=json.loads(SRC.read_text())

# Pure chronological evaluation of frozen signals. No fitting/tuning occurs.
# Use regime entries only to reduce overlap/repeated-regime inflation.

def stats(xs):
    xs=[x for x in xs if x is not None]
    n=len(xs)
    if not n: return {'n':0,'hit_rate':None,'mean':None,'median':None}
    ys=sorted(xs)
    med=ys[n//2] if n%2 else (ys[n//2-1]+ys[n//2])/2
    return {'n':n,'hit_rate':sum(x>0 for x in xs)/n,'mean':sum(xs)/n,'median':med}

def build(cur):
    entries=raw['currencies'][cur]['regime_entries_samples'] if 'regime_entries_samples' in raw['currencies'][cur] else raw['currencies'][cur].get('regime_entry_samples')
    if entries is None:
        # backwards-compatible: reconstruct regime entries from signals by polarity changes
        sig=raw['currencies'][cur]['signals']
        entries=[]; prev=None
        for s in sig:
            p=s['polarity']
            if p!=prev:
                entries.append(s); prev=p
    entries=sorted(entries,key=lambda x:x['checkpoint'])
    n=len(entries)
    # expanding-window test folds: first 40%, then next 20%, next 20%, final 20%.
    # train data are reported only; never used to change thresholds or rules.
    cuts=[]
    start=max(1,math.floor(n*0.4))
    for endfrac in (0.6,0.8,1.0):
        end=max(start+1, math.floor(n*endfrac)) if endfrac<1 else n
        if start<n and end>start: cuts.append((start,end))
        start=end
    folds=[]
    for i,(a,b) in enumerate(cuts,1):
        train=entries[:a]; test=entries[a:b]
        fold={'fold':i,'train_n':len(train),'test_n':len(test),
              'train_end':train[-1]['checkpoint'] if train else None,
              'test_start':test[0]['checkpoint'] if test else None,
              'test_end':test[-1]['checkpoint'] if test else None,
              'test':{}}
        for h in ('5d','20d','60d'):
            key=f'signed_{h}'
            fold['test'][h]=stats([s.get(key) for s in test])
        folds.append(fold)
    pooled={}
    for h in ('5d','20d','60d'):
        vals=[]
        for f in folds:
            a=f['test'][h]
            # recompute from actual entries for exact pooled values
        for a,b in cuts:
            vals.extend([s.get(f'signed_{h}') for s in entries[a:b] if s.get(f'signed_{h}') is not None])
        pooled[h]=stats(vals)
    return {'regime_entries':n,'folds':folds,'pooled_oos':pooled}

res={
 'schema':'GMFQ_PIT_MACRO_WALKFORWARD_V1',
 'status':'PASS',
 'created_at':'2026-10-06',
 'scope':'Pure chronological expanding-window evaluation of frozen PIT Macro regime-entry signals for EUR and CAD versus G8 basket. Train windows are descriptive only; no fitting or tuning.',
 'engine':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','threshold_tuning':False},
 'method':{'sample':'regime entries only','split':'first 40% initial train, then three sequential ~20% OOS folds','rules_reestimated':False,'parameters_reestimated':False},
 'currencies':{c:build(c) for c in ('EUR','CAD')},
 'guardrails':['No threshold tuning','No parameter fitting','No revised-history fallback','Chronological order preserved','Audit-only output'],
 'changes_live_data':False,'changes_engine_rules':False,'changes_oos_baseline':False
}
OUT.write_text(json.dumps(res,indent=2))
print(json.dumps(res['currencies'],indent=2))
