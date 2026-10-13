#!/usr/bin/env python3
import csv
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

POLICY = Path('validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json')
LIQ = Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT = Path('validation/liquidity-eur-ecb-candidates.json')
BASE = 'https://data-api.ecb.europa.eu/service/data'

SERIES = {
    'EUR.liquidity': {
        'dataset': 'ILM',
        'key': 'D.U2.C.EXLIQ.U2.EUR',
        'full_key': 'ILM.D.U2.C.EXLIQ.U2.EUR',
        'runtime_path': ('EUR', 'liquidity'),
        'frequency': 'Daily',
        'policy_revalidation': False,
    },
    'EUR.money': {
        'dataset': 'BSI',
        'key': 'M.U2.Y.V.M30.X.1.U2.2300.Z01.E',
        'full_key': 'BSI.M.U2.Y.V.M30.X.1.U2.2300.Z01.E',
        'runtime_path': ('EUR', 'money'),
        'frequency': 'Monthly',
        'policy_revalidation': True,
    },
}


def normalize_date(value, frequency):
    text = str(value or '').strip()
    if frequency == 'Daily':
        return text[:10]
    if frequency == 'Monthly':
        return text[:7]
    return text


def fetch_csv(dataset, key):
    params = urllib.parse.urlencode({'format': 'csvdata', 'startPeriod': '2026-01-01'})
    url = f'{BASE}/{dataset}/{key}?{params}'
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'global-macro-fx-quant/1.0',
            'Accept': 'text/csv,application/vnd.sdmx.data+csv;version=2.0.0',
        },
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        text = response.read().decode('utf-8-sig')
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise SystemExit(f'ECB returned no rows for {dataset}/{key}')
    return url, rows


def parse_rows(rows, frequency):
    parsed = []
    for row in rows:
        date_raw = row.get('TIME_PERIOD') or row.get('TIME_PERIOD_START') or row.get('TIME_PERIOD_START_DATE')
        value_raw = row.get('OBS_VALUE')
        if not date_raw or value_raw in (None, ''):
            continue
        try:
            value = float(value_raw)
        except ValueError:
            continue
        date = normalize_date(date_raw, frequency)
        parsed.append((date, value))
    if not parsed:
        raise SystemExit('ECB CSV contained no parseable observations')
    dedup = {}
    for date, value in parsed:
        if date in dedup and abs(dedup[date] - value) > 1e-9:
            raise SystemExit(f'conflicting ECB observations for {date}: {dedup[date]} vs {value}')
        dedup[date] = value
    return sorted(dedup.items())


def close_enough(a, b):
    return abs(a - b) <= max(1e-6, abs(b) * 1e-9)


def main():
    policy = json.loads(POLICY.read_text(encoding='utf-8'))
    liq = json.loads(LIQ.read_text(encoding='utf-8'))
    results = {}

    for policy_key, spec in SERIES.items():
        cfg = policy['mapped'][policy_key]
        policy_key_matches = cfg.get('series_key') == spec['full_key']
        if not policy_key_matches and not spec.get('policy_revalidation'):
            raise SystemExit(f'{policy_key} policy series mismatch: {cfg.get("series_key")} != {spec["full_key"]}')
        if cfg.get('automation_ready') is not True:
            raise SystemExit(f'{policy_key} must be automation-ready before collection')

        runtime = liq[spec['runtime_path'][0]][spec['runtime_path'][1]]
        runtime_date = normalize_date(runtime['last_date'], spec['frequency'])
        runtime_value = float(runtime['last_value'])

        url, rows = fetch_csv(spec['dataset'], spec['key'])
        parsed = parse_rows(rows, spec['frequency'])
        matches = [value for date, value in parsed if date == runtime_date]
        if len(matches) != 1:
            raise SystemExit(f'{policy_key}: expected one official observation for runtime date {runtime_date}, got {len(matches)}')
        official_runtime_value = matches[0]
        if not close_enough(official_runtime_value, runtime_value):
            raise SystemExit(
                f'{policy_key}: runtime/source mismatch on {runtime_date}: '
                f'runtime={runtime_value}, source={official_runtime_value}'
            )

        latest_date, latest_value = parsed[-1]
        if latest_date < runtime_date:
            raise SystemExit(f'{policy_key}: official source regressed behind runtime: {latest_date} < {runtime_date}')
        if latest_date > normalize_date(policy['as_of'], spec['frequency']):
            raise SystemExit(f'{policy_key}: future official observation relative to policy as_of: {latest_date}')

        results[policy_key] = {
            'source': {
                'publisher': 'European Central Bank / ESCB',
                'api': 'ECB Data API',
                'series_id': spec['full_key'],
                'url': url,
                'frequency': spec['frequency'],
            },
            'policy_series_id': cfg.get('series_key'),
            'policy_series_matches_candidate': policy_key_matches,
            'policy_revalidation_required': not policy_key_matches,
            'runtime': {'last_date': runtime_date, 'last_value': runtime_value},
            'official_runtime_value': official_runtime_value,
            'runtime_match_confirmed': True,
            'latest_date': latest_date,
            'latest_value': latest_value,
            'candidate_update_available': latest_date > runtime_date,
            'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        }

    receipt = {
        'schema': 'GMFQ_LIQUIDITY_EUR_ECB_CANDIDATES_V1',
        'policy_as_of': policy['as_of'],
        'series_count': len(results),
        'results': results,
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        'publication_performed': False,
        'runtime_mutated': False,
    }
    OUT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
