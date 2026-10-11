#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import re
import urllib.request
from html import unescape

INDEX_URL = "https://www.bls.gov/bls/news-release/cpi.htm"
ARCHIVE_PREFIX = "https://www.bls.gov/news.release/archives/"
UA = "GLOBAL-MACRO-FX-QUANT USD CPI BLS archive temporal discovery v1"
YEAR_MIN = 2018
YEAR_MAX = 2026

RE_LINK = re.compile(r'href=["\'](?P<href>/news\.release/archives/cpi_(?P<mdy>\d{8})\.htm)["\']', re.I)
RE_TITLE = re.compile(r'CONSUMER PRICE INDEX\s*[\u2013\-]\s*(?P<month>[A-Z]+)\s+(?P<year>\d{4})', re.I)
RE_YOY = re.compile(r'Over the last 12 months,\s+the all items\s+index\s+(?:rose|increased)\s+(?P<value>\d+(?:\.\d+)?)\s+percent', re.I | re.S)
RE_YOY_FELL = re.compile(r'Over the last 12 months,\s+the all items\s+index\s+(?:fell|decreased)\s+(?P<value>\d+(?:\.\d+)?)\s+percent', re.I | re.S)
RE_EMBARGO = re.compile(r'embargoed until\s+(?P<time>\d{1,2}:\d{2}\s*[ap]\.m\.)\s*\((?P<tz>EST|EDT)\)\s*(?P<date>[A-Z][a-z]+\s+\d{1,2},\s+\d{4})', re.I | re.S)


def get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def clean_html(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def discover_links(index_html: str) -> list[tuple[str, str]]:
    out = []
    for m in RE_LINK.finditer(index_html):
        mdy = m.group("mdy")
        year = int(mdy[4:])
        if YEAR_MIN <= year <= YEAR_MAX:
            out.append((mdy, ARCHIVE_PREFIX + f"cpi_{mdy}.htm"))
    unique = sorted(dict(out).items())
    return unique


def parse_release(item: tuple[str, str]) -> dict:
    mdy, url = item
    raw = get(url)
    text = clean_html(raw)
    title = RE_TITLE.search(text)
    yoy = RE_YOY.search(text)
    sign = 1.0
    if not yoy:
        yoy = RE_YOY_FELL.search(text)
        sign = -1.0
    embargo = RE_EMBARGO.search(text)
    if not title or not yoy:
        raise ValueError(f"cannot parse required CPI fields from {url}")
    return {
        "archive_id": mdy,
        "url": url,
        "release_year": int(mdy[4:]),
        "reference_month_label": f"{title.group('month').title()} {title.group('year')}",
        "reported_headline_yoy_pct": sign * float(yoy.group("value")),
        "embargo": ({"time": embargo.group("time"), "tz": embargo.group("tz"), "date": embargo.group("date")} if embargo else None),
        "http_sha256": hashlib.sha256(raw).hexdigest(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=pathlib.Path)
    args = ap.parse_args()

    index_raw = get(INDEX_URL)
    links = discover_links(index_raw.decode("utf-8", errors="replace"))
    if not links:
        raise SystemExit("no BLS CPI archive links found for 2018-2026")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        releases = list(pool.map(parse_release, links))
    releases.sort(key=lambda x: x["archive_id"])

    by_year: dict[str, int] = {}
    for r in releases:
        by_year[str(r["release_year"])] = by_year.get(str(r["release_year"]), 0) + 1

    expected_min = {str(y): (8 if y == 2026 else 11) for y in range(YEAR_MIN, YEAR_MAX + 1)}
    coverage_ok = all(by_year.get(y, 0) >= n for y, n in expected_min.items())
    all_embargo = all(r["embargo"] is not None for r in releases)

    semantic_rows = [
        [r["archive_id"], r["reference_month_label"], r["reported_headline_yoy_pct"], r["url"]]
        for r in releases
    ]
    semantic_sha = hashlib.sha256(json.dumps(semantic_rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    out = {
        "schema": "GMFQ_USD_CPI_BLS_ARCHIVE_FULL_WINDOW_DISCOVERY_V1",
        "status": "DISCOVERY_PASS" if coverage_ok else "DISCOVERY_WITHHELD",
        "authority": "U.S. Bureau of Labor Statistics",
        "source": "BLS Consumer Price Index archived news releases",
        "index_url": INDEX_URL,
        "window": {"start_year": YEAR_MIN, "end_year": YEAR_MAX},
        "release_count": len(releases),
        "by_year": by_year,
        "coverage_thresholds": expected_min,
        "coverage_ok": coverage_ok,
        "all_release_times_parsed": all_embargo,
        "semantic_sha256": semantic_sha,
        "releases": releases,
        "invariants": {
            "archived_release_source_only": True,
            "reported_release_yoy_not_recomputed_from_current_database": True,
            "no_interpolation": True,
            "production_write": False,
            "changes_live_data": False,
            "changes_engine_rules": False,
            "certification_implied": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ["status", "release_count", "by_year", "coverage_ok", "all_release_times_parsed", "semantic_sha256"]}, indent=2))
    return 0 if coverage_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
