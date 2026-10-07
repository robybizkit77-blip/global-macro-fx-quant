#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, re, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT_2Y=ROOT/'history/pit_v1/CHF_SNB_GOVT_2Y_DAILY_2018_2026.csv'
OUT_CPI=ROOT/'history/pit_v1/CHF_CPI_HEADLINE_PIT_COMPATIBLE_2018_2026.csv'
EVID=ROOT/'validation/CHF_REACTION_READINESS_V1_2026-10-07.json'
UA={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}

def get(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=90) as r:
        return r.read(), (r.headers.get('Content-Type') or '')

def snb_json(cube):
    raw,ctype=get(f'https://data.snb.ch/api/cube/{cube}/data/json/en')
    if 'json' not in ctype.lower(): raise RuntimeError(f'{cube}: non-json {ctype}')
    return json.loads(raw.decode('utf-8'))

def header_label(ts):
    h=ts.get('header')
    if not isinstance(h,list) or len(h)!=1 or not isinstance(h[0],dict): return None
    return h[0].get('dimItem') if h[0].get('dim')=='Overview' else None

def materialize_2y():
    base='https://data.snb.ch/api/cube/rendoblid/data/csv/en'
    params={'dimSel':'D0(2J)','fromDate':'2018-01-01','toDate':'2026-10-07'}
    url=base+'?'+urllib.parse.urlencode(params)
    raw,_=get(url)
    rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig','replace')),delimiter=';'))
    if len(rows)<500: raise RuntimeError(f'2Y unexpectedly short rows={len(rows)}')
    header=rows[0]
    # identify date and 2Y columns mechanically
    date_idx=next((i for i,x in enumerate(header) if str(x).strip().lower() in {'date','datum'}),0)
    candidate_idxs=[i for i,x in enumerate(header) if re.search(r'2\s*(year|jahre|j|y)',str(x),re.I)]
    if not candidate_idxs:
        # SNB compact CSV often returns one value column after date when dimSel is exact.
        candidate_idxs=[i for i in range(len(header)) if i!=date_idx]
    if len(candidate_idxs)!=1: raise RuntimeError(f'2Y column ambiguity header={header} candidates={candidate_idxs}')
    vi=candidate_idxs[0]
    out=[]
    for r in rows[1:]:
        if len(r)<=max(date_idx,vi): continue
        d=r[date_idx].strip(); v=r[vi].strip().replace(',','.')
        if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',d): continue
        try: x=float(v)
        except: continue
        out.append((d,x))
    if len(out)<1500: raise RuntimeError(f'2Y valid obs too short n={len(out)}')
    OUT_2Y.parent.mkdir(parents=True,exist_ok=True)
    with OUT_2Y.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['date','chf_govt_2y_pct','source','cube','series_selector'])
        for d,x in out: w.writerow([d,f'{x:.6f}','Swiss National Bank','rendoblid','D0(2J)'])
    return {'n':len(out),'first':out[0][0],'last':out[-1][0],'header':header,'url':url}

def next_month_15(ym):
    y,m=map(int,ym.split('-'))
    if m==12: y+=1;m=1
    else:m+=1
    return f'{y:04d}-{m:02d}-15'

def materialize_cpi():
    obj=snb_json('plkopr')
    ts=obj.get('timeseries',[])
    label='Change from the corresponding month of the previous year in %'
    hits=[x for x in ts if isinstance(x,dict) and header_label(x)==label]
    if len(hits)!=1: raise RuntimeError(f'CPI series exact match count={len(hits)}')
    vals=[]
    for v in hits[0].get('values',[]):
        ym=v.get('date'); x=v.get('value')
        if not isinstance(ym,str) or not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',ym): continue
        if ym<'2018-01' or ym>'2026-09': continue
        if isinstance(x,bool) or not isinstance(x,(int,float)): continue
        vals.append((ym,float(x),next_month_15(ym)))
    vals.sort()
    if len(vals)<100: raise RuntimeError(f'CPI valid obs too short n={len(vals)}')
    OUT_CPI.parent.mkdir(parents=True,exist_ok=True)
    with OUT_CPI.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['reference_month','headline_cpi_yoy_pct','available_from_conservative','source','cube','series_label','pit_note'])
        for ym,x,av in vals:
            w.writerow([ym,f'{x:.6f}',av,'SNB data portal / SFSO','plkopr',label,'overall headline CPI; conservative availability on 15th next month; not an archived-release reconstruction'])
    return {'n':len(vals),'first':vals[0][0],'last':vals[-1][0],'availability_rule':'15th calendar day of following month (conservative, deliberately later than normal FSO release timing)','pit_quality':'PIT_COMPATIBLE_FOR_TIMING_BUT_NOT_ARCHIVED_RELEASE_VINTAGE'}

def main():
    r2=materialize_2y(); cpi=materialize_cpi()
    payload={
      'schema':'GMFQ_CHF_REACTION_READINESS_V1',
      'status':'PARTIAL_PASS_LABOUR_PIT_REQUIRED',
      'created_at':'2026-10-07',
      'swiss_2y':{'status':'PASS_SAME_BASIS_OFFICIAL','details':r2},
      'cpi':{'status':'PASS_TIMING_CONSERVATIVE_NOT_RELEASE_ARCHIVE','details':cpi,'methodology_note':'Headline CPI is used only with conservative post-month availability; this does not substitute for an archived release vintage if later evidence shows historical headline revisions.'},
      'labour':{'status':'WITHHELD_VINTAGE_REQUIRED','reason':'SECO seasonally adjusted unemployment is explicitly recomputed when each new observation arrives; current historical SA data would therefore contain vintage revisions. Archived monthly first-release values are required.'},
      'fx_transactions':'PASS_OFFICIAL_QUARTERLY_PIT_POLICY',
      'replay_allowed':False,
      'blocker':'SECO seasonally adjusted unemployment first-release/vintage history with publication timing',
      'frozen_engine':'ff52198a75cc67f7dae96fc2bbf65623f170791c',
      'rules_fingerprint':'3356baf0',
      'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False
    }
    EVID.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2))
if __name__=='__main__': main()
