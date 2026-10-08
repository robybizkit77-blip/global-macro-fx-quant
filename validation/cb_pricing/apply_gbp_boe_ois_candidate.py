#!/usr/bin/env python3
"""Apply a GBP BoE OIS candidate to the current checkout only.

Designed for dry-run validation. Fail-closed: only GBP may change semantically
inside OIS/NATIVE; payload assignment round-trips are verified exactly. The caller
must rebuild manifest.v2 after this script. No git push or publication is performed.
"""
from __future__ import annotations
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
OIS = ROOT / 'live_data' / 'sections' / 'OIS_DATA.json'
NATIVE = ROOT / 'live_data' / 'sections' / 'NATIVE_CB_DATA.json'
PAYLOAD = ROOT / 'payload' / 'part-00.txt'
OIS_MARKER = b'window.__GMFQ_DATA.OIS_DATA='
NATIVE_MARKER = b'window.__GMFQ_DATA.NATIVE_CB_DATA='


def extract(raw: bytes, marker: bytes):
    pos = raw.find(marker)
    if pos < 0:
        raise SystemExit(f'missing runtime marker {marker!r}')
    start = pos + len(marker)
    text = raw[start:].decode('utf-8')
    value, chars = json.JSONDecoder().raw_decode(text)
    end = start + len(text[:chars].encode('utf-8'))
    cur = end
    while raw[cur:cur+1] in (b' ', b'\t', b'\r', b'\n'):
        cur += 1
    if raw[cur:cur+1] != b';':
        raise SystemExit('runtime assignment missing semicolon')
    return value, start, end


def replace(raw: bytes, marker: bytes, obj) -> bytes:
    _, start, end = extract(raw, marker)
    encoded = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    out = raw[:start] + encoded + raw[end:]
    check, _, _ = extract(out, marker)
    if check != obj:
        raise SystemExit('runtime round-trip mismatch')
    return out


def r4(x): return round(float(x), 4)
def r1(x): return round(float(x), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True, type=pathlib.Path)
    args = ap.parse_args()

    cand = json.loads(args.candidate.read_text(encoding='utf-8'))
    if cand.get('schema') != 'GMFQ_CB_PRICING_CANDIDATE_V1' or cand.get('currency') != 'GBP':
        raise SystemExit('invalid GBP candidate')
    if cand.get('status') != 'READY_FOR_DRY_RUN':
        raise SystemExit('candidate is not ready for dry run')
    req = ('source_validated','asof_validated','meeting_path_validated','changes_validated','current_real','previous_real','week_real','source_registry_authorized')
    if not all(cand.get('validation',{}).get(k) is True for k in req):
        raise SystemExit('candidate validation incomplete')

    ois = json.loads(OIS.read_text(encoding='utf-8'))
    native = json.loads(NATIVE.read_text(encoding='utf-8'))
    before_ois = json.loads(json.dumps(ois))
    before_native = json.loads(json.dumps(native))

    live = ois['currencies']['GBP']
    h = cand['horizons']
    live.update({
        'status': 'ACTIVE',
        'as_of': cand['as_of'],
        'source': cand['source'],
        'source_url': cand['source_url'],
        'source_meta': {
            'official_public': True,
            'instrument': cand['instrument'],
            'quotation': cand['quotation'],
            'horizon_mapping': 'BoE short-end instantaneous OIS forward curve: exact 3M / 6M / 12M columns; no interpolation'
        },
        'policy_rate': cand['policy_rate'],
        'meetings': cand['meeting_path'],
        'horizons': {k:{'rate':r4(h[k]['rate']),'change_1d_bp':r1(h[k]['change_1d_bp']),'change_1w_bp':r1(h[k]['change_1w_bp']),'policy_delta_bp':r1(h[k]['policy_delta_bp'])} for k in ('3m','6m','12m')},
        'cuts_hikes_priced': {f'{k}_bp': r1(h[k]['policy_delta_bp']) for k in ('3m','6m','12m')},
        'direction': cand['direction'],
        'change_direction_1d': cand['change_direction_1d'],
        'change_direction_1w': cand['change_direction_1w'],
        'validation': {k:v for k,v in cand['validation'].items() if k not in ('runtime_mutated','payload_mutated','source_registry_authorized')},
        'provenance': {
            'official_archive_workbook': cand['provenance']['official_archive_workbook'],
            'official_sheet': cand['provenance']['official_sheet'],
            'method': cand['provenance']['method'],
            'methodology_note': cand['provenance']['methodology_note'],
            'observations': cand['observations']
        }
    })

    ng = native['GBP']
    a,b,c = (r4(h[k]['rate']) for k in ('3m','6m','12m'))
    ng['pricing_tier'] = 'COMPLETO_OFFICIAL_BOE_OIS_HISTORY'
    ng['pricing_status'] = f'BoE official estimated SONIA OIS forward curve: 3M {a:.4f}%; 6M {b:.4f}%; 12M {c:.4f}%.'
    ng['market_3m'], ng['market_6m'], ng['market_12m'] = f'{a:.4f}%', f'{b:.4f}%', f'{c:.4f}%'
    ng['market_pricing'] = {
        'as_of': cand['as_of'],
        'instrument': cand['instrument'],
        'quality': 'COMPLETO_OFFICIAL_BOE_OIS_HISTORY',
        'h3m': a, 'h6m': b, 'h12m': c,
        'near_term': 'Official BoE short-end SONIA OIS forward-curve columns; current, 1D and homogeneous 1W history validated.',
        'source': cand['source'],
        'source_url': cand['source_url'],
        'note': cand['provenance']['methodology_note'],
        'freshness_status': 'CURRENT_VALIDATED'
    }

    changed_ois = [k for k in ois['currencies'] if ois['currencies'][k] != before_ois['currencies'][k]]
    changed_native = [k for k in native if native[k] != before_native[k]]
    if changed_ois != ['GBP'] or changed_native != ['GBP']:
        raise SystemExit(f'non-GBP semantic delta: OIS={changed_ois} NATIVE={changed_native}')

    raw = PAYLOAD.read_bytes()
    runtime_ois, _, _ = extract(raw, OIS_MARKER)
    runtime_native, _, _ = extract(raw, NATIVE_MARKER)
    if runtime_ois != before_ois or runtime_native != before_native:
        raise SystemExit('live sections and payload differ before apply')

    OIS.write_text(json.dumps(ois, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    NATIVE.write_text(json.dumps(native, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    updated = replace(raw, OIS_MARKER, ois)
    updated = replace(updated, NATIVE_MARKER, native)
    PAYLOAD.write_bytes(updated)

    print(json.dumps({'status':'PASS','scope':{'OIS':changed_ois,'NATIVE_CB':changed_native},'as_of':cand['as_of'],'changed_payload_part':0,'publication':False}, indent=2))

if __name__ == '__main__':
    main()
