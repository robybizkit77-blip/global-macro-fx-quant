#!/usr/bin/env python3
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path('live_data/sections/ESTIMATED_RESIDUAL_GAPS.json')

CREDIT_URL = 'https://data.snb.ch/api/cube/bakredinausbm/data/json/en'
CREDIT_LAST_UPDATE = 'https://data.snb.ch/api/cube/bakredinausbm/lastUpdate'
CREDIT_DIMSEL = 'D0(AV1),D1(A),D2(T1),D3(B)'

SIGHT_URL = 'https://data.snb.ch/api/warehouse/cube/BSTA.SNB.MONA_U.BIL.AKT.FMI.GGU/data/json/en'
SIGHT_LAST_UPDATE = 'https://data.snb.ch/api/warehouse/cube/BSTA.SNB.MONA_U.BIL.AKT.FMI.GGU/lastUpdate'
SIGHT_DIMSEL = 'KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(T),WAEHRUNG(T),BANKENGRUPPE(A40)'


def get_json(base, params=None):
    url = base
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'User-Agent': 'GMFQ/1.0 SNB official residual proxy refresh',
        'Accept': 'application/json,text/plain,*/*',
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f'SNB HTTP {resp.status}: {url}')
        return json.load(resp), url


def extract_single_series(payload, expected_key_fragment=None):
    series = payload.get('timeseries') if isinstance(payload, dict) else None
    if not isinstance(series, list) or not series:
        raise RuntimeError('SNB payload has no timeseries')
    candidates = []
    for s in series:
        meta = s.get('metadata') or {}
        key = str(meta.get('key') or '')
        vals = s.get('values') or []
        valid = []
        for row in vals:
            try:
                value = float(row.get('value'))
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                valid.append((str(row.get('date')), value))
        if not valid:
            continue
        candidates.append((key, meta, valid))
    if expected_key_fragment:
        exact = [x for x in candidates if expected_key_fragment in x[0]]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            raise RuntimeError(f'Ambiguous SNB series for {expected_key_fragment}: {len(exact)}')
    if len(candidates) != 1:
        raise RuntimeError(f'Expected one usable SNB series, found {len(candidates)}')
    return candidates[0]


def pct(a, b):
    if b == 0:
        return None
    return round((a / b - 1.0) * 100.0, 4)


def last_update(url):
    try:
        payload, _ = get_json(url)
        return payload
    except Exception as exc:
        return {'status': 'UNAVAILABLE_NON_BLOCKING', 'error': str(exc)}


def main():
    credit_payload, credit_request = get_json(CREDIT_URL, {
        'dimSel': CREDIT_DIMSEL,
        'fromDate': '2025-01',
        'toDate': '2026-12',
    })
    credit_key, credit_meta, credit_vals = extract_single_series(
        credit_payload, 'bakredinausbm{AV1,A,T1,B}'
    )
    credit_vals.sort(key=lambda x: x[0])
    c_date, c_value = credit_vals[-1]
    c_prev = credit_vals[-2][1] if len(credit_vals) >= 2 else None
    c_3m = credit_vals[-4][1] if len(credit_vals) >= 4 else None
    if not (100000 <= c_value <= 1000000):
        raise RuntimeError(f'CHF credit value outside plausibility band: {c_value}')

    sight_payload, sight_request = get_json(SIGHT_URL, {
        'dimSel': SIGHT_DIMSEL,
        'fromDate': '2025-01',
        'toDate': '2026-12',
    })
    sight_key, sight_meta, sight_vals = extract_single_series(
        sight_payload, 'BSTA@SNB.MONA_U.BIL.AKT.FMI.GGU{U,T,T,A40}'
    )
    sight_vals.sort(key=lambda x: x[0])
    s_date, s_raw = sight_vals[-1]
    s_prev_raw = sight_vals[-2][1] if len(sight_vals) >= 2 else None
    s_3m_raw = sight_vals[-4][1] if len(sight_vals) >= 4 else None
    # SNB metadata says unit CHF, exponent 3; residual layer stores CHF millions.
    s_value = s_raw / 1000.0
    s_prev = s_prev_raw / 1000.0 if s_prev_raw is not None else None
    s_3m = s_3m_raw / 1000.0 if s_3m_raw is not None else None
    if not (100000 <= s_value <= 1000000):
        raise RuntimeError(f'CHF sight-deposit value outside plausibility band after /1000: {s_value}')

    doc = json.loads(OUT.read_text(encoding='utf-8'))
    if doc.get('official_lanes_untouched') is not True:
        raise RuntimeError('Residual governance is not fail-closed')

    credit = doc['lanes']['CHF.credit']
    credit.update({
        'status': 'ESTIMATED_ACTIVE_AUTO_REFRESH_OFFICIAL_PROXY',
        'confidence': 'B/C',
        'proxy_as_of': c_date,
        'proxy_value': round(c_value, 6),
        'change_1m_pct': pct(c_value, c_prev) if c_prev is not None else None,
        'change_3m_pct': pct(c_value, c_3m) if c_3m is not None else None,
        'source': 'SNB official API · cube bakredinausbm · AV1 | A | T1 | B',
        'source_endpoint': credit_request,
        'timeseries_key': credit_key,
        'source_metadata': credit_meta,
        'source_last_update': last_update(CREDIT_LAST_UPDATE),
        'fetched_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'official_canonical_untouched': True,
        'interpretation': 'Official SNB dimensional proxy, auto-refreshed. Use direction/momentum/turning point; absolute runtime equivalence remains unproven.'
    })

    sight = doc['lanes']['CHF.sight_deposits']
    sight.update({
        'status': 'ESTIMATED_ACTIVE_AUTO_REFRESH_OFFICIAL_PROXY',
        'confidence': 'C',
        'proxy_as_of': s_date,
        'proxy_value': round(s_value, 6),
        'change_1m_pct': pct(s_value, s_prev) if s_prev is not None else None,
        'change_3m_pct': pct(s_value, s_3m) if s_3m is not None else None,
        'source': 'SNB official API · Sight deposits with the SNB · U,T,T,A40',
        'source_endpoint': sight_request,
        'timeseries_key': sight_key,
        'source_metadata': sight_meta,
        'source_last_update': last_update(SIGHT_LAST_UPDATE),
        'fetched_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'official_canonical_untouched': True,
        'interpretation': 'Official SNB series proxy, auto-refreshed and rescaled from CHF thousands to CHF millions. Use direction/momentum only; runtime level mismatch remains explicit.'
    })

    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': 'PASS',
        'credit': {'as_of': c_date, 'value': credit['proxy_value'], 'change_1m_pct': credit['change_1m_pct'], 'key': credit_key},
        'sight_deposits': {'as_of': s_date, 'value': sight['proxy_value'], 'change_1m_pct': sight['change_1m_pct'], 'key': sight_key},
        'official_canonical_untouched': True,
    }))


if __name__ == '__main__':
    main()
