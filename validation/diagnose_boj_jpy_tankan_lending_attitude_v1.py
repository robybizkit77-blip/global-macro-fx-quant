#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT = Path('validation/liquidity-jpy-tankan-lending-attitude-diagnostic.json')
BASE = 'https://www.stat-search.boj.or.jp/api/v1'
DB = 'CO'
UA = 'global-macro-fx-quant/1.0'
SCALES = (1.0, -1.0, 0.1, -0.1, 10.0, -10.0, 0.01, -0.01, 100.0, -100.0)


def get_json(endpoint: str, params: dict):
    url = BASE + '/' + endpoint + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=90) as r:
        return url, json.loads(r.read().decode('utf-8-sig'))


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def metadata_candidates():
    url, obj = get_json('getMetadata', {'format': 'json', 'lang': 'en', 'db': DB})
    if obj.get('STATUS') != 200:
        raise SystemExit(f'BOJ metadata API failure: {obj}')
    found = {}
    for row in walk(obj):
        code = None
        for k in ('SERIES_CODE', 'seriesCode', 'series_code', 'CODE', 'code'):
            if row.get(k):
                code = str(row[k])
                break
        if not code:
            continue
        text = ' '.join(str(v) for v in row.values() if isinstance(v, (str, int, float))).strip()
        low = text.lower()
        # BOJ official Tankan survey item 612 = Lending Attitude of Financial Institutions.
        score = 0
        if 'lending attitude' in low: score += 12
        if 'financial institution' in low: score += 5
        if '612' in code or '612' in text: score += 8
        if 'tankan' in low: score += 2
        if 'judgement' in low or 'judgment' in low: score += 2
        if 'quarter' in low: score += 1
        if score < 8:
            continue
        rec = {'series_code': code, 'metadata_score': score, 'text': text[:3000]}
        old = found.get(code)
        if old is None or score > old['metadata_score']:
            found[code] = rec
    ranked = sorted(found.values(), key=lambda x: (-x['metadata_score'], x['series_code']))
    return url, ranked[:250]


def quarter_key(raw) -> str | None:
    s = str(raw).strip()
    digits = ''.join(ch for ch in s if ch.isdigit())
    if len(digits) < 6:
        return None
    y, m = int(digits[:4]), int(digits[4:6])
    if m not in (3, 6, 9, 12):
        return None
    return f'{y}-Q{((m - 1) // 3) + 1}'


def fetch_series(code: str):
    url, obj = get_json('getDataCode', {
        'format': 'json', 'lang': 'en', 'db': DB,
        'startDate': '201601', 'endDate': '202612', 'code': code,
    })
    if obj.get('STATUS') != 200 or len(obj.get('RESULTSET') or []) != 1:
        return url, None, None
    row = obj['RESULTSET'][0]
    vals = row.get('VALUES') or {}
    src = {}
    for d, v in zip(vals.get('SURVEY_DATES') or [], vals.get('VALUES') or []):
        if v is None:
            continue
        q = quarter_key(d)
        if not q:
            continue
        try:
            src[q] = float(v)
        except (TypeError, ValueError):
            pass
    return url, row, src


def runtime_series():
    liq = json.loads(RUNTIME.read_text(encoding='utf-8'))
    row = liq['JPY']['conditions']
    dates = list(row.get('dates') or [])
    values = list(row.get('values') or [])
    if not dates or len(dates) != len(values):
        raise SystemExit('invalid JPY.conditions runtime arrays')
    rt = {str(d): float(v) for d, v in zip(dates, values)}
    return row, rt


def score(rt, src, scale):
    common = sorted(set(rt) & set(src))
    if not common:
        return {'scale': scale, 'overlap': 0, 'exact': 0, 'exact_ratio': 0.0, 'mae': None, 'max_abs_diff': None}
    diffs = [rt[d] - src[d] * scale for d in common]
    exact = sum(abs(x) <= 1e-9 for x in diffs)
    return {
        'scale': scale,
        'overlap': len(common),
        'exact': exact,
        'exact_ratio': exact / len(common),
        'mae': sum(abs(x) for x in diffs) / len(diffs),
        'max_abs_diff': max(abs(x) for x in diffs),
        'first_quarter': common[0],
        'last_quarter': common[-1],
        'runtime_last_value': rt[common[-1]],
        'scaled_source_last_value': src[common[-1]] * scale,
        'mismatches': [
            {'quarter': d, 'runtime': rt[d], 'source_raw': src[d], 'source_scaled': src[d] * scale,
             'diff': rt[d] - src[d] * scale}
            for d in common if abs(rt[d] - src[d] * scale) > 1e-9
        ][:30],
    }


def main():
    rtrow, rt = runtime_series()
    meta_url, candidates = metadata_candidates()
    if not candidates:
        raise SystemExit('no plausible CO Tankan lending-attitude metadata candidates found')
    results = []
    for c in candidates:
        try:
            url, row, src = fetch_series(c['series_code'])
        except Exception as exc:
            results.append({**c, 'fetch_error': repr(exc)})
            continue
        if not row or not src:
            continue
        scores = [score(rt, src, s) for s in SCALES]
        best = min(scores, key=lambda x: (
            -x['exact_ratio'], -x['overlap'], x['mae'] if x['mae'] is not None else 1e99,
            abs(x['scale'] - 1.0),
        ))
        results.append({
            **c,
            'url': url,
            'name': row.get('NAME_OF_TIME_SERIES'),
            'unit': row.get('UNIT'),
            'frequency': row.get('FREQUENCY'),
            'best_transform': best,
        })
    results.sort(key=lambda x: (
        -float((x.get('best_transform') or {}).get('exact_ratio', 0)),
        -int((x.get('best_transform') or {}).get('overlap', 0)),
        float((x.get('best_transform') or {}).get('mae') or 1e99),
    ))
    exact = [
        r for r in results
        if (r.get('best_transform') or {}).get('overlap', 0) == len(rt)
        and (r.get('best_transform') or {}).get('exact_ratio') == 1.0
        and (r.get('best_transform') or {}).get('scale') == 1.0
    ]
    report = {
        'schema': 'GMFQ_LIQUIDITY_JPY_TANKAN_LENDING_ATTITUDE_DIAGNOSTIC_V1',
        'status': (
            'UNIQUE_EXACT_CO_TANKAN_RUNTIME_MATCH_PROVEN' if len(exact) == 1
            else 'AMBIGUOUS_EXACT_CO_TANKAN_RUNTIME_MATCH' if len(exact) > 1
            else 'WITHHELD_EXACT_TANKAN_SERIES_OR_VINTAGE_PENDING'
        ),
        'source': {
            'publisher': 'Bank of Japan',
            'api': 'Time-Series Data Search API',
            'database': DB,
            'official_survey_item': '612',
            'official_survey_item_name': 'Lending Attitude of Financial Institutions',
            'metadata_url': meta_url,
        },
        'runtime': {
            'label': rtrow.get('label'),
            'count': len(rt),
            'first_quarter': min(rt),
            'last_quarter': max(rt),
            'last_value': float(rtrow.get('last_value')),
        },
        'metadata_candidate_count': len(candidates),
        'tested_series_count': len(results),
        'exact_match_count': len(exact),
        'exact_matches': exact[:20],
        'best_candidate': results[0] if results else None,
        'top_candidates': results[:30],
        'promotion_eligible': len(exact) == 1,
        'automation_ready': False,
        'runtime_mutated': False,
        'publication_performed': False,
        'bias_score_sizing_effect': 'NONE',
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
