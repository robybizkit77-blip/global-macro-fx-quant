#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import io
import json
import pathlib
import urllib.error
import urllib.request
import zipfile

BASE = "https://www.bls.gov/cpi/tables/supplemental-files"
UA = "GLOBAL-MACRO-FX-QUANT USD CPI BLS supplemental temporal discovery v1"
ANNUAL_YEARS = range(2018, 2025)
RECENT_MONTHS = [f"2025{m:02d}" for m in range(1, 13) if m != 10] + [f"2026{m:02d}" for m in range(1, 9)]


def get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/zip,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_annual(year: int) -> dict:
    url = f"{BASE}/archive-{year}.zip"
    raw = get(url)
    if raw[:2] != b"PK":
        raise ValueError(f"not a ZIP payload: {url}")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = sorted(n for n in z.namelist() if not n.endswith("/"))
    historical = [n for n in names if "historical-cpi-u" in n.lower() and n.lower().endswith(".xlsx")]
    return {
        "year": year,
        "url": url,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "member_count": len(names),
        "historical_cpi_u_members": historical,
    }


def fetch_recent(yyyymm: str) -> dict:
    url = f"{BASE}/historical-cpi-u-{yyyymm}.xlsx"
    raw = get(url)
    if raw[:2] != b"PK":
        raise ValueError(f"not an XLSX payload: {url}")
    return {
        "yyyymm": yyyymm,
        "url": url,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=pathlib.Path)
    args = ap.parse_args()

    errors = []
    annual = []
    recent = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        annual_f = {pool.submit(fetch_annual, y): y for y in ANNUAL_YEARS}
        recent_f = {pool.submit(fetch_recent, m): m for m in RECENT_MONTHS}
        for f, y in annual_f.items():
            try:
                annual.append(f.result())
            except Exception as exc:
                errors.append({"kind": "annual_zip", "key": str(y), "error": repr(exc)})
        for f, m in recent_f.items():
            try:
                recent.append(f.result())
            except Exception as exc:
                errors.append({"kind": "recent_xlsx", "key": m, "error": repr(exc)})

    annual.sort(key=lambda x: x["year"])
    recent.sort(key=lambda x: x["yyyymm"])
    annual_ok = len(annual) == len(list(ANNUAL_YEARS)) and all(len(x["historical_cpi_u_members"]) >= 10 for x in annual)
    recent_ok = len(recent) == len(RECENT_MONTHS)
    transport_ok = annual_ok and recent_ok and not errors

    semantic_rows = [
        ["annual", x["year"], x["sha256"], x["historical_cpi_u_members"]] for x in annual
    ] + [["recent", x["yyyymm"], x["sha256"]] for x in recent]
    semantic_sha = hashlib.sha256(json.dumps(semantic_rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    out = {
        "schema": "GMFQ_USD_CPI_BLS_SUPPLEMENTAL_FULL_WINDOW_DISCOVERY_V1",
        "status": "DISCOVERY_PASS" if transport_ok else "DISCOVERY_WITHHELD",
        "authority": "U.S. Bureau of Labor Statistics",
        "source": "BLS archived CPI supplemental files",
        "transport": "direct official static ZIP/XLSX endpoints; no HTML index dependency",
        "annual": annual,
        "recent": recent,
        "errors": errors,
        "annual_ok": annual_ok,
        "recent_ok": recent_ok,
        "transport_ok": transport_ok,
        "semantic_sha256": semantic_sha,
        "invariants": {
            "official_bls_static_files_only": True,
            "no_mirror": True,
            "no_interpolation": True,
            "production_write": False,
            "changes_live_data": False,
            "changes_engine_rules": False,
            "certification_implied": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": out["status"],
        "annual_ok": annual_ok,
        "recent_ok": recent_ok,
        "annual_count": len(annual),
        "recent_count": len(recent),
        "errors": errors,
        "semantic_sha256": semantic_sha,
    }, indent=2))
    return 0 if transport_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
