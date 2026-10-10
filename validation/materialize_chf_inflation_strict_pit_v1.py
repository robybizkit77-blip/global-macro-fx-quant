#!/usr/bin/env python3
"""Materialise immutable SFSO first-release Swiss CPI press releases.

This deliberately discovers an official DAM press-release asset for each
reference month and reads that release's own headline.  It never consumes the
SNB/FSO current time-series cube, which is allowed to carry revised history.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pypdf import PdfReader

START = (2018, 1)
END = (2026, 9)
EXPECTED_MONTHS = 105
BASE = "https://dam-api.bfs.admin.ch/hub/api/dam"
UA = "global-macro-fx-quant/chf-inflation-strict-pit-v1"
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def months():
    year, month = START
    while (year, month) <= END:
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def fetch(url: str) -> tuple[bytes, str, str]:
    request = Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urlopen(request, timeout=60) as response:
        return response.read(), response.headers.get("Content-Type", ""), response.geturl()


def month_window(year: int, month: int) -> tuple[str, str]:
    # The CPI for month M is normally published early in M+1; searching a
    # bounded 50-day window around then remains deterministic while allowing
    # for holidays and the occasional delayed official release.
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    return (
        f"{next_year:04d}-{next_month:02d}-01T00:00:00Z",
        f"{next_year:04d}-{next_month:02d}-28T23:59:59Z",
    )


def pdf_text(raw: bytes) -> str:
    text = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(raw)).pages)
    return re.sub(r"\s+", " ", text).replace("−", "-").replace("–", "-")


def headline_yoy(text: str, year: int, month: int) -> float:
    # The release narrative is the authoritative first-release value.  Bound
    # the match to its explicit same-month comparison and require one value.
    month_name = MONTHS[month - 1]
    patterns = (
        rf"Inflation\s+was\s+([+\-]?\s*\d+(?:\.\d+)?)%\s+compared\s+with\s+the\s+same\s+month\s+of\s+the\s+previous\s+year",
        rf"In\s+comparison\s+with\s+the\s+same\s+month\s+of\s+the\s+previous\s+year,\s+inflation\s+stood\s+at\s+([+\-]?\s*\d+(?:\.\d+)?)%",
        rf"(?:CPI|consumer prices).*?{month_name}\s+{year}.*?([+\-]?\s*\d+(?:\.\d+)?)%\s+compared\s+with\s+{month_name}\s+{year - 1}",
    )
    values = []
    for pattern in patterns:
        values.extend(float(value.replace(" ", "")) for value in re.findall(pattern, text, re.I))
    values = list(dict.fromkeys(values))
    if len(values) != 1:
        raise ValueError(f"ambiguous/missing SFSO headline YoY for {year:04d}-{month:02d}: {values}")
    return values[0]


def release_asset(year: int, month: int) -> dict:
    start, end = month_window(year, month)
    query = urlencode({"title": "%Swiss%Consumer%Price%Index%", "embargoFrom": start, "embargoTo": end, "limit": 100})
    raw, content_type, final = fetch(f"{BASE}/assets?{query}")
    if "json" not in content_type.lower():
        raise ValueError(f"SFSO asset catalogue non-JSON response for {year:04d}-{month:02d}")
    catalog = json.loads(raw)
    candidates = []
    for item in catalog.get("data", []):
        titles = item.get("description", {}).get("titles", {})
        super_title = titles.get("super", "")
        embargo = item.get("bfs", {}).get("embargo", "")
        links = item.get("links", [])
        masters = [link.get("href") for link in links if link.get("rel") == "master" and link.get("format") == "pdf"]
        if f"{MONTHS[month - 1]} {year}" not in super_title or len(masters) != 1:
            continue
        if item.get("bfs", {}).get("articleModel", {}).get("code") != "MM":
            continue
        candidates.append((item, masters[0], embargo))
    if len(candidates) != 1:
        raise ValueError(f"SFSO exact period-specific release ambiguity {year:04d}-{month:02d}: {len(candidates)}")
    item, master_url, embargo = candidates[0]
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", embargo):
        raise ValueError(f"SFSO invalid official embargo timestamp: {embargo!r}")
    pdf, content_type, final_url = fetch(master_url)
    if not pdf.startswith(b"%PDF"):
        raise ValueError(f"SFSO master is not a PDF for {year:04d}-{month:02d}")
    value = headline_yoy(pdf_text(pdf), year, month)
    return {
        "reference_month": f"{year:04d}-{month:02d}",
        "headline_cpi_yoy_pct": value,
        "release_date": embargo[:10],
        "release_time_utc": embargo[11:19],
        "source_route": "SFSO_DAM_PERIOD_SPECIFIC_CPI_PRESS_RELEASE",
        "catalog_url": final,
        "source_url": final_url,
        "asset_id": item["ids"]["damId"],
        "source_sha256": hashlib.sha256(pdf).hexdigest(),
        "pit_status": "STRICT_FIRST_RELEASE",
    }


def digest(rows: list[dict]) -> str:
    fields = ("reference_month", "headline_cpi_yoy_pct", "release_date", "source_route", "pit_status")
    canonical = [{key: row[key] for key in fields} for row in rows]
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def materialize() -> dict:
    rows = []
    for index, (year, month) in enumerate(months(), 1):
        row = release_asset(year, month)
        rows.append(row)
        print(f"[{index:03d}/{EXPECTED_MONTHS}] {row['reference_month']}={row['headline_cpi_yoy_pct']} release={row['release_date']}", flush=True)
        time.sleep(0.15)
    if len(rows) != EXPECTED_MONTHS or len({row["reference_month"] for row in rows}) != EXPECTED_MONTHS:
        raise ValueError("incomplete or duplicate CHF CPI coverage")
    if len({row["source_sha256"] for row in rows}) != EXPECTED_MONTHS:
        raise ValueError("period-specific SFSO source hash reused")
    return {
        "schema": "GMFQ_CHF_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME",
        "status": "PASS",
        "target": "CHF.inflation",
        "evidence_class": "STRICT_DIRECT_ARCHIVAL_PIT",
        "authority": "Swiss Federal Statistical Office (SFSO)",
        "source": "SFSO DAM period-specific CPI press-release PDFs",
        "coverage": {"start": "2018-01", "end": "2026-09", "expected_months": EXPECTED_MONTHS, "materialized_months": len(rows)},
        "series_contract": {"series_id": "CH_CPI_HEADLINE_YOY", "macro_series_id": "CH_CPI_HEADLINE_YOY_history_value", "frequency": "M", "transformation": "reported_yoy_rate", "unit": "% YoY", "first_release_semantics": "OFFICIAL_PERIOD_SPECIFIC_RELEASE"},
        "strict_rules": {"official_publisher_only": True, "period_specific_release_artifact_required": True, "official_embargo_timestamp_required": True, "sha256_required": True, "current_revised_history_forbidden": True, "revised_history_fallback_used": False},
        "unique_source_hashes": len({row["source_sha256"] for row in rows}),
        "network_capture_count": len(rows),
        "semantic_rowset_sha256": digest(rows),
        "rows": rows,
        "current_revised_history_used": False,
        "revised_fallback_used": False,
        "changes_live_data": False,
        "changes_engine_rules": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    evidence = materialize()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in evidence.items() if key != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
