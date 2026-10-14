#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
SERIES_PATH = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
HEATMAP_PATH = ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json"
SOURCE = "Statistics Bureau of Japan / Labour Force Survey"
SOURCE_URL = "https://www.stat.go.jp/data/roudou/sokuhou/tsuki/"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_ids() -> tuple[str, str, str, str]:
    series = load_json(SERIES_PATH)
    heat = load_json(HEATMAP_PATH)
    h = heat["currencies"]["JPY"]["labour"]
    heat_series_id = str(h["series_id"])
    rows = series["JPY"]
    exact = [r for r in rows if str(r.get("id")) == f"{heat_series_id}_history_value"]
    if len(exact) != 1:
        exact = [r for r in rows if str(r.get("id")) == heat_series_id]
    if len(exact) != 1:
        hits = []
        for r in rows:
            text = " ".join(str(r.get(k, "")) for k in ("id", "name", "title", "indicator", "label")).lower()
            if "unemp" in text:
                hits.append(r)
        if len(hits) != 1:
            raise ValueError(f"cannot resolve unique JPY unemployment MACRO_SERIES row; heatmap series_id={heat_series_id!r}")
        macro_series_id = str(hits[0]["id"])
    else:
        macro_series_id = str(exact[0]["id"])
    return macro_series_id, heat_series_id, str(h.get("frequency", "M")), str(h.get("transformation", "level"))


def fetch_html() -> str:
    req = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "global-macro-fx-quant/1.0 (+official-statistics-reader)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        header_charset = resp.headers.get_content_charset()

    encodings: list[str] = []
    if header_charset:
        encodings.append(header_charset)

    meta_match = re.search(br"charset\s*=\s*['\"]?\s*([A-Za-z0-9._-]+)", raw[:8192], flags=re.IGNORECASE)
    if meta_match:
        encodings.append(meta_match.group(1).decode("ascii", errors="strict"))

    # Statistics Bureau pages may be served in legacy Japanese encodings.
    # Decode strictly and fail closed if none of the declared/known encodings fit.
    encodings.extend(["utf-8", "cp932", "shift_jis"])
    tried: list[str] = []
    for encoding in encodings:
        normalized = encoding.strip()
        if not normalized or normalized.lower() in {e.lower() for e in tried}:
            continue
        tried.append(normalized)
        try:
            return raw.decode(normalized, errors="strict")
        except (LookupError, UnicodeDecodeError):
            continue

    raise UnicodeError(f"cannot decode Statistics Bureau JPY labour page; tried={tried}")


def previous_month(period: str) -> str:
    year, month = map(int, period.split("-"))
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def parse_official_page(html: str) -> tuple[str, float, str, float, dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    title_match = re.search(r"(20\d{2})年.{0,40}?(\d{1,2})月分結果", text)
    if not title_match:
        raise ValueError("cannot resolve latest Labour Force Survey reference month from official page")
    latest_period = f"{int(title_match.group(1)):04d}-{int(title_match.group(2)):02d}"

    marker_match = re.search(r"月次\s*[（(]\s*季節調整値\s*[）)]", text)
    if not marker_match:
        raise ValueError("official page lacks monthly seasonally-adjusted table marker")
    marker_pos = marker_match.end()
    row_pos = text.find("完全失業率", marker_pos)
    if row_pos < 0:
        raise ValueError("official page does not contain the headline unemployment-rate row after monthly marker")
    points_pos = text.find("ポイント", row_pos)
    row_end = points_pos if points_pos >= 0 else min(len(text), row_pos + 500)
    target_row = text[row_pos:row_end]

    values = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*[％%]", target_row)]
    if len(values) < 2:
        raise ValueError(f"need at least two unemployment-rate observations in official row: {target_row!r}")
    latest_value, prior_value = values[-1], values[-2]
    prior_period = previous_month(latest_period)

    # Cross-check against the narrative point, which explicitly describes the
    # seasonally adjusted headline rate. This makes layout changes fail closed.
    narrative_match = re.search(
        r"完全失業率\s*[（(]\s*季節調整値\s*[）)]\s*は\s*(\d+(?:\.\d+)?)\s*[％%]",
        text,
    )
    if not narrative_match:
        raise ValueError("official page lacks seasonally-adjusted unemployment narrative cross-check")
    narrative_value = float(narrative_match.group(1))
    if abs(narrative_value - latest_value) > 1e-12:
        raise ValueError(
            f"official unemployment table/narrative mismatch: table={latest_value} narrative={narrative_value}"
        )

    audit = {
        "latest_period": latest_period,
        "latest_value": latest_value,
        "prior_period": prior_period,
        "prior_value": prior_value,
        "delta": round(latest_value - prior_value, 10),
        "headline": "Unemployment rate, seasonally adjusted, Japan, both sexes, age 15+",
        "table_row": target_row,
        "narrative_cross_check": narrative_value,
    }
    return latest_period, latest_value, prior_period, prior_value, audit


def build_candidate(html: str) -> tuple[dict[str, Any], dict[str,Any]]:
    latest_period, latest_value, _, _, audit = parse_official_page(html)
    macro_series_id, heat_series_id, frequency, transformation = resolve_ids()
    candidate = {
        "currency": "JPY",
        "dimension": "labour",
        "macro_series_id": macro_series_id,
        "observation_date": latest_period,
        "value": latest_value,
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "series_id": heat_series_id,
        "frequency": frequency,
        "transformation": transformation,
        "unit": "%",
    }
    audit.update({
        "source_url": SOURCE_URL,
        "candidate_only": True,
        "live_data_written": False,
        "transport": "OFFICIAL_DIRECT_HTML",
    })
    return candidate, audit


def main() -> int:
    ap = argparse.ArgumentParser(description="Build canonical JPY unemployment candidate from Statistics Bureau monthly results")
    ap.add_argument("--fixture", type=Path, help="Read deterministic official HTML fixture instead of network")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--audit-output", type=Path)
    args = ap.parse_args()

    if args.fixture:
        html = args.fixture.read_text(encoding="utf-8")
        mode = "fixture"
    else:
        html = fetch_html()
        mode = "live"

    candidate, audit = build_candidate(html)
    audit["mode"] = mode
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.audit_output:
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "candidate": candidate, "audit": audit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
