#!/usr/bin/env python3
"""Fixed OOS EURUSD diagnostic: EUR-vs-USD rates differentials.

Uses only certified temporal-PIT EUR and USD 2Y/10Y rowsets. No macro-US
substitution, no tuning, no production signal.
"""
from __future__ import annotations
import argparse,csv,json,math
from bisect import bisect_right
from datetime import date
from pathlib import Path

SCHEMA='GMFQ_EURUSD_RELATIVE_RATES_PILOT_V1'
ALPHA=10.0
MIN_TRAIN=36
SETS={
 'RELATIVE_RATES':['diff_2y','diff_10y','diff_curve_bp'],
 'EUR_RATES_ONLY':['eur_2y','eur_10y','eur_curve_bp'],
 'USD_RATES_ONLY':['usd_2y','usd_10y','usd_curve_bp'],
}
BLOCKS=[('2021-03_to_2022-12','2021-03-10','2022-12-10'),('2023_to_2024','2023-01-10','2024-12-10'),('2025_to_2026-07','2025-01-10','2026-07-10')]

def mean(x): return sum(x)/len(x)
def stdev(x):
    if len(x)<2:return 0.0
    m=mean(x);return math.sqrt(sum((v-m)**2 for v in x)/(len(x)-1))
def corr(a,b):
    if len(a)<3:return None
    ma,mb=mean(a),mean(b);da=sum((x-ma)**2 for x in a);db=sum((x-mb)**2 for x in b)
    if da<=0 or db<=0:return None
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(da*db)
def sharpe(r):
    s=stdev(r);return None if s<=1e-12 else mean(r)/s*math.sqrt(12)
def mdd(r):
    w=p=1.0;d=0.0
    for x in r:
        w*=math.exp(x);p=max(p,w);d=min(d,w/p-1)
    return d

def solve(a,b):
    n=len(b);z=[a[i][:]+[b[i]] for i in range(n)]
    for c in range(n):
        q=max(range(c,n),key=lambda r:abs(z[r][c]));z[c],z[q]=z[q],z[c]
        if abs(z[c][c])<1e-12:raise RuntimeError('singular')
        k=z[c][c];z[c]=[v/k for v in z[c]]
        for r in range(n):
            if r==c:continue
            k=z[r][c]
            if k:z[r]=[z[r][j]-k*z[c][j] for j in range(n+1)]
    return [z[i][-1] for i in range(n)]
def fit(x,y):
    p=len(x[0]);mu=[mean([r[j] for r in x]) for j in range(p)];sd=[stdev([r[j] for r in x]) or 1.0 for j in range(p)]
    z=[[1.0]+[(r[j]-mu[j])/sd[j] for j in range(p)] for r in x];k=p+1
    xtx=[[0.0]*k for _ in range(k)];xty=[0.0]*k
    for row,t in zip(z,y):
        for i in range(k):
            xty[i]+=row[i]*t
            for j in range(k):xtx[i][j]+=row[i]*row[j]
    for i in range(1,k):xtx[i][i]+=ALPHA
    return solve(xtx,xty),mu,sd
def predict(beta,mu,sd,x):return beta[0]+sum(beta[j+1]*(x[j]-mu[j])/sd[j] for j in range(len(x)))

def load_rates(p:Path):
    rows=[]
    with p.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            rows.append({'obs':r['observation_date'],'eligible':r['first_eligible_decision_date'],'y2':float(r['yield_2y']),'y10':float(r['yield_10y'])})
    rows.sort(key=lambda r:r['eligible']);return rows

def select(rows,dp):
    eligible=[r for r in rows if r['eligible']<=dp]
    if not eligible:raise RuntimeError(f'no eligible row {dp}')
    r=eligible[-1]
    if not (r['obs']<dp and r['eligible']<=dp):raise RuntimeError('temporal violation')
    return r

def month_grid():
    out=[];y,m=2018,3
    while (y,m)<=(2026,8):
        out.append(f'{y:04d}-{m:02d}-10');y,m=(y+1,1) if m==12 else (y,m+1)
    return out

