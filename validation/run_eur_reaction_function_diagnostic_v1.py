import csv, json, math, os

FX='history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
SERV='history/pit_v1/EUR_HICP_SERVICES_FIRST_PUBLISHED_2024_2026.csv'
WAGES='history/pit_v1/EUR_NEGOTIATED_WAGES_CERTIFIED_VINTAGES_SEED.csv'
RATES='history/pit_v1/EUR_RATES_2Y_10Y_ECB_SAME_BASIS_2016_2026.csv'
DIRECT='validation/PIT_MACRO_SUBBLOCK_ATTRIBUTION_V1_2026-10-06.json'
OUT='validation/EUR_REACTION_FUNCTION_DIAGNOSTIC_V1_2026-10-06.json'
H=[5,20,60]
G8=['USD','GBP','JPY','CHF','CAD','AUD','NZD']
RATE_CONFIRM_WINDOW=5

def load_fx():
    with open(FX,encoding='utf-8') as f: rows=list(csv.DictReader(f))
    return [r for r in rows if r.get('date')]

def load_rates():
    with open(RATES,encoding='utf-8') as f: rows=list(csv.DictReader(f))
    return [r for r in rows if r.get('date') and r.get('eur_2y_pct') not in (None,'')]

def eur_basket_return(rows,i,h):
    if i+h>=len(rows): return None
    r0,r1=rows[i],rows[i+h]; vals=[]
    for c in G8:
        col=f'EUR{c}'
        try: p0=float(r0[col]); p1=float(r1[col])
        except: continue
        if p0>0 and p1>0: vals.append(math.log(p1/p0))
    return sum(vals)/len(vals) if vals else None

def first_idx_after(rows,d):
    for i,r in enumerate(rows):
        if r['date']>d: return i
    return None

def first_idx_on_or_after(rows,d):
    for i,r in enumerate(rows):
        if r['date']>=d: return i
    return None

