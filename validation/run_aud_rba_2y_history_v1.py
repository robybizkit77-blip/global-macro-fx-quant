#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, re, urllib.request
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'history/pit_v1/AUD_RBA_GOVT_2Y_DAILY_2018_2026.csv'
EVID=ROOT/'validation/AUD_RBA_2Y_HISTORY_V1_2026-10-07.json'
URL='https://www.rba.gov.au/statistics/tables/csv/f2-data.csv'
SERIES_ID='FCMYGBAG2D'
DESC='Australian Government 2 year bond'
ANCHORS={'2019-12-02':0.711,'2020-03-02':0.468,'2022-05-02':2.560,'2024-01-02':3.724,'2025-09-01':3.342}
UA={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}

def fetch():
    req=urllib.request.Request(URL,headers=UA)
    with urllib.request.urlopen(req,timeout=60) as r:return r.read().decode('utf-8-sig',errors='replace')

def parse_date(s):
    s=s.strip()
    for fmt in ('%d-%b-%Y','%d/%m/%Y','%Y-%m-%d','%d %b %Y'):
        try:return datetime.strptime(s,fmt).date().isoformat()
        except:pass
    return None

def main():
    rows=list(csv.reader(io.StringIO(fetch())))
    col=None
    for ri,row in enumerate(rows[:25]):
        for ci,cell in enumerate(row):
            if re.sub(r'\s+',' ',cell).strip()==DESC:
                col=ci; break
        if col is not None:break
    if col is None:raise RuntimeError('exact AUD 2Y descriptor not found')
    sid=None
    for row in rows[:25]:
        if row and row[0].strip().lower() in ('series id','series id.') and col<len(row):sid=row[col].strip()
    if sid!=SERIES_ID:raise RuntimeError(f'series id changed: {sid!r}')
    obs=[]
    for row in rows:
        if not row or col>=len(row):continue
        d=parse_date(row[0])
        if not d or not ('2018-01-01'<=d<='2026-12-31'):continue
        s=row[col].strip()
        if s in ('','-','na','n.a.'):continue
        try:v=float(s)
        except:continue
        obs.append({'date':d,'aud_govt_2y_pct':v})
    obs.sort(key=lambda x:x['date'])
    if len(obs)<2100:raise RuntimeError(f'insufficient observations {len(obs)}')
    by={r['date']:r['aud_govt_2y_pct'] for r in obs}
    for d,v in ANCHORS.items():
        assert d in by,(d,'missing')
        assert abs(by[d]-v)<1e-12,(d,by[d],v)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['date','aud_govt_2y_pct']); w.writeheader(); w.writerows(obs)
    payload={
      'schema':'GMFQ_AUD_RBA_2Y_HISTORY_V1','status':'PASS','created_at':'2026-10-07',
      'source':'Reserve Bank of Australia Table F2 – Capital Market Yields – Government Bonds – Daily',
      'source_url':URL,'descriptor':DESC,'series_id':SERIES_ID,
      'coverage':{'n':len(obs),'first':obs[0]['date'],'last':obs[-1]['date']},
      'anchors':{d:by[d] for d in ANCHORS},
      'same_basis_policy':'single RBA F2 daily 2-year Australian Government bond series; no vendor splice',
      'use_policy':'diagnostic front-end transmission input; never a standalone gate',
      'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False
    }
    EVID.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2))
if __name__=='__main__':main()
