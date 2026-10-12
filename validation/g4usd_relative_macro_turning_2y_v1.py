#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, json
from bisect import bisect_right
from collections import Counter
from pathlib import Path

CCYS=("EUR","JPY","CAD","AUD")
OFFICIAL_UNAVAILABLE={"UNAVAILABLE_OFFICIAL_NOT_PUBLISHED","NOT_PUBLISHED_OFFICIAL"}


def month_grid():
    out=[]; y,m=2018,3
    while (y,m)<=(2026,8):
        out.append(f"{y:04d}-{m:02d}-10")
        y,m=(y+1,1) if m==12 else (y,m+1)
    return out


def load_rates(path:Path):
    rows=[]
    with path.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            rows.append({'obs':r['observation_date'],'eligible':r['first_eligible_decision_date'],'y2':float(r['yield_2y'])})
    rows.sort(key=lambda r:(r['eligible'],r['obs']))
    return rows


def select_rate(rows,dp):
    eligible=[r for r in rows if r['eligible']<=dp]
    if not eligible: raise RuntimeError(f'no eligible rate row for {dp}')
    r=eligible[-1]
    if not (r['obs']<dp and r['eligible']<=dp):
        raise RuntimeError(f'temporal rate violation {dp}: {r}')
    return r


def load_macro(path:Path,date_col:str,value_col:str):
    out=[]
    with path.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            status=(r.get('availability_status') or '').strip()
            value=(r.get(value_col) or '').strip()
            rel=(r.get('release_date') or r.get('first_eligible_decision_date') or r.get('eligible_date') or '').strip()
            if status in OFFICIAL_UNAVAILABLE:
                if value or rel: raise RuntimeError(f'official-unavailable row carries data in {path}')
                continue
            if not rel: raise RuntimeError(f'missing PIT release eligibility in {path}')
            if not value: raise RuntimeError(f'missing macro value in {path}')
            out.append((rel[:10],float(value)))
    out.sort()
    return out


def latest_three(rows,asof):
    dates=[d for d,_ in rows]
    i=bisect_right(dates,asof)-1
    if i<2: return None
    return rows[i][1],rows[i-1][1],rows[i-2][1]


def second_diff(rows,asof):
    x=latest_three(rows,asof)
    if x is None: return None
    cur,prev,prev2=x
    return (cur-prev)-(prev-prev2)


def sign(v,eps=1e-12):
    return 1 if v>eps else (-1 if v<-eps else 0)


def macro_direction(local,usd,asof):
    li=second_diff(local['inf'],asof); ui=second_diff(usd['inf'],asof)
    ll=second_diff(local['lab'],asof); ul=second_diff(usd['lab'],asof)
    if None in (li,ui,ll,ul):
        return 0,{'relative_inflation_acceleration':None,'relative_labour_acceleration':None}
    rel_inf=li-ui
    # Rising unemployment acceleration is weaker macro; invert unemployment acceleration first, then local-minus-US.
    rel_lab=(-ll)-(-ul)
    s1,s2=sign(rel_inf),sign(rel_lab)
    direction=s1 if s1!=0 and s1==s2 else 0
    return direction,{
        'local_inflation_acceleration':li,'usd_inflation_acceleration':ui,'relative_inflation_acceleration':rel_inf,
        'local_labour_acceleration':-ll,'usd_labour_acceleration':-ul,'relative_labour_acceleration':rel_lab,
    }


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def summarize(rows):
    vals=[r['signed_next_month_relative_2y_bp'] for r in rows]
    return {
        'n':len(rows),
        'mean_signed_next_month_relative_2y_bp':mean(vals),
        'directional_accuracy':sum(v>0 for v in vals)/len(vals) if vals else None,
        'hawkish_n':sum(r['macro_direction']==1 for r in rows),
        'dovish_n':sum(r['macro_direction']==-1 for r in rows),
    }


