#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, math, statistics, urllib.request, zipfile
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CPI=ROOT/'history/pit_v1/AUD_CPI_HEADLINE_FIRST_RELEASE_2018_2025Q3.csv'
LAB=ROOT/'history/pit_v1/AUD_UNEMPLOYMENT_FIRST_RELEASE_2018_2026.csv'
Y2=ROOT/'history/pit_v1/AUD_RBA_GOVT_2Y_DAILY_2018_2026.csv'
OUT=ROOT/'validation/AUD_RBA_REACTION_REPLAY_V1_2026-10-07.json'
ECB_URL='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip'
G8=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
ENGINE='ff52198a75cc67f7dae96fc2bbf65623f170791c'
FP='3356baf0'

def sign(x): return 1 if x>0 else -1 if x<0 else 0

def qnum(q):
    y=int(q[:4]); n=int(q[-1]); return y*4+n

def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def load_fx():
    req=urllib.request.Request(ECB_URL,headers={'User-Agent':'GMFQ-AUD-replay/1.0'})
    with urllib.request.urlopen(req,timeout=60) as r: raw=r.read()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name=[n for n in zf.namelist() if n.lower().endswith('.csv')][0]
        with zf.open(name) as fh:
            rd=csv.DictReader(io.TextIOWrapper(fh,encoding='utf-8-sig',newline=''))
            out={}
            for row in rd:
                d=row['Date'].strip()
                if d<'2018-01-01' or d>'2026-12-31': continue
                rates={'EUR':1.0}; ok=True
                for c in G8:
                    if c=='EUR':continue
                    s=(row.get(c) or '').strip()
                    if not s: ok=False; break
                    try:v=float(s)
                    except: ok=False; break
                    if not math.isfinite(v) or v<=0: ok=False; break
                    rates[c]=v
                if ok:out[d]=rates
    return out

def basket(rates):
    # ECB q_c = currency units per EUR; q_B/q_A = units of B per A.
    # Mean log B-per-AUD across other G8: increase = AUD appreciation.
    qa=rates['AUD']
    return sum(math.log(rates[b]/qa) for b in G8 if b!='AUD')/7.0

def stats(rows):
    vals=[r['signed_20d'] for r in rows]
    if not vals:return {'n':0,'hit_rate':None,'mean':None,'median':None}
    return {'n':len(vals),'hit_rate':sum(v>0 for v in vals)/len(vals),'mean':sum(vals)/len(vals),'median':statistics.median(vals)}

