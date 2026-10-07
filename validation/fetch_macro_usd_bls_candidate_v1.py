#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERIES_PATH = ROOT/'live_data'/'sections'/'MACRO_SERIES.json'
HEATMAP_PATH = ROOT/'live_data'/'sections'/'MACRO_THERMOMETER_DATA.json'
BLS_URL = 'https://api.bls.gov/publicAPI/v2/timeseries/data/'

MAP = {
    'labour': {
        'bls_series_id': 'LNS14000000',
        'runtime_series_id': 'UNRATE',
        'transformation': 'level',
        'unit': 'Percent',
    },
    'inflation': {
        'bls_series_id': 'CUSR0000SA0',
        'runtime_series_id': 'CPIAUCSL',
        'transformation': 'yoy_pct_from_index',
        'unit': 'Percent YoY',
    },
}


def load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def fetch_bls(start_year: int, end_year: int) -> dict[str, Any]:
    payload = json.dumps({
        'seriesid': [MAP['labour']['bls_series_id'], MAP['inflation']['bls_series_id']],
        'startyear': str(start_year),
        'endyear': str(end_year),
    }).encode('utf-8')
    req = urllib.request.Request(
        BLS_URL,
        data=payload,
        headers={'Content-Type':'application/json','User-Agent':'GMFQ-research-ingress/1.0'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except Exception as e:
        raise RuntimeError(f'BLS transport failure; no fallback permitted: {e}') from e
    try:
        data = json.loads(raw.decode('utf-8'))
    except Exception as e:
        raise RuntimeError(f'BLS response is not valid JSON: {e}') from e
    if data.get('status') != 'REQUEST_SUCCEEDED':
        raise RuntimeError(f"BLS request failed: status={data.get('status')} message={data.get('message')}")
    return data


def monthly_points(series: dict[str, Any]) -> dict[str, float]:
    out: dict[str,float] = {}
    for row in series.get('data') or []:
        p = str(row.get('period',''))
        y = str(row.get('year',''))
        if not (p.startswith('M') and len(p)==3 and p != 'M13' and y.isdigit()):
            continue
        m = int(p[1:])
        if not 1 <= m <= 12:
            continue
        try:
            v = float(row['value'])
        except Exception:
            continue
        out[f'{int(y):04d}-{m:02d}-01'] = v
    return out


def resolve_macro_series_id(series_rows: list[dict[str,Any]], runtime_series_id: str) -> str:
    token = runtime_series_id.upper()
    hits = [str(r.get('id')) for r in series_rows if isinstance(r,dict) and token in str(r.get('id','')).upper()]
    if len(hits) != 1:
        raise RuntimeError(f'Cannot resolve unique macro_series_id for {runtime_series_id}; hits={hits}')
    return hits[0]


def latest_date(points: dict[str,float]) -> str:
    if not points:
        raise RuntimeError('No monthly points returned by BLS')
    return max(points)


def build() -> dict[str, Any]:
    series = load(SERIES_PATH)
    heatmap = load(HEATMAP_PATH)
    usd_series = series.get('USD') or []
    h = heatmap['currencies']['USD']

    now = datetime.now(timezone.utc)
    bls = fetch_bls(now.year-1, now.year)
    rows = {str(s.get('seriesID')):s for s in (bls.get('Results') or {}).get('series',[])}
    expected = {v['bls_series_id'] for v in MAP.values()}
    if set(rows) != expected:
        raise RuntimeError(f'Unexpected BLS series set: got={sorted(rows)} expected={sorted(expected)}')

    labour_pts = monthly_points(rows[MAP['labour']['bls_series_id']])
    cpi_pts = monthly_points(rows[MAP['inflation']['bls_series_id']])

    labour_date = latest_date(labour_pts)
    labour_value = labour_pts[labour_date]
    cpi_date = latest_date(cpi_pts)
    y = int(cpi_date[:4]); m = int(cpi_date[5:7])
    prior = f'{y-1:04d}-{m:02d}-01'
    if prior not in cpi_pts:
        raise RuntimeError(f'Cannot compute CPI YoY: missing BLS prior-year index {prior}')
    cpi_value = round(100.0*(cpi_pts[cpi_date]/cpi_pts[prior]-1.0), 6)

    built=[]
    for dim, obs_date, value in (
        ('labour', labour_date, labour_value),
        ('inflation', cpi_date, cpi_value),
    ):
        cfg=MAP[dim]
        hr=h[dim]
        if str(hr.get('series_id')) != cfg['runtime_series_id']:
            raise RuntimeError(f"USD {dim} runtime series mismatch: {hr.get('series_id')} != {cfg['runtime_series_id']}")
        macro_id=resolve_macro_series_id(usd_series,cfg['runtime_series_id'])
        runtime_asof=str(hr.get('as_of'))
        if not runtime_asof:
            raise RuntimeError(f'USD {dim} runtime as_of missing')
        status='CANDIDATE_READY' if obs_date > runtime_asof else 'NO_UPDATE'
        if obs_date < runtime_asof:
            status='SOURCE_BEHIND_RUNTIME'
        candidate={
            'currency':'USD',
            'dimension':dim,
            'macro_series_id':macro_id,
            'observation_date':obs_date,
            'value':value,
            'unit':cfg['unit'],
            'source':f"U.S. Bureau of Labor Statistics Public Data API v2 ({cfg['bls_series_id']})",
            'series_id':cfg['runtime_series_id'],
            'frequency':'M',
            'transformation':cfg['transformation'],
            'source_series_id':cfg['bls_series_id'],
            'retrieved_at_utc':now.isoformat().replace('+00:00','Z'),
            'first_release_capture_certified':False,
            'first_release_note':'Current official BLS release is captured read-only; first-release immutability is not certified until release-time snapshot/provenance/apply is enabled.',
        }
        built.append({
            'dimension':dim,
            'status':status,
            'runtime_as_of':runtime_asof,
            'source_observation_date':obs_date,
            'candidate':candidate,
        })

    statuses=[x['status'] for x in built]
    overall = 'CANDIDATE_READY' if 'CANDIDATE_READY' in statuses else ('SOURCE_BEHIND_RUNTIME' if 'SOURCE_BEHIND_RUNTIME' in statuses else 'NO_UPDATE')
    return {
        'schema':'GMFQ_MACRO_USD_BLS_CANDIDATE_V1',
        'status':overall,
        'mode':'READ_ONLY_OFFICIAL_SOURCE_CANDIDATE',
        'source':{
            'provider':'U.S. Bureau of Labor Statistics',
            'endpoint':BLS_URL,
            'series_ids':[MAP['labour']['bls_series_id'],MAP['inflation']['bls_series_id']],
            'fallback_used':False,
        },
        'observations':built,
        'guards':{
            'writes_live_data':False,
            'writes_payload':False,
            'changes_engine_rules':False,
            'changes_oos_baseline':False,
            'production_promotion':False,
            'schedule_enabled':False,
            'first_release_capture_certified':False,
        }
    }


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',default='/tmp/macro-usd-bls-candidate-v1.json')
    a=ap.parse_args()
    out=build()
    pathlib.Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(out,indent=2,ensure_ascii=False))
    return 0 if out['status'] in {'NO_UPDATE','CANDIDATE_READY'} else 2

if __name__=='__main__':
    sys.exit(main())
