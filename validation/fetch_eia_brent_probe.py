#!/usr/bin/env python3
import datetime as dt
import html.parser
import json
import re
import subprocess
import tempfile
from pathlib import Path

POLICY = Path('validation/risk/RISK_SOURCE_POLICY_V1_2026-10-12.json')
OUT = Path('validation/risk-brent-probe.json')
EIA_URL = 'https://www.eia.gov/dnav/pet/hist/RBRTED.htm'


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
            text = ' '.join(''.join(self.cell).split())
            self.row.append(text)
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None
            self.cell = None


def business_days_between(start: dt.date, end: dt.date) -> int:
    if end < start:
        return -1
    n = 0
    cur = start
    while cur < end:
        cur += dt.timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return n


def parse_week_start(label: str):
    m = re.search(r'(20\d{2})\s+([A-Z][a-z]{2})-\s*(\d{1,2})\s+to\s+([A-Z][a-z]{2})-\s*(\d{1,2})', label)
    if not m:
        return None
    year = int(m.group(1))
    month = dt.datetime.strptime(m.group(2), '%b').month
    day = int(m.group(3))
    return dt.date(year, month, day)


def main():
    policy = json.loads(POLICY.read_text(encoding='utf-8'))
    cfg = policy['gate_inputs']['Brent']
    as_of = dt.date.fromisoformat(policy['as_of'])

    tmp = Path(tempfile.gettempdir()) / 'gmfq-RBRTED.htm'
    cmd = [
        'curl', '-fL', '--compressed', '--http1.1',
        '--retry', '4', '--retry-all-errors', '--retry-delay', '2',
        '--connect-timeout', '15', '--max-time', '90',
        '-A', 'Mozilla/5.0', EIA_URL, '-o', str(tmp),
    ]
    subprocess.run(cmd, check=True)
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
        cells = row[1:6]
        for offset, value_raw in enumerate(cells):
            value_raw = value_raw.strip().replace(',', '')
            if not value_raw or value_raw in {'-', '--', 'NA', 'N/A', 'W'}:
                continue
            try:
                value = float(value_raw)
            except ValueError:
                continue
            date = start + dt.timedelta(days=offset)
            if date.weekday() >= 5 or date > as_of:
                continue
            if value <= 0:
                raise SystemExit(f'invalid Brent value on {date}: {value}')
            observations.append((date, value))

    if not observations:
        raise SystemExit('no valid EIA Brent daily observations parsed')
    observations.sort(key=lambda x: x[0])
    latest_date, latest_value = observations[-1]
    lag = business_days_between(latest_date, as_of)
    if lag < 0:
        raise SystemExit(f'future Brent observation relative to policy as_of: {latest_date}')

    max_lag = int(cfg['max_business_day_lag_vs_price'])
    observed_freshness_status = (
        'WITHIN_MAX_LAG_ON_THIS_OBSERVATION'
        if lag <= max_lag else 'EXCEEDS_MAX_LAG_ON_THIS_OBSERVATION'
    )
    result = {
        'schema': 'GMFQ_RISK_BRENT_SOURCE_PROBE_V1',
        'source': {
            'publisher': 'U.S. Energy Information Administration',
            'series_id': 'RBRTE',
            'fred_mirror_series_id': 'DCOILBRENTEU',
            'name': 'Europe Brent Spot Price FOB',
            'url': EIA_URL,
            'frequency': 'Daily',
        },
        'policy_as_of': policy['as_of'],
        'latest_date': latest_date.isoformat(),
        'latest_value': latest_value,
        'business_day_lag': lag,
        'max_business_day_lag': max_lag,
        'observed_freshness_status': observed_freshness_status,
        'status': cfg['status'],
        'eligible_for_controlled_apply': False,
        'reason': (
            'The point-in-time lag is observational evidence only. The EIA '
            'spot series remains ineligible for a one-business-day daily gate '
            'because its official batch release cadence is not timely by '
            'contract.'
        ),
        'publication_performed': False,
        'runtime_mutated': False,
    }
    OUT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
