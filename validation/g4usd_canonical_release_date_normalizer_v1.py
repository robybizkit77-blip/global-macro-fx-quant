#!/usr/bin/env python3
"""Mechanical canonical release-date normalization for frozen G4USD inputs.

This is a plumbing-only transform. It preserves row order, reference_period,
value, availability_status, and row count exactly. The only permitted mutation
is spelling a non-empty certified release date as ISO YYYY-MM-DD.
"""
from __future__ import annotations

import argparse,csv,datetime as dt,pathlib

FIELDS=['reference_period','release_date','value','availability_status']
UNAVAILABLE={'UNAVAILABLE_OFFICIAL_NOT_PUBLISHED','NOT_PUBLISHED_OFFICIAL'}


def iso_date(raw:str)->str:
    x=raw.strip()
    if not x:
        return ''
    token=x[:10]
    for fmt in ('%Y-%m-%d','%d/%m/%Y'):
        try:
            return dt.datetime.strptime(token,fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f'unsupported release_date format {raw!r}')


def normalize(src:pathlib.Path,dst:pathlib.Path)->tuple[int,int]:
    with src.open(newline='',encoding='utf-8-sig') as f:
        rd=csv.DictReader(f)
        if rd.fieldnames != FIELDS:
            raise ValueError(f'{src}: expected exact canonical fields {FIELDS}, got {rd.fieldnames}')
        original=list(rd)

    out=[]; changed=0
    for i,r in enumerate(original,1):
        status=(r['availability_status'] or '').strip()
        rel=(r['release_date'] or '').strip()
        if status in UNAVAILABLE:
            if rel:
                raise ValueError(f'{src} row {i}: unavailable row has release_date')
            new_rel=''
        else:
            if not rel:
                raise ValueError(f'{src} row {i}: available row missing release_date')
            new_rel=iso_date(rel)
        nr=dict(r); nr['release_date']=new_rel
        if new_rel != rel: changed += 1
        # Economic payload and availability semantics are immutable.
        for k in ('reference_period','value','availability_status'):
            if nr[k] != r[k]:
                raise AssertionError(f'{src} row {i}: forbidden mutation of {k}')
        out.append(nr)

    if len(out) != len(original):
        raise AssertionError('row count changed')
    dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open('w',newline='',encoding='utf-8') as f:
        wr=csv.DictWriter(f,fieldnames=FIELDS); wr.writeheader(); wr.writerows(out)
    return len(out),changed


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True,type=pathlib.Path); ap.add_argument('--output',required=True,type=pathlib.Path)
    a=ap.parse_args(); rows,changed=normalize(a.source,a.output)
    print(f'CANONICAL_RELEASE_DATE_NORMALIZATION_PASS rows={rows} changed={changed}')

if __name__=='__main__': main()
