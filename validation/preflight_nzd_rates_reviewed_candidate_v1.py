#!/usr/bin/env python3
"""Read-only NZD Rates promotion preflight.

Never authorizes automatic promotion. Cross-checks source page evidence,
independent second read, candidate receipt, current canonical Rates,
and semantic invariants before a separate future human-approved promotion.
"""
from __future__ import annotations
import argparse,copy,datetime as dt,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage_rbnz_b2_official_html_evidence_v1 import EVIDENCE,BASE,verify
from check_rbnz_b2_second_review_v1 import SECOND,check
from build_chf_nzd_official_rates_staging_v1 import make_candidate
def preflight(a,b,original,*,today):
    source_row=verify(a,original,today=today)
    independent=check(a,b,original)
    assert source_row['date']==independent['as_of']
    assert source_row['2Y']==independent['2Y'] and source_row['10Y']==independent['10Y']
    candidate,receipt=make_candidate(original,'NZD',source_row,
      source_sha256=hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),
      mode='RBNZ_HTML_TABLE_INDEPENDENT_REVIEW_PREFLIGHT',
      today=today)
    assert candidate is not None,'No advancing official candidate'
    assert receipt['eligible_for_automatic_promotion'] is False
    assert receipt['writes_live_data'] is False
    assert receipt['review']=='REQUIRED'
    assert set(candidate)==set(original)=={'USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'}
    assert [k for k in original if original[k]!=candidate[k]]==['NZD']
    old=original['NZD']; new=candidate['NZD']
    assert new['date']>old['date']
    assert new['2Y']==source_row['2Y'] and new['10Y']==source_row['10Y']
    assert new['curve_bp']==round((source_row['10Y']-source_row['2Y'])*100,1)
    assert new['quality']=='FULL_CURRENT_OFFICIAL_STAGING_REVIEW_REQUIRED'
    assert new['freshness_status']=='OFFICIAL_STAGING_REVIEW_REQUIRED'
    for hist,tenor in [('history2','2Y'),('history10','10Y')]:
        assert new[hist]['dates'][-1]==source_row['date']
        assert new[hist]['values'][-1]==source_row[tenor]
        assert new[hist]['dates'][:-1]==old[hist]['dates']
        assert new[hist]['values'][:-1]==old[hist]['values']
        assert len(new[hist]['dates'])==len(set(new[hist]['dates']))
    assert receipt['old_as_of']==old['date']
    return {'schema':'GMFQ_NZD_RATES_PROMOTION_PREFLIGHT_V1',
      'result':'PREFLIGHT_PASS_MANUAL_APPROVAL_STILL_REQUIRED',
      'candidate_date':new['date'],'source':'RBNZ B2 official published table',
      'rates_2Y':new['2Y'],'rates_10Y':new['10Y'],
      'changed_currencies':['NZD'],'other_7_currencies_unchanged':True,
      'verified_source_page_rows':len(a['observations']),
      'second_review_matches':True,'canonical_runtime_unmodified':True,
      'candidate_quality':new['quality'],
      'automatic_promotion_allowed':False,
      'requires':'Separate explicit decision, runtime full-contract validation, audited canonical update, and production publication QA'}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--receipt',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    args=ap.parse_args()
    for path in (args.receipt,args.candidate):
        if BASE.parents[2].resolve() in path.resolve().parents:
            raise SystemExit('Preflight output must not modify repository')
    first=json.loads(EVIDENCE.read_text());second=json.loads(SECOND.read_text())
    canonical=json.loads(BASE.read_text())
    baseline=json.dumps(canonical,sort_keys=True)
    result=preflight(first,second,canonical,today=dt.date.today())
    assert json.dumps(canonical,sort_keys=True)==baseline
    staged,receipt=make_candidate(canonical,'NZD',
      verify(first,canonical),source_sha256=hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),
      mode='RBNZ_HTML_TABLE_REVIEW_ONLY')
    assert staged is not None
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.candidate.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    args.candidate.write_text(json.dumps(staged,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps(result,ensure_ascii=False))
    print('NZD_RATES_PROMOTION_PREFLIGHT_NO_CANONICAL_WRITE_PASS')
if __name__=='__main__':main()