def main():
    cpi=read_csv(CPI); lab=read_csv(LAB); y2=read_csv(Y2); fx=load_fx()
    y2m={r['date']:float(r['aud_govt_2y_pct']) for r in y2}
    common=sorted(set(y2m)&set(fx))
    common_idx={d:i for i,d in enumerate(common)}
    labs=sorted([{'release_date':r['release_date'],'u':float(r['unemployment_rate_sa_pct']),'reference_month':r['reference_month']} for r in lab],key=lambda x:x['release_date'])
    cpis=sorted([{'q':r['reference_quarter'],'release_date':r['release_date'],'cpi':float(r['headline_cpi_yoy_pct'])} for r in cpi],key=lambda x:x['release_date'])
    events=[]; skipped=[]
    for i in range(1,len(cpis)):
        cur,prev=cpis[i],cpis[i-1]
        if qnum(cur['q'])-qnum(prev['q'])!=1:
            skipped.append({'q':cur['q'],'reason':'non_consecutive_cpi'}); continue
        known=[x for x in labs if x['release_date']<=cur['release_date']]
        if len(known)<2:
            skipped.append({'q':cur['q'],'reason':'insufficient_labour_history'}); continue
        lu,plu=known[-1],known[-2]
        cpi_dir=sign(cur['cpi']-prev['cpi'])
        labour_dir=-sign(lu['u']-plu['u'])
        macro_dir=cpi_dir if cpi_dir!=0 and cpi_dir==labour_dir else 0
        if macro_dir==0:
            skipped.append({'q':cur['q'],'reason':'mixed_or_neutral_dual_mandate','cpi_dir':cpi_dir,'labour_dir':labour_dir}); continue
        d0=next((d for d in common if d>=cur['release_date']),None)
        if not d0:
            skipped.append({'q':cur['q'],'reason':'no_common_market_date'}); continue
        j=common_idx[d0]
        if j+25>=len(common):
            skipped.append({'q':cur['q'],'reason':'insufficient_forward_window'}); continue
        d5,d25=common[j+5],common[j+25]
        rate5=y2m[d5]-y2m[d0]
        b0,b5,b25=basket(fx[d0]),basket(fx[d5]),basket(fx[d25])
        price5=b5-b0
        fwd20=b25-b5
        signed20=macro_dir*fwd20
        fe_dir=sign(rate5); px_dir=sign(price5)
        events.append({
            'reference_quarter':cur['q'],'release_date':cur['release_date'],'cpi_yoy':cur['cpi'],'prev_cpi_yoy':prev['cpi'],
            'labour_reference_month':lu['reference_month'],'unemployment':lu['u'],'prev_unemployment':plu['u'],
            'macro_direction':macro_dir,'macro_label':'HAWKISH' if macro_dir==1 else 'DOVISH',
            'market_t0':d0,'market_t5':d5,'market_t25':d25,'aud_2y_change_5d_pctpt':rate5,
            'aud_basket_log_change_5d':price5,'aud_basket_log_change_next20d':fwd20,'signed_20d':signed20,
            'front_end_state':'ALIGNED' if fe_dir==macro_dir else 'DIVERGENT' if fe_dir==-macro_dir else 'NEUTRAL',
            'price_state':'ALIGNED' if px_dir==macro_dir else 'DIVERGENT' if px_dir==-macro_dir else 'NEUTRAL',
            'transmission':'BOTH_ALIGNED' if fe_dir==macro_dir and px_dir==macro_dir else 'BOTH_DIVERGENT' if fe_dir==-macro_dir and px_dir==-macro_dir else 'MIXED'
        })
    events.sort(key=lambda x:x['release_date'])
    split=max(1,int(len(events)*0.4)) if events else 0
    for k,e in enumerate(events): e['sample']='INITIAL_40' if k<split else 'OOS_60'
    oos=[e for e in events if e['sample']=='OOS_60']
    def group(rows,key):
        vals=sorted(set(r[key] for r in rows)); return {v:stats([r for r in rows if r[key]==v]) for v in vals}
    out={
      'schema':'GMFQ_AUD_RBA_REACTION_REPLAY_V1','status':'PASS_DIAGNOSTIC_NOT_PROMOTED','created_at':'2026-10-07',
      'engine_baseline':{'commit':ENGINE,'rules_fingerprint':FP,'modified':False},
      'contract':{
        'checkpoint':'quarterly CPI first-release only','dual_mandate_rule':'HAWKISH iff CPI YoY rises and latest-known unemployment falls; DOVISH iff CPI YoY falls and unemployment rises; otherwise MIXED/WITHHELD',
        'cpi_continuity':'require consecutive quarterly CPI observations; skip across missing 2020-Q2 rather than using a six-month delta',
        'front_end_window':'5 common RBA/ECB market observations from first common date on/after release',
        'price_confirmation':'AUD equal-weight log basket vs other 7 G8 over same t0->t5 window',
        'outcome':'signed AUD G8 basket return t5->t25; positive means move in macro-expected direction',
        'oos':'first 40% chronology labelled INITIAL_40; remaining 60% forward OOS; no tuning'
      },
      'sources':{'labour':str(LAB.relative_to(ROOT)),'cpi':str(CPI.relative_to(ROOT)),'front_end':str(Y2.relative_to(ROOT)),'fx':ECB_URL},
      'coverage':{'eligible_events':len(events),'initial_n':split,'oos_n':len(oos),'skipped_n':len(skipped),'first_event':events[0]['release_date'] if events else None,'last_event':events[-1]['release_date'] if events else None},
      'full':{'all':stats(events),'by_macro':group(events,'macro_label'),'by_transmission':group(events,'transmission'),'front_end_aligned':stats([e for e in events if e['front_end_state']=='ALIGNED']),'front_end_divergent':stats([e for e in events if e['front_end_state']=='DIVERGENT'])},
      'oos':{'all':stats(oos),'by_macro':group(oos,'macro_label'),'by_transmission':group(oos,'transmission'),'front_end_aligned':stats([e for e in oos if e['front_end_state']=='ALIGNED']),'front_end_divergent':stats([e for e in oos if e['front_end_state']=='DIVERGENT'])},
      'events':events,'skipped':skipped,
      'assessment_policy':'diagnostic only; small samples must not be promoted as a gate; compare aligned vs divergent without threshold/window tuning',
      'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False
    }
    if len(events)<8: raise RuntimeError(f'too few coherent events: {len(events)}')
    OUT.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
