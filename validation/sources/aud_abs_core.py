#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import io
import json
import re
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
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


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def fetch_text(url: str) -> str:
    return fetch_bytes(url).decode("utf-8", errors="replace")


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


def quarter_table17_url(release_url: str) -> str:
    return release_url.rstrip("/") + "/6401017.xlsx"


def _xlsx_shared_strings(zf: zipfile.ZipFile, ns: str) -> list[str]:
    path = "xl/sharedStrings.xml"
    if path not in zf.namelist():
        return []
    root = ET.fromstring(zf.read(path))
    return ["".join(t.text or "" for t in si.iter(f"{{{ns}}}t")) for si in root.findall(f"{{{ns}}}si")]


def _xlsx_sheet_path(zf: zipfile.ZipFile, sheet_name: str, ns: str, rns: str) -> str:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    relroot = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rels = {e.attrib["Id"]: e.attrib["Target"] for e in relroot}
    sheets = workbook.find(f"{{{ns}}}sheets")
    if sheets is None:
        raise ValueError("ABS workbook has no sheets")
    for sheet in sheets:
        if sheet.attrib.get("name") == sheet_name:
            rid = sheet.attrib[f"{{{rns}}}id"]
            target = rels[rid].lstrip("/")
            return target if target.startswith("xl/") else "xl/" + target
    raise ValueError(f"ABS workbook missing sheet {sheet_name!r}")


def _xlsx_cell_value(cell: ET.Element, shared: list[str], ns: str) -> str | None:
    typ = cell.attrib.get("t")
    value = cell.find(f"{{{ns}}}v")
    raw = None if value is None else value.text
    if typ == "s" and raw is not None:
        return shared[int(raw)]
    if typ == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(f"{{{ns}}}t"))
    return raw


def parse_table17_quarterly_yoy(workbook_bytes: bytes, expected_year: int, expected_month: int) -> tuple[str, float, dict[str, Any]]:
    """Derive official quarterly CPI YoY from ABS Table 17 Australia index levels.

    Table 17 stores quarterly index levels and q/q changes. The Australia index is the
    ninth index series (column J in Data1). YoY is therefore index[t]/index[t-4]-1.
    This avoids mixing the post-Nov-2025 complete monthly CPI with the frozen Q contract.
    """
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as zf:
        shared = _xlsx_shared_strings(zf, ns)
        sheet_path = _xlsx_sheet_path(zf, "Data1", ns, rns)
        root = ET.fromstring(zf.read(sheet_path))
        observations: list[tuple[datetime, Decimal]] = []
        for row in root.findall(f".//{{{ns}}}sheetData/{{{ns}}}row"):
            cells = {c.attrib.get("r", ""): _xlsx_cell_value(c, shared, ns) for c in row.findall(f"{{{ns}}}c")}
            row_num = row.attrib.get("r", "")
            a = cells.get(f"A{row_num}")
            j = cells.get(f"J{row_num}")
            if not a or not j:
                continue
            try:
                dt = datetime(1899, 12, 30) + timedelta(days=int(Decimal(a)))
                idx = Decimal(j)
            except Exception:
                continue
            observations.append((dt, idx))
    observations.sort(key=lambda x: x[0])
    target_idx = next((i for i, (dt, _) in enumerate(observations) if dt.year == expected_year and dt.month == expected_month), None)
    if target_idx is None:
        raise ValueError(f"ABS Table 17 missing expected quarter {expected_year}-{expected_month:02d}")
    if target_idx < 4:
        raise ValueError("ABS Table 17 has insufficient history for YoY calculation")
    dt, current = observations[target_idx]
    prev_dt, previous = observations[target_idx - 4]
    if prev_dt.year != expected_year - 1 or prev_dt.month != expected_month:
        raise ValueError(f"ABS Table 17 t-4 mismatch: current={dt.date()} previous={prev_dt.date()}")
    yoy_raw = (current / previous - Decimal("1")) * Decimal("100")
    yoy = yoy_raw.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    date = f"{expected_year:04d}-{expected_month:02d}"
    audit = {
        "table": "17",
        "method": "quarterly_australia_index_t_over_t_minus_4",
        "current_index": float(current),
        "previous_year_index": float(previous),
        "raw_yoy": float(yoy_raw),
        "rounded_yoy": float(yoy),
    }
    return date, float(yoy), audit


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
        table_url = quarter_table17_url(release_url)
        date, value, table_audit = parse_table17_quarterly_yoy(fetch_bytes(table_url), qyear, qmonth)
        source_url = table_url
        audit_extra = {
            "latest_monthly_release": f"{latest_year:04d}-{latest_month:02d}",
            "quarter_selected": date,
            "quarter_release_url": release_url,
            **table_audit,
        }
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
