#!/usr/bin/env python3
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEATMAP = ROOT / 'live_data/sections/MACRO_THERMOMETER_DATA.json'
SERIES = ROOT / 'live_data/sections/MACRO_SERIES.json'
D_FILE = ROOT / 'live_data/sections/D.json'
OUT = ROOT / 'validation/MACRO_UNIFIED_AUDIT_V1.json'

CCYS = ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
DIMS = ['inflation','labour']
LABELS = [(0,20,'MOLTO_FREDDO'),(20,40,'FREDDO'),(40,60,'NORMALE'),(60,80,'CALDO'),(80,101,'MOLTO_CALDO')]

# V1 separates structural integrity from external freshness. Only a reusable
# official-source adapter may later emit NO_CHANGE / UPDATE_AVAILABLE.
ADAPTER_STATUS = {c: {d: 'WITHHOLD_EXTERNAL' for d in DIMS} for c in CCYS}
ADAPTER_STATUS['JPY']['labour'] = 'VALIDATED_SNAPSHOT_NO_LIVE_ADAPTER'


def midrank_percentile(values):
    x = values[-1]
    less = sum(v < x for v in values)
    equal = sum(v == x for v in values)
    return round((less + 0.5 * equal) / len(values) * 100, 1)


def temp_label(p):
    for lo, hi, label in LABELS:
        if lo <= p < hi:
            return label
    raise ValueError(f'percentile out of range: {p}')


def direction(values):
    if len(values) < 2: return 'WITHHELD'
    d = values[-1] - values[-2]
    if d > 0: return 'SALE'
    if d < 0: return 'SCENDE'
    return 'STABILE'


def acceleration(values):
    if len(values) < 3: return 'WITHHELD'
    d1 = values[-1] - values[-2]
    d0 = values[-2] - values[-3]
    eps = 1e-12
    if abs(d1) < eps and abs(d0) < eps: return 'STABILE'
    if d1 > d0 + eps: return 'ACCELERA'
    if d1 < d0 - eps: return 'RALLENTA'
    return 'STABILE'


def numeric_values(seq):
    out = []
    if not isinstance(seq, list): return out
    for v in seq:
        if isinstance(v, (int, float)):
            out.append(float(v)); continue
        if isinstance(v, dict):
            found = None
            for k in ('value','v','obs_value','y'):
                if isinstance(v.get(k), (int,float)):
                    found = float(v[k]); break
            if found is not None: out.append(found)
    return out


def candidate_series_dicts(series_doc):
    hits = []
    def walk(x, path=''):
        if isinstance(x, dict):
            for key in ('history','values','observations','data'):
                vals = numeric_values(x.get(key))
                if vals:
                    hits.append((path, x, vals, key))
                    break
            for k,v in x.items():
                walk(v, f'{path}.{k}' if path else k)
        elif isinstance(x, list):
            for i,v in enumerate(x):
                walk(v, f'{path}[{i}]')
    walk(series_doc)
    return hits


def seq_close(a, b, tol=1e-9):
    return len(a) == len(b) and all(math.isclose(x,y,rel_tol=0,abs_tol=tol) for x,y in zip(a,b))


def find_series_entry(series_doc, ccy, series_id, heat_history):
    # Preferred explicit ID if present.
    id_hits = []
    def walk_id(x, path=''):
        if isinstance(x, dict):
            if x.get('series_id') == series_id:
                id_hits.append((path, x, None, 'series_id'))
            for k,v in x.items(): walk_id(v, f'{path}.{k}' if path else k)
        elif isinstance(x, list):
            for i,v in enumerate(x): walk_id(v, f'{path}[{i}]')
    walk_id(series_doc)
    if len(id_hits) == 1:
        p,d,_,_ = id_hits[0]
        for key in ('history','values','observations','data'):
            vals = numeric_values(d.get(key))
            if vals: return p,d,vals,key,'ID'

    # MACRO_SERIES does not consistently retain source series IDs. Cross-link by
    # exact history or suffix match against the heatmap's canonical numeric history.
    hh = [float(v) for v in heat_history]
    exact = []
    suffix = []
    for p,d,vals,key in candidate_series_dicts(series_doc):
        if seq_close(vals, hh):
            exact.append((p,d,vals,key,'EXACT_HISTORY'))
        elif len(vals) >= len(hh) and seq_close(vals[-len(hh):], hh):
            suffix.append((p,d,vals,key,'HISTORY_SUFFIX'))
        elif len(hh) >= len(vals) and len(vals) >= 12 and seq_close(hh[-len(vals):], vals):
            suffix.append((p,d,vals,key,'SERIES_SUFFIX'))
    hits = exact if exact else suffix
    if len(hits) != 1:
        raise AssertionError(f'{ccy}/{series_id}: expected one MACRO_SERIES history match, got exact={len(exact)} suffix={len(suffix)}')
    return hits[0]


