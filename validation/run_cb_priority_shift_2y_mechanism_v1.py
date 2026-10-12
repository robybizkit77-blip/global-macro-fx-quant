#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,statistics
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path

ORD={'LABOUR_GROWTH':-1,'BALANCED':0,'INFLATION':1}
CB_CCY={'BOC':'CAD','BOJ':'JPY','RBA':'AUD','FED':'USD','ECB':'EUR'}
PRIMARY=('BOC','BOJ','RBA')


def load_rates(path):
    rows=[]
    with open(path,newline='',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            rows.append({
                'observation_date':r['observation_date'],
                'yield_2y':float(r['yield_2y']),
                'first_eligible_decision_date':r['first_eligible_decision_date'],
            })
    return sorted(rows,key=lambda x:x['first_eligible_decision_date'])


def build_transitions(label_rows):
    by=defaultdict(list)
    for r in label_rows: by[r['central_bank']].append(r)
    out=[]; excluded=Counter()
    for cb,rr in by.items():
        rr=sorted(rr,key=lambda x:x['decision_date'])
        prev=None
        for r in rr:
            lab=r['focus_primary']
            if lab not in ORD:
                prev=None; excluded['nonordinal_break']+=1; continue
            if prev is None:
                prev=r; excluded['no_immediate_ordinal_predecessor']+=1; continue
            shift=ORD[lab]-ORD[prev['focus_primary']]
            if shift==0:
                excluded['zero_shift']+=1
            else:
                out.append({
                    'central_bank':cb,
                    'currency':CB_CCY[cb],
                    'decision_date':r['decision_date'],
                    'previous_decision_date':prev['decision_date'],
                    'previous_focus':prev['focus_primary'],
                    'current_focus':lab,
                    'priority_shift_value':shift,
                    'priority_shift_sign':1 if shift>0 else -1,
                })
            prev=r
    return out,dict(excluded)


def attach_rate_event(e,rates):
    d=e['decision_date']
    pre=[x for x in rates if x['first_eligible_decision_date'] < d]
    post=[x for x in rates if x['first_eligible_decision_date'] > d]
    if not pre: return None,'missing_pre'
    if len(post)<5: return None,'missing_post_5'
    p=pre[-1]; p1=post[0]; p5=post[4]
    shift=e['priority_shift_sign']
    d1=100.0*(p1['yield_2y']-p['yield_2y'])
    d5=100.0*(p5['yield_2y']-p['yield_2y'])
    z=dict(e)
    z.update({
        'pre_observation_date':p['observation_date'],
        'pre_first_eligible_decision_date':p['first_eligible_decision_date'],
        'pre_yield_2y':p['yield_2y'],
        'post1_observation_date':p1['observation_date'],
        'post1_first_eligible_decision_date':p1['first_eligible_decision_date'],
        'post1_yield_2y':p1['yield_2y'],
        'post5_observation_date':p5['observation_date'],
        'post5_first_eligible_decision_date':p5['first_eligible_decision_date'],
        'post5_yield_2y':p5['yield_2y'],
        'delta_2y_1obs_bp':d1,
        'signed_delta_2y_1obs_bp':shift*d1,
        'delta_2y_5obs_bp':d5,
        'signed_delta_2y_5obs_bp':shift*d5,
        'direction_correct_5obs': bool(shift*d5>0),
    })
    return z,None


def summarize(rr):
    n=len(rr)
    vals=[r['signed_delta_2y_5obs_bp'] for r in rr]
    vals1=[r['signed_delta_2y_1obs_bp'] for r in rr]
    return {
        'n':n,
        'mean_signed_2y_5obs_bp':sum(vals)/n if n else None,
        'median_signed_2y_5obs_bp':statistics.median(vals) if n else None,
        'directional_accuracy_5obs':sum(v>0 for v in vals)/n if n else None,
        'mean_signed_2y_1obs_bp':sum(vals1)/n if n else None,
        'positive_shift_count':sum(r['priority_shift_sign']>0 for r in rr),
        'negative_shift_count':sum(r['priority_shift_sign']<0 for r in rr),
    }


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--labels',required=True);ap.add_argument('--contract',required=True);ap.add_argument('--rates-dir',required=True);ap.add_argument('--out-dir',required=True);a=ap.parse_args()
    c=json.load(open(a.contract)); labels_bytes=Path(a.labels).read_bytes(); labels=json.loads(labels_bytes)
    assert c['schema']=='GMFQ_CB_PRIORITY_SHIFT_2Y_MECHANISM_CONTRACT_V1'
    assert c['status']=='PREDECLARED_NO_RATES_JOIN_OBSERVED'
    assert hashlib.sha256(labels_bytes).hexdigest()==c['parent_label_dataset']['labeled_dataset_sha256']
    assert labels['schema']=='GMFQ_CB_PRIORITY_FOCUS_HISTORY_V1' and labels['performance_data_present'] is False

    transitions,excl=build_transitions(labels['rows'])
    expected=c['coverage_rule_frozen_before_rates_join']['known_label_only_shift_counts']
    actual=Counter(x['central_bank'] for x in transitions)
    assert {k:actual.get(k,0) for k in expected}==expected,(actual,expected)

    rate_files={'AUD':'aud_rates_2y_10y_temporal_pit_v1.csv','CAD':'cad_rates_2y_10y_temporal_pit_v1.csv','JPY':'jpy_rates_2y_10y_temporal_pit_v1.csv'}
    rates={ccy:load_rates(Path(a.rates_dir)/fn) for ccy,fn in rate_files.items()}
    events=[]; withheld=Counter()
    for e in transitions:
        if e['central_bank'] not in PRIMARY: continue
        z,reason=attach_rate_event(e,rates[e['currency']])
        if z is None: withheld[reason]+=1
        else: events.append(z)

    by_cb={cb:[r for r in events if r['central_bank']==cb] for cb in PRIMARY}
    per={cb:summarize(rr) for cb,rr in by_cb.items()}
    pooled=summarize(events)
    gate=c['predeclared_mechanism_gate_all_required']
    shares={cb:(len(rr)/len(events) if events else 1) for cb,rr in by_cb.items()}
    gates={
        'pooled_n':len(events)>=gate['minimum_pooled_eligible_events'],
        'per_cb_n':all(len(by_cb[cb])>=gate['minimum_events_per_primary_panel_central_bank'] for cb in PRIMARY),
        'pooled_mean_positive':pooled['mean_signed_2y_5obs_bp'] is not None and pooled['mean_signed_2y_5obs_bp']>gate['pooled_mean_signed_2y_change_bp_gt'],
        'pooled_accuracy':pooled['directional_accuracy_5obs'] is not None and pooled['directional_accuracy_5obs']>=gate['pooled_directional_accuracy_gte'],
        'positive_cb_means':sum(per[cb]['mean_signed_2y_5obs_bp']>0 for cb in PRIMARY)>=gate['minimum_central_banks_with_positive_mean_signed_2y_change'],
        'concentration':max(shares.values())<=gate['maximum_single_central_bank_event_share_lte'] if shares else False,
    }
    passed=all(gates.values())
    result={
        'schema':'GMFQ_CB_PRIORITY_SHIFT_2Y_MECHANISM_RESULT_V1',
        'label_dataset_sha256':hashlib.sha256(labels_bytes).hexdigest(),
        'primary_panel_central_banks':list(PRIMARY),
        'primary_panel_currencies':[CB_CCY[x] for x in PRIMARY],
        'label_only_transition_counts':dict(sorted(actual.items())),
        'mechanism_sample_withheld':dict(withheld),
        'pooled':pooled,
        'per_central_bank':per,
        'event_shares':shares,
        'predeclared_gates':gates,
        'verdict':'PASS_PREDECLARED_2Y_MECHANISM_GATE' if passed else 'FAIL_PREDECLARED_2Y_MECHANISM_GATE',
        'fx_data_present':False,
        'sharpe_present':False,
        'pnl_present':False,
        'production_signal_authorized':False,
        'sizing_authorized':False,
        'interpretation':'Historical mechanism diagnostic only; not independent edge certification.'
    }
    out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    rb=(json.dumps(result,indent=2,sort_keys=True)+'\n').encode();(out/'CB_PRIORITY_SHIFT_2Y_MECHANISM_RESULT_V1_2026-10-12.json').write_bytes(rb)
    fields=list(events[0].keys()) if events else []
    with (out/'cb_priority_shift_2y_events_v1.csv').open('w',newline='',encoding='utf-8') as f:
        if fields:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(events)
    receipt={'result_json_sha256':hashlib.sha256(rb).hexdigest(),'event_rows':len(events),'verdict':result['verdict'],'all_gates_pass':passed,'excluded_transition_counts':excl}
    (out/'CB_PRIORITY_SHIFT_2Y_MECHANISM_RECEIPT_V1.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=='__main__':main()