def main():
    ap=argparse.ArgumentParser()
    for c in ('eur','jpy','cad','aud','usd'):
        ap.add_argument(f'--{c}-rates',required=True)
        ap.add_argument(f'--{c}-inflation',required=True)
        ap.add_argument(f'--{c}-labour',required=True)
    ap.add_argument('--contract',required=True)
    ap.add_argument('--output',required=True)
    a=ap.parse_args()

    c=json.load(open(a.contract,encoding='utf-8'))
    assert c['schema']=='GMFQ_G4USD_RELATIVE_MACRO_TURNING_2Y_CONTRACT_V1'
    assert c['status']=='PREDECLARED_RESULT_BLIND'
    meta={
      'EUR':('reference_month','cpi_yoy','reference_month','unemployment_rate'),
      'JPY':('reference_month','cpi_yoy','reference_month','unemployment_rate'),
      'CAD':('reference_month','cpi_yoy_full_precision','reference_month','unemployment_rate'),
      'AUD':('reference_quarter','cpi_yoy','reference_month','unemployment_rate'),
      'USD':('reference_month','cpi_yoy','reference_month','unemployment_rate'),
    }
    rates={k:load_rates(Path(getattr(a,f'{k.lower()}_rates'))) for k in (*CCYS,'USD')}
    macro={}
    for k in (*CCYS,'USD'):
        ic,iv,lc,lv=meta[k]
        macro[k]={
          'inf':load_macro(Path(getattr(a,f'{k.lower()}_inflation')),ic,iv),
          'lab':load_macro(Path(getattr(a,f'{k.lower()}_labour')),lc,lv),
        }

    all_events=[]
    coverage={}
    for ccy in CCYS:
        levels=[]
        for dp in month_grid():
            lr=select_rate(rates[ccy],dp); ur=select_rate(rates['USD'],dp)
            levels.append({'dp':dp,'diff_2y':lr['y2']-ur['y2'],'local_obs':lr['obs'],'usd_obs':ur['obs']})
        repriced=[]
        for i in range(1,len(levels)):
            r=dict(levels[i]); r['d_diff_2y']=r['diff_2y']-levels[i-1]['diff_2y']; repriced.append(r)
        signals=[]
        for i in range(len(repriced)-1):
            r=repriced[i]
            direction,diag=macro_direction(macro[ccy],macro['USD'],r['dp'])
            if direction==0: continue
            nxt=repriced[i+1]
            signed_bp=direction*nxt['d_diff_2y']*100.0
            e={
              'currency':ccy,'asof_date':r['dp'],'macro_direction':direction,
              'macro_state':'LOCAL_HAWKISH' if direction>0 else 'LOCAL_DOVISH',
              'next_rates_asof_date':nxt['dp'],'next_month_d_diff_2y':nxt['d_diff_2y'],
              'signed_next_month_relative_2y_bp':signed_bp,
              **diag,
            }
            signals.append(e)
        cut=int(len(signals)*0.60)
        # Keep at least one OOS row when any signal exists, without changing the frozen 60/40 rule.
        if signals and cut>=len(signals): cut=len(signals)-1
        for j,e in enumerate(signals):
            e['split']='IS' if j<cut else 'OOS'
            all_events.append(e)
        coverage[ccy]={'signals_total':len(signals),'is_n':cut,'oos_n':len(signals)-cut}

    oos=[r for r in all_events if r['split']=='OOS']
    per={ccy:summarize([r for r in oos if r['currency']==ccy]) for ccy in CCYS}
    pooled=summarize(oos)
    counts=Counter(r['currency'] for r in oos)
    max_share=max(counts.values())/len(oos) if oos else 1.0
    g=c['predeclared_oos_gate']
    gates={
      'minimum_pooled_events':len(oos)>=g['minimum_pooled_events'],
      'minimum_events_per_currency':all(per[x]['n']>=g['minimum_events_per_currency'] for x in CCYS),
      'positive_mean_signed_2y':pooled['mean_signed_next_month_relative_2y_bp'] is not None and pooled['mean_signed_next_month_relative_2y_bp']>g['mean_signed_next_month_relative_2y_bp_gt'],
      'directional_accuracy':pooled['directional_accuracy'] is not None and pooled['directional_accuracy']>=g['directional_accuracy_min'],
      'positive_currencies':sum(per[x]['mean_signed_next_month_relative_2y_bp'] is not None and per[x]['mean_signed_next_month_relative_2y_bp']>0 for x in CCYS)>=g['minimum_currencies_positive_mean'],
      'concentration':max_share<=g['max_single_currency_share'],
      'both_directions':pooled['hawkish_n']>0 and pooled['dovish_n']>0,
    }
    result={
      'schema':'GMFQ_G4USD_RELATIVE_MACRO_TURNING_2Y_RESULT_V1',
      'status':'PASS_PREDECLARED_MECHANISM_GATE' if all(gates.values()) else 'FAIL_PREDECLARED_MECHANISM_GATE',
      'contract_schema':c['schema'],
      'fx_outcomes_joined':False,
      'production_signal_authorized':False,
      'sizing_authorized':False,
      'coverage':coverage,
      'oos_pooled':pooled,
      'oos_per_currency':per,
      'max_single_currency_share':max_share,
      'gates':gates,
      'mechanism_survival':all(gates.values()),
      'events':all_events,
    }
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','coverage','oos_pooled','oos_per_currency','max_single_currency_share','gates')},indent=2,sort_keys=True))

if __name__=='__main__': main()
