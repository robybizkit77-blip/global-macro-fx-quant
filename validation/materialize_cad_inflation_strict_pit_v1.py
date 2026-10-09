#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
from datetime import date, datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

UA = 'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'
START = (2018, 1)
END = (2026, 8)
MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']
ROW_KEYS = [
    'reference_month','cpi_index_current','cpi_index_prior_year','cpi_yoy_full_precision',
    'headline_yoy_reported','release_date','release_time','timezone','source_url','table_url',
    'article_sha256','table_sha256','combined_sha256','pit_status'
]
SEMANTIC_KEYS = [
    'reference_month','cpi_index_current','cpi_index_prior_year','cpi_yoy_full_precision',
    'headline_yoy_reported','release_date','release_time','timezone','pit_status'
]


def months():
    y, m = START
    while (y, m) <= END:
        yield y, m
        m += 1
        if m == 13:
            y += 1
            m = 1


def next_month(y: int, m: int) -> tuple[int, int]:
    return (y + 1, 1) if m == 12 else (y, m + 1)


def get(url: str):
    req = Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en-CA,en;q=0.9'})
    with urlopen(req, timeout=35) as r:
        return r.read(), r.headers.get('Content-Type',''), r.geturl()


def textify(raw: bytes) -> str:
    s = raw.decode('utf-8', errors='replace')
    s = re.sub(r'<script\b.*?</script>', ' ', s, flags=re.I|re.S)
    s = re.sub(r'<style\b.*?</style>', ' ', s, flags=re.I|re.S)
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s))
    return re.sub(r'\s+', ' ', s).strip()


def candidate_dates(y: int, m: int):
    ry, rm = next_month(y, m)
    preferred_days = [18,19,20,17,21,16,22,15,23,14,24,25,13,26]
    for d in preferred_days:
        try:
            yield date(ry, rm, d)
        except ValueError:
            pass


def token_for(dt: date) -> str:
    return dt.strftime('%y%m%d')


def article_url(dt: date) -> str:
    t = token_for(dt)
    return f'https://www150.statcan.gc.ca/n1/daily-quotidien/{t}/dq{t}a-eng.htm'


def table_url(dt: date) -> str:
    t = token_for(dt)
    return f'https://www150.statcan.gc.ca/n1/daily-quotidien/{t}/t001a-eng.htm'


def valid_article(text: str, y: int, m: int) -> bool:
    month = MONTHS[m-1]
    if re.search(r'Consumer Price Index', text, flags=re.I) is None:
        return False
    return re.search(rf'\b{month}\s+{y}\b', text, flags=re.I) is not None


def parse_release_date(text: str) -> str | None:
    q = re.search(r'Released:\s*(20\d{2}-\d{2}-\d{2})', text, flags=re.I)
    if q:
        return q.group(1)
    q = re.search(r'Released:\s*([A-Z][a-z]+)\s+(\d{1,2}),\s*(20\d{2})', text)
    if q and q.group(1) in MONTHS:
        mm = MONTHS.index(q.group(1)) + 1
        return f'{int(q.group(3)):04d}-{mm:02d}-{int(q.group(2)):02d}'
    return None


def parse_headline_yoy(text: str, y: int, m: int) -> float | None:
    month = MONTHS[m-1]
    patterns = [
        rf'Consumer Price Index\s+{month}\s+{y}\s+(-?[0-9]+(?:\.[0-9]+)?)\s*%.{{0,80}}?\(12-month change\)',
        rf'{month}\s+{y}\s+(-?[0-9]+(?:\.[0-9]+)?)\s*%.{{0,80}}?\(12-month change\)',
    ]
    for p in patterns:
        q = re.search(p, text, flags=re.I|re.S)
        if q:
            return float(q.group(1))
    q = re.search(r'Consumer Price Index.{0,700}?(-?[0-9]+(?:\.[0-9]+)?)\s*%.{0,80}?\(12-month change\)', text, flags=re.I|re.S)
    return float(q.group(1)) if q else None


def parse_all_items_indexes(raw: bytes) -> tuple[float, float]:
    s = raw.decode('utf-8', errors='replace')
    row_hits = re.findall(r'<tr\b[^>]*>.*?</tr>', s, flags=re.I|re.S)
    candidates = []
    for row in row_hits:
        txt = html.unescape(re.sub(r'<[^>]+>', ' ', row))
        txt = re.sub(r'\s+', ' ', txt).strip()
        if not re.search(r'\bAll-items\b', txt, flags=re.I):
            continue
        if re.search(r'All-items\s+excluding', txt, flags=re.I):
            continue
        nums = [float(x.replace(',', '')) for x in re.findall(r'-?[0-9]+(?:\.[0-9]+)?', txt)]
        candidates.append((txt, nums))
    if len(candidates) != 1:
        raise ValueError(f'expected one exact All-items row; got {len(candidates)}')
    txt, nums = candidates[0]
    if len(nums) < 6:
        raise ValueError(f'All-items row has too few numeric fields: {txt}')
    try:
        k = next(i for i, x in enumerate(nums) if 99.5 <= x <= 100.5)
    except StopIteration:
        raise ValueError(f'All-items row missing relative-importance field near 100: {txt}')
    # Footnote anchors in archived HTML can surface as standalone small integers
    # immediately after 100.00. The next three plausible CPI index values are,
    # by the period-specific table contract: prior-year, prior-month, current.
    indexes = [x for x in nums[k+1:] if 80.0 <= x <= 250.0]
    if len(indexes) < 3:
        raise ValueError(f'All-items row missing three plausible CPI indexes: {txt}')
    prior_year, _prior_month, current = indexes[:3]
    return current, prior_year


