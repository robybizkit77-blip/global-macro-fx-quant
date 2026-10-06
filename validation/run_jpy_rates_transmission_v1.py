#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, math, statistics, urllib.request
from bisect import bisect_right
from pathlib import Path

MOF_URL='https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv'
OUT_CSV=Path('history/pit_v1/JPY_MOF_JGB_2Y_DAILY_2018_2023.csv')
OUT_JSON=Path('validation/JPY_RATES_TRANSMISSION_V1_2026-10-07.json')
REPLAY=Path('validation/JPY_REACTION_FUNCTION_REPLAY_V1_2026-10-06.json')
USD=Path('history/pit_v1/USD_TREASURY_PAR_2Y_DAILY_2016_2026.csv')
ENGINE='ff52198a75cc67f7dae96fc2bbf65623f170791c'
FP='3356baf0'

def fetch_mof():
    req=urllib.request.Request(MOF_URL,headers={'User-Agent':'Mozilla/5.0'})
    raw=urllib.request.urlopen(req,timeout=60).read()
    text=None
    for enc in ('utf-8-sig','cp932','shift_jis'):
        try: text=raw.decode(enc); break
        except UnicodeDecodeError: pass
    if text is None: raise RuntimeError('cannot decode MOF csv')
    rows=list(csv.reader(io.StringIO(text)))
    # locate header row and semantic columns robustly
    header_i=None
    for i,r in enumerate(rows[:20]):
        joined='|'.join(x.strip().lower() for x in r)
        if ('date' in joined or '年月日' in joined) and ('2' in joined): header_i=i; break
    if header_i is None: raise RuntimeError('MOF header not found')
    hdr=[x.strip() for x in rows[header_i]]
    def norm(s): return s.lower().replace(' ','').replace('-','').replace('_','').replace('year','y').replace('years','y')
    date_candidates=[i for i,h in enumerate(hdr) if norm(h) in ('date','年月日') or 'date' in norm(h)]
    y2_candidates=[i for i,h in enumerate(hdr) if norm(h) in ('2y','2年','2') or ('2' in norm(h) and ('y' in norm(h) or '年' in norm(h)))]
    if len(date_candidates)!=1 or len(y2_candidates)!=1: raise RuntimeError(f'ambiguous columns header={hdr}')
    di,yi=date_candidates[0],y2_candidates[0]
    out=[]
    for r in rows[header_i+1:]:
        if max(di,yi)>=len(r): continue
        d=r[di].strip(); v=r[yi].strip()
        if not d or not v or v in ('-','NA','N/A'): continue
        d=d.replace('/','-')
        if len(d)>=10: d=d[:10]
        try: fv=float(v)
        except: continue
        if '2018-01-01'<=d<='2023-12-31': out.append((d,fv))
    out=sorted(dict(out).items())
    if len(out)<1000: raise RuntimeError(f'insufficient MOF rows: {len(out)}')
    OUT_CSV.parent.mkdir(parents=True,exist_ok=True)
    with OUT_CSV.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['date','jpy_mof_jgb_2y_pct','source_url','source_basis'])
        for d,v in out: w.writerow([d,v,MOF_URL,'MOF constant-maturity JGB secondary-market close 3pm, published next business day'])
    return out,hdr

def load_usd():
    out=[]
    with USD.open(newline='',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            d=r['date'];
            if '2018-01-01'<=d<='2023-12-31': out.append((d,float(r['usd_treasury_par_2y_pct'])))
    return out

def previous_value(series,date):
    dates=[d for d,_ in series]; i=bisect_right(dates,date)-1
    return (dates[i],series[i][1],i) if i>=0 else (None,None,None)

def change_n(series,date,n):
    d,v,i=previous_value(series,date)
    if i is None or i<n: return None
    return v-series[i-n][1]

def stats(vals):
    vals=[x for x in vals if x is not None]
    if not vals:return {'n':0,'hit_rate':None,'mean':None,'median':None}
    return {'n':len(vals),'hit_rate':sum(x>0 for x in vals)/len(vals),'mean':sum(vals)/len(vals),'median':statistics.median(vals)}

def main():
    jpy,hdr=fetch_mof(); usd=load_usd(); replay=json.loads(REPLAY.read_text())
    assert replay['engine']['frozen_commit']==ENGINE and replay['engine']['rules_fingerprint']==FP
    samples=replay['directional_samples']
    rows=[]
    for s in samples:
        cp=s['checkpoint']; pol=int(s['jpy_polarity'])
        jd,jv,_=previous_value(jpy,cp); ud,uv,_=previous_value(usd,cp)
        if jv is None or uv is None: continue
        spread=jv-uv
        r={'checkpoint':cp,'polarity':pol,'jpy2y_date':jd,'jpy2y':jv,'usd2y_date':ud,'usd2y':uv,'jpy_minus_usd_2y':spread,'signed_20d':s.get('signed_20d')}
        for n in (5,20):
            dj=change_n(jpy,cp,n); du=change_n(usd,cp,n)
            ds=None if dj is None or du is None else dj-du
            r[f'jpy2y_change_{n}obs']=dj; r[f'diff_change_{n}obs']=ds
            if dj is not None: r[f'jpy2y_state_{n}obs']='CONFIRM' if pol*dj>0 else ('DIVERGE' if pol*dj<0 else 'FLAT')
            if ds is not None: r[f'diff_state_{n}obs']='CONFIRM' if pol*ds>0 else ('DIVERGE' if pol*ds<0 else 'FLAT')
        rows.append(r)
    analysis={}
    for key in ('jpy2y_state_5obs','jpy2y_state_20obs','diff_state_5obs','diff_state_20obs'):
        analysis[key]={}
        for st in ('CONFIRM','DIVERGE','FLAT'):
            vals=[r['signed_20d'] for r in rows if r.get(key)==st and r.get('signed_20d') is not None]
            analysis[key][st]=stats(vals)
    payload={
      'schema':'GMFQ_JPY_RATES_TRANSMISSION_V1','status':'PASS_DIAGNOSTIC_NOT_PROMOTED','created_at':'2026-10-07',
      'engine_frozen_commit':ENGINE,'rules_fingerprint':FP,
      'source':{'jpy2y':MOF_URL,'authority':'Japan Ministry of Finance','definition':'constant-maturity semiannual compound JGB yield from secondary-market closing prices; released next business day','usd2y':str(USD)},
      'coverage':{'jpy2y_rows':len(jpy),'first':jpy[0][0],'last':jpy[-1][0],'directional_macro_events':len(samples),'paired_events':len(rows)},
      'method':{'purpose':'transmission attribution only, not a new trading rule','rate_windows_observations':[5,20],'confirmation':'sign(macro JPY polarity) equals sign(change in JPY 2Y or JPY-minus-USD 2Y differential)','threshold_tuning':False,'event_filter_tuning':False},
      'analysis_20d_fx_outcome':analysis,'paired_events':rows,
      'guardrails':['official rates only','no revised macro substitution','no threshold tuning','no engine changes','no live data changes','no OOS baseline changes'],
      'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False,'mof_header_detected':hdr
    }
    OUT_JSON.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':payload['status'],'coverage':payload['coverage'],'analysis':analysis},indent=2,ensure_ascii=False))

if __name__=='__main__': main()
