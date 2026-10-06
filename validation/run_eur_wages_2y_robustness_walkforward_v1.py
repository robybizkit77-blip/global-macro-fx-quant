import json, math, random, statistics, os
SRC='validation/EUR_REACTION_FUNCTION_DIAGNOSTIC_V1_2026-10-06.json'
OUT='validation/EUR_WAGES_2Y_ROBUSTNESS_WALKFORWARD_V1_2026-10-06.json'
H=['5d','20d','60d']
SEED=3356
NBOOT=20000

def wilson(k,n,z=1.96):
    if n==0:return [None,None]
    p=k/n; den=1+z*z/n; c=(p+z*z/(2*n))/den; m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [c-m,c+m]

def boot_ci(xs,fn):
    if not xs:return [None,None]
    rng=random.Random(SEED); vals=[]; n=len(xs)
    for _ in range(NBOOT): vals.append(fn([xs[rng.randrange(n)] for __ in range(n)]))
    vals.sort(); return [vals[int(.025*NBOOT)],vals[int(.975*NBOOT)-1]]

def stats(ev):
    out={}
    for h in H:
        xs=[e[f'signed_{h}'] for e in ev if e.get(f'signed_{h}') is not None]
        n=len(xs); k=sum(x>0 for x in xs)
        out[h]={'n':n,'hit_rate':k/n if n else None,'mean':sum(xs)/n if n else None,'median':statistics.median(xs) if n else None,
                'wilson95_hit':wilson(k,n) if n else [None,None],
                'bootstrap95_mean':boot_ci(xs,lambda a:sum(a)/len(a)) if n else [None,None],
                'bootstrap95_hit':boot_ci(xs,lambda a:sum(x>0 for x in a)/len(a)) if n else [None,None]}
    return out

def main():
    d=json.load(open(SRC,encoding='utf-8'))
    ev=sorted(d['wages_plus_2y_confirmation']['confirmed_events'], key=lambda x:x['entry_date'])
    n=len(ev); cut=max(1,int(n*0.4)); remain=n-cut; base=remain//3; extra=remain%3
    folds=[]; start=cut
    for i in range(3):
        size=base+(1 if i<extra else 0); test=ev[start:start+size]; train=ev[:start]
        folds.append({'fold':i+1,'train_n':len(train),'test_n':len(test),'train_end':train[-1]['entry_date'] if train else None,
                      'test_start':test[0]['entry_date'] if test else None,'test_end':test[-1]['entry_date'] if test else None,'test_stats':stats(test)})
        start+=size
    pooled=ev[cut:]
    # stability halves, no tuning
    half=n//2
    audit={'schema':'GMFQ_EUR_WAGES_2Y_ROBUSTNESS_WALKFORWARD_V1','status':'PASS','created_at':'2026-10-06',
      'scope':'Robustness and pure chronological walk-forward of predeclared EUR negotiated-wages plus 5-market-day EUR 2Y confirmation diagnostic. No fitting or threshold tuning.',
      'guardrails':['5-market-day confirmation window frozen','no threshold tuning','no parameter optimization','FX entry after confirmation only','engine untouched','live_data untouched'],
      'all_confirmed_stats':stats(ev),'chronological_walkforward':{'initial_train_fraction':0.4,'folds':folds,'pooled_oos':stats(pooled)},
      'stability':{'first_half':stats(ev[:half]),'second_half':stats(ev[half:])},
      'assessment':'DIAGNOSTIC_ONLY_NOT_STATISTICALLY_LOCKED','changes_engine_rules':False,'changes_live_data':False}
    os.makedirs('validation',exist_ok=True); json.dump(audit,open(OUT,'w',encoding='utf-8'),indent=2); print(json.dumps(audit,indent=2))
if __name__=='__main__':main()
