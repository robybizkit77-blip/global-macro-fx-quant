#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
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
    'reference_month','unemployment_rate_sa','release_date','release_time','timezone',
    'source_url','sha256','route','pit_status'
]
SEMANTIC_KEYS = ['reference_month','unemployment_rate_sa','release_date','release_time','timezone','pit_status']
ANCHORS = {
    '2018-01': 5.9,
    '2020-04': 13.0,
    '2022-01': 6.5,
    '2024-12': 6.7,
    '2026-08': 6.4,
}


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
    cal = calendar.monthcalendar(ry, rm)
    fridays = [week[calendar.FRIDAY] for week in cal if week[calendar.FRIDAY] != 0][:2]
    preferred = []
    for d in fridays:
        preferred.extend([d, d-1])
    fallback = list(range(1, 13))
    seen = set()
    for d in preferred + fallback:
        if d < 1:
            continue
        try:
            dt = date(ry, rm, d)
        except ValueError:
            continue
        if dt in seen:
            continue
        seen.add(dt)
        yield dt


def url_for(dt: date) -> str:
    token = dt.strftime('%y%m%d')
    return f'https://www150.statcan.gc.ca/n1/daily-quotidien/{token}/dq{token}a-eng.htm'


def valid_identity(text: str, y: int, m: int) -> bool:
    month = MONTHS[m-1]
    if re.search(r'Labour Force Survey', text, flags=re.I) is None:
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


def unemployment_rate(text: str, y: int, m: int) -> float | None:
    month = MONTHS[m-1]
    # The first national headline has a stable semantic order across archived
    # Daily pages: "Unemployment rate — Canada" -> value -> reference month.
    headline = re.search(
        rf'Unemployment rate\s*[—-]\s*Canada\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*{month}\s+{y}\b',
        text,
        flags=re.I|re.S,
    )
    if headline:
        v = float(headline.group(1))
        if 2.0 <= v <= 20.0:
            return v

    # Fail closed: only inspect a short window that begins exactly at the
    # Canada headline and require the requested reference month before taking
    # a percentage. Never search generic narrative/provincial unemployment text.
    pos = re.search(r'Unemployment rate\s*[—-]\s*Canada\b', text, flags=re.I)
    if not pos:
        return None
    win = text[pos.start():pos.start()+300]
    if re.search(rf'\b{month}\s+{y}\b', win, flags=re.I) is None:
        return None
    q = re.search(r'Canada\s*([0-9]+(?:\.[0-9]+)?)\s*%', win, flags=re.I|re.S)
    if not q:
        return None
    v = float(q.group(1))
    return v if 2.0 <= v <= 20.0 else None


def one(y: int, m: int):
    ref = f'{y:04d}-{m:02d}'
    for dt in candidate_dates(y, m):
        url = url_for(dt)
        try:
            raw, ct, final = get(url)
        except (HTTPError, URLError, TimeoutError, ValueError):
            continue
        text = textify(raw)
        if not valid_identity(text, y, m):
            continue
        rate = unemployment_rate(text, y, m)
        release_date = parse_release_date(text)
        if rate is None or release_date is None:
            continue
        return {
            'reference_month': ref,
            'unemployment_rate_sa': rate,
            'release_date': release_date,
            'release_time': '08:30',
            'timezone': 'Eastern Time',
            'source_url': url,
            'sha256': hashlib.sha256(raw).hexdigest(),
            'route': 'STATCAN_THE_DAILY',
            'pit_status': 'STRICT_FIRST_RELEASE',
            'content_type': ct,
            'bytes': len(raw),
            'final_url': final,
        }
    raise ValueError(f'no strict period-specific Statistics Canada Labour Force Survey source for {ref}')


def digest(rows, keys):
    canon = [{k: r[k] for k in keys} for r in rows]
    blob = json.dumps(canon, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


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
        print(f'[{i:03d}/{expected}] {r["reference_month"]} {r["unemployment_rate_sa"]} {r["release_date"]}', flush=True)
        time.sleep(0.02)

    hashes = [r['sha256'] for r in rows]
    by_ref = {r['reference_month']: float(r['unemployment_rate_sa']) for r in rows}
    assert expected == 104
    assert len(rows) == expected
    assert rows[0]['reference_month'] == '2018-01' and rows[-1]['reference_month'] == '2026-08'
    assert len(set(hashes)) == expected
    assert all(r['pit_status'] == 'STRICT_FIRST_RELEASE' for r in rows)
    for ref, expected_value in ANCHORS.items():
        assert by_ref[ref] == expected_value, f'anchor mismatch {ref}: {by_ref[ref]} != {expected_value}'

    with open(args.csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=ROW_KEYS, lineterminator='\n')
        w.writeheader()
        w.writerows({k: r[k] for k in ROW_KEYS} for r in rows)

    evidence = {
        'schema': 'GMFQ_CAD_LABOUR_STRICT_PIT_EVIDENCE_V1_RUNTIME',
        'status': 'PASS',
        'target': 'CAD.labour',
        'evidence_class': 'STRICT_DIRECT_ARCHIVAL_PIT',
        'authority': 'Statistics Canada',
        'coverage': {'start':'2018-01','end':'2026-08','expected_months':expected,'materialized_months':len(rows)},
        'series_contract': {
            'series_id': 'CA_UNEMP_RATE',
            'frequency': 'M',
            'transformation': 'level',
            'seasonal_adjustment': 'seasonally adjusted'
        },
        'anchor_checks': ANCHORS,
        'route_counts': {'STATCAN_THE_DAILY': len(rows)},
        'unique_source_hashes': len(set(hashes)),
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
            'publication_timestamp_required': True,
            'sha256_required': True,
            'canada_headline_required': True,
            'generic_narrative_or_provincial_fallback_forbidden': True,
            'current_revised_history_forbidden': True,
            'revised_history_fallback_used': False
        },
        'generated_at_utc': datetime.now(timezone.utc).isoformat()
    }
    with open(args.evidence, 'w', encoding='utf-8') as f:
        json.dump(evidence, f, indent=2)
        f.write('\n')

    print(json.dumps({k:evidence[k] for k in ['status','coverage','anchor_checks','route_counts','unique_source_hashes','semantic_rowset_sha256','raw_fetch_rowset_sha256']}, indent=2))


if __name__ == '__main__':
    main()
