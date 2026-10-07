#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, re, urllib.request
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EVID=ROOT/'validation/AUD_RBA_2Y_PROBE_V1_2026-10-07.json'
URL='https://www.rba.gov.au/statistics/tables/csv/f2-data.csv'
UA={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}

def fetch():
    req=urllib.request.Request(URL,headers=UA)
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read().decode('utf-8-sig',errors='replace')

def parse_date(s):
    s=s.strip()
    for fmt in ('%d-%b-%Y','%d/%m/%Y','%Y-%m-%d','%d %b %Y'):
        try:return datetime.strptime(s,fmt).date().isoformat()
        except:pass
    return None

def main():
    text=fetch(); rows=list(csv.reader(io.StringIO(text)))
    target=None; descriptor=None
    for ri,row in enumerate(rows[:25]):
        for ci,cell in enumerate(row):
            x=re.sub(r'\s+',' ',cell).strip().lower()
            if 'australian government' in x and '2 year' in x and 'bond' in x:
                target=ci; descriptor={'row':ri,'col':ci,'text':cell}; break
        if target is not None:break
    if target is None:
        raise RuntimeError('RBA F2 2-year Australian Government bond column not found')
    series_id=None
    for row in rows[:25]:
        if row and row[0].strip().lower() in ('series id','series id.') and target < len(row):
            series_id=row[target].strip()
    obs=[]
    for row in rows:
        if not row or target>=len(row):continue
        d=parse_date(row[0])
        if not d:continue
        v=row[target].strip()
        if v in ('','-','na','n.a.'):continue
        try:f=float(v)
        except:continue
        if '2018-01-01'<=d<='2026-12-31':obs.append((d,f))
    if len(obs)<1500:raise RuntimeError(f'insufficient daily observations: {len(obs)}')
    dates={d:v for d,v in obs}
    wanted=['2019-12-02','2020-03-02','2022-05-02','2024-01-02','2025-09-01']
    anchors={d:dates.get(d) for d in wanted}
    payload={
      'schema':'GMFQ_AUD_RBA_2Y_PROBE_V1','status':'PASS_PROBE_NOT_CERTIFIED','created_at':'2026-10-07',
      'source':'Reserve Bank of Australia Table F2 – Capital Market Yields – Government Bonds – Daily',
      'source_url':URL,'descriptor':descriptor,'series_id':series_id,
      'coverage':{'n':len(obs),'first':obs[0][0],'last':obs[-1][0]},
      'candidate_anchors':anchors,
      'value_range':{'min':min(v for _,v in obs),'max':max(v for _,v in obs)},
      'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False
    }
    EVID.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2))
if __name__=='__main__':main()
