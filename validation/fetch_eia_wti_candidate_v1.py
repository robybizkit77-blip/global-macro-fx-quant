#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html.parser
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / 'validation' / 'risk' / 'RISK_SOURCE_POLICY_V1_2026-10-12.json'


class TableParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('td', 'th') and self.cell is not None and self.row is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None
            self.cell = None


def parse_week_start(label: str):
    m = re.search(r'(20\d{2})\s+([A-Z][a-z]{2})-\s*(\d{1,2})\s+to\s+([A-Z][a-z]{2})-\s*(\d{1,2})', label)
    if not m:
        return None
    return dt.date(int(m.group(1)), dt.datetime.strptime(m.group(2), '%b').month, int(m.group(3)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    cfg = policy['secondary_runtime_series']['WTI']
    if cfg.get('status') != 'SOURCE_READY_NOT_PRIMARY_GATE':
        raise SystemExit(f'WTI source policy not ready: {cfg}')
    if cfg.get('publisher') != 'U.S. Energy Information Administration':
        raise SystemExit(f'unexpected WTI publisher: {cfg}')
    if cfg.get('direct_series_code') != 'RWTC' or cfg.get('fred_mirror_series_id') != 'DCOILWTICO':
        raise SystemExit(f'unexpected WTI source identity: {cfg}')
    if cfg.get('primary_gate_input') is not False:
        raise SystemExit('WTI must remain outside the primary VIX/Brent gate')

    tmp = Path(tempfile.gettempdir()) / 'gmfq-RWTCD.htm'
    subprocess.run([
        'curl','-fL','--http1.1','--compressed','--retry','5','--retry-all-errors','--retry-delay','2',
        '--connect-timeout','20','--max-time','120','-A','Mozilla/5.0',cfg['source_url'],'-o',str(tmp)
    ], check=True)
    raw = tmp.read_text(encoding='utf-8', errors='replace')
    parser = TableParser()
    parser.feed(raw)

    observations = []
    for row in parser.rows:
        if not row:
            continue
        start = parse_week_start(row[0])
        if start is None:
            continue
        for offset, raw_value in enumerate(row[1:6]):
            text = raw_value.strip().replace(',', '')
            if not text or text in {'-', '--', 'NA', 'N/A', 'W'}:
                continue
            try:
                value = float(text)
            except ValueError:
                continue
            day = start + dt.timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            observations.append({'date': day.isoformat(), 'value': value})

    observations.sort(key=lambda x: x['date'])
    if len(observations) < 6000:
        raise SystemExit(f'WTI EIA history unexpectedly short: {len(observations)}')
    if observations[0]['date'] > '2000-01-31':
        raise SystemExit(f'WTI EIA first date unexpectedly late: {observations[0]["date"]}')
    dates = [x['date'] for x in observations]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SystemExit('WTI EIA dates are not unique/monotonic')

    receipt = {
        'schema': 'GMFQ_RISK_WTI_DIRECT_EIA_CANDIDATE_V1',
        'source': {
            'publisher': cfg['publisher'],
            'name': cfg['source_name'],
            'url': cfg['source_url'],
            'direct_series_code': cfg['direct_series_code'],
            'fred_mirror_series_id': cfg['fred_mirror_series_id'],
            'frequency': cfg['frequency'],
        },
        'observation_count': len(observations),
        'first_date': observations[0]['date'],
        'latest_date': observations[-1]['date'],
        'latest_value': observations[-1]['value'],
        'observations': observations,
        'status': 'GREEN_OFFICIAL_EIA_CANDIDATE',
        'primary_gate_input': False,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    printable = dict(receipt)
    printable.pop('observations')
    print(json.dumps(printable, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