def main():
    heat = json.loads(HEATMAP.read_text())
    series = json.loads(SERIES.read_text())
    d_before = D_FILE.read_bytes()

    rows = []
    issues = []
    for ccy in CCYS:
        c = heat['currencies'][ccy]
        for dim in DIMS:
            h = c[dim]
            values = [float(v) for v in h['history']]
            if not values:
                issues.append(f'{ccy}/{dim}: empty history'); continue
            sid = h['series_id']
            try:
                spath, s, svals, skey, match_mode = find_series_entry(series, ccy, sid, values)
            except Exception as e:
                issues.append(str(e));
                spath, svals, skey, match_mode = None, [], None, 'NO_MATCH'

            latest = float(h['latest_value'])
            if not math.isclose(values[-1], latest, rel_tol=0, abs_tol=1e-9):
                issues.append(f'{ccy}/{dim}: heatmap latest != heatmap history[-1]')
            if svals and not math.isclose(svals[-1], latest, rel_tol=0, abs_tol=1e-9):
                issues.append(f'{ccy}/{dim}: MACRO_SERIES latest != heatmap latest')

            calc_p = midrank_percentile(values)
            calc_t = temp_label(calc_p)
            calc_dir = direction(values)
            calc_acc = acceleration(values)
            checks = (
                ('percentile', float(h['percentile']), calc_p),
                ('temperature_label', h['temperature_label'], calc_t),
                ('direction', h['direction'], calc_dir),
                ('acceleration', h['acceleration'], calc_acc),
            )
            for name, actual, expected in checks:
                if actual != expected:
                    issues.append(f'{ccy}/{dim}: {name}={actual} expected={expected}')

            rows.append({
                'currency': ccy,
                'dimension': dim,
                'series_id': sid,
                'source': h.get('source'),
                'frequency': h.get('frequency'),
                'as_of': h.get('as_of'),
                'latest_value': latest,
                'history_count': len(values),
                'computed_percentile': calc_p,
                'computed_temperature': calc_t,
                'computed_direction': calc_dir,
                'computed_acceleration': calc_acc,
                'macro_series_path': spath,
                'macro_series_value_key': skey,
                'macro_series_match_mode': match_mode,
                'adapter_status': ADAPTER_STATUS[ccy][dim],
                'external_freshness': 'WITHHELD' if ADAPTER_STATUS[ccy][dim] != 'LIVE_ADAPTER_READY' else 'PENDING_CHECK'
            })

    if D_FILE.read_bytes() != d_before:
        issues.append('D.json changed during read-only audit')

    out = {
        'schema_version': 'GMFQ_MACRO_UNIFIED_AUDIT_V1',
        'status': 'PASS' if not issues else 'FAIL',
        'policy': {
            'read_only': True,
            'd_macro_frozen': True,
            'external_freshness_rule': 'Only a canonical reusable official-source adapter may emit NO_CHANGE or UPDATE_AVAILABLE. Otherwise WITHHOLD.',
            'series_count_expected': 16,
        },
        'summary': {
            'series_checked': len(rows),
            'structural_issues': len(issues),
            'live_adapters_ready': sum(r['adapter_status']=='LIVE_ADAPTER_READY' for r in rows),
            'validated_snapshot_without_live_adapter': sum(r['adapter_status']=='VALIDATED_SNAPSHOT_NO_LIVE_ADAPTER' for r in rows),
            'withhold_external': sum(r['adapter_status']=='WITHHOLD_EXTERNAL' for r in rows),
        },
        'issues': issues,
        'series': rows,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(out['summary'], indent=2))
    if issues:
        for x in issues: print('ISSUE:', x)
        raise SystemExit(1)

if __name__ == '__main__':
    main()
