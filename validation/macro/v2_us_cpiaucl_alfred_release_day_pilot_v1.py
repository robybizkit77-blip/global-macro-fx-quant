#!/usr/bin/env python3
"""Read-only ALFRED CPIAUCSL release-day vintage PILOT, not original BLS bytes.

Two independently dated BLS CPI releases are fixed anchors, not a claim of
24 recovered first releases. ALFRED is a Fed-maintained mirror of the
seasonally adjusted CPI level; BLS's NSA headline YoY is NOT substituted.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import time
from urllib.error import HTTPError, URLError
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

SCHEMA = "GMFQ_MACRO_V2_US_CPIAUCSL_ALFRED_TWO_RELEASE_DATE_PILOT_V1"
RELEASES = {
    "2025-09": ("2025-10-24", "https://www.bls.gov/news.release/archives/cpi_10242025.htm"),
    "2026-09": ("2026-10-14", "https://www.bls.gov/cpi/news.htm"),
}
SERIES = "CPIAUCSL"
ASOF = "2026-10-26T23:59:59Z"


def ensure(ok, why):
    if not ok:
        raise ValueError("USD_CPI_ALFRED_PILOT_REJECTED: " + why)


def earlier_month(month, n):
    y, m = map(int, month.split("-"))
    i = y * 12 + m - 1 - n
    return f"{i//12:04d}-{i%12+1:02d}"


def url_for(month):
    ensure(month in RELEASES, "unverified BLS CPI release-date mapping")
    vintage = RELEASES[month][0]
    query = urlencode({"id": SERIES, "vintage_date": vintage,
                       "cosd": earlier_month(month, 13) + "-01",
                       "coed": month + "-01"})
    return "https://alfred.stlouisfed.org/graph/alfredgraph.csv?" + query


def acquire(month):
    """Optional explicit opt-in: never run a web download in tests or during import."""
    req = Request(url_for(month), headers={"User-Agent": "GlobalMacroFXQuant-Research/1.0"})
    # ALFRED historic-vintage exports can be slow. Fail closed after bounded
    # retries instead of silently replacing a vintage with today's FRED data.
    for attempt in range(3):
        try:
            with urlopen(req, timeout=60) as response:
                ensure(urlsplit(response.geturl()).hostname == "alfred.stlouisfed.org",
                       "unexpected redirect outside ALFRED")
                data = response.read(524289)
            ensure(len(data) <= 524288, "unexpectedly large response")
            return data
        except (TimeoutError, URLError, HTTPError) as exc:
            if attempt == 2:
                raise RuntimeError(
                    "Official ALFRED as-of CSV retrieval unavailable; no data substituted"
                ) from exc
            time.sleep(2 ** attempt)


def inspect(month, raw):
    ensure(month in RELEASES, "release period not independently verified")
    ensure(isinstance(raw, bytes) and 10 < len(raw) <= 524288, "raw CSV bytes required")
    ensure(b"\x00" not in raw, "invalid CSV bytes")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeError as e:
        raise ValueError("invalid UTF-8 in ALFRED CSV") from e
    reader = csv.reader(io.StringIO(decoded))
    header = next(reader, [])
    vintage, bls_url = RELEASES[month]
    ensure(header in (["observation_date", SERIES + "_" + vintage.replace("-", "")],
                      ["DATE", SERIES + "_" + vintage.replace("-", "")]),
           "wrong series / wrong requested vintage / extra columns")
    values = {}
    for row in reader:
        ensure(len(row) == 2, "CSV must contain exactly two fields per observation")
        day, value = row
        ensure(len(day) == 10 and day.endswith("-01") and
               date.fromisoformat(day).isoformat() == day,
               "unexpected observation timestamp")
        period = day[:7]
        ensure(period not in values and period <= month, "duplicate or future data")
        if value == ".":
            continue
        try:
            numeric = float(value)
        except ValueError as e:
            raise ValueError("non-numeric CPI index") from e
        ensure(math.isfinite(numeric) and 100 <= numeric <= 1000,
               "implausible or nonfinite index")
        values[period] = numeric
    ensure("2025-10" not in values,
           "October 2025 all-items CPI never published by BLS")
    prior = earlier_month(month, 12)
    ensure(month in values and prior in values,
           "release-day SA CPI index and comparable 12-month base required")
    ensure(values[prior] > 0, "invalid CPI base")
    yoy = 100 * (values[month] / values[prior] - 1)
    ensure(math.isfinite(yoy), "invalid SA 12-month change")
    return {
        "schema": SCHEMA, "research_as_of_utc": ASOF,
        "status": "ALFRED_RELEASE_DAY_ASOF_SA_INDEX_PILOT_NOT_BLS_RAW_FIRST_RELEASE",
        "economic_month": month, "BLS_published_release_day": vintage,
        "official_BLS_release_url": bls_url,
        "ALFRED_source_url": url_for(month),
        "ALFRED_exact_download_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "ALFRED_source_kind": "FED_VINTAGE_MIRROR_NOT_BLS_ORIGINAL_ARCHIVED_BYTES",
        "CPIAUCSL_SA_index_current_at_release_day": values[month],
        "CPIAUCSL_SA_index_12m_base_as_of_same_day": values[prior],
        "index_based_SA_YOY_pct_as_of_release_day": yoy,
        "BLS_NSA_official_headline_YOY_identical": False,
        "vintage_contains_proof_of_BLS_intraday_publication": False,
        "ALFRED_vintage_date_does_not_prove_exact_publisher_intraday_timestamp": True,
        "first_release_BLS_download_sha256_verified": False,
        "structural_2025_10_observation_imputed": False,
        "research_first_release_training_24M_complete": False,
        "not_PIT_model_certified": True,
        "safe_to_publish_new_D": False, "safe_to_change_28_pairs": False,
        "safe_for_beta": False, "safe_for_forward": False,
        "writes_live_data": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", choices=sorted(RELEASES), required=True)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=Path, help="Previously downloaded CSV file")
    group.add_argument("--download", action="store_true", help="Opt-in live ALFRED retrieval")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    if args.output:
        ensure(args.output.resolve().is_relative_to(Path("/tmp")),
               "only write an isolated research receipt under /tmp")
    raw = acquire(args.month) if args.download else args.input.read_bytes()
    result = inspect(args.month, raw)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
