#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader

UA = 'GMFQ-research/1.0 result-blind-cb-priority-labeling'
METHOD = 'GMFQ_CB_PRIORITY_LABELING_CONTRACT_V1'
DOMAINS = {
    'FED': 'federalreserve.gov',
    'ECB': 'ecb.europa.eu',
    'BOJ': 'boj.or.jp',
    'BOC': 'bankofcanada.ca',
    'RBA': 'rba.gov.au',
}

BLOCK_TAGS = {
    'p','div','section','article','main','h1','h2','h3','h4','h5','h6','li','br','tr','td','th'
}
SKIP_TAGS = {'script','style','nav','footer','noscript','svg'}


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth == 0 and tag in BLOCK_TAGS:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth == 0 and tag in BLOCK_TAGS:
            self.parts.append('\n')

    def handle_data(self, data):
        if self.skip_depth == 0 and data.strip():
            self.parts.append(data)


def fetch_bytes(url: str) -> tuple[bytes, str]:
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': UA,
                    'Accept': 'text/html,application/pdf;q=0.9,*/*;q=0.8',
                },
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read()
                ctype = (resp.headers.get('Content-Type') or '').lower()
                return data, ctype
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f'fetch_failed:{type(last).__name__}:{last}')


def extract_text(data: bytes, ctype: str, url: str) -> tuple[str, str]:
    is_pdf = 'application/pdf' in ctype or url.lower().endswith('.pdf') or data[:5] == b'%PDF-'
    if is_pdf:
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            t = page.extract_text() or ''
            if t.strip():
                pages.append(t)
        text = '\n'.join(pages)
        kind = 'PDF_TEXT'
    else:
        raw = data.decode('utf-8', 'ignore')
        parser = VisibleTextParser()
        parser.feed(raw)
        text = ''.join(parser.parts)
        kind = 'HTML_VISIBLE_TEXT'
    text = html.unescape(text).replace('\xa0', ' ')
    text = re.sub(r'[ \t\r\f\v]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    return text.strip(), kind


def sentences(text: str) -> list[str]:
    out: list[str] = []
    for para in text.split('\n'):
        para = ' '.join(para.split()).strip()
        if not para:
            continue
        chunks = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9\"“])', para)
        for s in chunks:
            s = ' '.join(s.split()).strip()
            if len(s) >= 12:
                out.append(s)
    return out


def contains_term(s: str, term: str) -> bool:
    # Phrase-aware boundary matching prevents e.g. "prices" from matching unrelated substrings.
    return re.search(r'(?<![a-z0-9])' + re.escape(term) + r'(?![a-z0-9])', s) is not None


def classify_text(text: str, contract: dict) -> dict:
    topic_terms = {k: [x.lower() for x in v] for k, v in contract['topic_terms'].items()}
    relevance = [x.lower() for x in contract['policy_relevance_cues']]
    dominance = [x.lower() for x in contract['explicit_dominance_cues']]

    evidence: dict[str, list[str]] = {k: [] for k in topic_terms}
    dominance_candidates: set[str] = set()

    for sentence in sentences(text):
        low = sentence.lower()
        rel = any(contains_term(low, cue) for cue in relevance)
        dom = any(contains_term(low, cue) for cue in dominance)
        topics = [topic for topic, terms in topic_terms.items() if any(contains_term(low, t) for t in terms)]
        if not topics:
            continue
        for topic in topics:
            if rel or dom:
                evidence[topic].append(sentence)
            if dom:
                dominance_candidates.add(topic)

    # Distinct qualifying sentences only, preserving first occurrence order.
    for topic in evidence:
        evidence[topic] = list(dict.fromkeys(evidence[topic]))

    inf = len(evidence['INFLATION'])
    lab = len(evidence['LABOUR_GROWTH'])
    fin = len(evidence['FINANCIAL_STABILITY_OTHER'])

    explicit_topic = next(iter(dominance_candidates)) if len(dominance_candidates) == 1 else None
    if explicit_topic is not None:
        focus = explicit_topic
    elif inf >= 2 and (inf - lab) >= 2:
        focus = 'INFLATION'
    elif lab >= 2 and (lab - inf) >= 2:
        focus = 'LABOUR_GROWTH'
    elif inf >= 1 and lab >= 1:
        focus = 'BALANCED'
    else:
        focus = 'WITHHELD_AMBIGUOUS'

    if focus == 'BALANCED':
        focus_evidence = list(dict.fromkeys(evidence['INFLATION'] + evidence['LABOUR_GROWTH']))
    elif focus in evidence:
        focus_evidence = evidence[focus]
    else:
        focus_evidence = []

    return {
        'focus_primary': focus,
        'focus_evidence': focus_evidence,
        'inflation_topic_score': inf,
        'labour_growth_topic_score': lab,
        'financial_stability_other_topic_score': fin,
        'explicit_dominance_topic': explicit_topic,
        'explicit_dominance_candidates': sorted(dominance_candidates),
    }


def label_event(event: dict, contract: dict) -> dict:
    row = {
        'central_bank': event['central_bank'],
        'decision_date': event['decision_date'],
        'publication_timestamp': event['publication_timestamp'],
        'source_url': event['source_url'],
        'source_document_type': event['source_document_type'],
        'focus_primary': 'WITHHELD_AMBIGUOUS',
        'focus_evidence': [],
        'inflation_topic_score': 0,
        'labour_growth_topic_score': 0,
        'financial_stability_other_topic_score': 0,
        'explicit_dominance_topic': None,
        'explicit_dominance_candidates': [],
        'label_method_version': METHOD,
        'pit_eligible': False,
        'source_fetch_status': 'NOT_ATTEMPTED',
        'source_extract_kind': None,
        'source_content_sha256': None,
        'source_text_chars': 0,
    }
    try:
        data, ctype = fetch_bytes(event['source_url'])
        text, kind = extract_text(data, ctype, event['source_url'])
        row['source_content_sha256'] = hashlib.sha256(data).hexdigest()
        row['source_extract_kind'] = kind
        row['source_text_chars'] = len(text)
        if len(text) < 100:
            row['source_fetch_status'] = 'WITHHELD_TEXT_TOO_SHORT'
            return row
        row.update(classify_text(text, contract))
        row['pit_eligible'] = True
        row['source_fetch_status'] = 'OK'
        return row
    except Exception as exc:
        row['source_fetch_status'] = f'WITHHELD_FETCH_OR_PARSE:{type(exc).__name__}:{str(exc)[:180]}'
        return row


def official_url_ok(row: dict) -> bool:
    host = urllib.parse.urlparse(row['source_url']).netloc.lower()
    domain = DOMAINS[row['central_bank']]
    return host == domain or host.endswith('.' + domain)


def write_csv(path: Path, rows: list[dict], required: list[str]):
    fields = required + [
        'explicit_dominance_candidates','source_fetch_status','source_extract_kind',
        'source_content_sha256','source_text_chars'
    ]
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            x = dict(row)
            x['focus_evidence'] = json.dumps(x['focus_evidence'], ensure_ascii=False, separators=(',', ':'))
            x['explicit_dominance_candidates'] = json.dumps(x['explicit_dominance_candidates'], separators=(',', ':'))
            w.writerow({k: x.get(k) for k in fields})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inventory', required=True)
    ap.add_argument('--contract', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--workers', type=int, default=12)
    args = ap.parse_args()

    inventory_bytes = Path(args.inventory).read_bytes()
    inventory_sha = hashlib.sha256(inventory_bytes).hexdigest()
    inventory = json.loads(inventory_bytes)
    contract = json.load(open(args.contract, encoding='utf-8'))
    parent = contract['parent_event_inventory']

    assert contract['schema'] == METHOD
    assert contract['status'] == 'PREDECLARED_LABEL_METHOD_NO_LABELS_OBSERVED'
    assert inventory_sha == parent['inventory_json_sha256'], (inventory_sha, parent['inventory_json_sha256'])
    assert inventory['schema'] == 'GMFQ_CB_PRIORITY_DECISION_EVENT_INVENTORY_V1'
    assert inventory['status'] == parent['required_status'] == 'RESULT_BLIND_EVENT_INVENTORY_COMPLETE'
    assert inventory['focus_labels_present'] is False and inventory['performance_data_present'] is False
    assert len(inventory['events']) == 365

    seen = set()
    for e in inventory['events']:
        key = (e['central_bank'], e['decision_date'])
        assert key not in seen, key
        seen.add(key)
        assert e['official_domain_verified'] is True
        assert official_url_ok(e)

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(label_event, e, contract): e for e in inventory['events']}
        for fut in as_completed(futures):
            rows.append(fut.result())
    rows.sort(key=lambda x: (x['decision_date'], x['central_bank']))

    required = contract['required_label_row_fields']
    missing = sum(1 for row in rows if any(k not in row for k in required))
    nonwithheld_empty_evidence = sum(
        1 for row in rows
        if row['focus_primary'] != 'WITHHELD_AMBIGUOUS' and not row['focus_evidence']
    )
    official_fail = sum(1 for row in rows if not official_url_ok(row))
    duplicates = len(rows) - len({(r['central_bank'], r['decision_date']) for r in rows})

    per_cb = {}
    quality_cfg = contract['quality_gate_before_performance']
    for cb in DOMAINS:
        rr = [r for r in rows if r['central_bank'] == cb]
        counts = Counter(r['focus_primary'] for r in rr)
        withheld = counts['WITHHELD_AMBIGUOUS'] / len(rr) if rr else 1.0
        fetch_fail = sum(r['source_fetch_status'] != 'OK' for r in rr)
        per_cb[cb] = {
            'total': len(rr),
            'label_counts': dict(sorted(counts.items())),
            'withheld_ambiguous_share': withheld,
            'fetch_or_parse_failures': fetch_fail,
            'minimum_events_gate': len(rr) >= quality_cfg['minimum_events_per_central_bank'],
            'withheld_share_gate': withheld <= quality_cfg['maximum_withheld_ambiguous_share_per_central_bank'],
        }

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dataset = {
        'schema': 'GMFQ_CB_PRIORITY_FOCUS_HISTORY_V1',
        'as_of': contract['as_of'],
        'label_method_version': METHOD,
        'inventory_json_sha256': inventory_sha,
        'result_blind': True,
        'performance_data_present': False,
        'performance_test_authorized': False,
        'production_signal_authorized': False,
        'sizing_authorized': False,
        'rows': rows,
    }
    dataset_bytes = (json.dumps(dataset, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    dataset_path = out / 'CB_PRIORITY_FOCUS_HISTORY_V1.json'
    dataset_path.write_bytes(dataset_bytes)
    dataset_sha = hashlib.sha256(dataset_bytes).hexdigest()
    write_csv(out / 'cb_priority_focus_history.csv', rows, required)

    global_gate = (
        all(v['minimum_events_gate'] and v['withheld_share_gate'] for v in per_cb.values())
        and missing == 0
        and nonwithheld_empty_evidence == 0
        and official_fail == 0
        and duplicates == 0
        and bool(dataset_sha)
    )
    quality = {
        'schema': 'GMFQ_CB_PRIORITY_LABELING_QUALITY_V1',
        'inventory_json_sha256': inventory_sha,
        'labeled_dataset_sha256': dataset_sha,
        'rows': len(rows),
        'per_central_bank': per_cb,
        'missing_required_fields_rows': missing,
        'nonwithheld_empty_evidence_rows': nonwithheld_empty_evidence,
        'official_source_failures': official_fail,
        'duplicate_decision_events': duplicates,
        'quality_gate_pass': global_gate,
        'performance_test_authorized': False,
        'note': 'Quality gate concerns label-dataset validity only; passing it does not imply predictive value.',
    }
    (out / 'CB_PRIORITY_LABELING_QUALITY_V1.json').write_text(
        json.dumps(quality, indent=2, sort_keys=True) + '\n', encoding='utf-8'
    )
    print(json.dumps(quality, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
