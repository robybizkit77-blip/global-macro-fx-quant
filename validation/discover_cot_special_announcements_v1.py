#!/usr/bin/env python3
"""Read-only discovery of CFTC COT Historical Special Announcements.

Captures the official page as provenance and extracts timing-relevant announcement
blocks for 2018-2026. This is discovery evidence only: it does not certify a full
release calendar or write production/history data.
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
        body=text[m.end():end].strip()
        # Cap huge table-rich blocks but retain enough context for 2025 catch-up table.
        body=body[:12000]
        low=body.lower()
        timing=any(w in low for w in TIMING_WORDS)
        blocks.append({
            'announcement_date':iso_date(m.group('month').title(),m.group('day'),m.group('year')),
            'timing_relevant':timing,
            'text':body,
            'text_sha256':hashlib.sha256(body.encode()).hexdigest(),
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
    # CFTC wording gives the original scheduled publish date and the announcement
    # date on which that delayed report is being issued. Do not infer report_date here.
    out=[]
    pat=re.compile(r'originally scheduled to be published on\s+(Friday,\s+)?(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(2023)',re.I)
    for b in blocks:
        if not b['announcement_date'].startswith('2023-'): continue
        if 'ION' not in b['text'] and 'cyber' not in b['text'].lower(): continue
        m=pat.search(b['text'])
        if not m: continue
        original=iso_date(m.group(2).title(),m.group(3),m.group(4))
        out.append({'original_publish_date':original,'actual_publish_date':b['announcement_date'],'source_announcement_date':b['announcement_date']})
    return sorted(out,key=lambda r:r['original_publish_date'])


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); args=ap.parse_args()
    raw=fetch(); text=visible(raw); blocks=extract_blocks(text)
    timing=[b for b in blocks if b['timing_relevant']]
    catchup=extract_2025_catchup(text)
    ion=extract_ion_mappings(blocks)
    out={
      'schema':'GMFQ_COT_SPECIAL_ANNOUNCEMENTS_DISCOVERY_V1',
      'status':'DISCOVERY_PASS',
      'authority':'U.S. Commodity Futures Trading Commission (CFTC)',
      'source_url':URL,
      'raw_sha256':hashlib.sha256(raw).hexdigest(),
      'visible_text_sha256':hashlib.sha256(text.encode()).hexdigest(),
      'announcement_blocks_2018_2026':len(blocks),
      'timing_relevant_blocks':timing,
      'final_2025_appropriations_catchup':catchup,
      'ion_2023_original_to_actual_publish':ion,
      'invariants':{
        'official_cftc_only':True,
        'final_2025_schedule_only':True,
        'ion_mapping_does_not_infer_report_date':True,
        'full_release_calendar_certified':False,
        'production_write':False,
      }
    }
    # Minimum anchors that must exist or discovery fails closed.
    anchors=' '.join(b['text'] for b in timing)
    if len(catchup) < 10: raise RuntimeError(f'2025 final catch-up table too sparse: {len(catchup)}')
    if len(ion) < 7: raise RuntimeError(f'ION mapping too sparse: {len(ion)}')
    for phrase in ('June 21, 2021','December 28, 2020','January 13, 2025'):
        if phrase.lower() not in text.lower(): raise RuntimeError(f'missing official timing anchor: {phrase}')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({
      'status':out['status'],'raw_sha256':out['raw_sha256'],
      'announcement_blocks_2018_2026':out['announcement_blocks_2018_2026'],
      'timing_relevant_count':len(timing),'catchup_2025_rows':len(catchup),
      'ion_2023_rows':len(ion),'ion':ion,'catchup_2025':catchup,
    },indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
