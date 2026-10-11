#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, html, json, pathlib, re, time, urllib.request
from datetime import datetime

BASE='https://www.bls.gov/news.release/archives/cpi_{stamp}.htm'
UA='Mozilla/5.0 (compatible; GLOBAL-MACRO-FX-QUANT/1.0; strict PIT release-chain validation)'
SEED_RELEASE='2018-01-12'
SEED_REFERENCE='2017-12'
TARGET_START='2018-01'
TARGET_END='2026-08'
EXPECTED=104

# Only documented BLS schedule exceptions are allowed. A pure reschedule changes
# availability date but not the observation sequence. A documented nonpublication
# creates an explicit unavailable reference month and is never imputed.
SPECIAL_TRANSITIONS={
    '2025-09': {
        'announced_release_date':'2025-10-15',
        'actual_release_date':'2025-10-24',
        'kind':'RESCHEDULED_2025_LAPSE',
        'evidence_url':'https://www.bls.gov/bls/092025-cpi-reschedule-notice.htm',
        'missing_reference_month':'2025-10',
        'missing_kind':'NOT_PUBLISHED_2025_LAPSE',
        'missing_evidence_url':'https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm',
        'resume_reference_month':'2025-11',
        'resume_release_date':'2025-12-18',
    },
    '2026-01': {
        'announced_release_date':'2026-02-11',
        'actual_release_date':'2026-02-13',
        'kind':'RESCHEDULED_2026_LAPSE',
        'evidence_url':'https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm',
    },
}


def stamp(iso:str)->str:
    y,m,d=iso.split('-'); return f'{m}{d}{y}'

def fetch_url(url:str)->tuple[bytes,str]:
    last=None
    for wait in (0,2,5,10):
        if wait: time.sleep(wait)
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*;q=0.8','Connection':'close'})
            with urllib.request.urlopen(req,timeout=30) as r:
                raw=r.read(); final=r.geturl()
            return raw,final
        except Exception as exc: last=exc
    raise RuntimeError(f'BLS fetch failed {url}: {last!r}')

def fetch(release_date:str)->tuple[bytes,str]:
    return fetch_url(BASE.format(stamp=stamp(release_date)))

def plain(raw:bytes)->str:
    s=raw.decode('utf-8','replace')
    s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s)
    s=re.sub(r'(?s)<[^>]+>',' ',s)
    s=html.unescape(s).replace('\xa0',' ')
    return ' '.join(s.split())

def month_key(label:str)->str:
    return datetime.strptime(label.strip(),'%B %Y').strftime('%Y-%m')

def iso_date(label:str)->str:
    return datetime.strptime(' '.join(label.split()),'%B %d, %Y').date().isoformat()

def parse(raw:bytes, expected_release_date:str, allow_missing_next:bool=False)->dict:
    text=plain(raw)
    m=re.search(r'CONSUMER PRICE INDEX\s+[^A-Za-z0-9]{1,6}\s*([A-Za-z]+\s+\d{4})',text,re.I)
    if not m:
        m=re.search(r'CONSUMER PRICE INDEX.{0,12}?([A-Za-z]+\s+\d{4})',text,re.I)
    if not m: raise ValueError('current reference month not found')
    ref=month_key(m.group(1))
    emb=re.search(
        r'embargoed until\s+8:30\s*a\.m\.\s*\((EST|EDT|ET)\)\s+'
        r'(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+)?'
        r'([A-Za-z]+\s+\d{1,2},\s+\d{4})',text,re.I)
    if not emb: raise ValueError(f'embargo timestamp not found for {ref}')
    embargo_date=iso_date(emb.group(2))
    if embargo_date != expected_release_date:
        raise ValueError(f'archive URL date {expected_release_date} != embargo date {embargo_date}')

    # Historical wording: "The Consumer Price Index for <month> is scheduled
    # to be released...". Beginning in mid-2026 BLS changed this to "The
    # Consumer Price Index news release for <month> is scheduled to be
    # published...". Both forms still carry the exact official next-release
    # month, date, time, and timezone; accept only these tightly anchored forms.
    next_patterns=[
      r'The Consumer Price Index for\s+([A-Za-z]+\s+\d{4})\s+is scheduled to be released on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}),?\s+at\s+8:30\s*a\.m\.\s*\((EST|EDT|ET)\)',
      r'The Consumer Price Index for\s+([A-Za-z]+\s+\d{4})\s+is scheduled to be released on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}),?\s+at\s+8:30\s*a\.m\.\s*\((EST|EDT|ET)\)',
      r'The Consumer Price Index news release for\s+([A-Za-z]+\s+\d{4})\s+is scheduled to be published on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}),?\s+at\s+8:30\s*a\.m\.\s*\((EST|EDT|ET)\)',
      r'The Consumer Price Index news release for\s+([A-Za-z]+\s+\d{4})\s+is scheduled to be published on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}),?\s+at\s+8:30\s*a\.m\.\s*\((EST|EDT|ET)\)',
    ]
    nxt=None
    for pattern in next_patterns:
        nxt=re.search(pattern,text,re.I)
        if nxt: break
    if not nxt and not allow_missing_next:
        raise ValueError(f'next-release statement not found for {ref}')
    out={
      'reference_month':ref,
      'release_date':expected_release_date,
      'release_time':'08:30',
      'release_timezone':'America/New_York',
      'embargo_tz_abbrev':emb.group(1).upper(),
      'availability_status':'PUBLISHED',
      'next_reference_month':month_key(nxt.group(1)) if nxt else None,
      'next_release_date':iso_date(nxt.group(2)) if nxt else None,
    }
    return out

