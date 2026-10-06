#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

OUT = Path('/tmp/gmfq-gbp-ons-pit/archive_probe.json')
UA = 'global-macro-fx-quant/1.0 (+read-only PIT archive validation)'

FAMILIES = {
    'production': {
        'runtime_ids': ['UK_PRODUCTION_history_value'],
        'latest': 'https://www.ons.gov.uk/economy/economicoutputandproductivity/output/bulletins/indexofproduction/latest',
    },
    'retail': {
        'runtime_ids': ['UK_RETAIL_VOL_history_value'],
        'latest': 'https://www.ons.gov.uk/businessindustryandtrade/retailindustry/bulletins/retailsales/latest',
    },
    'labour_market': {
        'runtime_ids': ['UK_UNEMP_RATE_history_value', 'UK_EMPLOYMENT_RATE_history_value'],
        'latest': 'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/uklabourmarket/latest',
    },
    'paye': {
        'runtime_ids': ['UK_PAYE_PAYROLLED_EMPLOYEES_SA_history_value'],
        'latest': 'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/bulletins/earningsandemploymentfrompayasyouearnrealtimeinformationuk/latest',
    },
}

MONTHS = '(?:january|february|march|april|may|june|july|august|september|october|november|december)'
SLUG_RE = re.compile(rf'/({MONTHS}\d{{4}})(?:/|$|\?)', re.I)

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'a': return
        href = dict(attrs).get('href')
        if href: self.links.append(href)

def fetch(url: str, retries: int = 4) -> tuple[str, str]:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
            with urllib.request.urlopen(req, timeout=45) as r:
                text = r.read().decode('utf-8', 'replace')
                time.sleep(1.0)
                return r.geturl(), text
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 429 or attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    raise last or RuntimeError('fetch failed')

def archive_url_from_latest(final_url: str, html: str) -> str:
    p = Links(); p.feed(html)
    candidates = []
    for href in p.links:
        low = href.lower()
        if 'previousreleases' in low or 'previous-releases' in low:
            candidates.append(urljoin(final_url, href))
    if candidates:
        return sorted(set(candidates), key=len)[0]
    base = final_url.rstrip('/')
    return (base[:-7] if base.endswith('/latest') else base) + '/previousreleases'

def parse_archive(url: str, html: str) -> list[dict]:
    p = Links(); p.feed(html)
    base_path = urlparse(url).path.rsplit('/previousreleases', 1)[0].rstrip('/') + '/'
    rows = []; seen = set()
    for href in p.links:
        full = urljoin(url, href)
        parsed = urlparse(full)
        if parsed.netloc and parsed.netloc != 'www.ons.gov.uk':
            continue
        if not parsed.path.startswith(base_path):
            continue
        m = SLUG_RE.search(parsed.path + ('?' + parsed.query if parsed.query else ''))
        if m and full not in seen:
            seen.add(full)
            rows.append({'url': full.split('#')[0], 'slug_period': m.group(1).lower()})
    return rows

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result = {'schema':'GMFQ_GBP_ONS_PIT_ARCHIVE_PROBE_V1','status':'PASS','families':{},'guardrails':{
        'read_only':True,'live_data_modified':False,'model_rules_modified':False,'rules_fingerprint_expected_unchanged':'3356baf0'
    }}
    all_ok = True
    for name, cfg in FAMILIES.items():
        try:
            final, html = fetch(cfg['latest'])
            archive = archive_url_from_latest(final, html)
            af, ah = fetch(archive)
            releases = parse_archive(af, ah)
            recent = [r for r in releases if any(str(y) in r['slug_period'] for y in range(2018, 2027))]
            row = {
                'runtime_ids': cfg['runtime_ids'], 'latest_requested': cfg['latest'], 'latest_final': final,
                'archive_url': af, 'archive_pages_scanned': 1, 'release_link_count_first_page': len(releases),
                'release_links_2018_2026_first_page': len(recent),
                'first_release_link': releases[0] if releases else None,
                'last_release_link': releases[-1] if releases else None,
                'pit_archive_discoverable': len(recent) >= 8,
            }
            if not row['pit_archive_discoverable']: all_ok = False
        except Exception as e:
            row = {'runtime_ids': cfg['runtime_ids'], 'pit_archive_discoverable': False, 'error': repr(e)}
            all_ok = False
        result['families'][name] = row
        time.sleep(1.5)
    result['status'] = 'PASS' if all_ok else 'FAIL'
    result['summary'] = {
        'families_total': len(FAMILIES),
        'families_archive_discoverable': sum(1 for x in result['families'].values() if x.get('pit_archive_discoverable')),
        'runtime_series_covered': sum(len(x['runtime_ids']) for x in FAMILIES.values()),
        'probe_scope': 'first archive page only; enough to establish dated-release discoverability without bulk crawling',
        'next_gate': 'value-level first-release extraction from dated ONS release pages at model checkpoints; current revised time-series API alone is not PIT evidence'
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not all_ok: raise SystemExit(1)

if __name__ == '__main__': main()
