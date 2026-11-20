#!/usr/bin/env python3
"""Offline official CSV contract checks for daily AUD F2 research history."""
import csv
import datetime as dt
import importlib.util
import io
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('build_aud_f2_daily',HERE/'build_fxv2_aud_f2_daily_history_v1.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
TODAY=dt.date(2026,11,8)
PUB='06-Nov-2026'
def fixture(n=40, pub=PUB, duplicate=False, wrong_source=False, invalid=False):
    row=[['']*4 for _ in range(11)]
    row[1][1]='Australian Government 2 year bond'
    row[1][2]='Australian Government 10 year bond'
    row[3][1]=row[3][2]='Daily'
    row[8][1]=row[8][2]='RBA' if not wrong_source else 'UNKNOWN'
    row[9][1]=row[9][2]=pub
    row[10]=['Series ID',m.SERIES_2Y,m.SERIES_10Y,'DUMMY']
    d=dt.date(2026,11,4)
    days=[]
    while len(days)<n:
        if d.weekday()<5: days.append(d)
        d-=dt.timedelta(days=1)
    days.reverse()
    for i,day in enumerate(days):
        two=round(4.5+i*.01,3)
        ten=round(4.8+i*.01,3)
        if day==dt.date(2026,11,4):two,ten=4.826,5.082
        if invalid and i==2:two=100
        row.append([day.strftime('%d-%b-%Y'),str(two),str(ten),''])
    if duplicate:row.append(list(row[-1]))
    f=io.StringIO()
    csv.writer(f).writerows(row)
    return f.getvalue().encode('utf-8')+b' '*260

class AUDDailyResearchContract(unittest.TestCase):
 def source(self):
    return m.parse_daily(fixture(),TODAY)
 def snapshot(self,c):
    last=c['observations'][-1]
    return {'as_of':c['last_observation_date'],'publication_date':c['publication_date'],
            '2Y':last['2Y'],'10Y':last['10Y'],'source_sha256':c['source_response_sha256']}
 def test_preserve_actual_daily_rows(self):
    c=self.source()
    self.assertEqual(c['status'],'OFFICIAL_F2_DAILY_RESEARCH_ONLY_NOT_POINT_IN_TIME')
    self.assertEqual(len(c['observations']),40)
    self.assertEqual(c['last_observation_date'],'2026-11-04')
    self.assertEqual(c['publication_date'],'2026-11-06')
    self.assertEqual(c['observations'][-1]['2Y'],4.826)
    self.assertEqual(c['observations'][-1]['10Y'],5.082)
    self.assertEqual(c['observations'][-2]['date'],'2026-11-03')
    for k in ('eligible_for_core','eligible_for_fx_pair_engine',
              'eligible_for_backtests','eligible_for_automatic_promotion'):
        self.assertFalse(c[k])
    self.assertTrue(c['no_interpolation'])
 def test_fails_closed_on_bad_source(self):
    with self.assertRaises(ValueError):m.parse_daily(fixture(wrong_source=True),TODAY)
 def test_fails_closed_on_duplicates(self):
    with self.assertRaises(ValueError):m.parse_daily(fixture(duplicate=True),TODAY)
 def test_fails_closed_on_unsafe_rates(self):
    with self.assertRaises(ValueError):m.parse_daily(fixture(invalid=True),TODAY)
 def test_fails_closed_on_future_publication(self):
    with self.assertRaises(ValueError):m.parse_daily(fixture(pub='10-Nov-2026'),TODAY)
 def test_fails_closed_on_too_few_rows(self):
    with self.assertRaises(ValueError):m.parse_daily(fixture(n=10),TODAY)
 def test_canonical_and_research_anchor_reconcile(self):
    c=self.source()
    snapshot=self.snapshot(c)
    canon={'AUD':{'date':'2026-11-04'}}
    m.validate_and_merge(c,canon,snapshot,None,TODAY)
    with self.assertRaises(ValueError):
        m.validate_and_merge(c,canon,{**snapshot,'2Y':1.0},None,TODAY)
    with self.assertRaisesRegex(ValueError,'same F2 edition'):
        m.validate_and_merge(c,canon,{**snapshot,'source_sha256':'a'*64},None,TODAY)
    with self.assertRaises(ValueError):
        m.validate_and_merge(c,{'AUD':{'date':'2026-11-05'}},snapshot,None,TODAY)
 def test_source_revision_detected(self):
    c=self.source()
    snap=self.snapshot(c)
    canon={'AUD':{'date':'2026-11-04'}}
    m.validate_and_merge(c,canon,snap,c,TODAY)
    prior={**c,'observations':[dict(r) for r in c['observations']]}
    prior['observations'][1]['2Y']+=.1
    with self.assertRaises(ValueError):
        m.validate_and_merge(c,canon,snap,prior,TODAY)
 def test_new_release_preserves_observed_revision_and_is_idempotent(self):
    prior=self.source()
    c={**prior,'observations':[dict(r) for r in prior['observations']],
       'last_observation_date':'2026-11-11','publication_date':'2026-11-13',
       'source_response_sha256':'b'*64}
    first=c['observations'][0]
    first['2Y']+=.001
    c['observations'].append({'date':'2026-11-11','2Y':4.808,'10Y':5.044})
    today=dt.date(2026,11,13)
    canon={'AUD':{'date':'2026-11-11'}}
    result=m.validate_and_merge(c,canon,self.snapshot(c),prior,today)
    receipt=result['source_revisions']
    self.assertEqual(receipt['previous_source_response_sha256'],prior['source_response_sha256'])
    self.assertEqual(receipt['changed_observations'],[
        {'date':first['date'],'previous':prior['observations'][0],'current':first}])
    self.assertEqual(m.validate_and_merge(c,canon,self.snapshot(c),result,today),result)
    same_edition={**c,'publication_date':prior['publication_date']}
    with self.assertRaisesRegex(ValueError,'newer official F2 publication'):
        m.validate_and_merge(same_edition,canon,self.snapshot(same_edition),prior,today)
 def test_placeholder_not_promoted(self):
    c=self.source()
    p={'schema':m.SCHEMA,'status':'AWAITING_OFFICIAL_F2_DAILY_HISTORY','observations':[]}
    snap=self.snapshot(c)
    m.validate_and_merge(c,{'AUD':{'date':'2026-11-04'}},snap,p,TODAY)

if __name__=='__main__':unittest.main()
