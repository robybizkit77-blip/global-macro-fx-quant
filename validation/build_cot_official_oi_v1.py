#!/usr/bin/env python3
"""Persist exact official OI separately from the canonical FX runtime."""
import argparse, json, pathlib
from datetime import date
try:
    from .verify_cftc_current_snapshot import CURRENCIES
except ImportError:
    from verify_cftc_current_snapshot import CURRENCIES

def build(summary, chart):
    official = summary['official']
    asof = summary['official_as_of']
    if date.fromisoformat(asof).isoformat() != asof:
        raise ValueError('invalid date')
    if summary['source'] != 'CFTC Legacy Futures Only current reports' or summary['status'] not in ('NO_UPDATE', 'CANDIDATE_READY'):
        raise ValueError('invalid official candidate')
    if set(official) != set(CURRENCIES) or set(chart) != set(CURRENCIES):
        raise ValueError('incomplete G8')
    rows = {}
    for c, (code, url) in CURRENCIES.items():
        x, h = official[c], chart[c]
        oi, l, s, n = (x[k] for k in ('open_interest', 'long', 'short', 'net'))
        if any(type(z) is not int for z in (oi,l,s,n)) or oi <= 0 or min(l,s) < 0 or oi < max(l,s) or n != l-s:
            raise ValueError(c + ': invalid official counts')
        if x['date'] != asof or h['dates'][-1] != asof or any(h[k][-1] != x[k] for k in ('long','short','net')):
            raise ValueError(c + ': canonical date or positions mismatch')
        if abs(n/oi*100 - h['netoi'][-1]) > .000501:
            raise ValueError(c + ': Net/OI mismatch')
        rows[c] = dict(date=asof,market_code=code,open_interest=oi,long=l,short=s,net=n,source_url=url)
    return dict(schema='GMFQ_CFTC_OFFICIAL_OI_V1',as_of=asof,report_type='LEGACY_FUTURES_ONLY',research_only=True,affects_fx_ranking=False,currencies=rows)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--summary',required=True)
    p.add_argument('--chart',required=True)
    p.add_argument('--output',required=True)
    args=p.parse_args()
    load=lambda path: json.loads(pathlib.Path(path).read_text())
    out=build(load(args.summary),load(args.chart))
    target=pathlib.Path(args.output)
    if target.exists():
        prior=load(target)
        if prior.get('as_of','') > out['as_of']:
            raise ValueError('official OI regression')
    target.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print('CFTC_OFFICIAL_OI_G8_PASS',out['as_of'])

if __name__=='__main__':
    main()