def stats(events):
    out={}
    for h in H:
        xs=[e[f'signed_{h}d'] for e in events if e.get(f'signed_{h}d') is not None]
        if xs:
            ys=sorted(xs); n=len(xs); med=ys[n//2] if n%2 else (ys[n//2-1]+ys[n//2])/2
            out[f'{h}d']={'n':n,'hit_rate':sum(x>0 for x in xs)/n,'mean':sum(xs)/n,'median':med}
        else: out[f'{h}d']={'n':0,'hit_rate':None,'mean':None,'median':None}
    return out

def regime_events(points,fx):
    ev=[]; prev=0
    for d,val,src in points:
        sig=1 if val>0 else -1 if val<0 else 0
        if sig==0 or sig==prev: continue
        prev=sig; i=first_idx_after(fx,d)
        if i is None: continue
        e={'checkpoint':d,'signal':sig,'source':src,'entry_date':fx[i]['date']}
        for h in H:
            r=eur_basket_return(fx,i,h); e[f'signed_{h}d']=None if r is None else sig*r
        ev.append(e)
    return ev

def attach_returns_from_confirmation(events,fx):
    out=[]
    for base in events:
        d=base['confirmation_date']; sig=base['signal']; i=first_idx_after(fx,d)
        if i is None: continue
        e=dict(base); e['entry_date']=fx[i]['date']
        for h in H:
            r=eur_basket_return(fx,i,h); e[f'signed_{h}d']=None if r is None else sig*r
        out.append(e)
    return out

def main():
    fx=load_fx(); rates=load_rates()
    s=[]
    with open(SERV,encoding='utf-8') as f: sr=list(csv.DictReader(f))
    prev=None
    for r in sr:
        v=float(r['annual_rate_pct'])
        if prev is not None:
            y,m=map(int,r['reference_month'].split('-')); d=f'{y+1}-01-01' if m==12 else f'{y}-{m+1:02d}-01'
            s.append((d,v-prev,'HICP_SERVICES_FIRST_PUBLISHED_CHANGE'))
        prev=v
    sev=regime_events(s,fx)

    # At a single availability date multiple historical quarters can become certified.
    # Only the latest reference quarter is actionable at that timestamp; intermediate
    # backfilled quarters must not create fictitious same-day trades.
    with open(WAGES,encoding='utf-8') as f: wr=list(csv.DictReader(f))
    by_date={}
    for r in wr:
        d=r['certified_available_date']
        if not d: continue
        if d not in by_date or r['reference_quarter']>by_date[d]['reference_quarter']:
            by_date[d]=r
    actionable=[by_date[d] for d in sorted(by_date)]
    w=[]; prev=None
    for r in actionable:
        v=float(r['annual_growth_pct'])
        if prev is not None: w.append((r['certified_available_date'],v-prev,'NEGOTIATED_WAGES_CERTIFIED_CHANGE'))
        prev=v
    wev=regime_events(w,fx)

    joint=[]
    for d,wdelta,_ in w:
        candidates=[p for p in s if p[0]<=d]
        if not candidates: continue
        sdelta=candidates[-1][1]; ws=1 if wdelta>0 else -1 if wdelta<0 else 0; ss=1 if sdelta>0 else -1 if sdelta<0 else 0
        if ws!=0 and ws==ss: joint.append((d,ws,'WAGES_AND_SERVICES_CONCORDANT'))
    jev=regime_events(joint,fx)

    # Reaction-function diagnostic: after each wage-release timestamp, observe the
    # same-basis EUR 2Y move over a fixed 5-market-day window. Confirmation is valid
    # only when the 2Y move has the same sign as the wage impulse. EUR returns are
    # measured strictly after the confirmation window, preventing look-ahead.
    rate_confirmed=[]; rate_rejected=[]
    for d,wdelta,_ in w:
        ws=1 if wdelta>0 else -1 if wdelta<0 else 0
        if ws==0: continue
        i=first_idx_on_or_after(rates,d)
        if i is None or i+RATE_CONFIRM_WINDOW>=len(rates): continue
        r0=float(rates[i]['eur_2y_pct']); r1=float(rates[i+RATE_CONFIRM_WINDOW]['eur_2y_pct'])
        dr=r1-r0; rs=1 if dr>0 else -1 if dr<0 else 0
        rec={
          'wage_checkpoint':d,'signal':ws,'rate_start_date':rates[i]['date'],
          'confirmation_date':rates[i+RATE_CONFIRM_WINDOW]['date'],
          'eur_2y_start_pct':r0,'eur_2y_end_pct':r1,'eur_2y_change_pp':dr,
          'rate_signal':rs,'source':'NEGOTIATED_WAGES_PLUS_EUR2Y_5D_CONFIRMATION'
        }
        if rs==ws: rate_confirmed.append(rec)
        else: rate_rejected.append(rec)
    rcev=attach_returns_from_confirmation(rate_confirmed,fx)

    with open(DIRECT,encoding='utf-8') as f: direct=json.load(f)
    direct_stats=direct['currencies']['EUR']['Labour']['walkforward']['pooled_oos']
    audit={
      'schema':'GMFQ_EUR_REACTION_FUNCTION_DIAGNOSTIC_V1','status':'PASS','created_at':'2026-10-06',
      'scope':'Diagnostic only. Compares frozen direct EUR Labour benchmark with policy-relevant mediator signals from PIT services inflation, certified negotiated wages, and same-basis EUR 2Y confirmation. Not a production rule and not a causal proof.',
      'guardrails':['no threshold tuning','no parameter optimization','no revised-history substitution','same-date wage backfill collapsed to latest reference quarter','fixed 5-market-day 2Y confirmation window predeclared before evaluation','FX entry strictly after 2Y confirmation window','engine untouched','live_data untouched'],
      'direct_labour_frozen_oos':direct_stats,
      'services_mediator':{'definition':'sign of change in first-published annual HICP services rate; new-sign regime entries only','events':sev,'stats':stats(sev)},
      'wages_mediator':{'definition':'sign of change in latest actionable certified negotiated-wage annual growth at each unique availability date; new-sign regime entries only','events':wev,'stats':stats(wev),'small_sample_warning':True},
      'joint_wages_services':{'definition':'wage and latest services changes must have same sign at unique certified wage availability date','events':jev,'stats':stats(jev),'small_sample_warning':True},
      'wages_plus_2y_confirmation':{
        'definition':'wage impulse must be confirmed by same-sign change in EUR 2Y over fixed 5 market days after certified wage availability; FX measured only after confirmation',
        'confirmation_window_market_days':RATE_CONFIRM_WINDOW,
        'confirmed_count':len(rate_confirmed),'rejected_count':len(rate_rejected),
        'confirmed_events':rcev,'rejected_diagnostics':rate_rejected,'stats':stats(rcev),'small_sample_warning':True
      },
      'interpretation_policy':'Treat all mediator and 2Y-confirmation results as diagnostic evidence only. No thresholds or model rules are changed from these results.',
      'changes_engine_rules':False,'changes_live_data':False,'threshold_tuning':False}
    with open(OUT,'w',encoding='utf-8') as f: json.dump(audit,f,indent=2)
    print(json.dumps(audit,indent=2))
if __name__=='__main__': main()
