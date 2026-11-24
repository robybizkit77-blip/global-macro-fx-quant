#!/usr/bin/env python3
import json
import math
import re
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


def extract_single_series(payload, expected_key):
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
    exact = [item for item in candidates if item[0] == expected_key]
    if len(exact) != 1:
        raise RuntimeError(f'Expected one usable SNB series for {expected_key}, found {len(exact)}')
    return exact[0]


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


def monthly_observations(values, today):
    dates = [stamp for stamp, _ in values]
    if (not all(re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', stamp) for stamp in dates)
            or len(dates) != len(set(dates)) or max(dates) >= today.strftime('%Y-%m')):
        raise RuntimeError('SNB returned invalid, repeated or future monthly periods')
    return dict(sorted(values))


def previous_month_value(values, stamp, lag):
    year, month = map(int, stamp.split('-'))
    year, month = divmod(year * 12 + month - 1 - lag, 12)
    return values.get(f'{year:04}-{month + 1:02}')


RATE_URL = 'https://data.snb.ch/api/cube/zikredlauf/data/json/en'
RATE_DIMENSIONS = 'https://data.snb.ch/api/cube/zikredlauf/dimensions/en'
RATE_SOURCE = 'https://data.snb.ch/en/topics/ziredev/cube/zikredlauf'
RATE_KEY = 'EPB@SNB.zikredlauf{FI,L16M,MP0}'
COUNT_KEY = 'EPB@SNB.zikredlauf{FI,L16M,AK}'


def parse_new_loan_rates(dimensions,payload,today):
    expected = {'D0':('FI','Investment loans with fixed interest rates'),
                'D1':('L16M','Maturity of over 1 month up to 6 months'),
                'D2':('MP0','Mean value in %')}
    dims = {d['id']:d for d in dimensions['dimensions']}
    if dimensions.get('cubeId')!='zikredlauf':
        raise RuntimeError('Wrong SNB rate cube')
    for dim,(key,label) in expected.items():
        matches=[x for x in dims[dim]['dimensionItems'] if x['id']==key and x['name']==label]
        if len(matches)!=1:raise RuntimeError('SNB loan-rate dimension mismatch: '+dim)
    if not any(x['id']=='AK' and x['name']=='Number of loan agreements' for x in dims['D2']['dimensionItems']):
        raise RuntimeError('SNB count dimension mismatch')
    _,rate_meta,rates=extract_single_series(payload,RATE_KEY)
    _,count_meta,counts=extract_single_series(payload,COUNT_KEY)
    if any(x.get('frequency')!='P1M' or x.get('scale')!='' for x in (rate_meta,count_meta)):
        raise RuntimeError('SNB rate/count metadata mismatch')
    rate=monthly_observations(rates,today);count=monthly_observations(counts,today)
    if not all(-5<=v<=25 for v in rate.values()) or not all(v>=0 and v.is_integer() for v in count.values()):
        raise RuntimeError('SNB rate or count range invalid')
    if max(rate)!=max(count):
        raise RuntimeError('SNB rate/count latest observations differ')
    dates=sorted(set(rate)&set(count))[-36:]
    if len(dates)<6 or any(count[d]<1 for d in dates):
        raise RuntimeError('SNB loan rate/count overlap inadequate')
    latest=dates[-1]
    age=(today.date()-datetime.strptime(latest,'%Y-%m').date()).days
    if age>155:raise RuntimeError('SNB loan-rate release stale')
    return {'series_id':RATE_KEY,'count_series_id':COUNT_KEY,'source_url':RATE_SOURCE,
            'frequency':'M','unit':'percent_per_annum','proxy_kind':'loan_price_not_lending_standards',
            'product':'fixed_rate_investment_loans','maturity':'over_1_to_6_months',
            'dates':dates,'values':[rate[d] for d in dates],'contract_counts':[int(count[d]) for d in dates],
            'latest_observation':latest,'eligible_for_fx_core':False,'eligible_for_backtest':False,
            'first_release_pit_verified':False}


def fetch_new_loan_rates(today):
    dimensions,_=get_json(RATE_DIMENSIONS)
    payload,_=get_json(RATE_URL,{'dimSel':'D0(FI),D1(L16M),D2(MP0,AK)',
          'fromDate':'2023-01','toDate':today.strftime('%Y-%m')})
    return parse_new_loan_rates(dimensions,payload,today)


def main():
    today = datetime.now(timezone.utc)
    bounds = {'fromDate': f'{today.year - 1}-01', 'toDate': today.strftime('%Y-%m')}
    credit_payload, credit_request = get_json(CREDIT_URL, {
        'dimSel': CREDIT_DIMSEL,
        **bounds,
    })
    credit_key, credit_meta, credit_vals = extract_single_series(
        credit_payload, 'EPB@SNB.bakredinausbm{AV1,A,T1,B}'
    )
    if credit_meta.get('frequency') != 'P1M' or credit_meta.get('unit') != 'In CHF millions' or credit_meta.get('scale') != '':
        raise RuntimeError('Unexpected SNB credit frequency or unit')
    credit_vals = monthly_observations(credit_vals, today)
    c_date = max(credit_vals)
    c_value = credit_vals[c_date]
    c_prev = previous_month_value(credit_vals, c_date, 1)
    c_3m = previous_month_value(credit_vals, c_date, 3)
    if not (100000 <= c_value <= 1000000):
        raise RuntimeError(f'CHF credit value outside plausibility band: {c_value}')

    sight_payload, sight_request = get_json(SIGHT_URL, {
        'dimSel': SIGHT_DIMSEL,
        **bounds,
    })
    sight_key, sight_meta, sight_vals = extract_single_series(
        sight_payload, 'BSTA@SNB.MONA_U.BIL.AKT.FMI.GGU{U,T,T,A40}'
    )
    if sight_meta.get('frequency') != 'P1M' or sight_meta.get('unit') != 'CHF' or sight_meta.get('scale') != '3':
        raise RuntimeError('Unexpected SNB sight deposits frequency or unit')
    sight_vals = monthly_observations(sight_vals, today)
    s_date = max(sight_vals)
    s_raw = sight_vals[s_date]
    s_prev_raw = previous_month_value(sight_vals, s_date, 1)
    s_3m_raw = previous_month_value(sight_vals, s_date, 3)
    # SNB metadata says unit CHF, exponent 3; residual layer stores CHF millions.
    s_value = s_raw / 1000.0
    s_prev = s_prev_raw / 1000.0 if s_prev_raw is not None else None
    s_3m = s_3m_raw / 1000.0 if s_3m_raw is not None else None
    if not (100000 <= s_value <= 1000000):
        raise RuntimeError(f'CHF sight-deposit value outside plausibility band after /1000: {s_value}')

    doc = json.loads(OUT.read_text(encoding='utf-8'))
    if doc.get('official_lanes_untouched') is not True:
        raise RuntimeError('Residual governance is not fail-closed')

    original = json.loads(json.dumps(doc))
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
        'official_canonical_untouched': True,
        'interpretation': 'Official SNB series proxy, auto-refreshed and rescaled from CHF thousands to CHF millions. Use direction/momentum only; runtime level mismatch remains explicit.'
    })

    rate_status={'status':'WITHHELD'}
    try:
        rate=fetch_new_loan_rates(today)
        prior=original['lanes']['CHF.credit'].get('lending_rate_proxy')
        if prior and rate['latest_observation']<prior['latest_observation']:
            raise RuntimeError('SNB loan rate rolled back')
        credit['lending_rate_proxy']=rate
        rate_status={'status':'VERIFIED','latest_observation':rate['latest_observation'],
                     'value':rate['values'][-1],'contracts':rate['contract_counts'][-1]}
    except (OSError,RuntimeError,ValueError,KeyError,TypeError) as exc:
        rate_status['reason']=str(exc)[:300]
        if credit.get('lending_rate_proxy'):
            rate_status['retained_observation']=credit['lending_rate_proxy']['latest_observation']

    for name in ('CHF.credit', 'CHF.sight_deposits'):
        lane, previous = doc['lanes'][name], original['lanes'][name]
        if lane['proxy_as_of'] < previous['proxy_as_of']:
            raise RuntimeError(f'{name}: source predates the published observation')
        if lane['source_last_update'].get('status') == 'UNAVAILABLE_NON_BLOCKING':
            lane['source_last_update'] = (previous.get('source_last_update') if
                                          lane['proxy_as_of'] == previous['proxy_as_of'] else
                                          {'status': 'UNAVAILABLE_NON_BLOCKING'})
        # Query bounds roll with the calendar. They are not evidence of a release.
        if {k: v for k, v in lane.items() if k != 'source_endpoint'} == {
                k: v for k, v in previous.items() if k != 'source_endpoint'}:
            lane['source_endpoint'] = previous['source_endpoint']
        if lane != previous:
            lane['fetched_at_utc'] = today.isoformat().replace('+00:00', 'Z')
    if doc != original:
        temp = OUT.with_suffix('.tmp')
        temp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        temp.replace(OUT)
    print(json.dumps({
        'status': 'PASS',
        'lending_rate_proxy': rate_status,
        'credit': {'as_of': c_date, 'value': credit['proxy_value'], 'change_1m_pct': credit['change_1m_pct'], 'key': credit_key},
        'sight_deposits': {'as_of': s_date, 'value': sight['proxy_value'], 'change_1m_pct': sight['change_1m_pct'], 'key': sight_key},
        'official_canonical_untouched': True,
    }))


if __name__ == '__main__':
    main()
