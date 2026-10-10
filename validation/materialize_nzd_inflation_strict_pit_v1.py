#!/usr/bin/env python3
"""Materialise Stats NZ's archived, quarter-specific CPI first releases.

The released HTML page is the immutable period-specific publication artifact.
This module deliberately does not query Infoshare, Aotearoa Data Explorer, the
RBNZ, or any current CPI time series: all can expose a revised history.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

START = (2018, 3)
END = (2026, 6)
EXPECTED_QUARTERS = 34
MONTHS = {3: "march", 6: "june", 9: "september", 12: "december"}
UA = "global-macro-fx-quant/nzd-inflation-strict-pit-v1"


def quarters():
    year, month = START
    while (year, month) <= END:
        yield year, month
        month += 3
        if month == 15:
            year, month = year + 1, 3


def url_for(year: int, month: int) -> str:
    return f"https://www.stats.govt.nz/information-releases/consumers-price-index-{MONTHS[month]}-{year}-quarter/"


def fetch(url: str) -> tuple[bytes, str, str]:
    request = Request(url, headers={"User-Agent": UA, "Accept-Language": "en-NZ,en;q=0.9"})
    with urlopen(request, timeout=60) as response:
        raw = response.read()
        return raw, response.headers.get("Content-Type", ""), response.geturl()


def text_of(raw: bytes) -> str:
    # The page includes structured data and rendered text.  Decode only; no
    # JavaScript executes during capture, keeping parsing deterministic.
    value = html.unescape(raw.decode("utf-8", errors="replace"))
    return re.sub(r"\s+", " ", value).strip()


def release_date(page: str, label: str) -> str:
    # Prefer schema.org publication date, which Stats NZ attaches to the exact
    # information-release page.  The visible English date is the narrow
    # fallback and is required to agree when present.
    iso = re.findall(r'"datePublished"\s*:\s*"(20\d{2}-\d{2}-\d{2})(?:T[^"]*)?"', page)
    iso = list(dict.fromkeys(iso))
    date_pattern = r'([0-3]?\d\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2})'
    # Archive pages contain related-release and download dates.  The first
    # visible date after this page's exact H1/title is the publication date;
    # do not treat unrelated dates elsewhere in the same HTML as ambiguity.
    anchored = re.search(re.escape(label) + r".{0,12000}?" + date_pattern, page, re.I)
    visible_dates = [] if not anchored else [datetime.strptime(anchored.group(1), "%d %B %Y").date().isoformat()]
    if len(iso) == 1:
        if visible_dates and set(visible_dates) != {iso[0]}:
            raise ValueError(f"Stats NZ publication date conflict: schema={iso}, visible={visible_dates}")
        return iso[0]
    if len(visible_dates) == 1:
        return visible_dates[0]
    raise ValueError(f"Stats NZ exact release date ambiguous/missing: schema={iso}, visible={visible_dates}")


def headline_yoy(page: str, year: int, month: int) -> float:
    period = f"{MONTHS[month].capitalize()} {year} quarter"
    # Permit precisely the two Stats NZ wording families for this first release,
    # retaining the period anchor so incidental chart/table percentages cannot
    # be selected.  A negative rate is explicit in the source wording.
    patterns = (
        rf"CPI (?:increased|rose|fell)\s+([0-9]+(?:\.[0-9]+)?)\s+percent in the 12 months to the {re.escape(period)}",
        # 2018-era release templates summarise the two rates in this exact
        # labelled line (eg ``annual: 1.1 percent``), rather than prose.
        rf"Inflation rates? for (?:the )?{re.escape(period)}.*?annual(?:\s+change)?\s*(?:(?:was\s*)?:\s*|was\s+|:\s*|[–-]\s*|\s+)([0-9]+(?:\.[0-9]+)?)\s+percent",
        rf"Inflation rates? for (?:the )?{re.escape(period)}\s+were\s+[0-9]+(?:\.[0-9]+)?\s+percent\s+quarterly\s+and\s+([0-9]+(?:\.[0-9]+)?)\s+percent\s+annual",
        rf"Inflation rates? for (?:the )?{re.escape(period)}:\s*[0-9]+(?:\.[0-9]+)?\s+percent\s*\(quarterly\)\s+and\s+([0-9]+(?:\.[0-9]+)?)\s+percent\s*\(annual\)",
        rf"annual inflation rate for (?:the )?{re.escape(period)}\s+was\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        rf"From the {MONTHS[month].capitalize()} {year - 1} quarter to the {re.escape(period)}, the CPI inflation rate (?:rose|increased|fell|was)\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        rf"In the {re.escape(period)} compared with the {MONTHS[month].capitalize()} {year - 1} quarter, the CPI inflation rate was\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        rf"For the 12 months to the {re.escape(period)}, the CPI inflation rate was\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        rf"Inflation was (?:up|down)\s+[0-9]+(?:\.[0-9]+)?\s+percent in the {MONTHS[month].capitalize()} {year} quarter, and (?:up|down)\s+([0-9]+(?:\.[0-9]+)?)\s+percent in the {MONTHS[month].capitalize()} {year} year",
        rf"annual inflation (?:was|is)\s+([0-9]+(?:\.[0-9]+)?)\s+percent.*?{re.escape(period)}",
        rf"{re.escape(period)}.*?annual inflation (?:was|is)\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
    )
    values: list[float] = []
    for pattern in patterns:
        values.extend(float(x) for x in re.findall(pattern, page, flags=re.I))
    values = list(dict.fromkeys(values))
    if len(values) != 1:
        raise ValueError(f"Stats NZ annual CPI ambiguity/missing for {year:04d}-{month:02d}: {values}")
    return values[0]


def parse(raw: bytes, year: int, month: int) -> tuple[float, str]:
    page = text_of(raw)
    label = f"Consumers price index: {MONTHS[month].capitalize()} {year} quarter"
    if label.lower() not in page.lower():
        raise ValueError(f"Stats NZ period identity absent: {label}")
    value = headline_yoy(page, year, month)
    published = release_date(page, label)
    if date.fromisoformat(published) <= date(year, month, 1):
        raise ValueError(f"Stats NZ implausible chronology for {year:04d}-{month:02d}: {published}")
    return value, published


def semantic_hash(rows: list[dict]) -> str:
    fields = ("observation_date", "value", "release_date", "source_url", "source_sha256")
    payload = [{key: row[key] for key in fields} for row in rows]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def replay(captured: list[dict]) -> list[dict]:
    rows = []
    for item in captured:
        raw = bytes.fromhex(item["source_hex"])
        year, month = map(int, item["observation_date"].split("-"))
        value, published = parse(raw, year, month)
        if value != item["value"] or published != item["release_date"]:
            raise ValueError(f"Stats NZ replay value/date mismatch: {item['observation_date']}")
        if hashlib.sha256(raw).hexdigest() != item["source_sha256"]:
            raise ValueError(f"Stats NZ replay hash mismatch: {item['observation_date']}")
        rows.append({key: item[key] for key in item if key != "source_hex"})
    return rows


def materialize() -> dict:
    captured: list[dict] = []
    for index, (year, month) in enumerate(quarters(), 1):
        requested = url_for(year, month)
        raw, content_type, final_url = fetch(requested)
        if "html" not in content_type.lower() or len(raw) < 2000:
            raise ValueError(f"Stats NZ release not a usable HTML artifact: {requested} ({content_type}, {len(raw)} bytes)")
        value, published = parse(raw, year, month)
        row = {
            "observation_date": f"{year:04d}-{month:02d}",
            "value": value,
            "release_date": published,
            "source_route": "STATS_NZ_PERIOD_SPECIFIC_CPI_INFORMATION_RELEASE",
            "source_url": final_url,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "pit_status": "STRICT_FIRST_RELEASE",
        }
        captured.append({**row, "source_hex": raw.hex()})
        print(f"[capture {index:02d}/{EXPECTED_QUARTERS}] {row['observation_date']}={value} release={published} sha={row['source_sha256'][:12]}", flush=True)
        time.sleep(0.35)
    rows = replay(captured)
    replay2 = replay(captured)
    expected = [f"{year:04d}-{month:02d}" for year, month in quarters()]
    if [row["observation_date"] for row in rows] != expected or len(rows) != EXPECTED_QUARTERS:
        raise ValueError("Stats NZ strict coverage/order invariant failed")
    if len({row["source_sha256"] for row in rows}) != EXPECTED_QUARTERS:
        raise ValueError("Stats NZ strict invariant failed: a period-specific source hash was reused")
    if rows != replay2:
        raise ValueError("Stats NZ strict invariant failed: two replays differ")
    return {
        "schema": "GMFQ_NZD_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME",
        "status": "PASS", "target": "NZD.inflation", "authority": "Stats NZ",
        "source": "Stats NZ period-specific Consumers price index information releases",
        "evidence_class": "STRICT_DIRECT_ARCHIVAL_PIT", "verdict": "STRICT_DIRECT_ARCHIVAL_PIT_CERTIFIABLE",
        "series_contract": {"series_id": "NZ_CPI_HEADLINE_YOY", "macro_series_id": "NZ_CPI_HEADLINE_YOY_history_value", "frequency": "Q", "transformation": "reported_yoy_rate", "unit": "% YoY", "first_release_semantics": "OFFICIAL_PERIOD_SPECIFIC_INFORMATION_RELEASE"},
        "coverage": {"start": "2018-03", "end": "2026-06", "expected_quarters": EXPECTED_QUARTERS, "materialized_quarters": len(rows)},
        "unique_source_hashes": len({row["source_sha256"] for row in rows}), "network_capture_count": len(rows),
        "replay_count": 2, "replay_equal": True, "semantic_rowset_sha256": semantic_hash(rows),
        "current_revised_history_used": False, "revised_fallback_used": False,
        "changes_live_data": False, "changes_engine_rules": False, "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = materialize()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in evidence.items() if key != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
