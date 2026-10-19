#!/usr/bin/env python3
"""Cross-check two separately recorded RBNZ B2 public-table observations.

Read-only second source review gate. Passing this does NOT make a machine-
accessible live source or permit writes to canonical rates.
"""
import copy, datetime as dt, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIRST=ROOT/'validation/fixtures/rbnz_b2_official_table_2026-10-19_review_required.json'
SECOND=ROOT/'validation/fixtures/rbnz_b2_independent_source_review_2026-10-19.json'
RATES=ROOT/'live_data/sections/NATIVE_RATES_DATA.json'
URL='https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates'

def check(a,b,canonical):
    assert a['source_url']==b['source_url']==URL,'source authority mismatch'
    assert a['usable_for_automatic_promotion'] is False
    assert b['live_data_promotion_allowed'] is False
    assert b['status']=='SOURCE_TABLE_CROSS_CHECKED_STAGING_ONLY'
    assert b['review_type']=='INDEPENDENT_WEB_PAGE_READ_NOT_MACHINE_FETCHED_IN_GITHUB'
    assert 'government bond closing yields' in a['basis'].lower()
    assert 'government bond closing yields' in b['basis'].lower()
    aa=a['observations'];bb=b['source_rows']
    assert len(aa)>=8 and len(bb)>=8
    assert aa==bb,'independent published page review does not match first evidence'
    assert len({x['date'] for x in aa})==len(aa)
    assert [x['date'] for x in aa]==sorted(x['date'] for x in aa)
    assert all(set(x)=={'date','2Y','10Y'} and isinstance(x['2Y'],(int,float))
               and isinstance(x['10Y'],(int,float)) for x in aa)
    anchor=next(x for x in aa if x['date']==canonical['NZD']['date'])
    assert abs(anchor['2Y']-canonical['NZD']['2Y'])<1e-9
    assert abs(anchor['10Y']-canonical['NZD']['10Y'])<1e-9
    last=aa[-1]
    assert last=={'date':'2026-10-16','2Y':3.89,'10Y':5.0}
    assert (dt.date(2026,10,19)-dt.date.fromisoformat(last['date'])).days==3
    return {'schema':'GMFQ_RBNZ_SECOND_REVIEW_RECEIPT_V1',
       'state':'SOURCE_PUBLISHED_TABLE_CROSS_CHECK_PASS_STAGING_ONLY',
       'as_of':last['date'],'2Y':last['2Y'],'10Y':last['10Y'],
       'row_count':len(aa),'source':URL,
       'first_evidence_sha256':hashlib.sha256(FIRST.read_bytes()).hexdigest(),
       'second_evidence_sha256':hashlib.sha256(SECOND.read_bytes()).hexdigest(),
       'canonical_data_unchanged':True,'automatic_promotion':False}

def main():
    a=json.loads(FIRST.read_text());b=json.loads(SECOND.read_text())
    rates=json.loads(RATES.read_text())
    receipt=check(a,b,rates)
    for label,change in [
        ('changed value',lambda x:x['source_rows'][-1].update({'10Y':7.0})),
        ('changed basis',lambda x:x.update({'basis':'interest rate swap closing yields'})),
        ('wrong source',lambda x:x.update({'source_url':'https://other.example'})),
        ('promotion turned on',lambda x:x.update({'live_data_promotion_allowed':True}))]:
        corrupt=copy.deepcopy(b);change(corrupt)
        try:check(a,corrupt,rates)
        except AssertionError:pass
        else:raise AssertionError('review gate failed to reject '+label)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    print('RBNZ_B2_SECOND_INDEPENDENT_PAGE_REVIEW_QA_PASS')

if __name__=='__main__':main()
