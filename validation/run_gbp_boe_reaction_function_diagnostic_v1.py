import csv,json,math
from datetime import datetime
from pathlib import Path

FX='history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
AWE='history/pit_v1/GBP_AWE_K54L_CERTIFIED_VINTAGES_2018_2026.csv'
SERV='history/pit_v1/GBP_CPI_SERVICES_D7NN_CERTIFIED_VINTAGES_2018_2026.csv'
OIS='history/pit_v1/GBP_BOE_OIS_SPOT_2Y_DAILY_2018_2026.csv'
OUT=Path('validation/GBP_BOE_REACTION_FUNCTION_DIAGNOSTIC_V1_2026-10-06.json')
H=[5,20,60]; PEERS=['USD','EUR','JPY','CHF','CAD','AUD','NZD']

def iso(s): return datetime.strptime(s,'%d %B %Y').strftime('%Y-%m-%d')
def load(path):
    with open(path,encoding='utf-8') as f:return list(csv.DictReader(f))

def first_new_ref(rows,date_field,value_field):
    # Scheduled macro only: first vintage for each new reference month. Ignore later same-month corrections.
    out=[]; seen=set()
    for r in sorted(rows,key=lambda x:iso(x[date_field])):
        ref=r['reference_month']
        if ref in seen: continue
        seen.add(ref)
        try:v=float(r[value_field])
        except:continue
        out.append((iso(r[date_field]),ref,v))
    return out

def deltas(points):
    out=[]
    for a,b in zip(points,points[1:]):
        d=b[2]-a[2]
        if d!=0:out.append((b[0],b[1],d))
    return out

def sign(x):return 1 if x>0 else -1 if x<0 else 0

def fxret(rows,i,h):
    if i+h>=len(rows):return None
    a,b=rows[i],rows[i+h]; vals=[]
    for p in PEERS:
        direct='GBP'+p; inv=p+'GBP'
        try:
            if direct in a and a[direct] and b[direct]: r=math.log(float(b[direct])/float(a[direct]))
            elif inv in a and a[inv] and b[inv]: r=-math.log(float(b[inv])/float(a[inv]))
            else:continue
            vals.append(r)
        except:continue
    return sum(vals)/len(vals) if vals else None

def first_after(rows,d):
    for i,r in enumerate(rows):
        if r['date']>d:return i
    return None

def regime_events(ds,fx,source):
    ev=[]; prev=0
    for d,ref,x in ds:
        s=sign(x)
        if not s or s==prev:continue
        prev=s;i=first_after(fx,d)
        if i is None:continue
        e={'checkpoint':d,'reference_month':ref,'signal':s,'source':source,'entry_date':fx[i]['date']}
        for h in H:
            r=fxret(fx,i,h);e[f'signed_{h}d']=None if r is None else s*r
        ev.append(e)
    return ev

def stats(ev):
    z={}
    for h in H:
        xs=[e[f'signed_{h}d'] for e in ev if e.get(f'signed_{h}d') is not None]
        if not xs:z[f'{h}d']={'n':0,'hit_rate':None,'mean':None,'median':None};continue
        ys=sorted(xs);n=len(xs);med=ys[n//2] if n%2 else (ys[n//2-1]+ys[n//2])/2
        z[f'{h}d']={'n':n,'hit_rate':sum(x>0 for x in xs)/n,'mean':sum(xs)/n,'median':med}
    return z

def confirmed(wd,ois,fx):
    bydate={r['date']:float(r['gbp_ois_spot_2y_pct']) for r in ois}; dates=sorted(bydate)
    yes=[];no=[]
    for d,ref,chg in wd:
        s=sign(chg); idx=next((i for i,x in enumerate(dates) if x>=d),None)
        if idx is None or idx+5>=len(dates):continue
        d0,d1=dates[idx],dates[idx+5]; dr=bydate[d1]-bydate[d0]; rs=sign(dr)
        base={'wage_checkpoint':d,'reference_month':ref,'signal':s,'rate_start_date':d0,'confirmation_date':d1,'gbp_ois_2y_start_pct':bydate[d0],'gbp_ois_2y_end_pct':bydate[d1],'gbp_ois_2y_change_pp':dr,'rate_signal':rs}
        if rs!=s:no.append(base);continue
        i=first_after(fx,d1)
        if i is None:continue
        e=dict(base);e['entry_date']=fx[i]['date']
        for h in H:
            r=fxret(fx,i,h);e[f'signed_{h}d']=None if r is None else s*r
        yes.append(e)
    return yes,no

def main():
    fx=load(FX); awe=load(AWE); serv=load(SERV); ois=load(OIS)
    wp=first_new_ref(awe,'available_date','yoy_pct'); sp=first_new_ref(serv,'available_date','annual_rate_pct')
    wd=deltas(wp); sd=deltas(sp)
    wev=regime_events(wd,fx,'AWE_K54L_YOY_CHANGE'); sev=regime_events(sd,fx,'CPI_SERVICES_D7NN_CHANGE')
    # Joint: at each wage event, latest known services delta must agree.
    joint=[]
    for d,ref,w in wd:
        known=[x for x in sd if x[0]<=d]
        if known and sign(w)==sign(known[-1][2]):joint.append((d,ref,w))
    jev=regime_events(joint,fx,'AWE_AND_SERVICES_CONCORDANT')
    cev,rej=confirmed(wd,ois,fx)
    audit={'schema':'GMFQ_GBP_BOE_REACTION_FUNCTION_DIAGNOSTIC_V1','status':'PASS','created_at':'2026-10-06','scope':'Audit-only BoE-specific reaction-function diagnostic; no production rule or causal proof.','guardrails':['first vintage per new reference month only','same-month correction vintages do not create signals','K54L definition frozen before results','D7NN definition frozen before results','5-market-day 2Y OIS confirmation frozen before results','FX entry strictly after confirmation','no threshold tuning','engine untouched','live_data untouched'],'direct_labour_benchmark':{'status':'PIT_CERTIFIED_REPLAY_PENDING','note':'GBP labour PIT is certified from ONS A01, but no direct-labour historical replay is materialized on this branch; no benchmark is fabricated.'},'wages':{'actionable_months':len(wp),'nonzero_changes':len(wd),'regime_events':wev,'stats':stats(wev)},'services':{'actionable_months':len(sp),'nonzero_changes':len(sd),'regime_events':sev,'stats':stats(sev)},'joint_wages_services':{'events':jev,'stats':stats(jev)},'wages_plus_2y_ois_confirmation':{'confirmation_window_market_days':5,'confirmed_count':len(cev),'rejected_count':len(rej),'confirmed_events':cev,'rejected_diagnostics':rej,'stats':stats(cev)},'changes_engine_rules':False,'changes_live_data':False,'threshold_tuning':False}
    OUT.write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(audit,indent=2))
if __name__=='__main__':main()
