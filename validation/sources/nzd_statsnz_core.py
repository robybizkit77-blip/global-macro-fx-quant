#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERIES = ROOT / "live_data/sections/MACRO_SERIES.json"
HEAT = ROOT / "live_data/sections/MACRO_THERMOMETER_DATA.json"
SOURCE = "Stats NZ"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)"}

# Stable official indicator pages. These always expose the latest published
# observation, so the adapter is not tied to a specific quarterly release URL.
INDICATOR_URLS = {
    "inflation": "https://www.stats.govt.nz/indicators/consumers-price-index-cpi/",
    "labour": "https://www.stats.govt.nz/indicators/unemployment-rate/",
}

CONFIG = {
    "inflation": {
        "series_id": "NZ_CPI_HEADLINE_YOY",
        "macro_series_id": "NZ_CPI_HEADLINE_YOY_history_value",
        "frequency": "Q",
        "transformation": "reported_yoy_rate",
        "unit": "% YoY",
        "indicator": "consumers-price-index-cpi",
    },
    "labour": {
        "series_id": "NZ_UNEMP_RATE",
        "macro_series_id": "NZ_UNEMP_RATE_history_value",
        "frequency": "Q",
        "transformation": "level",
        "unit": "%",
        "indicator": "unemployment-rate",
    },
}

MONTHS = {"march": 3, "june": 6, "september": 9, "december": 12}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def html_text(raw: str) -> str:
    parser = TextExtractor()
    parser.feed(raw)
    return re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_html_text(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read().decode("utf-8", errors="replace")
    text = html_text(raw)
    if len(text) < 200:
        raise ValueError(f"Stats NZ indicator response unexpectedly short: {url}")
    return text


def quarter_date(month_name: str, year: str) -> str:
    month = MONTHS[month_name.lower()]
    return f"{int(year):04d}-{month:02d}-01"


def parse_indicator(dimension: str, text: str) -> tuple[str, float]:
    if dimension == "inflation":
        patterns = [
            # Current Stats NZ CPI indicator card: Annual change +4.1% June 2026 year
            r"Annual\s+change\s*\+?(-?[0-9]+(?:\.[0-9]+)?)\s*%\s*(March|June|September|December)\s+(20\d{2})\s+year",
            # Defensive fallback if wording changes to quarter.
            r"Annual\s+change\s*\+?(-?[0-9]+(?:\.[0-9]+)?)\s*%\s*(March|June|September|December)\s+(20\d{2})\s+quarter",
        ]
    else:
        patterns = [
            # Current Stats NZ unemployment indicator card.
            r"Unemployment\s+rate\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*(March|June|September|December)\s+(20\d{2})\s+quarter",
            # Tolerate a short label between title and value, but keep the match local.
            r"Unemployment\s+rate.{0,120}?([0-9]+(?:\.[0-9]+)?)\s*%\s*(March|June|September|December)\s+(20\d{2})\s+quarter",
        ]

    hits: list[tuple[str, float]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I | re.S):
            value = float(match.group(1))
            date = quarter_date(match.group(2), match.group(3))
            hits.append((date, value))
        if hits:
            break

    if not hits:
        raise ValueError(f"cannot parse latest Stats NZ {dimension} indicator card")

    # The card should resolve to one latest observation. Duplicate identical hits are fine.
    unique = sorted(set(hits))
    dates = {date for date, _ in unique}
    if len(dates) != 1:
        raise ValueError(f"ambiguous Stats NZ {dimension} indicator periods: {unique}")
    values = {value for _, value in unique}
    if len(values) != 1:
        raise ValueError(f"ambiguous Stats NZ {dimension} indicator values: {unique}")
    return unique[0]


def contract(dimension: str) -> str:
    heat = load(HEAT)["currencies"]["NZD"][dimension]
    cfg = CONFIG[dimension]
    got = (heat.get("series_id"), heat.get("frequency"), heat.get("transformation"))
    expected = (cfg["series_id"], cfg["frequency"], cfg["transformation"])
    if got != expected:
        raise ValueError(f"NZD {dimension} frozen contract changed: {got} != {expected}")
    rows = load(SERIES)["NZD"]
    hits = [row for row in rows if isinstance(row, dict) and row.get("id") == cfg["macro_series_id"]]
    if len(hits) != 1:
        raise ValueError(f"NZD {dimension} canonical target count={len(hits)}")
    return cfg["macro_series_id"]


def build(dimension: str, fixture: Path | None = None):
    cfg = CONFIG[dimension]
    target = contract(dimension)
    source_url = INDICATOR_URLS[dimension]

    if fixture:
        payload = load(fixture)
        date = payload["observation_date"]
        value = float(payload["value"])
        mode = "fixture"
    else:
        text = fetch_html_text(source_url)
        date, value = parse_indicator(dimension, text)
        mode = "live"

    candidate = {
        "currency": "NZD",
        "dimension": dimension,
        "macro_series_id": target,
        "observation_date": date,
        "value": value,
        "source": SOURCE,
        "source_url": source_url,
        "series_id": cfg["series_id"],
        "frequency": cfg["frequency"],
        "transformation": cfg["transformation"],
        "unit": cfg["unit"],
    }
    audit = {
        "candidate_only": True,
        "live_data_written": False,
        "mode": mode,
        "source_url": source_url,
        "retrieval_url": source_url,
        "observation_date": date,
        "value": value,
        "upstream_indicator": cfg["indicator"],
        "dynamic_release_discovery": True,
    }
    return candidate, audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dimension", choices=CONFIG, required=True)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path)
    args = parser.parse_args()

    candidate, audit = build(args.dimension, args.fixture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
    if args.audit_output:
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "candidate": candidate, "audit": audit}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
