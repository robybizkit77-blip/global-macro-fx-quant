#!/usr/bin/env python3
"""Fixed OOS EURUSD diagnostic: monthly EUR-vs-USD rates repricing changes."""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
from eurusd_relative_rates_pilot_v1 import load_rates,select,month_grid,load_prices,first_after,run_model

SCHEMA='GMFQ_EURUSD_RELATIVE_REPRICING_PILOT_V1'
SETS={
 'RELATIVE_REPRICING':['chg_diff_2y','chg_diff_10y','chg_diff_curve_bp'],
 'EUR_REPRICING_ONLY':['chg_eur_2y','chg_eur_10y','chg_eur_curve_bp'],
 'USD_REPRICING_ONLY':['chg_usd_2y','chg_usd_10y','chg_usd_curve_bp'],
}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--eur-rates',type=Path,required=True);ap.add_argument('--usd-rates',type=Path,required=True);ap.add_argument('--ecb-csv',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    er,ur=load_rates(a.eur_rates),load_rates(a.usd_rates);dates,prices=load_prices(a.ecb_csv)
    levels=[]
    for dp in month_grid():
        e,u=select(er,dp),select(ur,dp);fd,px=first_after(dp,dates,prices)
        ec=(e['y10']-e['y2'])*100;uc=(u['y10']-u['y2'])*100
        levels.append({'dp':dp,'price':px,'fixing_date':fd,'eur_2y':e['y2'],'eur_10y':e['y10'],'eur_curve_bp':ec,'usd_2y':u['y2'],'usd_10y':u['y10'],'usd_curve_bp':uc,'diff_2y':e['y2']-u['y2'],'diff_10y':e['y10']-u['y10'],'diff_curve_bp':ec-uc})
    rows=[]
    for i in range(1,len(levels)):
        c,p=levels[i],levels[i-1]
        r={'dp':c['dp'],'price':c['price'],'fixing_date':c['fixing_date']}
        for k in ['eur_2y','eur_10y','eur_curve_bp','usd_2y','usd_10y','usd_curve_bp','diff_2y','diff_10y','diff_curve_bp']:
            r['chg_'+k]=c[k]-p[k]
        rows.append(r)
    labelled=[]
    for i in range(len(rows)-1):
        r=dict(rows[i]);r['ret']=math.log(rows[i+1]['price']/r['price']);labelled.append(r)
    models={k:run_model(labelled,v) for k,v in SETS.items()}
    rel=models['RELATIVE_REPRICING']['overall'];eur=models['EUR_REPRICING_ONLY']['overall']
    out={'schema':SCHEMA,'status':'DIAGNOSTIC_COMPLETE','scope':{'instrument':'EURUSD','monthly_repricing_rows':len(rows),'labelled_months':len(labelled),'oos_predictions_per_model':len(models['RELATIVE_REPRICING']['predictions'])},'method':{'models':SETS,'ridge_alpha_fixed':10.0,'minimum_training_months':36,'hyperparameter_tuning':False,'hypothesis':'monthly change in EUR-vs-USD rates differentials predicts next-month EURUSD return','price_source':'ECB official EURUSD reference rate','rates_sources':'certified temporal-PIT EUR and USD 2Y/10Y rowsets'},'models':models,'comparison':{'relative_minus_eur_sharpe':rel['strategy_annualized_sharpe']-eur['strategy_annualized_sharpe'],'relative_minus_eur_hit_rate':rel['directional_accuracy']-eur['directional_accuracy']},'policy':{'diagnostic_only':True,'production_signal_authorized':False,'parameter_changes_from_results_authorized':False}}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'comparison':out['comparison'],'relative':rel,'blocks':models['RELATIVE_REPRICING']['time_blocks']},indent=2,sort_keys=True))
if __name__=='__main__':main()
