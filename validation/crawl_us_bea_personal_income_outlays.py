#!/usr/bin/env python3
"""Build a point-in-time panel for three USD macro series from BEA archived
Personal Income and Outlays releases.

Recovered first-release monthly growth rates:
- US_PI_history_PI              -> Personal income, current dollars
- US_DSPIC96_history_DSPIC96    -> Real disposable personal income (Real DPI)
- US_PCEC96_history_value       -> Real personal consumption expenditures (Real PCE)

The script intentionally reads dated BEA news releases rather than the current
revised NIPA history. Missing or unparsable releases remain explicit gaps.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.bea.gov"
ARCHIVE = BASE + "/news/archive"
OUT = Path("validation/pit_batch/bea/BEA_PIO_PIT_BATCH_V1_2026-10-03.json")
START_OBS = "2020-08"
MAX_PAGES = 80
HEADERS = {"User-Agent": "GMFQ-PIT-research/1.0"}
PIO_PRODUCT_ID = "476"

MONTHS = {m: i for i, m in enumerate([
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
], 1)}


def signed(word: str, value: str) -> float:
    x = float(value)
    return -abs(x) if word.lower().startswith(("decreas", "declin", "fell", "fall")) else abs(x)


def obs_from_title(text: str) -> str | None:
    m = re.search(r"Personal Income and Outlays,\s+([A-Za-z]+)\s+(\d{4})", text, re.I)
    if not m:
        return None
    month = MONTHS.get(m.group(1).title())
    if not month:
        return None
    return f"{int(m.group(2)):04d}-{month:02d}"


def release_date_from_page(soup: BeautifulSoup, text: str) -> str | None:
    for tag in soup.find_all("time"):
        dt = tag.get("datetime")
        if dt and re.match(r"\d{4}-\d{2}-\d{2}", dt):
            return dt[:10]
    m = re.search(
        r"EMBARGOED UNTIL RELEASE AT[^\n]*?([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        text,
        re.I,
    )
    if m:
        from datetime import datetime
        return datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat()
    return None


def first_match(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        m = re.search(pattern, text, re.I | re.S)
        if m:
            return signed(m.group(1), m.group(2))
    return None


def parse_release(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.get_text(" ", strip=True)
    h1 = soup.find("h1")
    title_text = h1.get_text(" ", strip=True) if h1 else title
    obs = obs_from_title(title_text)
    text = soup.get_text(" ", strip=True)
    release_date = release_date_from_page(soup, text)

    personal_income = first_match(text, [
        r"Personal income\s+(increased|decreased|rose|fell)\b.*?\(([-+]?[0-9]+(?:\.[0-9]+)?)\s*percent(?:\s+at a monthly rate)?\)",
        r"Personal income\s+(increased|decreased|rose|fell)\s+[-$0-9., billionmillion]+\s*\(([-+]?[0-9]+(?:\.[0-9]+)?)\s*percent",
        r"Personal income\s+(increased|decreased|rose|fell)\s+([-+]?[0-9]+(?:\.[0-9]+)?)\s*percent",
    ])
    real_dpi = first_match(text, [
        r"Real\s+(?:disposable personal income\s*\(DPI\)|DPI)\s+(increased|decreased|rose|fell)\s+([-+]?[0-9]+(?:\.[0-9]+)?)\s*percent",
    ])
    real_pce = first_match(text, [
        r"Real\s+(?:personal consumption expenditures\s*\(PCE\)|PCE)\s+(increased|decreased|rose|fell)\s+([-+]?[0-9]+(?:\.[0-9]+)?)\s*percent",
    ])

    return {
        "observation_month": obs,
        "release_date": release_date,
        "personal_income_first_release_mom_pct": personal_income,
        "real_dpi_first_release_mom_pct": real_dpi,
        "real_pce_first_release_mom_pct": real_pce,
        "source_url": url,
        "parse_complete": bool(obs and release_date and personal_income is not None and real_dpi is not None and real_pce is not None),
    }


def collect_release_urls() -> list[str]:
    seen: set[str] = set()
    stagnant_pages = 0
    for page in range(MAX_PAGES):
        # BEA's archive product filter is reliable; the free-text title filter is not.
        params = {
            "created_1": "All",
            "field_related_product_target_id": PIO_PRODUCT_ID,
            "title": "",
            "page": page,
        }
        r = requests.get(ARCHIVE, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        before = len(seen)
        for a in soup.find_all("a", href=True):
            label = a.get_text(" ", strip=True)
            href = a["href"]
            if label.lower().startswith("personal income and outlays") and "/news/" in href:
                seen.add(urljoin(BASE, href))
        if len(seen) == before:
            stagnant_pages += 1
        else:
            stagnant_pages = 0
        if stagnant_pages >= 3:
            break
        time.sleep(0.15)
    return sorted(seen)


def main() -> None:
    urls = collect_release_urls()
    rows = []
    errors = []
    for url in urls:
        try:
            row = parse_release(url)
            if row["observation_month"] and row["observation_month"] >= START_OBS:
                rows.append(row)
        except Exception as exc:
            errors.append({"source_url": url, "error": f"{type(exc).__name__}: {exc}"})
        time.sleep(0.15)

    rows.sort(key=lambda x: x["observation_month"] or "")
    complete = sum(1 for r in rows if r["parse_complete"])
    payload = {
        "schema": "GMFQ_BEA_PIO_PIT_BATCH_V1",
        "created_at": date.today().isoformat(),
        "provider": "U.S. Bureau of Economic Analysis",
        "release_family": "Personal Income and Outlays",
        "source_strategy": "DATED_RELEASE_ARCHIVE",
        "archive_product_id": PIO_PRODUCT_ID,
        "target_runtime_series": {
            "US_PI_history_PI": "personal_income_first_release_mom_pct",
            "US_DSPIC96_history_DSPIC96": "real_dpi_first_release_mom_pct",
            "US_PCEC96_history_value": "real_pce_first_release_mom_pct",
        },
        "guardrail": "Only values printed in the dated BEA release are eligible. Current revised NIPA history is never used to fill missing observations.",
        "start_observation_month": START_OBS,
        "release_urls_found": len(urls),
        "rows_found": len(rows),
        "rows_complete": complete,
        "rows_incomplete": len(rows) - complete,
        "rows": rows,
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"release_urls_found": len(urls), "rows_found": len(rows), "rows_complete": complete, "errors": len(errors)}, indent=2))
    if not urls:
        raise SystemExit("No BEA PIO release URLs found; archive discovery failed")


if __name__ == "__main__":
    main()
