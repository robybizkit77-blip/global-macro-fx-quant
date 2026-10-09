#!/usr/bin/env python3
import copy
import json
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    s = p.read_text()
    n = s.count(old)
    assert n == 1, (path, n, old[:100])
    p.write_text(s.replace(old, new, 1))


adapter = 'validation/sources/us_bls_core_macro.py'
replace_once(
    adapter,
    '    cpi_yoy = yoy_from_index(cpi_index)\n    if len(labour) < 2:\n',
    '    cpi_yoy = yoy_from_index(cpi_index)\n    cpi_index_by_date = dict(cpi_index)\n    if len(labour) < 2:\n',
)
replace_once(
    adapter,
    '            "value": latest_inf[1],\n            "source": inf_source,\n',
    '            "value": latest_inf[1],\n            "series_value": cpi_index_by_date[latest_inf[0]],\n            "series_unit": "Index 1982-1984=100",\n            "source": inf_source,\n',
)
replace_once(
    adapter,
    '            "prior_value": prior_inf[1] if prior_inf else None,\n            "calculation": "100 * (CUSR0000SA0_t / CUSR0000SA0_t-12 - 1)",\n',
    '            "prior_value": prior_inf[1] if prior_inf else None,\n            "latest_index": cpi_index_by_date[latest_inf[0]],\n            "prior_year_index": cpi_index_by_date[f"{int(latest_inf[0][:4])-1:04d}-{latest_inf[0][5:7]}"],\n            "calculation": "100 * (CUSR0000SA0_t / CUSR0000SA0_same_month_prior_year - 1)",\n',
)

sp = Path('live_data/sections/MACRO_SERIES.json')
hp = Path('live_data/sections/MACRO_THERMOMETER_DATA.json')
series = json.loads(sp.read_text())
before_series = copy.deepcopy(series)
heat = json.loads(hp.read_text())
before_heat = copy.deepcopy(heat)
row = next(r for r in series['USD'] if r.get('id') == 'US_CPIAUCSL_history_value')
dates = [str(x)[:7] for x in row['dates']]
vals = [float(x) for x in row['values']]
by = dict(zip(dates, vals))
assert row['last_date'][:7] == '2026-08'
assert abs(float(row['last_value']) - 334.131) < 1e-12
assert '2025-10' not in by

keyed = []
for d, v in zip(dates, vals):
    y, m = map(int, d.split('-'))
    prior = f'{y-1:04d}-{m:02d}'
    if prior in by:
        keyed.append((d, (v / by[prior] - 1.0) * 100.0))
repair = [(d, v) for d, v in keyed if d >= '2025-11']
assert [d for d, _ in repair] == [
    '2025-11','2025-12','2026-01','2026-02','2026-03',
    '2026-04','2026-05','2026-06','2026-07','2026-08'
], repair

h = heat['currencies']['USD']['inflation']
hist = [float(x) for x in h['history']]
assert len(hist) == 120
expected_old = [2.9883,3.002262,2.82868,2.664589,3.320206,3.947027,4.270033,3.72653,3.539751,3.712958]
assert all(abs(a-b) < 1e-6 for a,b in zip(hist[-10:], expected_old)), hist[-10:]
hist[-10:] = [v for _, v in repair]
h['history'] = hist
h['latest_value'] = hist[-1]
h['as_of'] = '2026-08-01'
heat['currencies']['USD'].setdefault('as_of_detail', {})['inflation'] = '2026-08-01'

below = sum(1 for x in hist if x < hist[-1])
equal = sum(1 for x in hist if x == hist[-1])
pct = round(100.0 * (below + 0.5 * equal) / len(hist), 1)
h['percentile'] = pct
h['temperature_score'] = pct
label = None
for t in heat['thresholds']:
    lo, hi = float(t['min']), float(t['max'])
    if lo <= pct < hi or (pct == 100.0 and hi == 100.0):
        label = str(t['label'])
        break
assert label is not None
h['temperature_label'] = label
d = hist[-1] - hist[-2]
h['direction'] = 'SALE' if d > 1e-12 else 'SCENDE' if d < -1e-12 else 'STABILE'
d1 = hist[-2] - hist[-3]
d2 = hist[-1] - hist[-2]
dd = d2 - d1
h['acceleration'] = 'ACCELERA' if dd > 1e-12 else 'RALLENTA' if dd < -1e-12 else 'STABILE'

assert series == before_series, 'raw MACRO_SERIES must remain unchanged'
for c in heat['currencies']:
    if c != 'USD':
        assert heat['currencies'][c] == before_heat['currencies'][c], c
for dim in heat['currencies']['USD']:
    if dim not in ('inflation', 'as_of_detail'):
        assert heat['currencies']['USD'][dim] == before_heat['currencies']['USD'][dim], dim
old_detail = before_heat['currencies']['USD'].get('as_of_detail', {})
new_detail = heat['currencies']['USD'].get('as_of_detail', {})
for k, v in old_detail.items():
    if k != 'inflation':
        assert new_detail.get(k) == v, (k, new_detail.get(k), v)

hp.write_text(json.dumps(heat, ensure_ascii=False, separators=(',', ':')) + '\n')
print(json.dumps({
    'status': 'PASS',
    'repair': repair,
    'latest': h['latest_value'],
    'percentile': pct,
    'temperature': label,
    'direction': h['direction'],
    'acceleration': h['acceleration'],
}, indent=2))
