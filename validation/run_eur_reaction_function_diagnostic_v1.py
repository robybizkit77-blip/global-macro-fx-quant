import csv, json, math, os
from datetime import datetime

FX='history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
SERV='history/pit_v1/EUR_HICP_SERVICES_FIRST_PUBLISHED_2024_2026.csv'
WAGES='history/pit_v1/EUR_NEGOTIATED_WAGES_CERTIFIED_VINTAGES_SEED.csv'
DIRECT='validation/PIT_MACRO_SUBBLOCK_ATTRIBUTION_V1_2026-10-06.json'
OUT='validation/EUR_REACTION_FUNCTION_DIAGNOSTIC_V1_2026-10-06.json'
H=[5,20,60]
G8=['USD','GBP','JPY','CHF','CAD','AUD','NZD']


def load_fx():
    with open(FX,encoding='utf-8') as f: rows=list(csv.DictReader(f))
    rows=[r for r in rows if r.get('date')]
    return rows

def eur_basket_return(rows,i,h):
    if i+h>=len(rows): return None
    r0,r1=rows[i],rows[i+h]
    vals=[]
    for c in G8:
        col=f'EUR{c}'
        try:
            p0=float(r0[col]); p1=float(r1[col])
        except: continue
        if p0>0 and p1>0: vals.append(math.log(p1/p0))
    return sum(vals)/len(vals) if vals else None

def first_idx_after(rows, d):
    for i,r in enumerate(rows):
        if r['date']>d: return i
    return None

def stats(events):
    out={}
    for h in H:
        xs=[e[f'signed_{h}d'] for e in events if e.get(f'signed_{h}d') is not None]
        if xs:
            ys=sorted(xs); n=len(xs)
            med=ys[n//2] if n%2 else (ys[n//2-1]+ys[n//2])/2
            out[f'{h}d']={'n':n,'hit_rate':sum(x>0 for x in xs)/n,'mean':sum(xs)/n,'median':med}
        else: out[f'{h}d']={'n':0,'hit_rate':None,'mean':None,'median':None}
    return out

def regime_events(points, fx):
    ev=[]; prev=0
    for d,val,src in points:
        sig=1 if val>0 else -1 if val<0 else 0
        if sig==0 or sig==prev: continue
        prev=sig
        i=first_idx_after(fx,d)
        if i is None: continue
        e={'checkpoint':d,'signal':sig,'source':src,'entry_date':fx[i]['date']}
        for h in H:
            r=eur_basket_return(fx,i,h)
            e[f'signed_{h}d']=None if r is None else sig*r
        ev.append(e)
    return ev

def main():
    fx=load_fx()
    # Services mediator: sign of month-over-month change in first-published annual services inflation.
    s=[]
    with open(SERV,encoding='utf-8') as f: sr=list(csv.DictReader(f))
    prev=None
    for r in sr:
        v=float(r['annual_rate_pct'])
        if prev is not None:
            # conservative availability proxy: use first day of following month; diagnostic only
            y,m=map(int,r['reference_month'].split('-'))
            if m==12: d=f'{y+1}-01-01'
            else: d=f'{y}-{m+1:02d}-01'
            s.append((d,v-prev,'HICP_SERVICES_FIRST_PUBLISHED_CHANGE'))
        prev=v
    sev=regime_events(s,fx)

    # Wages mediator: sign of change in annual negotiated-wage growth at certified availability date.
    w=[]; prev=None
    with open(WAGES,encoding='utf-8') as f: wr=list(csv.DictReader(f))
    for r in wr:
        v=float(r['annual_growth_pct'])
        if prev is not None:
            w.append((r['certified_available_date'],v-prev,'NEGOTIATED_WAGES_CERTIFIED_CHANGE'))
        prev=v
    wev=regime_events(w,fx)

    # Joint mediator: at each certified wage update, require latest services-change sign to agree.
    joint=[]
    for d,wdelta,_ in w:
        candidates=[p for p in s if p[0] <= d]
        if not candidates: continue
        sdelta=candidates[-1][1]
        ws=1 if wdelta>0 else -1 if wdelta<0 else 0
        ss=1 if sdelta>0 else -1 if sdelta<0 else 0
        if ws!=0 and ws==ss: joint.append((d,ws,'WAGES_AND_SERVICES_CONCORDANT'))
    jev=regime_events(joint,fx)

    with open(DIRECT,encoding='utf-8') as f: direct=json.load(f)
    direct_stats=direct['currencies']['EUR']['Labour']['walkforward']['pooled_oos']

    audit={
      'schema':'GMFQ_EUR_REACTION_FUNCTION_DIAGNOSTIC_V1',
      'status':'PASS',
      'created_at':'2026-10-06',
      'scope':'Diagnostic only. Compares frozen direct EUR Labour benchmark with policy-relevant mediator signals from PIT services inflation and certified negotiated wages. Not a production rule and not a causal proof of Labour->mediator transmission.',
      'guardrails':['no threshold tuning','no parameter optimization','no revised-history substitution','engine untouched','live_data untouched'],
      'direct_labour_frozen_oos':direct_stats,
      'services_mediator':{'definition':'sign of change in first-published annual HICP services rate; new-sign regime entries only','events':sev,'stats':stats(sev)},
      'wages_mediator':{'definition':'sign of change in certified first-known negotiated-wage annual growth; new-sign regime entries only','events':wev,'stats':stats(wev),'small_sample_warning':True},
      'joint_wages_services':{'definition':'wage and latest services changes must have same sign at certified wage availability date','events':jev,'stats':stats(jev),'small_sample_warning':True},
      'interpretation_policy':'Treat mediator results as diagnostic evidence only. They do not yet validate the full Labour->wages/services->ECB->rates->EUR causal chain because explicit PIT ECB reaction/front-end repricing is not included.',
      'changes_engine_rules':False,'changes_live_data':False,'threshold_tuning':False
    }
    os.makedirs('validation',exist_ok=True)
    with open(OUT,'w',encoding='utf-8') as f: json.dump(audit,f,indent=2)
    print(json.dumps(audit,indent=2))

if __name__=='__main__': main()
