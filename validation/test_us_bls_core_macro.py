#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "validation" / "sources" / "us_bls_core_macro.py"
FIXTURE = ROOT / "validation" / "fixtures" / "us_bls_core_macro_fixture.json"

spec = importlib.util.spec_from_file_location("us_bls_core_macro", ADAPTER)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

lab = mod.parse_series(payload, mod.LABOUR_BLS_SERIES)
assert lab[-2:] == [("2026-08", 4.1), ("2026-09", 4.2)], lab

cpi = mod.parse_series(payload, mod.INFLATION_BLS_SERIES)
assert all(date != "2025-13" for date, _ in cpi), cpi
yoy = mod.yoy_from_index(cpi)
by_date = dict(yoy)
assert abs(by_date["2026-08"] - 3.4) < 1e-12, by_date
assert abs(by_date["2026-07"] - ((329.0 / 319.0 - 1.0) * 100.0)) < 1e-12, by_date

candidates, audit = mod.build(payload)
assert candidates["labour"]["currency"] == "USD"
assert candidates["labour"]["dimension"] == "labour"
assert candidates["labour"]["macro_series_id"] == "US_UNRATE_history_value"
assert candidates["labour"]["observation_date"] == "2026-09"
assert candidates["labour"]["value"] == 4.2
assert candidates["labour"]["series_id"] == "UNRATE"
assert candidates["inflation"]["currency"] == "USD"
assert candidates["inflation"]["dimension"] == "inflation"
assert candidates["inflation"]["macro_series_id"] == "US_CPIAUCSL_history_value"
assert candidates["inflation"]["observation_date"] == "2026-08"
assert abs(candidates["inflation"]["value"] - 3.4) < 1e-12
assert candidates["inflation"]["series_id"] == "CPIAUCSL"
assert audit["authority"] == "U.S. Bureau of Labor Statistics"
assert audit["transport"] == "BLS Public Data API v2"
assert audit["canonical_contract"]["labour"]["macro_series_id"] == "US_UNRATE_history_value"
assert audit["canonical_contract"]["inflation"]["macro_series_id"] == "US_CPIAUCSL_history_value"
assert audit["historical_pit_certified"] is False
assert audit["live_data_written"] is False

print(json.dumps({
    "status": "PASS",
    "fixture": str(FIXTURE.relative_to(ROOT)),
    "labour_latest": {"date": candidates["labour"]["observation_date"], "value": candidates["labour"]["value"]},
    "inflation_latest": {"date": candidates["inflation"]["observation_date"], "value": candidates["inflation"]["value"]},
    "inflation_formula": audit["inflation"]["calculation"],
    "historical_pit_certified": False,
    "live_data_written": False
}, indent=2))
