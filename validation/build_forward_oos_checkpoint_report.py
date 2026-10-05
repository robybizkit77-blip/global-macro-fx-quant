#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, tempfile
from pathlib import Path

T0_PATH=Path('validation/CANONICAL_ENGINE_OOS_T0_V3_2026-10-01.json')
FINGERPRINT='3356baf0'
FREEZE_SHA='ff52198a75cc67f7dae96fc2bbf65623f170791c'
ROLE={
  '1W':('EARLY_READ_ONLY','KEEP_FROZEN_AND_WAIT_FOR_4W'),
  '4W':('INTERMEDIATE_VALIDATION','KEEP_FROZEN_AND_WAIT_FOR_12W'),
  '12W':('FIRST_COMPLETE_FORWARD_CYCLE','OPEN_POST_OOS_REVIEW'),
}

def load(p): return json.loads(Path(p).read_text())

def favored_return(row):
    base,quote=row['pair'].split('/')
    r=float(row['return_pct'])
    return r if row.get('favored')==base else -r

def bucket_stats(rows):
    out={}
    for r in rows:
        q=r.get('quality') or 'UNKNOWN'
        z=out.setdefault(q,{'n':0,'hits':0,'favored_return_sum_pct':0.0})
        z['n']+=1; z['hits']+=int(r.get('hit') is True); z['favored_return_sum_pct']+=favored_return(r)
    for z in out.values():
        z['hit_rate_pct']=round(100*z['hits']/z['n'],2) if z['n'] else None
        z['mean_favored_return_pct']=round(z['favored_return_sum_pct']/z['n'],4) if z['n'] else None
        del z['favored_return_sum_pct']
    return out

def behavior(rows,t0,key,value):
    subset=[r for r in rows if t0['pairs'].get(r['pair'],{}).get(key)==value]
    if not subset: return {'n':0,'hits':0,'hit_rate_pct':None}
    h=sum(r.get('hit') is True for r in subset)
    return {'n':len(subset),'hits':h,'hit_rate_pct':round(100*h/len(subset),2)}

def make_report(ev,t0):
    if ev.get('schema')!='GMFQ_FORWARD_OOS_CHECKPOINT_EVALUATION_V1' or ev.get('status')!='EVALUATED':
        raise SystemExit('Input is not a validated EVALUATED checkpoint artifact')
    cp=ev.get('checkpoint')
    if cp not in ROLE: raise SystemExit('Unknown checkpoint')
    if ev.get('rules_fingerprint')!=FINGERPRINT or ev.get('engine_freeze_sha')!=FREEZE_SHA:
        raise SystemExit('Frozen OOS contract mismatch')
    if t0.get('rules_fingerprint')!=FINGERPRINT or len(t0.get('pairs',{}))!=28:
        raise SystemExit('Canonical T0 mismatch')

    rows=[r for r in ev.get('pair_results',[]) if r.get('eligible')]
    if not rows: raise SystemExit('No eligible pairs')
    buckets=bucket_stats(rows)
    ranked=sorted(rows,key=favored_return,reverse=True)
    bucket_rank=sorted(buckets.items(),key=lambda kv:(kv[1]['hit_rate_pct'],kv[1]['n']),reverse=True)
    best={'quality':bucket_rank[0][0],**bucket_rank[0][1]}
    worst={'quality':bucket_rank[-1][0],**bucket_rank[-1][1]}

    strong=[r for r in rows if r.get('quality')=='CONTRASTO STRUTTURALE FORTE']
    partial=[r for r in rows if r.get('quality')=='VANTAGGIO RELATIVO PARZIALE']
    macro_supported=[r for r in rows if t0['pairs'][r['pair']].get('macro_side') in ('A','B')]
    policy_supported=[r for r in rows if t0['pairs'][r['pair']].get('policy_side') in ('A','B')]

    def compact(rs):
        return [{'pair':r['pair'],'favored':r.get('favored'),'quality':r.get('quality'),'hit':r.get('hit'),'return_pct':round(float(r['return_pct']),4),'favored_return_pct':round(favored_return(r),4)} for r in rs]
    def stat(rs):
        if not rs:return {'n':0,'hits':0,'hit_rate_pct':None}
        h=sum(r.get('hit') is True for r in rs)
        return {'n':len(rs),'hits':h,'hit_rate_pct':round(100*h/len(rs),2)}

    role,next_action=ROLE[cp]
    hit_rate=round(100*sum(r.get('hit') is True for r in rows)/len(rows),2)
    if hit_rate>=60: label='SUPPORTIVE'
    elif hit_rate>=40: label='INCONCLUSIVE'
    else: label='CHALLENGED'

    confirmed=[r for r in rows if t0['pairs'][r['pair']].get('price_reading') in ('MERCATO GIÀ ALLINEATO','PREZZO CONFERMA')]
    divergent=[r for r in rows if 'DIVERGENZA' in str(t0['pairs'][r['pair']].get('price_reading','')) or t0['pairs'][r['pair']].get('price_reading')=='PREZZO DIVERGE']

    return {
      'schema':'GMFQ_FORWARD_OOS_CHECKPOINT_REPORT_V1',
      'source_evaluation':{'checkpoint':cp,'evaluation_target':ev.get('evaluation_target'),'fixing_date_used':ev.get('fixing_date_used'),'price_source':ev.get('price_source')},
      'frozen_contract':{'rules_fingerprint':FINGERPRINT,'engine_freeze_sha':FREEZE_SHA,'t0_effective_date':t0.get('t0_effective_date')},
      'headline':{'checkpoint':cp,'role':role,'eligible_pairs':len(rows),'hits':sum(r.get('hit') is True for r in rows),'hit_rate_pct':hit_rate,'status_label':label,'decision':next_action},
      'quality_breakdown':{'by_quality':buckets,'best_quality_bucket':best,'weakest_quality_bucket':worst},
      'pair_detail':{'top_positive_contributors':compact(ranked[:5]),'top_negative_contributors':compact(list(reversed(ranked[-5:]))),'strong_contrast_pairs':{'stats':stat(strong),'pairs':compact(strong)},'partial_advantage_pairs':{'stats':stat(partial),'pairs':compact(partial)}},
      'signal_diagnostics':{
        'macro_supported_hits':stat(macro_supported),
        'policy_supported_hits':stat(policy_supported),
        'price_confirmation_behavior':stat(confirmed),
        'price_divergence_behavior':stat(divergent)
      },
      'regime_read':{
        'what_worked':[r['pair'] for r in ranked if r.get('hit') is True][:5],
        'what_failed':[r['pair'] for r in reversed(ranked) if r.get('hit') is False][:5],
        'what_is_inconclusive':'Checkpoint 1W is an early read only.' if cp=='1W' else ('Checkpoint 4W is intermediate evidence only.' if cp=='4W' else 'Assess jointly with 1W and 4W before any new research cycle.'),
        'next_checkpoint_question':'Do strong structural contrasts outperform partial advantages, and does performance persist at the next horizon?'
      },
      'governance':{'tuning_allowed':False,'engine_change_allowed':False if cp in ('1W','4W') else 'POST_OOS_RESEARCH_ONLY','oos_restart_required':False,'next_action':next_action},
      'guardrails':['Descriptive reporting only','No rewriting T0 or anchors','No threshold/weight/hierarchy tuning from this report','Implementation/data defects must be separated from model-performance misses']
    }

