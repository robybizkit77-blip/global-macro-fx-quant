#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,hashlib,json,math
from bisect import bisect_right
from collections import Counter
from datetime import date
from pathlib import Path

CCYS=('EUR','JPY','CAD','AUD')
PARENT_SHA='1cb6e8ea5e86fb5c8d6701c746fc97aeff70dcee3cef54d6ee3fe52ba8d0af7b'


def load_ecb(path:Path):
    out={}
    with path.open(newline='',encoding='utf-8-sig') as f:
        rd=csv.DictReader(f); fs=rd.fieldnames or []
        dk=next(k for k in ['TIME_PERIOD','TIME PERIOD','Date','DATE'] if k in fs)
        vk=next(k for k in ['OBS_VALUE','OBS VALUE','Value','VALUE'] if k in fs)
        for r in rd:
            ds=(r.get(dk) or '')[:10]; vs=(r.get(vk) or '').strip()
            try: date.fromisoformat(ds); v=float(vs)
            except Exception: continue
            if v>0: out[ds]=v
    return out


def first_common_after(dp,*series):
    common=sorted(set.intersection(*(set(s.keys()) for s in series)))
    i=bisect_right(common,dp)
    if i>=len(common): raise RuntimeError(f'missing common fixing after {dp}')
    return common[i]


def next_month_day10(dp:str)->str:
    d=date.fromisoformat(dp); y,m=d.year,d.month
    y,m=(y+1,1) if m==12 else (y,m+1)
    return f'{y:04d}-{m:02d}-10'


def local_usd_price(ccy,ds,usd_per_eur,local_per_eur):
    if ccy=='EUR': return usd_per_eur[ds]
    return usd_per_eur[ds]/local_per_eur[ds]


def mean(x): return sum(x)/len(x) if x else None


def metrics(rows):
    vals=[r['signed_fx_log_return'] for r in rows]
    return {
      'n':len(rows),
      'mean_signed_fx_log_return':mean(vals),
      'directional_accuracy':sum(v>0 for v in vals)/len(vals) if vals else None,
      'hawkish_n':sum(r['macro_direction']==1 for r in rows),
      'dovish_n':sum(r['macro_direction']==-1 for r in rows),
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--parent',required=True,type=Path)
    ap.add_argument('--contract',required=True,type=Path)
    ap.add_argument('--usd-ecb',required=True,type=Path)
    ap.add_argument('--jpy-ecb',required=True,type=Path)
    ap.add_argument('--cad-ecb',required=True,type=Path)
    ap.add_argument('--aud-ecb',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    a=ap.parse_args()

    raw=a.parent.read_bytes(); sha=hashlib.sha256(raw).hexdigest(); assert sha==PARENT_SHA,(sha,PARENT_SHA)
    parent=json.loads(raw)
    c=json.load(a.contract.open(encoding='utf-8'))
    assert parent['status']=='PASS_PREDECLARED_MECHANISM_GATE' and parent['mechanism_survival'] is True
    assert c['schema']=='GMFQ_G4USD_RELATIVE_MACRO_TURNING_2Y_FX_CONTRACT_V1'
    assert c['status']=='PREDECLARED_FX_RESULT_BLIND'

    confirmed=[r for r in parent['events'] if r['split']=='OOS' and r['signed_next_month_relative_2y_bp']>0]
    counts=Counter(r['currency'] for r in confirmed)
    expected=c['event_selection']['expected_confirmed_events_from_parent_only']
    assert len(confirmed)==expected['pooled']==40,(len(confirmed),expected)
    assert {x:counts[x] for x in CCYS}=={x:expected[x] for x in CCYS}

    usd=load_ecb(a.usd_ecb)
    locals_={'EUR':None,'JPY':load_ecb(a.jpy_ecb),'CAD':load_ecb(a.cad_ecb),'AUD':load_ecb(a.aud_ecb)}
    rows=[]
    for e in confirmed:
        ccy=e['currency']; confirm=e['next_rates_asof_date']; exit_anchor=next_month_day10(confirm)
        if ccy=='EUR':
            entry=first_common_after(confirm,usd); exitd=first_common_after(exit_anchor,usd)
        else:
            entry=first_common_after(confirm,usd,locals_[ccy]); exitd=first_common_after(exit_anchor,usd,locals_[ccy])
        p0=local_usd_price(ccy,entry,usd,locals_[ccy]); p1=local_usd_price(ccy,exitd,usd,locals_[ccy])
        ret=math.log(p1/p0); signed=e['macro_direction']*ret
        rows.append({
          'currency':ccy,'macro_signal_asof':e['asof_date'],'rates_confirmation_asof':confirm,
          'macro_direction':e['macro_direction'],'macro_state':e['macro_state'],
          'entry_fixing_date':entry,'exit_anchor':exit_anchor,'exit_fixing_date':exitd,
          'fx_log_return_local_vs_usd':ret,'signed_fx_log_return':signed
        })

    pooled=metrics(rows); per={x:metrics([r for r in rows if r['currency']==x]) for x in CCYS}
    shares={x:per[x]['n']/len(rows) for x in CCYS}; maxshare=max(shares.values())
    g=c['predeclared_candidate_gate']
    gates={
      'minimum_pooled_confirmed_events':len(rows)>=g['minimum_pooled_confirmed_events'],
      'minimum_confirmed_events_per_currency':all(per[x]['n']>=g['minimum_confirmed_events_per_currency'] for x in CCYS),
      'positive_mean_signed_fx':pooled['mean_signed_fx_log_return'] is not None and pooled['mean_signed_fx_log_return']>g['mean_signed_fx_log_return_gt'],
      'directional_accuracy':pooled['directional_accuracy'] is not None and pooled['directional_accuracy']>=g['directional_accuracy_min'],
      'positive_currencies':sum(per[x]['mean_signed_fx_log_return'] is not None and per[x]['mean_signed_fx_log_return']>0 for x in CCYS)>=g['minimum_currencies_positive_mean'],
      'concentration':maxshare<=g['max_single_currency_share'],
      'both_directions':pooled['hawkish_n']>0 and pooled['dovish_n']>0,
    }
    passed=all(gates.values())
    out={
      'schema':'GMFQ_G4USD_RELATIVE_MACRO_TURNING_2Y_FX_RESULT_V1',
      'status':'PASS_HISTORICAL_CONDITIONAL_FX_CANDIDATE_GATE' if passed else 'FAIL_HISTORICAL_CONDITIONAL_FX_CANDIDATE_GATE',
      'parent_result_sha256':sha,'confirmed_event_counts':{**{x:counts[x] for x in CCYS},'pooled':len(rows)},
      'pooled':pooled,'per_currency':per,'currency_shares':shares,'max_single_currency_share':maxshare,
      'gates':gates,'candidate_generated_for_future_confirmation':passed,
      'edge_certified':False,'production_signal_authorized':False,'sizing_authorized':False,
      'events':rows,
    }
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:out[k] for k in ['status','confirmed_event_counts','pooled','per_currency','gates']},indent=2,sort_keys=True))

if __name__=='__main__': main()
