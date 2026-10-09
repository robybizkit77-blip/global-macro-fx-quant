#!/usr/bin/env python3
import hashlib
import json
import re
from datetime import datetime
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

UA = 'GMFQ-Strict-PIT-validation/2.0 (+https://github.com/robybizkit77-blip/global-macro-fx-quant)'
BASE = 'https://www.e-stat.go.jp'
# Deliberately sparse cross-era anchors first. This is a route-integrity probe, not publication.
MONTHS = ['2023-09', '2024-01', '2025-01', '2026-08']


def get(url):
    req = Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ja,en;q=0.8'})
    with urlopen(req, timeout=45) as r:
        raw = r.read()
        ctype = r.headers.get('Content-Type', '')
        final_url = r.geturl()
    return raw, ctype, final_url


def search_url(month):
    y, m = month.split('-')
    params = {
        'cycle': '1',
        'layout': 'datalist',
        'month': '11010301',
        'page': '1',
        'result_back': '1',
        'tclass1': '000001226833',
        'tclass2': '000001226834',
        'tclass3val': '0',
        'toukei': '00200531',
        'tstat': '000001226583',
        'year': f'{y}0',
    }
    # e-Stat uses the selected calendar month as a separate query value on some routes.
    # Add explicit search text so discovery fails closed if the page does not identify the month.
    return BASE + '/stat-search/files?' + urlencode(params), y, int(m)


def probe(month):
    url, y, m = search_url(month)
    raw, ctype, final_url = get(url)
    text = raw.decode('utf-8', errors='replace')
    # The first query can land on a year-level list. Follow only links that explicitly encode
    # the requested survey month and preserve the official Labour Force Survey classification.
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', text, flags=re.I)
    month_tokens = [f'year={y}0', f'{y}年{m}月', f'{y}%E5%B9%B4{m}%E6%9C%88']
    candidate_pages = []
    for h in hrefs:
        if 'stat-search/files' not in h:
            continue
        absu = urljoin(BASE, h.replace('&amp;', '&'))
        if f'year={y}0' in absu:
            candidate_pages.append(absu)
    pages = [final_url] + list(dict.fromkeys(candidate_pages))[:80]
    found = []
    for p in pages:
        praw, _, pfinal = get(p)
        ptxt = praw.decode('utf-8', errors='replace')
        # Require visible requested period + the Basic Tabulation/result-summary context.
        if f'{y}年' not in ptxt or f'{m}月' not in ptxt:
            continue
        if '労働力調査' not in ptxt or '基本集計' not in ptxt or '結果の概要' not in ptxt:
            continue
        # statInfId uniquely identifies an e-Stat file/download record.
        ids = list(dict.fromkeys(re.findall(r'statInfId=(\d+)', ptxt, flags=re.I)))
        for sid in ids:
            durl = BASE + '/stat-search/file-download?fileKind=2&statInfId=' + sid
            try:
                draw, dct, dfinal = get(durl)
            except Exception:
                continue
            if not draw.startswith(b'%PDF'):
                continue
            # Require the downloaded PDF itself to identify Labour Force Survey and requested month.
            # Full semantic extraction is done in the materializer; here immutable identity is enough.
            found.append({
                'stat_inf_id': sid,
                'download_url': durl,
                'final_download_url': dfinal,
                'sha256': hashlib.sha256(draw).hexdigest(),
                'bytes': len(draw),
                'content_type': dct,
                'source_page': pfinal,
            })
    # Multiple PDF ids may exist (monthly + quarterly etc.). Do not silently guess.
    uniq = {x['sha256']: x for x in found}
    return {
        'reference_month': month,
        'search_url': url,
        'pdf_candidates': list(uniq.values()),
        'candidate_count': len(uniq),
    }


def main():
    out = {'schema': 'GMFQ_JPY_LABOUR_ESTAT_ARCHIVE_ROUTE_PROBE_V2', 'checked_at_utc': datetime.utcnow().isoformat() + 'Z', 'months': [], 'status': 'PASS'}
    for month in MONTHS:
        try:
            row = probe(month)
        except Exception as e:
            row = {'reference_month': month, 'error': repr(e), 'candidate_count': 0, 'pdf_candidates': []}
        out['months'].append(row)
        if row.get('candidate_count', 0) < 1:
            out['status'] = 'FAIL'
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out['status'] != 'PASS':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
