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
VALUE_TOL = 1e-5
PCT_TOL = 0.5

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
            for k in ('value','v','obs_value','y'):
                if isinstance(v.get(k), (int,float)):
                    out.append(float(v[k])); break
    return out


def candidate_series_dicts(series_doc):
    hits = []
    def walk(x, path=''):
        if isinstance(x, dict):
            for key in ('history','values','observations','data'):
                vals = numeric_values(x.get(key))
                if vals:
                    hits.append((path, x, vals, key)); break
            for k,v in x.items(): walk(v, f'{path}.{k}' if path else k)
        elif isinstance(x, list):
            for i,v in enumerate(x): walk(v, f'{path}[{i}]')
    walk(series_doc)
    return hits


def seq_close(a, b, tol=VALUE_TOL):
    return len(a) == len(b) and all(math.isclose(x,y,rel_tol=0,abs_tol=tol) for x,y in zip(a,b))


def resolve_series_crosslink(series_doc, series_id, heat_history):
    id_hits = []
    def walk_id(x, path=''):
        if isinstance(x, dict):
            if x.get('series_id') == series_id: id_hits.append((path,x))
            for k,v in x.items(): walk_id(v, f'{path}.{k}' if path else k)
        elif isinstance(x, list):
            for i,v in enumerate(x): walk_id(v, f'{path}[{i}]')
    walk_id(series_doc)
    if len(id_hits) == 1:
        p,d = id_hits[0]
        for key in ('history','values','observations','data'):
            vals = numeric_values(d.get(key))
            if vals: return p,vals,key,'ID'

    hh = [float(v) for v in heat_history]
    exact, suffix = [], []
    for p,d,vals,key in candidate_series_dicts(series_doc):
        if seq_close(vals, hh): exact.append((p,vals,key,'EXACT_HISTORY'))
        elif len(vals) >= len(hh) and seq_close(vals[-len(hh):], hh): suffix.append((p,vals,key,'HISTORY_SUFFIX'))
        elif len(hh) >= len(vals) and len(vals) >= 12 and seq_close(hh[-len(vals):], vals): suffix.append((p,vals,key,'SERIES_SUFFIX'))
    hits = exact if exact else suffix
    if len(hits) == 1: return hits[0]
    return None, [], None, 'UNRESOLVED'


def main():
    heat = json.loads(HEATMAP.read_text())
    series = json.loads(SERIES.read_text())
    d_before = D_FILE.read_bytes()

    rows, issues, warnings = [], [], []
    for ccy in CCYS:
        c = heat.get('currencies',{}).get(ccy)
        if not isinstance(c, dict):
            issues.append(f'{ccy}: missing currency block'); continue
        for dim in DIMS:
            h = c.get(dim)
            if not isinstance(h, dict):
                issues.append(f'{ccy}/{dim}: missing dimension block'); continue
            values = [float(v) for v in h.get('history',[]) if isinstance(v,(int,float))]
            if len(values) < 3:
                issues.append(f'{ccy}/{dim}: insufficient history'); continue
            sid = h.get('series_id')
            spath, svals, skey, match_mode = resolve_series_crosslink(series, sid, values)
            if match_mode == 'UNRESOLVED':
                warnings.append(f'{ccy}/{dim}: MACRO_SERIES cross-link unresolved; transformation mapping required')

            latest = float(h['latest_value'])
            if not math.isclose(values[-1], latest, rel_tol=0, abs_tol=VALUE_TOL):
                issues.append(f'{ccy}/{dim}: heatmap latest materially differs from history[-1]')
            if svals and not math.isclose(svals[-1], latest, rel_tol=0, abs_tol=VALUE_TOL):
                warnings.append(f'{ccy}/{dim}: MACRO_SERIES latest differs from heatmap latest; transformed/raw basis may differ')

            calc_p = midrank_percentile(values)
            stored_p = float(h['percentile'])
            calc_t = temp_label(stored_p)
            calc_dir = direction(values)
            calc_acc = acceleration(values)

            if abs(stored_p - calc_p) > PCT_TOL:
                issues.append(f'{ccy}/{dim}: percentile={stored_p} recomputed={calc_p} exceeds tolerance')
            if h['temperature_label'] != calc_t:
                issues.append(f"{ccy}/{dim}: temperature_label={h['temperature_label']} expected={calc_t}")
            if h['direction'] != calc_dir:
                issues.append(f"{ccy}/{dim}: direction={h['direction']} expected={calc_dir}")
            if h['acceleration'] != calc_acc:
                issues.append(f"{ccy}/{dim}: acceleration={h['acceleration']} expected={calc_acc}")

            rows.append({
                'currency': ccy,
                'dimension': dim,
                'series_id': sid,
                'source': h.get('source'),
                'frequency': h.get('frequency'),
                'as_of': h.get('as_of'),
                'latest_value': latest,
                'history_count': len(values),
                'stored_percentile': stored_p,
                'rounded_history_percentile': calc_p,
                'temperature': h['temperature_label'],
                'direction': h['direction'],
                'acceleration': h['acceleration'],
                'macro_series_path': spath,
                'macro_series_value_key': skey,
                'macro_series_match_mode': match_mode,
                'adapter_status': ADAPTER_STATUS[ccy][dim],
                'external_freshness': 'WITHHELD'
            })

    if len(rows) != 16: issues.append(f'series count={len(rows)} expected=16')
    if D_FILE.read_bytes() != d_before: issues.append('D.json changed during read-only audit')

    out = {
        'schema_version': 'GMFQ_MACRO_UNIFIED_AUDIT_V1',
        'status': 'PASS' if not issues else 'FAIL',
        'policy': {
            'read_only': True,
            'd_macro_frozen': True,
            'value_tolerance': VALUE_TOL,
            'percentile_tolerance_for_display_rounding': PCT_TOL,
            'unresolved_crosslink_is_warning': True,
            'external_freshness_rule': 'Only a canonical reusable official-source adapter may emit NO_CHANGE or UPDATE_AVAILABLE. Otherwise WITHHOLD.',
        },
        'summary': {
            'series_checked': len(rows),
            'structural_issues': len(issues),
            'warnings': len(warnings),
            'crosslinks_resolved': sum(r['macro_series_match_mode'] != 'UNRESOLVED' for r in rows),
            'crosslinks_unresolved': sum(r['macro_series_match_mode'] == 'UNRESOLVED' for r in rows),
            'live_adapters_ready': 0,
            'validated_snapshot_without_live_adapter': 1,
            'withhold_external': 15,
        },
        'issues': issues,
        'warnings': warnings,
        'series': rows,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(out['summary'], indent=2))
    if issues:
        for x in issues: print('ISSUE:', x)
        raise SystemExit(1)

if __name__ == '__main__':
    main()