def next_month(k:str)->str:
    y,m=map(int,k.split('-')); m+=1
    if m==13: y+=1; m=1
    return f'{y:04d}-{m:02d}'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    current_date=SEED_RELEASE; expected_ref=SEED_REFERENCE
    selected=[]; chain=[]; errors=[]
    try:
        while True:
            special=SPECIAL_TRANSITIONS.get(expected_ref)
            if special and current_date==special['announced_release_date']:
                current_date=special['actual_release_date']

            # Only the 2025 transition with a documented missing following month
            # may lack a normal next-release sentence in the rescheduled release.
            has_gap=bool(special and special.get('missing_reference_month'))
            raw,url=fetch(current_date); row=parse(raw,current_date,allow_missing_next=has_gap)
            if row['reference_month'] != expected_ref:
                raise ValueError(f'expected reference {expected_ref}, got {row["reference_month"]}')
            row['source_url']=url; row['source_sha256']=hashlib.sha256(raw).hexdigest()

            if special:
                eraw,efinal=fetch_url(special['evidence_url'])
                row['schedule_exception']=special['kind']
                row['schedule_exception_evidence_url']=efinal
                row['schedule_exception_evidence_sha256']=hashlib.sha256(eraw).hexdigest()
                row['announced_release_date']=special['announced_release_date']
                row['actual_release_date']=special['actual_release_date']

            chain.append(row)
            if TARGET_START <= row['reference_month'] <= TARGET_END:
                selected.append(row)
            if row['reference_month']==TARGET_END: break

            if has_gap:
                mraw,mfinal=fetch_url(special['missing_evidence_url'])
                missing={
                  'reference_month':special['missing_reference_month'],
                  'release_date':None,
                  'release_time':None,
                  'release_timezone':'America/New_York',
                  'availability_status':'NOT_PUBLISHED_OFFICIAL',
                  'official_gap_reason':special['missing_kind'],
                  'source_url':mfinal,
                  'source_sha256':hashlib.sha256(mraw).hexdigest(),
                  'next_reference_month':special['resume_reference_month'],
                  'next_release_date':special['resume_release_date'],
                }
                chain.append(missing)
                if TARGET_START <= missing['reference_month'] <= TARGET_END:
                    selected.append(missing)
                expected_ref=special['resume_reference_month']; current_date=special['resume_release_date']
                time.sleep(0.15)
                continue

            if row['next_reference_month'] != next_month(row['reference_month']):
                raise ValueError(f'non-consecutive next reference after {row["reference_month"]}: {row["next_reference_month"]}')
            expected_ref=row['next_reference_month']; current_date=row['next_release_date']
            time.sleep(0.15)
    except Exception as exc:
        errors.append(repr(exc))

    refs=[r['reference_month'] for r in selected]
    published=sum(r.get('availability_status')=='PUBLISHED' for r in selected)
    unavailable=sum(r.get('availability_status')=='NOT_PUBLISHED_OFFICIAL' for r in selected)
    status='CERTIFIABLE_RELEASE_CALENDAR_WITH_OFFICIAL_GAP' if not errors and len(selected)==EXPECTED and refs and refs[0]==TARGET_START and refs[-1]==TARGET_END and len(set(refs))==EXPECTED and unavailable==1 else 'WITHHELD'
    semantic_rows=[{k:v for k,v in r.items() if k not in {'source_sha256','schedule_exception_evidence_sha256'}} for r in selected]
    semantic_sha=hashlib.sha256(json.dumps(semantic_rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    out={
      'schema':'GMFQ_USD_CPI_BLS_RELEASE_CHAIN_V1',
      'status':status,
      'authority':'U.S. Bureau of Labor Statistics',
      'coverage':{'start':TARGET_START,'end':TARGET_END,'expected_months':EXPECTED,'observed_months':len(selected),'published_months':published,'official_unavailable_months':unavailable},
      'seed':{'reference_month':SEED_REFERENCE,'release_date':SEED_RELEASE},
      'release_rows':selected,
      'errors':errors,
      'semantic_sha256':semantic_sha,
      'invariants':{
        'official_archive_only':True,
        'official_schedule_exception_evidence_only':True,
        'official_embargo_timestamp_required_for_published_rows':True,
        'availability_rule':'AT_OR_AFTER_08:30_AMERICA_NEW_YORK_ON_ACTUAL_RELEASE_DATE; EXPLICIT_UNAVAILABLE_IF_BLS_DID_NOT_PUBLISH',
        'documented_reschedules_do_not_create_synthetic_observations':True,
        'no_inflation_values_materialized':True,
        'no_imputation_for_missing_official_release':True,
        'certifies_values':False,
        'production_write':False,
      }
    }
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k!='release_rows'},indent=2,sort_keys=True))
    if status!='CERTIFIABLE_RELEASE_CALENDAR_WITH_OFFICIAL_GAP': raise SystemExit(2)

if __name__=='__main__': main()
