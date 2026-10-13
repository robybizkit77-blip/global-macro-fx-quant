#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path

RUNTIME_PATH = Path('live_data/sections/NATIVE_LIQ_DATA.json')
KEYWORDS = ('bakredinausbm', 'snb', 'credito bancario', 'credit', 'chf')


def sh(*args, check=True):
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {p.stderr[-1200:]}")
    return p.stdout


def log_rows(flag, term):
    out = sh(
        'git', 'log', '--all', '--reverse', '--date=iso-strict',
        '--format=%H\t%ad\t%s', f'{flag}{term}', '--', check=False
    )
    return [x for x in out.splitlines() if x.strip()]


def changed_files(commit):
    return [x for x in sh(
        'git', 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', commit,
        check=False
    ).splitlines() if x.strip()]


def compact_hits(commit, variants):
    hits = []
    for path in changed_files(commit):
        if not path.endswith(('.py', '.js', '.html', '.json', '.txt', '.md', '.yml', '.yaml', '.csv')):
            continue
        txt = sh('git', 'show', f'{commit}:{path}', check=False)
        if not txt:
            continue
        low = txt.lower()
        matched = [v for v in variants if v.lower() in low]
        kw = [k for k in KEYWORDS if k in low]
        if not matched and not kw:
            continue
        anchors = matched or kw
        anchor = anchors[0]
        i = low.find(anchor.lower())
        a = max(0, i - 180)
        b = min(len(txt), i + len(anchor) + 420)
        hits.append({
            'path': path,
            'matched_variants': matched[:4],
            'matched_keywords': kw[:5],
            'snippet': re.sub(r'\s+', ' ', txt[a:b])[:700]
        })
        if len(hits) >= 8:
            break
    return hits


def main():
    data = json.loads(RUNTIME_PATH.read_text())
    chf = data.get('CHF') or {}
    credit = chf.get('credit') or {}
    value = credit.get('last_value')
    date = credit.get('last_date')
    if value is None:
        raise SystemExit('CHF.credit.last_value missing')

    # Preserve both Python/JSON forms plus the previously observed full-precision form.
    variants = []
    for v in (
        str(value),
        json.dumps(value),
        f'{float(value):.2f}',
        f'{float(value):.6f}',
        '400255.9803935034',
        '400255.98',
        '400.255,98',
    ):
        if v not in variants:
            variants.append(v)

    searches = {v: log_rows('-S', v) for v in variants}
    exact_candidates = []
    seen = set()
    for rows in searches.values():
        for row in rows:
            sha = row.split('\t', 1)[0]
            if sha not in seen:
                seen.add(sha)
                exact_candidates.append(row)

    # --reverse guarantees each list is oldest -> newest. Resolve true oldest by commit timestamp.
    def stamp(row):
        parts = row.split('\t', 2)
        return parts[1] if len(parts) > 1 else ''

    first_row = min(exact_candidates, key=stamp) if exact_candidates else None
    first_sha = first_row.split('\t', 1)[0] if first_row else None

    source_regex = log_rows('-G', 'bakredinausbm|SNB|Credito bancario|CHF.{0,40}credit|credit.{0,40}CHF')
    result = {
        'schema': 'GMFQ_CHF_LIQUIDITY_PROVENANCE_AUDIT_V3_COMPACT',
        'head': sh('git', 'rev-parse', 'HEAD').strip(),
        'runtime': {
            'path': str(RUNTIME_PATH),
            'date': date,
            'value': value,
            'label': credit.get('label'),
        },
        'searched_value_variants': variants,
        'first_exact_value_commit': first_row,
        'first_exact_value_commit_hits': compact_hits(first_sha, variants) if first_sha else [],
        'source_reference_first_rows': source_regex[:8],
        'source_reference_hits_in_first_value_commit': compact_hits(first_sha, ['bakredinausbm', 'SNB']) if first_sha else [],
        'verdict': (
            'FIRST_VALUE_COMMIT_FOUND_REVIEW_HITS'
            if first_sha else 'EXACT_VALUE_NOT_FOUND_IN_REACHABLE_HISTORY'
        ),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
