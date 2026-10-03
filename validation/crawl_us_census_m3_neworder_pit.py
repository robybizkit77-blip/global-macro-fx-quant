#!/usr/bin/env python3
"""Reconstruct PIT first-release values for US_NEWORDER_history_NEWORDER.

Target identity:
Manufacturers' New Orders: Nondefense Capital Goods Excluding Aircraft
(NEWORDER), seasonally adjusted, millions of dollars.

Source: U.S. Census Bureau M3 Advance Report on Durable Goods historical
press-release PDFs. Only values printed in each dated release are eligible.
"""
from __future__ import annotations

import io
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

INDEX = "https://www.census.gov/manufacturing/m3/adv/historical_data/index.html"
BASE = "https://www.census.gov"
OUT = Path("validation/pit_batch/census/CENSUS_M3_NEWORDER_PIT_BATCH_V1_2026-10-03.json")
START_OBS = "2020-08"
HEADERS = {"User-Agent": "GMFQ-PIT-research/1.0"}
MONTHS = {m: i for i, m in enumerate([
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
], 1)}


def month_key(label: str) -> str | None:
    m = re.search(r"([A-Za-z]+)\s+(\d{4})", label)
    if not m:
        return None
    mm = MONTHS.get(m.group(1).title())
    return f"{int(m.group(2)):04d}-{mm:02d}" if mm else None


def collect_release_links() -> list[tuple[str, str]]:
    r = requests.get(INDEX, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    seen = set()
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        obs = month_key(label)
        href = a["href"]
        if not obs or obs < START_OBS:
            continue
        if "/historical_data/pressreleases/adv/" not in href or not href.lower().endswith(".pdf"):
            continue
        url = urljoin(BASE, href)
        if url in seen:
            continue
        seen.add(url)
        out.append((obs, url))
    return sorted(out)


def extract_pdf_text(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    reader = PdfReader(io.BytesIO(r.content))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def release_date(text: str) -> str | None:
    m = re.search(r"FOR RELEASE AT .*?,\s*(?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY),\s*([A-Z]+\s+\d{1,2},\s+\d{4})", text, re.I)
    if not m:
        m = re.search(r"([A-Z][a-z]+\s+\d{1,2},\s+\d{4})\s*[—-]\s*The U\.S\. Census Bureau", text)
    if not m:
        return None
    from datetime import datetime
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(m.group(1).title(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_core_capex_new_orders(text: str) -> float | None:
    # pypdf usually preserves this block as:
    # Nondefense capital goods: ... New Orders ...
    # Excluding aircraft: Shipments ... New Orders ...
    # The first SA number on the Excluding-aircraft New Orders row is current-month NEWORDER.
    compact = re.sub(r"[ \t]+", " ", text)
    m = re.search(
        r"Nondefense capital goods:.*?Excluding aircraft:.*?New Orders[^\n\r]*?([0-9]{2,3}(?:,[0-9]{3})+)",
        compact,
        re.I | re.S,
    )
    if m:
        return float(m.group(1).replace(",", ""))

    # Line-oriented fallback: after 'Excluding aircraft:' take the first New Orders row.
    lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines()]
    in_block = False
    for line in lines:
        low = line.lower()
        if "excluding aircraft" in low:
            in_block = True
            continue
        if in_block and "defense capital goods" in low:
            break
        if in_block and "new orders" in low:
            vals = re.findall(r"(?<![.\d-])([0-9]{2,3}(?:,[0-9]{3})+)(?![\d])", line)
            if vals:
                return float(vals[0].replace(",", ""))
    return None


def main() -> None:
    links = collect_release_links()
    rows, errors = [], []
    for obs, url in links:
        try:
            text = extract_pdf_text(url)
            rows.append({
                "observation_month": obs,
                "release_date": release_date(text),
                "neworder_first_release_millions_sa": parse_core_capex_new_orders(text),
                "source_url": url,
            })
        except Exception as exc:
            errors.append({"observation_month": obs, "source_url": url, "error": f"{type(exc).__name__}: {exc}"})

    for row in rows:
        row["parse_complete"] = bool(row["release_date"] and row["neworder_first_release_millions_sa"] is not None)
    rows.sort(key=lambda x: x["observation_month"])

    payload = {
        "schema": "GMFQ_CENSUS_M3_NEWORDER_PIT_BATCH_V1",
        "created_at": date.today().isoformat(),
        "provider": "U.S. Census Bureau",
        "release_family": "M3 Advance Report on Durable Goods",
        "target_runtime_series": "US_NEWORDER_history_NEWORDER",
        "series_identity": "Manufacturers' New Orders: Nondefense Capital Goods Excluding Aircraft (NEWORDER), Millions of Dollars, Seasonally Adjusted, Monthly",
        "source_strategy": "DATED_HISTORICAL_PRESS_RELEASE_PDF",
        "guardrail": "Only current-month values printed in the dated M3 advance release are eligible; current revised history is never used to fill missing observations.",
        "start_observation_month": START_OBS,
        "release_links_found": len(links),
        "rows_found": len(rows),
        "rows_complete": sum(r["parse_complete"] for r in rows),
        "rows": rows,
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "release_links_found": len(links),
        "rows_found": len(rows),
        "rows_complete": payload["rows_complete"],
        "value_available": sum(r["neworder_first_release_millions_sa"] is not None for r in rows),
        "release_date_available": sum(r["release_date"] is not None for r in rows),
        "errors": len(errors),
    }, indent=2))
    if not links:
        raise SystemExit("No Census M3 advance historical release links found")
    if not rows:
        raise SystemExit("Census M3 links found but no rows parsed")


if __name__ == "__main__":
    main()
