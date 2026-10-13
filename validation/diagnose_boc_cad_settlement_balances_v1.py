#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT = Path('validation/liquidity-cad-settlement-diagnostic.json')
BASE = 'https://www.bankofcanada.ca/valet'
SOURCE_PAGE = 'https://www.bankofcanada.ca/rates/interest-rates/canadian-interest-rates/'
DOCUMENTED_MONTHLY_RULE = 'last Wednesday of each month'


def get_json(url: str):
    req = urllib.request.Request(url, headers={'User-Agent': 'GMFQ-validation/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))


def norm_month(v: str) -> str:
    s = str(v).strip()
    for fmt in ('%Y-%m', '%Y-%m-%d', '%d %b %Y', '%d %B %Y'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m')
        except ValueError:
            pass
    raise SystemExit(f'unparseable CAD liquidity date {v!r}')


def runtime_series():
    rt = json.loads(RUNTIME.read_text(encoding='utf-8'))
    row = rt['CAD']['liquidity']
    dates = list(row.get('dates') or [])
    vals = list(row.get('values') or [])
    if not dates or len(dates) != len(vals):
        raise SystemExit('invalid CAD.liquidity runtime arrays')
    by_month = {norm_month(d): float(v) for d, v in zip(dates, vals)}
    return row, by_month


def flatten_series_catalog(obj):
    out = []
    series = obj.get('series') or obj.get('terms') or {}
    if isinstance(series, dict):
        for k, v in series.items():
            meta = v if isinstance(v, dict) else {}
            label = ' '.join(str(meta.get(x, '')) for x in ('label','description','name','title'))
            out.append((k, label.strip(), meta))
    elif isinstance(series, list):
        for item in series:
            if not isinstance(item, dict):
                continue
            k = item.get('name') or item.get('series') or item.get('id')
            if not k:
                continue
            label = ' '.join(str(item.get(x, '')) for x in ('label','description','name','title'))
            out.append((k, label.strip(), item))
    return out


def discover_candidates():
    catalog = get_json(f'{BASE}/lists/series/json')
    rows = flatten_series_catalog(catalog)
    terms = ('settlement', 'lynx', 'lvts')
    ranked = []
    for sid, label, meta in rows:
        text = f'{sid} {label}'.lower()
        score = sum(1 for t in terms if t in text)
        if score:
            ranked.append((score, sid, label, meta))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return ranked[:50]


def fetch_observations(series_id: str):
    url = f'{BASE}/observations/{urllib.parse.quote(series_id)}/json?start_date=2016-01-01'
    obj = get_json(url)
    obs = obj.get('observations') or []
    out = []
    for row in obs:
        d = row.get('d')
        cell = row.get(series_id)
        if not d or not isinstance(cell, dict):
            continue
        v = cell.get('v')
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        out.append((d, fv))
    return sorted(out)


def group_by_month(obs):
    by = defaultdict(list)
    for d, v in obs:
        by[d[:7]].append((d, v))
    return {m: sorted(rows) for m, rows in by.items()}


def monthly_rules(obs):
    by = group_by_month(obs)
    out = {}
    for name in ('last', 'first', 'mean', 'median', 'last_wednesday'):
        vals = {}
        for m, rows in by.items():
            if name == 'last':
                vals[m] = rows[-1][1]
            elif name == 'first':
                vals[m] = rows[0][1]
            elif name == 'mean':
                vals[m] = sum(v for _, v in rows) / len(rows)
            elif name == 'median':
                vals[m] = statistics.median(v for _, v in rows)
            else:
                wed = [(d, v) for d, v in rows if datetime.strptime(d, '%Y-%m-%d').weekday() == 2]
                if wed:
                    vals[m] = wed[-1][1]
        out[name] = vals
    return out


def score_rule(runtime, derived):
    common = sorted(set(runtime) & set(derived))
    if not common:
        return {'overlap': 0, 'exact': 0, 'exact_ratio': 0.0, 'mae': None, 'max_abs_diff': None}
    diffs = [runtime[m] - derived[m] for m in common]
    exact = sum(1 for x in diffs if abs(x) <= 1e-9)
    return {
        'overlap': len(common),
        'exact': exact,
        'exact_ratio': exact / len(common),
        'mae': sum(abs(x) for x in diffs) / len(diffs),
        'max_abs_diff': max(abs(x) for x in diffs),
        'runtime_last_month': common[-1],
        'runtime_last_value': runtime[common[-1]],
        'derived_last_value': derived[common[-1]],
    }


def recent_window_scores(runtime, derived):
    common=sorted(set(runtime)&set(derived))
    out={}
    for n in (12,24,36,60):
        months=common[-n:] if len(common)>=n else common
        diffs=[runtime[m]-derived[m] for m in months]
        exact=sum(1 for x in diffs if abs(x)<=1e-9)
        out[str(n)]={
            'overlap':len(months),
            'exact':exact,
            'exact_ratio': exact/len(months) if months else 0.0,
            'mae': sum(abs(x) for x in diffs)/len(diffs) if diffs else None,
            'max_abs_diff': max((abs(x) for x in diffs),default=None),
            'first_month': months[0] if months else None,
            'last_month': months[-1] if months else None,
        }
    return out


def mismatch_details(runtime, obs, rule='last'):
    by = group_by_month(obs)
    out = []
    for month in sorted(set(runtime) & set(by)):
        rows = by[month]
        if rule=='last':
            official_date, official_value = rows[-1]
        else:
            wed=[(d,v) for d,v in rows if datetime.strptime(d,'%Y-%m-%d').weekday()==2]
            if not wed:
                continue
            official_date, official_value=wed[-1]
        rv = runtime[month]
        if abs(rv - official_value) <= 1e-9:
            continue
        exact_daily = [{'date': d, 'value': v} for d, v in rows if abs(rv - v) <= 1e-9]
        nearest_date, nearest_value = min(rows, key=lambda x: abs(rv - x[1]))
        out.append({
            'month': month,
            'runtime_value': rv,
            'official_date': official_date,
            'official_value': official_value,
            'diff_runtime_minus_official': rv - official_value,
            'exact_daily_matches': exact_daily,
            'nearest_daily_observation': {
                'date': nearest_date,
                'value': nearest_value,
                'abs_diff': abs(rv - nearest_value),
            },
        })
    return out


def main():
    row, runtime = runtime_series()
    discovered = discover_candidates()
    results = []
    actual_obs=None
    actual_result=None
    for score, sid, label, meta in discovered:
        try:
            obs = fetch_observations(sid)
        except Exception as exc:
            results.append({'series_id': sid, 'label': label, 'discovery_score': score, 'fetch_error': repr(exc)})
            continue
        if not obs:
            continue
        rules = monthly_rules(obs)
        rule_scores = {name: score_rule(runtime, vals) for name, vals in rules.items()}
        best_name, best = max(rule_scores.items(), key=lambda kv: (kv[1]['exact_ratio'], kv[1]['overlap'], -(kv[1]['mae'] or 1e99)))
        result={
            'series_id': sid,
            'label': label,
            'discovery_score': score,
            'observation_count': len(obs),
            'first_date': obs[0][0],
            'latest_date': obs[-1][0],
            'latest_value': obs[-1][1],
            'best_rule': best_name,
            'best_score': best,
            'all_rule_scores': rule_scores,
        }
        if sid.upper() == 'ACTUAL':
            actual_obs=obs
            actual_result=result
            result['last_rule_recent_windows']=recent_window_scores(runtime,rules['last'])
        results.append(result)
    results.sort(key=lambda x: (-float((x.get('best_score') or {}).get('exact_ratio', 0)), -int((x.get('best_score') or {}).get('overlap', 0))))

    last_score=((actual_result or {}).get('all_rule_scores') or {}).get('last') or {}
    last_windows=(actual_result or {}).get('last_rule_recent_windows') or {}
    last_mismatches=mismatch_details(runtime,actual_obs,'last') if actual_obs else []
    wed_mismatches=mismatch_details(runtime,actual_obs,'last_wednesday') if actual_obs else []

    exact_month_end = (
        actual_result is not None
        and int(last_score.get('overlap',0)) >= 24
        and float(last_score.get('exact_ratio',0)) == 1.0
    )
    recent_exact = (
        (last_windows.get('24') or {}).get('exact_ratio') == 1.0
        and (last_windows.get('12') or {}).get('exact_ratio') == 1.0
    )
    if exact_month_end:
        status='EXACT_ACTUAL_MONTH_END_PROVEN'
    elif recent_exact and last_score.get('exact_ratio',0) >= 0.85:
        status='OFFICIAL_SERIES_IDENTIFIED_HISTORICAL_VINTAGE_DRIFT_PENDING'
    else:
        status='DIAGNOSTIC_ONLY_NO_PROMOTION'

    report = {
        'schema': 'GMFQ_LIQUIDITY_CAD_SETTLEMENT_DIAGNOSTIC_V1',
        'status': status,
        'source_contract': {
            'publisher': 'Bank of Canada',
            'series_family': 'Lynx settlement balances — Actual',
            'series_id_candidate': 'ACTUAL',
            'source_page': SOURCE_PAGE,
            'documented_monthly_display_rule': DOCUMENTED_MONTHLY_RULE,
            'runtime_empirical_rule_candidate':'last available official ACTUAL observation in each month',
        },
        'runtime': {
            'label': row.get('label'),
            'count': len(runtime),
            'first_month': min(runtime),
            'last_month': max(runtime),
            'last_value': runtime[max(runtime)],
            'raw_last_date': row.get('last_date'),
            'raw_last_value': row.get('last_value'),
        },
        'candidate_count': len(discovered),
        'results': results[:20],
        'actual_result': actual_result,
        'actual_month_end_mismatches': last_mismatches,
        'actual_month_end_mismatch_count': len(last_mismatches),
        'actual_last_wednesday_mismatch_count': len(wed_mismatches),
        'recent_month_end_windows': last_windows,
        'promotion_eligible': exact_month_end,
        'revision_contract_pending': status=='OFFICIAL_SERIES_IDENTIFIED_HISTORICAL_VINTAGE_DRIFT_PENDING',
        'promotion_performed': False,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