def load_prices(p:Path):
    d={}
    with p.open(newline='',encoding='utf-8-sig') as f:
        rd=csv.DictReader(f);fs=rd.fieldnames or []
        dk=next(k for k in ['TIME_PERIOD','TIME PERIOD','Date','DATE'] if k in fs);vk=next(k for k in ['OBS_VALUE','OBS VALUE','Value','VALUE'] if k in fs)
        for r in rd:
            ds=(r.get(dk) or '')[:10];vs=(r.get(vk) or '').strip()
            try: date.fromisoformat(ds);v=float(vs)
            except: continue
            if v>0:d[ds]=v
    return sorted(d),d

def first_after(dp,dates,prices):
    i=bisect_right(dates,dp)
    if i>=len(dates):raise RuntimeError('missing fixing')
    return dates[i],prices[dates[i]]

def metrics(preds):
    y=[r['actual'] for r in preds];p=[r['prediction'] for r in preds];sr=[r['strategy'] for r in preds]
    hit=sum(1 for a,b in zip(p,y) if (a>0 and b>0) or (a<0 and b<0))/len(preds)
    return {'observations':len(preds),'directional_accuracy':hit,'prediction_return_correlation':corr(p,y),'strategy_total_return':math.exp(sum(sr))-1,'strategy_annualized_sharpe':sharpe(sr),'strategy_max_drawdown':mdd(sr),'mean_monthly_strategy_log_return':mean(sr)}

def run_model(labelled,features):
    preds=[]
    for t in range(MIN_TRAIN,len(labelled)):
        tr=labelled[:t];beta,mu,sd=fit([[r[f] for f in features] for r in tr],[r['ret'] for r in tr])
        pr=predict(beta,mu,sd,[labelled[t][f] for f in features]);a=labelled[t]['ret'];sg=1 if pr>0 else -1 if pr<0 else 0
        preds.append({'decision_point':labelled[t]['dp'],'prediction':pr,'actual':a,'strategy':sg*a})
    blocks={}
    for name,lo,hi in BLOCKS:
        q=[r for r in preds if lo<=r['decision_point']<=hi];blocks[name]=metrics(q)
    return {'features':features,'overall':metrics(preds),'time_blocks':blocks,'predictions':preds}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--eur-rates',type=Path,required=True);ap.add_argument('--usd-rates',type=Path,required=True);ap.add_argument('--ecb-csv',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    er,ur=load_rates(a.eur_rates),load_rates(a.usd_rates);dates,prices=load_prices(a.ecb_csv)
    rows=[]
    for dp in month_grid():
        e,u=select(er,dp),select(ur,dp);ed,ep=first_after(dp,dates,prices)
        ec=(e['y10']-e['y2'])*100;uc=(u['y10']-u['y2'])*100
        rows.append({'dp':dp,'fixing_date':ed,'price':ep,'eur_obs':e['obs'],'usd_obs':u['obs'],'eur_2y':e['y2'],'eur_10y':e['y10'],'eur_curve_bp':ec,'usd_2y':u['y2'],'usd_10y':u['y10'],'usd_curve_bp':uc,'diff_2y':e['y2']-u['y2'],'diff_10y':e['y10']-u['y10'],'diff_curve_bp':ec-uc})
    labelled=[]
    for i in range(len(rows)-1):
        r=dict(rows[i]);r['ret']=math.log(rows[i+1]['price']/r['price']);labelled.append(r)
    models={k:run_model(labelled,v) for k,v in SETS.items()}
    rel=models['RELATIVE_RATES']['overall'];eur=models['EUR_RATES_ONLY']['overall']
    out={'schema':SCHEMA,'status':'DIAGNOSTIC_COMPLETE','scope':{'instrument':'EURUSD','snapshot_count':len(rows),'labelled_months':len(labelled),'oos_predictions_per_model':len(models['RELATIVE_RATES']['predictions'])},'method':{'models':SETS,'ridge_alpha_fixed':ALPHA,'minimum_training_months':MIN_TRAIN,'hyperparameter_tuning':False,'price_source':'ECB official EURUSD reference rate','rates_sources':'certified temporal-PIT EUR and USD 2Y/10Y rowsets'},'models':models,'comparison':{'relative_minus_eur_sharpe':rel['strategy_annualized_sharpe']-eur['strategy_annualized_sharpe'],'relative_minus_eur_hit_rate':rel['directional_accuracy']-eur['directional_accuracy']},'policy':{'diagnostic_only':True,'production_signal_authorized':False,'parameter_changes_from_results_authorized':False}}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'comparison':out['comparison'],'relative':rel,'eur_only':eur},indent=2,sort_keys=True))
if __name__=='__main__':main()
