#!/usr/bin/env python3
"""Materialise Stats NZ quarter-specific unemployment-rate first releases."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen

START = (2018, 3)
END = (2026, 6)
EXPECTED_QUARTERS = 34
MONTHS = {3: "march", 6: "june", 9: "september", 12: "december"}
UA = "global-macro-fx-quant/nzd-labour-strict-pit-v1"


def quarters():
    year, month = START
    while (year, month) <= END:
        yield year, month
        month += 3
        if month == 15:
            year, month = year + 1, 3


def url_for(year: int, month: int) -> str:
    return f"https://www.stats.govt.nz/information-releases/labour-market-statistics-{MONTHS[month]}-{year}-quarter/"


def fetch(url: str) -> tuple[bytes, str, str]:
    req = Request(url, headers={"User-Agent": UA, "Accept-Language": "en-NZ,en;q=0.9"})
    with urlopen(req, timeout=60) as response:
        raw = response.read()
        return raw, response.headers.get("Content-Type", ""), response.geturl()


def text_of(raw: bytes) -> str:
    value = html.unescape(raw.decode("utf-8", errors="replace"))
    return re.sub(r"\s+", " ", value).strip()


def release_date(page: str, label: str) -> str:
    iso = re.findall(r'"datePublished"\s*:\s*"(20\d{2}-\d{2}-\d{2})(?:T[^"]*)?"', page)
    iso = list(dict.fromkeys(iso))
    date_pattern = r'([0-3]?\d\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2})'
    anchored = re.search(re.escape(label) + r".{0,12000}?" + date_pattern, page, re.I)
    visible = [] if not anchored else [datetime.strptime(anchored.group(1), "%d %B %Y").date().isoformat()]
    if len(iso) == 1:
        if visible and set(visible) != {iso[0]}:
            raise ValueError(f"Stats NZ publication date conflict: schema={iso}, visible={visible}")
        return iso[0]
    if len(visible) == 1:
        return visible[0]
    raise ValueError(f"Stats NZ exact release date ambiguous/missing: schema={iso}, visible={visible}")


def unemployment_rate(page: str, year: int, month: int) -> float:
    period = f"{MONTHS[month].capitalize()} {year} quarter"
    p = re.escape(period)
    # Ordered from strongest national headline wording to weaker same-sentence
    # variants. Stop at the first family with one unique value so subgroup
    # rates later in the page (Māori, women, etc.) cannot contaminate a valid
    # national first-release match.
    patterns = (
        rf"seasonally adjusted unemployment rate (?:fell|rose|increased|decreased) to\s+([0-9]+(?:\.[0-9]+)?)\s+percent in the {p}",
        rf"In the {p},?\s+(?:the\s+)?seasonally adjusted unemployment rate (?:fell|rose|increased|decreased) to\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        rf"In the {p},?\s+(?:the\s+)?unemployment rate (?:fell|rose) to\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        rf"(?:The\s+)?unemployment rate (?:fell|rose) to\s+([0-9]+(?:\.[0-9]+)?)\s+percent in the {p}",
        rf"seasonally adjusted unemployment rate was unchanged at\s+([0-9]+(?:\.[0-9]+)?)\s+percent in the {p}",
        rf"seasonally adjusted unemployment rate was\s+([0-9]+(?:\.[0-9]+)?)\s+percent in the {p}",
        rf"In the {p}[^.]{{0,220}}?seasonally adjusted unemployment rate was\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        rf"{p}[^.]{{0,220}}?seasonally adjusted unemployment rate was\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        rf"seasonally adjusted unemployment rate was\s+([0-9]+(?:\.[0-9]+)?)\s+percent[^.]{{0,220}}?{p}",
    )
    for pattern in patterns:
        values = list(dict.fromkeys(float(v) for v in re.findall(pattern, page, re.I)))
        if len(values) == 1:
            return values[0]
        if len(values) > 1:
            raise ValueError(
                f"Stats NZ unemployment-rate ambiguity for {year:04d}-{month:02d} in one official wording family: {values}"
            )
    raise ValueError(f"Stats NZ unemployment-rate missing for {year:04d}-{month:02d}")


def parse(raw: bytes, year: int, month: int) -> tuple[float, str]:
    page = text_of(raw)
    label = f"Labour market statistics: {MONTHS[month].capitalize()} {year} quarter"
    if label.lower() not in page.lower():
        raise ValueError(f"Stats NZ period identity absent: {label}")
    value = unemployment_rate(page, year, month)
    published = release_date(page, label)
    if date.fromisoformat(published) <= date(year, month, 1):
        raise ValueError(f"Stats NZ implausible chronology for {year:04d}-{month:02d}: {published}")
    return value, published


def semantic_hash(rows: list[dict]) -> str:
    fields = ("observation_date", "value", "release_date", "source_url")
    payload = [{k: row[k] for k in fields} for row in rows]
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
        rows.append({k: item[k] for k in item if k != "source_hex"})
    return rows


def materialize() -> dict:
    captured: list[dict] = []
    for idx, (year, month) in enumerate(quarters(), 1):
        requested = url_for(year, month)
        raw, content_type, final_url = fetch(requested)
        if "html" not in content_type.lower() or len(raw) < 2000:
            raise ValueError(f"Stats NZ release not usable HTML: {requested} ({content_type}, {len(raw)} bytes)")
        value, published = parse(raw, year, month)
        row = {
            "observation_date": f"{year:04d}-{month:02d}",
            "value": value,
            "release_date": published,
            "source_route": "STATS_NZ_PERIOD_SPECIFIC_LABOUR_MARKET_INFORMATION_RELEASE",
            "source_url": final_url,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "pit_status": "STRICT_FIRST_RELEASE",
        }
        captured.append({**row, "source_hex": raw.hex()})
        print(f"[capture {idx:02d}/{EXPECTED_QUARTERS}] {row['observation_date']}={value} release={published} sha={row['source_sha256'][:12]}", flush=True)
        time.sleep(0.35)
    rows = replay(captured)
    replay2 = replay(captured)
    expected = [f"{y:04d}-{m:02d}" for y, m in quarters()]
    if [r["observation_date"] for r in rows] != expected or len(rows) != EXPECTED_QUARTERS:
        raise ValueError("Stats NZ strict coverage/order invariant failed")
    if len({r["source_sha256"] for r in rows}) != EXPECTED_QUARTERS:
        raise ValueError("Stats NZ strict invariant failed: period-specific source hash reused")
    if rows != replay2:
        raise ValueError("Stats NZ strict invariant failed: two replays differ")
    return {
        "schema": "GMFQ_NZD_LABOUR_STRICT_PIT_EVIDENCE_V1_RUNTIME",
        "status": "PASS",
        "target": "NZD.labour",
        "authority": "Stats NZ",
        "source": "Stats NZ period-specific Labour market statistics information releases",
        "evidence_class": "STRICT_DIRECT_ARCHIVAL_PIT",
        "verdict": "STRICT_DIRECT_ARCHIVAL_PIT_CERTIFIABLE",
        "series_contract": {"series_id": "NZ_UNEMP_RATE", "macro_series_id": "NZ_UNEMP_RATE_history_value", "frequency": "Q", "transformation": "level", "unit": "%", "first_release_semantics": "OFFICIAL_PERIOD_SPECIFIC_INFORMATION_RELEASE"},
        "coverage": {"start": "2018-03", "end": "2026-06", "expected_quarters": EXPECTED_QUARTERS, "materialized_quarters": len(rows)},
        "unique_source_hashes": len({r["source_sha256"] for r in rows}),
        "network_capture_count": len(rows),
        "replay_count": 2,
        "replay_equal": True,
        "semantic_rowset_sha256": semantic_hash(rows),
        "current_revised_history_used": False,
        "revised_fallback_used": False,
        "changes_live_data": False,
        "changes_engine_rules": False,
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    evidence = materialize()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in evidence.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