def self_test():
    t0=load(T0_PATH)
    rows=[]
    i=0
    for pair,p in t0['pairs'].items():
        fav=p.get('favored'); eligible=fav in pair.split('/')
        ret=(1 if i%3 else -1)*(0.2+i*0.01); i+=1
        if eligible:
            base=pair.split('/')[0]
            hit=(ret>0) if fav==base else (ret<0)
        else: hit=None
        rows.append({'pair':pair,'favored':fav,'quality':p.get('quality'),'anchor_price':p.get('anchor_price'),'evaluation_price':p.get('anchor_price'),'return_pct':ret,'eligible':eligible,'hit':hit})
    ev={'schema':'GMFQ_FORWARD_OOS_CHECKPOINT_EVALUATION_V1','status':'EVALUATED','checkpoint':'1W','evaluation_target':'2026-10-08','fixing_date_used':'2099-01-01','price_source':'SELF_TEST_ONLY','rules_fingerprint':FINGERPRINT,'engine_freeze_sha':FREEZE_SHA,'pair_results':rows}
    rep=make_report(ev,t0)
    assert rep['headline']['eligible_pairs']>0
    assert rep['governance']['tuning_allowed'] is False
    assert rep['headline']['decision']=='KEEP_FROZEN_AND_WAIT_FOR_4W'
    print(json.dumps({'status':'REPORTER_SELF_TEST_PASS','eligible_pairs':rep['headline']['eligible_pairs'],'decision':rep['headline']['decision']},indent=2))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--evaluation')
    ap.add_argument('--output')
    ap.add_argument('--self-test',action='store_true')
    a=ap.parse_args()
    if a.self_test: self_test(); return
    if not a.evaluation: ap.error('--evaluation required unless --self-test')
    ev=load(a.evaluation); t0=load(T0_PATH); rep=make_report(ev,t0)
    out=Path(a.output) if a.output else Path(str(a.evaluation).replace('_EVALUATION_','_REPORT_'))
    out.write_text(json.dumps(rep,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':'REPORT_BUILT','path':str(out),'headline':rep['headline']},indent=2))

if __name__=='__main__': main()
