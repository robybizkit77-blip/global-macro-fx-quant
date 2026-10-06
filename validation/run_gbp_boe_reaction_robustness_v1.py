import json,math,random
from pathlib import Path
SRC=Path('validation/GBP_BOE_REACTION_FUNCTION_DIAGNOSTIC_V1_2026-10-06.json')
OUT=Path('validation/GBP_BOE_REACTION_ROBUSTNESS_WALKFORWARD_V1_2026-10-06.json')
H=[5,20,60]; SEED=3356; B=20000

def med(xs):
    y=sorted(xs);n=len(y);return y[n//2] if n%2 else (y[n//2-1]+y[n//2])/2

def wilson(k,n,z=1.959963984540054):
    if not n:return [None,None]
    p=k/n;den=1+z*z/n;c=(p+z*z/(2*n))/den;h=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [max(0,c-h),min(1,c+h)]

def q(a,p):
    y=sorted(a);i=(len(y)-1)*p;lo=int(math.floor(i));hi=int(math.ceil(i))
    return y[lo] if lo==hi else y[lo]+(y[hi]-y[lo])*(i-lo)

def stats(events,bootstrap=True):
    out={};rng=random.Random(SEED)
    for h in H:
        xs=[e.get(f'signed_{h}d') for e in events if e.get(f'signed_{h}d') is not None]
        n=len(xs)
        if not n:out[f'{h}d']={'n':0};continue
        d={'n':n,'hit_rate':sum(x>0 for x in xs)/n,'mean':sum(xs)/n,'median':med(xs),'wilson95_hit':wilson(sum(x>0 for x in xs),n)}
        if bootstrap:
            means=[];hits=[]
            for _ in range(B):
                s=[xs[rng.randrange(n)] for __ in range(n)];means.append(sum(s)/n);hits.append(sum(x>0 for x in s)/n)
            d['bootstrap95_mean']=[q(means,.025),q(means,.975)];d['bootstrap95_hit']=[q(hits,.025),q(hits,.975)]
        out[f'{h}d']=d
    return out

def chrono(events):
    ev=sorted(events,key=lambda e:e['entry_date']);n=len(ev);cut=max(1,int(n*.4));rem=n-cut
    sizes=[rem//3+(1 if i<rem%3 else 0) for i in range(3)]
    folds=[];pos=cut;pool=[]
    for i,s in enumerate(sizes,1):
        test=ev[pos:pos+s];train=ev[:pos];pos+=s;pool+=test
        folds.append({'fold':i,'train_n':len(train),'test_n':len(test),'train_end':train[-1]['entry_date'] if train else None,'test_start':test[0]['entry_date'] if test else None,'test_end':test[-1]['entry_date'] if test else None,'test_stats':stats(test)})
    return {'initial_train_fraction':.4,'folds':folds,'pooled_oos':stats(pool),'pooled_oos_n':len(pool)}

def main():
    d=json.loads(SRC.read_text())
    wage=d['wages']['regime_events']; conf=d['wages_plus_2y_ois_confirmation']['confirmed_events']
    def halves(ev):
        x=sorted(ev,key=lambda e:e['entry_date']);m=len(x)//2;return {'first_half':stats(x[:m]),'second_half':stats(x[m:])}
    out={'schema':'GMFQ_GBP_BOE_REACTION_ROBUSTNESS_WALKFORWARD_V1','status':'PASS','created_at':'2026-10-06','scope':'Robustness and pure chronological walk-forward of predeclared GBP AWE and AWE+5-market-day BoE OIS 2Y confirmation diagnostics. No fitting or threshold tuning.','guardrails':['K54L wage definition frozen','5-market-day OIS window frozen','no parameter optimization','FX entry after confirmation','engine untouched','live_data untouched'],'wages_standalone':{'all':stats(wage),'walkforward':chrono(wage),'stability':halves(wage)},'wages_plus_2y_ois':{'all':stats(conf),'walkforward':chrono(conf),'stability':halves(conf)},'assessment_policy':'Compare persistence and OOS stability; do not select or tune based on best historical horizon.','changes_engine_rules':False,'changes_live_data':False,'threshold_tuning':False}
    OUT.write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
