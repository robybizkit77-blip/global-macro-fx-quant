#!/usr/bin/env python3
"""Read-only discovery of CFTC COT Historical Special Announcements.

Captures the official page as transport provenance and extracts normalized
publication-timing exceptions for 2018-2026. Full-page bytes may vary between
requests; reproducibility is therefore judged on the normalized timing evidence,
not volatile HTML bytes. This is discovery evidence only.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import pathlib
import re
import urllib.request
from datetime import datetime

URL='https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm'
UA='global-macro-fx-quant/cot-special-announcements-discovery-v1'
DATE_RE=re.compile(r'(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)\s+(?P<day>\d{1,2}),\s+(?P<year>20\d{2})\s*:',re.I)
TIMING_WORDS=('delay','delayed','postpon','publish','publication','release','released','shutdown','appropriation','holiday','mourning','cyber','ion')


def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()


def fetch()->bytes:
    req=urllib.request.Request(URL,headers={'User-Agent':UA,'Accept':'text/html,*/*;q=0.8'})
    with urllib.request.urlopen(req,timeout=90) as r:
        raw=r.read()
        if r.status!=200: raise RuntimeError(f'HTTP {r.status}')
        return raw


def visible(raw:bytes)->str:
    text=raw.decode('utf-8',errors='replace')
    text=re.sub(r'<script\b.*?</script>',' ',text,flags=re.I|re.S)
    text=re.sub(r'<style\b.*?</style>',' ',text,flags=re.I|re.S)
    text=html.unescape(re.sub(r'<[^>]+>',' ',text))
    return re.sub(r'\s+',' ',text).strip()


def iso_date(month:str,day:str,year:str)->str:
    return datetime.strptime(f'{month} {day} {year}','%B %d %Y').date().isoformat()


def extract_blocks(text:str)->list[dict]:
    matches=list(DATE_RE.finditer(text))
    blocks=[]
    for i,m in enumerate(matches):
        year=int(m.group('year'))
        if not 2018 <= year <= 2026: continue
        end=matches[i+1].start() if i+1 < len(matches) else min(len(text),m.end()+4000)
        body=text[m.end():end].strip()[:12000]
        low=body.lower()
        blocks.append({
            'announcement_date':iso_date(m.group('month').title(),m.group('day'),m.group('year')),
            'timing_relevant':any(w in low for w in TIMING_WORDS),
            'text':body,
            'text_sha256':sha(body.encode()),
        })
    return blocks


def extract_2025_catchup(text:str)->list[dict]:
    # Final Dec 9 schedule supersedes the earlier Nov 18 intended schedule.
    start=text.find('December 9, 2025:')
    end=text.find('November 18, 2025:',start)
    if start<0 or end<0: return []
    block=text[start:end]
    rows=[]
    pat=re.compile(r'(\d{2}/\d{2}/2025)\s+(\d{2}/\d{2}/2025)\s+(\d{2}/\d{2}/2025)')
    for report,original,new in pat.findall(block):
        conv=lambda s: datetime.strptime(s,'%m/%d/%Y').date().isoformat()
        rows.append({'report_date':conv(report),'original_publish_date':conv(original),'actual_publish_date':conv(new)})
    return rows


def extract_ion_mappings(blocks:list[dict])->list[dict]:
    # CFTC wording gives original scheduled publish date and the announcement date
    # on which that delayed report is being issued. Do not infer report_date here.
    out=[]
    pat=re.compile(r'originally scheduled to be published on\s+(Friday,\s+)?(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(2023)',re.I)
    for b in blocks:
        if not b['announcement_date'].startswith('2023-'): continue
        if 'ION' not in b['text'] and 'cyber' not in b['text'].lower(): continue
        m=pat.search(b['text'])
        if not m: continue
        out.append({
            'original_publish_date':iso_date(m.group(2).title(),m.group(3),m.group(4)),
            'actual_publish_date':b['announcement_date'],
            'source_announcement_date':b['announcement_date'],
        })
    return sorted(out,key=lambda r:r['original_publish_date'])


def block_for(blocks:list[dict], announcement_date:str)->dict:
    found=[b for b in blocks if b['announcement_date']==announcement_date]
    if len(found)!=1:
        raise RuntimeError(f'expected one special-announcement block for {announcement_date}, got {len(found)}')
    return found[0]


def extract_other_timing_anchors(blocks:list[dict])->list[dict]:
    specs=[
        ('2020-12-18','2020-12-21','2020-12-28'),
        ('2021-06-18','2021-06-15','2021-06-21'),
        ('2025-01-08','2025-01-07','2025-01-13'),
    ]
    out=[]
    for announcement,report,actual in specs:
        b=block_for(blocks,announcement)
        # Require both the report-date day and actual publication date to be
        # recoverable from the CFTC text before emitting the normalized anchor.
        report_fmt=datetime.fromisoformat(report).strftime('%B %-d, %Y')
        actual_fmt=datetime.fromisoformat(actual).strftime('%B %-d, %Y')
        low=b['text'].lower()
        if report_fmt.lower() not in low or actual_fmt.lower() not in low:
            raise RuntimeError(f'official block {announcement} does not prove {report}->{actual}')
        out.append({
            'report_date':report,
            'actual_publish_date':actual,
            'source_announcement_date':announcement,
        })
    return out


def semantic_evidence(catchup:list[dict],ion:list[dict],anchors:list[dict])->dict:
    return {
        'final_2025_appropriations_catchup':catchup,
        'ion_2023_original_to_actual_publish':ion,
        'other_timing_anchors':anchors,
    }


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); args=ap.parse_args()
    raw=fetch(); text=visible(raw); blocks=extract_blocks(text)
    timing=[b for b in blocks if b['timing_relevant']]
    catchup=extract_2025_catchup(text)
    ion=extract_ion_mappings(blocks)
    anchors=extract_other_timing_anchors(blocks)
    semantic=semantic_evidence(catchup,ion,anchors)
    out={
      'schema':'GMFQ_COT_SPECIAL_ANNOUNCEMENTS_DISCOVERY_V1',
      'status':'DISCOVERY_PASS',
      'authority':'U.S. Commodity Futures Trading Commission (CFTC)',
      'source_url':URL,
      'transport_provenance':{
        'raw_sha256':sha(raw),
        'visible_text_sha256':sha(text.encode()),
        'note':'Full-page transport hashes are retained for provenance but are not expected to be identical across requests because CFTC HTML contains volatile page content.'
      },
      'announcement_blocks_2018_2026':len(blocks),
      'timing_relevant_blocks':timing,
      'final_2025_appropriations_catchup':catchup,
      'ion_2023_original_to_actual_publish':ion,
      'other_timing_anchors':anchors,
      'semantic_timing_sha256':sha(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()),
      'invariants':{
        'official_cftc_only':True,
        'final_2025_schedule_only':True,
        'ion_mapping_does_not_infer_report_date':True,
        'volatile_transport_hash_not_used_as_economic_reproducibility_key':True,
        'full_release_calendar_certified':False,
        'production_write':False,
      }
    }
    if len(catchup) != 13: raise RuntimeError(f'2025 final catch-up table unexpected length: {len(catchup)}')
    if len(ion) != 7: raise RuntimeError(f'ION mapping unexpected length: {len(ion)}')
    if len(anchors) != 3: raise RuntimeError(f'other timing anchors unexpected length: {len(anchors)}')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({
      'status':out['status'],
      'transport_raw_sha256':out['transport_provenance']['raw_sha256'],
      'semantic_timing_sha256':out['semantic_timing_sha256'],
      'announcement_blocks_2018_2026':out['announcement_blocks_2018_2026'],
      'timing_relevant_count':len(timing),'catchup_2025_rows':len(catchup),
      'ion_2023_rows':len(ion),'other_timing_anchors':anchors,
      'ion':ion,'catchup_2025':catchup,
    },indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
