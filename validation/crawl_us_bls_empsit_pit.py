#!/usr/bin/env python3
"""Build PIT rows for USD payrolls and average hourly earnings from archived BLS
Employment Situation releases.

Targets:
- US_PAYEMS_history_value -> total nonfarm payroll employment level (thousands)
- US_AHE_TOTAL_PRIVATE_history_value -> average hourly earnings, total private ($/hour)

Only values printed in each dated archived release are eligible. No current BLS
history is used to fill gaps.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.bls.gov"
INDEX = BASE + "/bls/news-release/empsit.htm"
OUT = Path("validation/pit_batch/bls/BLS_EMPSIT_PIT_BATCH_V1_2026-10-03.json")
START_OBS = "2020-08"
HEADERS = {"User-Agent": "GMFQ-PIT-research/1.0"}
MONTHS = {m:i for i,m in enumerate([
    "January","February","March","April","May","June","July","August","September","October","November","December"
],1)}


def obs_from_text(text: str) -> str | None:
    m = re.search(r"THE\s+EMPLOYMENT\s+SITUATION\s*--\s*([A-Za-z]+)\s+(\d{4})", text, re.I)
    if not m:
        return None
    mm = MONTHS.get(m.group(1).title())
    return f"{int(m.group(2)):04d}-{mm:02d}" if mm else None


def release_date_from_text(text: str) -> str | None:
    m = re.search(r"8:30\s*a\.m\.\s*\(ET\)\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, re.I)
    if not m:
        m = re.search(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, re.I)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat()


def parse_ahe(text: str) -> float | None:
    pats = [
        r"average hourly earnings for all employees on private nonfarm payrolls.*?to\s*\$([0-9]+(?:\.[0-9]+)?)",
        r"average hourly earnings of all employees on private nonfarm payrolls.*?to\s*\$([0-9]+(?:\.[0-9]+)?)",
        r"average hourly earnings.*?private nonfarm payrolls.*?\$([0-9]+(?:\.[0-9]+)?)",
    ]
    for p in pats:
        m = re.search(p, text, re.I | re.S)
        if m:
            return float(m.group(1))
    return None


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_payems_from_tables(soup: BeautifulSoup, obs: str | None) -> float | None:
    if not obs:
        return None
    year, month = obs.split("-")
    month_name = list(MONTHS.keys())[int(month)-1]
    # Archived HTML tables usually contain a Total nonfarm row with several monthly levels.
    # We look for a row in a table whose header includes the observation month, then select
    # the numeric cell aligned to that month. If header alignment cannot be proven, leave null.
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = []
        for r in rows[:6]:
            cells = [norm(c.get_text(" ", strip=True)) for c in r.find_all(["th","td"])]
            if cells:
                header_cells.append(cells)
        flat_header = " | ".join(" | ".join(x) for x in header_cells)
        if "Total nonfarm" not in table.get_text(" ", strip=True):
            continue
        # Find candidate month column from the most detailed header row.
        month_col = None
        for cells in reversed(header_cells):
            for i, cell in enumerate(cells):
                if re.search(rf"\b{re.escape(month_name[:3])}\b", cell, re.I) or re.search(rf"\b{re.escape(month_name)}\b", cell, re.I):
                    month_col = i
            if month_col is not None:
                break
        for r in rows:
            cells = [norm(c.get_text(" ", strip=True)) for c in r.find_all(["th","td"])]
            if not cells:
                continue
            label = cells[0].lower()
            if label == "total nonfarm" or label.startswith("total nonfarm "):
                if month_col is not None and month_col < len(cells):
                    raw = cells[month_col].replace(",", "")
                    m = re.search(r"-?\d+(?:\.\d+)?", raw)
                    if m:
                        val = float(m.group(0))
                        if val > 10000:
                            return val
                # Conservative fallback: inspect row values and use the last plausible employment level
                vals = []
                for cell in cells[1:]:
                    raw = cell.replace(",", "")
                    if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
                        v = float(raw)
                        if v > 10000:
                            vals.append(v)
                if vals:
                    return vals[-1]
    return None


def parse_release(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    obs = obs_from_text(text)
    release_date = release_date_from_text(text)
    payems = parse_payems_from_tables(soup, obs)
    ahe = parse_ahe(text)
    return {
        "observation_month": obs,
        "release_date": release_date,
        "payems_first_release_level_thousands": payems,
        "ahe_total_private_first_release_dollars_per_hour": ahe,
        "source_url": url,
        "parse_complete": bool(obs and release_date and payems is not None and ahe is not None),
    }


def collect_urls() -> list[str]:
    r = requests.get(INDEX, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/news.release/archives/empsit_" in href and href.endswith(".htm"):
            urls.add(urljoin(BASE, href))
    return sorted(urls)


def main() -> None:
    urls = collect_urls()
    rows, errors = [], []
    for url in urls:
        try:
            row = parse_release(url)
            if row["observation_month"] and row["observation_month"] >= START_OBS:
                rows.append(row)
        except Exception as exc:
            errors.append({"source_url": url, "error": f"{type(exc).__name__}: {exc}"})
        time.sleep(0.1)
    rows.sort(key=lambda x: (x["observation_month"] or "", x["release_date"] or ""))
    payload = {
        "schema": "GMFQ_BLS_EMPSIT_PIT_BATCH_V1",
        "created_at": date.today().isoformat(),
        "provider": "U.S. Bureau of Labor Statistics",
        "release_family": "The Employment Situation",
        "source_strategy": "DATED_ARCHIVED_NEWS_RELEASES",
        "target_runtime_series": {
            "US_PAYEMS_history_value": "payems_first_release_level_thousands",
            "US_AHE_TOTAL_PRIVATE_history_value": "ahe_total_private_first_release_dollars_per_hour"
        },
        "guardrail": "Only values printed in the dated BLS archived release are eligible. Current revised BLS history is never used to fill missing observations.",
        "start_observation_month": START_OBS,
        "release_urls_found": len(urls),
        "rows_found": len(rows),
        "rows_complete": sum(1 for x in rows if x["parse_complete"]),
        "rows": rows,
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "release_urls_found": len(urls),
        "rows_found": len(rows),
        "rows_complete": payload["rows_complete"],
        "payems_available": sum(x["payems_first_release_level_thousands"] is not None for x in rows),
        "ahe_available": sum(x["ahe_total_private_first_release_dollars_per_hour"] is not None for x in rows),
        "errors": len(errors)
    }, indent=2))
    if not urls:
        raise SystemExit("No archived BLS Employment Situation URLs discovered")
    if not rows:
        raise SystemExit("BLS archive URLs found but no observation months parsed")

if __name__ == "__main__":
    main()
