#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / 'discover_aud_asx_ib_temporal_pit_v1.py'

spec = importlib.util.spec_from_file_location('aud_sfn_discovery', SOURCE)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)

# Discovery-only probe of the official ASX Futures Total/Day Traded report.
# It intentionally does NOT combine SFT and SFN observations. The objective is
# to determine whether SFT alone provides a homogeneous historical basis.
mod.BASE = 'https://www.asx.com.au/data/futures/reports/EODWebMarketSummary{date}SFT.htm'
mod.UA = 'Mozilla/5.0 GMFQ AUD CB pricing SFT coverage probe v1'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=pathlib.Path, required=True)
    args = ap.parse_args()
    out = mod.discover()
    out['schema'] = 'GMFQ_AUD_CB_PRICING_ASX_SFT_COVERAGE_PROBE_V1'
    out['purpose'] = 'Read-only probe of ASX SFT report coverage as a standalone homogeneous alternative to SFN. No SFT/SFN mixing is authorized.'
    out['report_variant'] = 'SFT'
    out['archive_pattern'] = mod.BASE
    out['certification_authorized'] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ('rows','missing')}, indent=2))


if __name__ == '__main__':
    main()
