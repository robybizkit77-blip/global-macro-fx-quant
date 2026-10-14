#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import urllib.request
import xml.etree.ElementTree as ET

URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'
REQUIRED = ('USD','GBP','JPY','CHF','CAD','AUD','NZD')


def fetch(url: str = URL, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent':'GMFQ/1.0 (+official ECB reference-rates updater)'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    root = ET.fromstring(raw)
    dated = None
    for node in root.iter():
        if 'time' in node.attrib:
            dated = node
            break
    if dated is None:
        raise ValueError('ECB XML missing dated Cube')
    as_of = dated.attrib['time']
    dt.date.fromisoformat(as_of)
    vals = {'EUR': 1.0}
    for child in list(dated):
        ccy = child.attrib.get('currency')
        rate = child.attrib.get('rate')
        if ccy and rate:
            vals[ccy] = float(rate)
    missing = [x for x in REQUIRED if x not in vals]
    if missing:
        raise ValueError(f'ECB XML missing required G8 currencies: {missing}')
    if any(vals[x] <= 0 for x in REQUIRED):
        raise ValueError('ECB XML contains non-positive required rate')
    return {
        'schema':'GMFQ_ECB_G8_PRICE_CANDIDATE_V1',
        'source':'ECB euro foreign exchange reference rates',
        'source_url':URL,
        'as_of':as_of,
        'base':'EUR',
        'rates':{k:vals[k] for k in ('EUR',)+REQUIRED},
        'pair_count':28,
        'status':'CANDIDATE_OFFICIAL',
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out')
    args=ap.parse_args()
    data=fetch()
    text=json.dumps(data, indent=2, sort_keys=True) + '\n'
    if args.out:
        open(args.out,'w',encoding='utf-8').write(text)
    print(text,end='')


if __name__=='__main__':
    main()
