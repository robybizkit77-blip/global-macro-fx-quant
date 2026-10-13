#!/usr/bin/env python3
import argparse
import io
import json
import re
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from pathlib import Path

URL = 'https://www.rba.gov.au/statistics/tables/xls/a03.xlsx'
SERIES_ID = 'AESAT'
RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
DEFAULT_OUT = Path('validation/liquidity-aud-es-balances-candidate.json')
NS = {'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL_NS = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
DOC_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def norm_date(v):
    if isinstance(v, (datetime, date)):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, str):
        s = v.strip()
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d %b %Y', '%d %B %Y'):
            try:
                return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
            except ValueError:
                pass
    return None


def excel_date(value):
    try:
        serial = float(value)
    except (TypeError, ValueError):
        return None
    if not 20000 <= serial <= 80000:
        return None
    return (date(1899, 12, 30) + timedelta(days=int(serial))).isoformat()


def fetch_workbook_bytes():
    req = urllib.request.Request(URL, headers={'User-Agent': 'GMFQ-validation/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    if len(body) < 10000:
        raise SystemExit(f'RBA A3 workbook unexpectedly small: {len(body)} bytes')
    return body


def runtime_series():
    rt = json.loads(RUNTIME.read_text(encoding='utf-8'))
    row = rt['AUD']['liquidity']
    out = {}
    for d, v in zip(row['dates'], row['values']):
        nd = norm_date(d)
        if not nd:
            raise SystemExit(f'unparseable runtime date {d!r}')
        out[nd] = float(v)
    if len(out) != len(row['dates']):
        raise SystemExit('duplicate AUD.liquidity runtime dates after normalization')
    return row, out


def infer_weekly_snapshot_contract(runtime):
    dates = sorted(runtime)
    if len(dates) < 12:
        raise SystemExit('insufficient AUD.liquidity runtime history to infer snapshot cadence')
    recent = [datetime.strptime(x, '%Y-%m-%d').date() for x in dates[-12:]]
    weekday = recent[-1].weekday()
    if any(x.weekday() != weekday for x in recent[-8:]):
        raise SystemExit('recent AUD.liquidity runtime does not preserve one weekly snapshot weekday')
    gaps = [(b - a).days for a, b in zip(recent[-8:-1], recent[-7:])]
    if any(g != 7 for g in gaps):
        raise SystemExit(f'recent AUD.liquidity runtime is not strict weekly cadence: {gaps}')
    return weekday, recent[-1].strftime('%A').upper()


def shared_strings(zf):
    path = 'xl/sharedStrings.xml'
    if path not in zf.namelist():
        return []
    root = ET.fromstring(zf.read(path))
    values = []
    for si in root.findall('a:si', NS):
        values.append(''.join(t.text or '' for t in si.iterfind('.//a:t', NS)))
    return values


def workbook_sheet_map(zf):
    wb = ET.fromstring(zf.read('xl/workbook.xml'))
    rels = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
    targets = {r.attrib['Id']: r.attrib['Target'] for r in rels.findall('r:Relationship', REL_NS)}
    out = {}
    for sheet in wb.findall('a:sheets/a:sheet', NS):
        rid = sheet.attrib.get(f'{{{DOC_REL}}}id')
        target = targets.get(rid, '')
        if not target:
            continue
        if target.startswith('/'):
            path = target.lstrip('/')
        elif target.startswith('xl/'):
            path = target
        else:
            path = 'xl/' + target.lstrip('./')
        out[path] = sheet.attrib.get('name', path)
    return out


def cell_value(cell, shared):
    ctype = cell.attrib.get('t')
    if ctype == 'inlineStr':
        return ''.join(t.text or '' for t in cell.iterfind('.//a:t', NS))
    v = cell.find('a:v', NS)
    if v is None or v.text is None:
        return None
    if ctype == 's':
        try:
            return shared[int(v.text)]
        except (ValueError, IndexError):
            raise SystemExit(f'invalid shared string index {v.text!r}')
    if ctype in {'str', 'e'}:
        return v.text
    try:
        return float(v.text)
    except ValueError:
        return v.text


def col_name(ref):
    m = re.match(r'([A-Z]+)', ref or '')
    return m.group(1) if m else None


def official_series(body):
    with zipfile.ZipFile(io.BytesIO(body)) as zf:
        shared = shared_strings(zf)
        sheet_names = workbook_sheet_map(zf)
        for path in sorted(p for p in zf.namelist() if p.startswith('xl/worksheets/sheet') and p.endswith('.xml')):
            root = ET.fromstring(zf.read(path))
            rows = []
            series_col = None
            series_row = None
            for row in root.findall('.//a:sheetData/a:row', NS):
                parsed = {}
                row_num = int(row.attrib.get('r', '0') or 0)
                for cell in row.findall('a:c', NS):
                    col = col_name(cell.attrib.get('r'))
                    if not col:
                        continue
                    value = cell_value(cell, shared)
                    parsed[col] = value
                    if row_num <= 40 and str(value or '').strip() == SERIES_ID:
                        series_col = col
                        series_row = row_num
                rows.append((row_num, parsed))
            if not series_col:
                continue
            values = {}
            for row_num, parsed in rows:
                if row_num <= series_row:
                    continue
                val = parsed.get(series_col)
                if not isinstance(val, (int, float)):
                    continue
                nd = None
                for col in ('A', 'B', 'C', 'D', 'E'):
                    raw = parsed.get(col)
                    nd = norm_date(raw) or excel_date(raw)
                    if nd:
                        break
                if nd:
                    values[nd] = float(val)
            if values:
                return sheet_names.get(path, path), values
    raise SystemExit(f'RBA A3 series {SERIES_ID} not found')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    args = parser.parse_args()
    out_path = Path(args.out)

    runtime_row, runtime = runtime_series()
    snapshot_weekday, snapshot_weekday_name = infer_weekly_snapshot_contract(runtime)
    sheet, official = official_series(fetch_workbook_bytes())
    common = sorted(set(runtime) & set(official))
    exact_dates = [d for d in common if abs(runtime[d] - official[d]) <= 1e-9]
    mismatches = [
        {'date': d, 'runtime': runtime[d], 'official': official[d], 'diff': runtime[d] - official[d]}
        for d in common if abs(runtime[d] - official[d]) > 1e-9
    ]
    if len(common) < 250:
        raise SystemExit(f'insufficient RBA/runtime overlap: {len(common)}')
    ratio = len(exact_dates) / len(common)
    if ratio < 0.98:
        raise SystemExit(f'RBA AESAT historical exact-match ratio below contract: {ratio:.4f}')
    runtime_last = max(runtime)
    if runtime_last not in official or abs(runtime[runtime_last] - official[runtime_last]) > 1e-9:
        raise SystemExit('latest runtime AUD ES balance does not match RBA AESAT exactly')
    recent = common[-20:]
    if any(abs(runtime[d] - official[d]) > 1e-9 for d in recent):
        raise SystemExit('recent 20-date AUD ES balance window is not exact')

    latest_official = max(official)
    eligible_dates = [
        d for d in sorted(official)
        if d > runtime_last and datetime.strptime(d, '%Y-%m-%d').date().weekday() == snapshot_weekday
    ]
    new_observations = [{'date': d, 'value': official[d]} for d in eligible_dates]
    latest_eligible = eligible_dates[-1] if eligible_dates else runtime_last
    latest_eligible_value = official[latest_eligible] if eligible_dates else runtime[runtime_last]

    receipt = {
        'schema': 'GMFQ_LIQUIDITY_AUD_ES_BALANCES_CANDIDATE_V1',
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        'source': {
            'publisher': 'Reserve Bank of Australia',
            'table': 'A3 — ES Balances and Repo Agreements',
            'series_id': SERIES_ID,
            'series_name': 'Total Exchange Settlement Balances',
            'frequency': 'DAILY',
            'unit': 'AUD million',
            'url': URL,
            'sheet': sheet,
        },
        'runtime': {
            'count': len(runtime),
            'last_date': runtime_last,
            'last_value': runtime[runtime_last],
            'declared_last_date': runtime_row.get('last_date'),
            'declared_last_value': runtime_row.get('last_value'),
        },
        'snapshot_contract': {
            'runtime_frequency': 'WEEKLY_SNAPSHOT',
            'weekday': snapshot_weekday,
            'weekday_name': snapshot_weekday_name,
            'inferred_from_recent_observations': 8,
            'interpolation_allowed': False,
        },
        'proof': {
            'overlap_count': len(common),
            'exact_match_count': len(exact_dates),
            'exact_match_ratio': ratio,
            'recent_20_exact': True,
            'mismatch_count': len(mismatches),
            'mismatches': mismatches,
            'runtime_last_matches_official': True,
        },
        'latest_date': latest_official,
        'latest_value': official[latest_official],
        'latest_eligible_snapshot_date': latest_eligible,
        'latest_eligible_snapshot_value': latest_eligible_value,
        'new_observations': new_observations,
        'candidate_update_available': bool(new_observations),
        'candidate_pipeline_ready': True,
        'publication_performed': False,
        'runtime_mutated': False,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
