#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SERIES_PATH = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
HEATMAP_PATH = ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json"
SOURCE = "Australian Bureau of Statistics"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)"}
CPI_LATEST_URL = "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/latest-release"
LABOUR_LATEST_URL = "https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/latest-release"
MONTHS = {m: i for i, m in enumerate(("January","February","March","April","May","June","July","August","September","October","November","December"), 1)}
MONTH_ABBR = {3: "mar", 6: "jun", 9: "sep", 12: "dec"}
CONFIG = {
    "inflation": {
        "series_id": "AU_CPI_HEADLINE_Q_YOY",
        "macro_series_id": "AU_CPI_HEADLINE_Q_YOY_history_value",
        "frequency": "Q",
        "transformation": "reported_yoy_rate",
        "unit": "% YoY",
    },
    "labour": {
        "series_id": "AU_UNEMP_RATE",
        "macro_series_id": "AU_UNEMP_RATE_history_value",
        "frequency": "M",
        "transformation": "level",
        "unit": "%",
    },
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def text_from_html(raw: str) -> str:
    p = TextExtractor()
    p.feed(raw)
    return re.sub(r"\s+", " ", html.unescape(" ".join(p.parts))).strip()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_reference_period(text: str) -> tuple[int, int]:
    m = re.search(r"Reference period\s+([A-Z][a-z]+)\s+(20\d{2})", text)
    if not m or m.group(1) not in MONTHS:
        raise ValueError("cannot parse ABS reference period")
    return int(m.group(2)), MONTHS[m.group(1)]


def latest_quarter_month(month: int) -> int:
    quarters = [q for q in (3, 6, 9, 12) if q <= month]
    if not quarters:
        return 12
    return quarters[-1]


def quarter_release_url(latest_year: int, latest_month: int) -> tuple[str, int, int]:
    qmonth = latest_quarter_month(latest_month)
    qyear = latest_year
    if latest_month < 3:
        qmonth, qyear = 12, latest_year - 1
    return (
        f"https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/{MONTH_ABBR[qmonth]}-{qyear}",
        qyear,
        qmonth,
    )


def parse_quarter_cpi_yoy(text: str, year: int, month: int) -> float:
    month_name = next(name for name, num in MONTHS.items() if num == month)
    patterns = [
        rf"In the 12 months to {month_name} {year}:.*?Consumer Price Index \(CPI\) rose\s+([0-9]+(?:\.[0-9]+)?)%",
        rf"CPI annual inflation was\s+([0-9]+(?:\.[0-9]+)?)\s+per cent in the 12 months to {month_name} {year}",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I | re.S)
        if m:
            return float(m.group(1))
    raise ValueError(f"cannot parse ABS CPI annual rate for {year}-{month:02d}")


def parse_labour_unemployment(text: str, year: int, month: int) -> float:
    month_name = next(name for name, num in MONTHS.items() if num == month)
    patterns = [
        rf"In seasonally adjusted terms, in {month_name} {year}:.*?unemployment rate.*?to\s+([0-9]+(?:\.[0-9]+)?)%",
        rf"In {month_name} {year}, the unemployment rate increased to\s+([0-9]+(?:\.[0-9]+)?)% in seasonally adjusted terms",
        rf"Unemployment rate\s+\|[^|]*\|\s*([0-9]+(?:\.[0-9]+)?)%",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I | re.S)
        if m:
            return float(m.group(1))
    raise ValueError(f"cannot parse ABS seasonally adjusted unemployment rate for {year}-{month:02d}")


def heat_contract(dimension: str) -> tuple[str, str, str]:
    heat = load_json(HEATMAP_PATH)["currencies"]["AUD"][dimension]
    cfg = CONFIG[dimension]
    got = (str(heat.get("series_id")), str(heat.get("frequency")), str(heat.get("transformation")))
    expected = (cfg["series_id"], cfg["frequency"], cfg["transformation"])
    if got != expected:
        raise ValueError(f"AUD {dimension} frozen contract changed: got={got} expected={expected}")
    return got


def verify_macro_target(dimension: str) -> str:
    cfg = CONFIG[dimension]
    rows = load_json(SERIES_PATH)["AUD"]
    hits = [r for r in rows if isinstance(r, dict) and r.get("id") == cfg["macro_series_id"]]
    if len(hits) != 1:
        raise ValueError(f"AUD {dimension} canonical target must exist exactly once; got {len(hits)}")
    if str(hits[0].get("frequency")) != cfg["frequency"]:
        raise ValueError(f"AUD {dimension} target frequency changed: {hits[0].get('frequency')!r}")
    return cfg["macro_series_id"]


def build_from_fixture(dimension: str, fixture: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = CONFIG[dimension]
    heat_contract(dimension)
    target = verify_macro_target(dimension)
    if dimension == "inflation":
        date = str(fixture["quarter_period"])
        value = float(fixture["quarter_yoy"])
        source_url = str(fixture.get("source_url") or CPI_LATEST_URL)
    else:
        date = str(fixture["reference_period"])
        value = float(fixture["unemployment_rate"])
        source_url = str(fixture.get("source_url") or LABOUR_LATEST_URL)
    candidate = {
        "currency": "AUD",
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
    audit = {"candidate_only": True, "live_data_written": False, "mode": "fixture", "source_url": source_url}
    return candidate, audit


def build_live(dimension: str) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = CONFIG[dimension]
    heat_contract(dimension)
    target = verify_macro_target(dimension)
    if dimension == "inflation":
        latest_text = text_from_html(fetch_text(CPI_LATEST_URL))
        latest_year, latest_month = parse_reference_period(latest_text)
        release_url, qyear, qmonth = quarter_release_url(latest_year, latest_month)
        quarter_text = text_from_html(fetch_text(release_url))
        value = parse_quarter_cpi_yoy(quarter_text, qyear, qmonth)
        date = f"{qyear:04d}-{qmonth:02d}"
        source_url = release_url
        audit_extra = {"latest_monthly_release": f"{latest_year:04d}-{latest_month:02d}-01", "quarter_selected": date}
    else:
        source_url = LABOUR_LATEST_URL
        labour_text = text_from_html(fetch_text(source_url))
        year, month = parse_reference_period(labour_text)
        value = parse_labour_unemployment(labour_text, year, month)
        date = f"{year:04d}-{month:02d}-01"
        audit_extra = {"seasonal_adjustment": "seasonally adjusted"}
    candidate = {
        "currency": "AUD",
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
        "mode": "live",
        "source_url": source_url,
        "observation_date": date,
        "value": value,
        **audit_extra,
    }
    return candidate, audit


def main() -> int:
    ap = argparse.ArgumentParser(description="Build AUD core macro candidates from official ABS releases")
    ap.add_argument("--dimension", choices=sorted(CONFIG), required=True)
    ap.add_argument("--fixture", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--audit-output", type=Path)
    args = ap.parse_args()
    if args.fixture:
        candidate, audit = build_from_fixture(args.dimension, load_json(args.fixture))
    else:
        candidate, audit = build_live(args.dimension)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.audit_output:
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "candidate": candidate, "audit": audit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
