#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SERIES_PATH = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
HEATMAP_PATH = ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json"
LANDING_URL = "https://www.abs.gov.au/statistics/labour/employment-and-unemployment"
SOURCE = "Australian Bureau of Statistics"
MONTHS = {m.lower(): i for i, m in enumerate(("January","February","March","April","May","June","July","August","September","October","November","December"), 1)}


class ReleaseLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href") or ""
        if re.search(r"/labour-force-australia/[a-z]{3}-20\d{2}$", href):
            self.links.append(href)


class TableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("tr", "p", "li", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append("\t")
    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.parts.append(text + " ")
    def text(self) -> str:
        return "".join(self.parts)


def get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "global-macro-fx-quant/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def discover_latest_release() -> str:
    html = get_text(LANDING_URL)
    parser = ReleaseLinkParser()
    parser.feed(html)
    if not parser.links:
        raise ValueError("could not discover ABS Labour Force release link")
    # Landing page is latest-first; de-duplicate while preserving order.
    seen: set[str] = set()
    links = []
    for href in parser.links:
        if href not in seen:
            seen.add(href)
            links.append(href)
    href = links[0]
    return urllib.parse.urljoin("https://www.abs.gov.au", href)


def month_key(label: str) -> str:
    m = re.fullmatch(r"([A-Za-z]+)\s+(20\d{2})", label.strip())
    if not m or m.group(1).lower() not in MONTHS:
        raise ValueError(f"invalid ABS reference period: {label!r}")
    return f"{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}"


def parse_release(html: str) -> tuple[str, float, float]:
    p = TableTextParser()
    p.feed(html)
    text = p.text()
    ref = re.search(r"Reference period\s+([A-Za-z]+\s+20\d{2})", text, flags=re.I)
    if not ref:
        raise ValueError("ABS reference period not found")
    period = month_key(ref.group(1))

    # Prefer the seasonally-adjusted key-statistics table; first two percentage
    # values in the unemployment-rate row are previous and current month.
    block_match = re.search(
        r"Key statistics\s*-\s*Seasonally adjusted(?P<block>.*?)Key statistics\s*-\s*Trend",
        text,
        flags=re.I | re.S,
    )
    if not block_match:
        raise ValueError("ABS seasonally-adjusted key statistics table not found")
    block = block_match.group("block")
    row = re.search(r"Unemployment rate(?P<row>[^\n]+)", block, flags=re.I)
    if not row:
        raise ValueError("ABS unemployment-rate row not found")
    vals = [float(x) for x in re.findall(r"(-?\d+(?:\.\d+)?)%", row.group("row"))]
    if len(vals) < 2:
        raise ValueError(f"ABS unemployment row missing previous/current values: {row.group(0)!r}")
    return period, vals[1], vals[0]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_ids() -> tuple[str, str, str, str]:
    series = load_json(SERIES_PATH)
    heat = load_json(HEATMAP_PATH)
    h = heat["currencies"]["AUD"]["labour"]
    source_id = str(h["series_id"])
    hits = [r for r in series["AUD"] if source_id.lower() in str(r.get("id", "")).lower()]
    if len(hits) != 1:
        hits = [r for r in series["AUD"] if str(r.get("id")) == "AU_UNEMP_RATE_history_value"]
    if len(hits) != 1:
        raise ValueError(f"cannot resolve unique AUD unemployment history row; heatmap series_id={source_id!r}")
    return str(hits[0]["id"]), source_id, str(h.get("frequency", "M")), str(h.get("transformation", "level"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Build canonical AUD unemployment candidate from ABS latest Labour Force release")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--audit-output", type=Path)
    args = ap.parse_args()

    release_url = discover_latest_release()
    period, latest, prior = parse_release(get_text(release_url))
    macro_id, series_id, frequency, transformation = resolve_ids()
    candidate = {
        "currency": "AUD",
        "dimension": "labour",
        "macro_series_id": macro_id,
        "observation_date": period,
        "value": latest,
        "source": SOURCE,
        "source_url": release_url,
        "series_id": series_id,
        "frequency": frequency,
        "transformation": transformation,
        "unit": "%",
    }
    audit = {
        "mode": "live",
        "release_url": release_url,
        "latest_period": period,
        "latest_value": latest,
        "prior_value": prior,
        "delta": round(latest - prior, 10),
        "seasonal_adjustment": "seasonally adjusted",
        "candidate_only": True,
        "live_data_written": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.audit_output:
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status":"PASS","candidate":candidate,"audit":audit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