def digest(rows, keys):
    canon = [{k: r[k] for k in keys} for r in rows]
    blob = json.dumps(canon, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


def one(y: int, m: int):
    ref = f'{y:04d}-{m:02d}'
    diagnostics = []
    for dt in candidate_dates(y, m):
        aurl = article_url(dt)
        try:
            araw, _, afinal = get(aurl)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            diagnostics.append(f'{dt}:article_fetch:{type(exc).__name__}')
            continue
        article_text = textify(araw)
        if not valid_article(article_text, y, m):
            diagnostics.append(f'{dt}:identity_miss')
            continue
        release_date = parse_release_date(article_text)
        headline = parse_headline_yoy(article_text, y, m)
        if release_date is None or headline is None:
            diagnostics.append(f'{dt}:article_parse:release={release_date}:headline={headline}')
            continue
        turl = table_url(dt)
        try:
            traw, _, tfinal = get(turl)
            current, prior = parse_all_items_indexes(traw)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            diagnostics.append(f'{dt}:table:{type(exc).__name__}:{exc}')
            continue
        yoy = (current / prior - 1.0) * 100.0
        if abs(yoy - headline) > 0.055:
            raise ValueError(f'{ref} index-derived YoY {yoy} does not reconcile to reported headline {headline}')
        ah = hashlib.sha256(araw).hexdigest()
        th = hashlib.sha256(traw).hexdigest()
        combined = hashlib.sha256(araw + b'\n--TABLE--\n' + traw).hexdigest()
        return {
            'reference_month': ref,
            'cpi_index_current': current,
            'cpi_index_prior_year': prior,
            'cpi_yoy_full_precision': yoy,
            'headline_yoy_reported': headline,
            'release_date': release_date,
            'release_time': '08:30',
            'timezone': 'Eastern Time',
            'source_url': afinal,
            'table_url': tfinal,
            'article_sha256': ah,
            'table_sha256': th,
            'combined_sha256': combined,
            'pit_status': 'STRICT_FIRST_RELEASE',
        }
    raise ValueError(f'no strict period-specific Statistics Canada CPI release/table source for {ref}; diagnostics={diagnostics}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--evidence', required=True)
    args = ap.parse_args()

    rows = []
    expected = sum(1 for _ in months())
    for i, (y, m) in enumerate(months(), 1):
        r = one(y, m)
        rows.append(r)
        print(f'[{i:03d}/{expected}] {r["reference_month"]} idx={r["cpi_index_current"]}/{r["cpi_index_prior_year"]} yoy={r["cpi_yoy_full_precision"]:.12f} release={r["release_date"]}', flush=True)
        time.sleep(0.02)

    assert expected == 104 and len(rows) == 104
    assert rows[0]['reference_month'] == '2018-01' and rows[-1]['reference_month'] == '2026-08'
    assert len({r['combined_sha256'] for r in rows}) == 104
    assert len({r['table_sha256'] for r in rows}) == 104
    assert all(r['pit_status'] == 'STRICT_FIRST_RELEASE' for r in rows)

    with open(args.csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=ROW_KEYS, lineterminator='\n')
        w.writeheader()
        w.writerows({k: r[k] for k in ROW_KEYS} for r in rows)

    evidence = {
        'schema': 'GMFQ_CAD_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME',
        'status': 'PASS',
        'target': 'CAD.inflation',
        'evidence_class': 'STRICT_DIRECT_ARCHIVAL_PIT',
        'authority': 'Statistics Canada',
        'coverage': {'start':'2018-01','end':'2026-08','expected_months':104,'materialized_months':104},
        'series_contract': {
            'series_id': 'CA_CPI_HEADLINE_YOY',
            'frequency': 'M',
            'transformation': 'derived_yoy_from_index',
            'seasonal_adjustment': 'not seasonally adjusted',
            'unit': '% YoY'
        },
        'route_counts': {'STATCAN_THE_DAILY_PLUS_TABLE1': 104},
        'unique_combined_source_hashes': len({r['combined_sha256'] for r in rows}),
        'unique_table_hashes': len({r['table_sha256'] for r in rows}),
        'semantic_rowset_sha256': digest(rows, SEMANTIC_KEYS),
        'raw_fetch_rowset_sha256': digest(rows, ROW_KEYS),
        'publication_time_basis': {
            'release_vehicle': 'The Daily',
            'time': '08:30',
            'timezone': 'Eastern Time',
            'official_policy_url': 'https://www150.statcan.gc.ca/n1/dai-quo/info3-eng.htm'
        },
        'strict_rules': {
            'official_publisher_only': True,
            'period_specific_release_artifact_required': True,
            'period_specific_table_required': True,
            'publication_timestamp_required': True,
            'article_and_table_sha256_required': True,
            'headline_rounding_reconciliation_required': True,
            'full_precision_derived_from_release_table_indexes': True,
            'current_revised_history_forbidden': True,
            'revised_history_fallback_used': False
        },
        'generated_at_utc': datetime.now(timezone.utc).isoformat()
    }
    with open(args.evidence, 'w', encoding='utf-8') as f:
        json.dump(evidence, f, indent=2)
        f.write('\n')
    print(json.dumps({k:evidence[k] for k in ['status','coverage','route_counts','unique_combined_source_hashes','unique_table_hashes','semantic_rowset_sha256','raw_fetch_rowset_sha256']}, indent=2))


if __name__ == '__main__':
    main()
