#!/usr/bin/env python3
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

UA = 'GMFQ-Strict-PIT-validation/2.1 (+https://github.com/robybizkit77-blip/global-macro-fx-quant)'
BASE = 'https://www.e-stat.go.jp'
# Sparse cross-era anchors only. This proves the post-2023 archive route before full materialization.
MONTHS = ['2023-09', '2024-01', '2025-01', '2026-08']
QUARTER_CODE = {1: '110103', 2: '120406', 3: '230709', 4: '241012'}


def get(url):
    req = Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ja,en;q=0.8'})
    with urlopen(req, timeout=40) as r:
        return r.read(), r.headers.get('Content-Type', ''), r.geturl()


def month_code(m):
    q = (m - 1) // 3 + 1
    return QUARTER_CODE[q] + f'{m:02d}'


def search_url(month):
    y, ms = month.split('-'); m = int(ms)
    params = {
        'cycle': '1', 'layout': 'datalist', 'month': month_code(m), 'page': '1',
        'result_back': '1', 'tclass1': '000001226833', 'tclass2': '000001226834',
        'tclass3val': '0', 'toukei': '00200531', 'tstat': '000001226583',
        'year': f'{y}0',
    }
    return BASE + '/stat-search/files?' + urlencode(params), y, m


def ids_near_result_summary(text):
    # e-Stat currently uses stat_infid in dataset links; accept legacy camelCase too.
    hits = []
    for m in re.finditer(r'(?:stat_infid|statInfId)=(\d+)', text, flags=re.I):
        window = html.unescape(text[max(0, m.start()-1200):m.end()+1200])
        if '結果の概要' in window:
            hits.append(m.group(1))
    return list(dict.fromkeys(hits))


def validate_metadata(sid, y, m):
    meta_url = BASE + '/stat-search/files?' + urlencode({'stat_infid': sid})
    raw, _, final = get(meta_url)
    text = html.unescape(raw.decode('utf-8', errors='replace'))
    compact = re.sub(r'<[^>]+>', ' ', text)
    compact = re.sub(r'\s+', ' ', compact)
    required = ['労働力調査', '基本集計', '結果の概要']
    if not all(x in compact for x in required):
        return None
    if not re.search(rf'調査年月\s*{y}年\s*{m}月', compact):
        return None
    # Reject notices/other PDFs that merely mention result-summary wording.
    if re.search(r'統計表名\s*結果の概要', compact) is None and '結果の概要 月次' not in compact:
        return None
    pub = re.search(r'公開年月日時分\s*(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})', compact)
    if not pub:
        pub = re.search(r'公開（更新）日\s*(\d{4}-\d{2}-\d{2})', compact)
    publication = (pub.group(1) + ('T' + pub.group(2) + ':00+09:00' if pub.lastindex and pub.lastindex >= 2 else 'T08:30:00+09:00')) if pub else None
    return {'metadata_url': final, 'publication_timestamp_jst': publication}


def probe(month):
    url, y, m = search_url(month)
    raw, _, final_url = get(url)
    text = html.unescape(raw.decode('utf-8', errors='replace'))
    visible = re.sub(r'<[^>]+>', ' ', text)
    visible = re.sub(r'\s+', ' ', visible)
    if f'{y}年' not in visible or f'{m}月' not in visible or '労働力調査' not in visible or '基本集計' not in visible:
        raise ValueError('exact month/basic-tabulation page identity not established')

    ids = ids_near_result_summary(text)
    exact = []
    for sid in ids:
        meta = validate_metadata(sid, y, m)
        if not meta:
            continue
        durl = BASE + '/stat-search/file-download?' + urlencode({'fileKind': '2', 'statInfId': sid})
        draw, dct, dfinal = get(durl)
        if not draw.startswith(b'%PDF'):
            continue
        exact.append({
            'stat_inf_id': sid,
            'metadata_url': meta['metadata_url'],
            'publication_timestamp_jst': meta['publication_timestamp_jst'],
            'download_url': durl,
            'final_download_url': dfinal,
            'sha256': hashlib.sha256(draw).hexdigest(),
            'bytes': len(draw),
            'content_type': dct,
        })

    # Strict PIT: exactly one period-specific result-summary PDF. Never choose among ambiguous matches.
    uniq = {x['sha256']: x for x in exact}
    candidates = list(uniq.values())
    return {
        'reference_month': month,
        'search_url': final_url,
        'month_filter_code': month_code(m),
        'pdf_candidates': candidates,
        'candidate_count': len(candidates),
        'strict_unique': len(candidates) == 1,
    }


def main():
    out = {
        'schema': 'GMFQ_JPY_LABOUR_ESTAT_ARCHIVE_ROUTE_PROBE_V2',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'route_class': 'OFFICIAL_DIRECT_PERIOD_SPECIFIC_ARCHIVE',
        'months': [], 'status': 'PASS'
    }
    for month in MONTHS:
        try:
            row = probe(month)
        except Exception as e:
            row = {'reference_month': month, 'error': repr(e), 'candidate_count': 0, 'pdf_candidates': [], 'strict_unique': False}
        out['months'].append(row)
        if row.get('strict_unique') is not True:
            out['status'] = 'FAIL'
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out['status'] != 'PASS':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
