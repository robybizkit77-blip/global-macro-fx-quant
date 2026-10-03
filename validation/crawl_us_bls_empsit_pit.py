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
from datetime import datetime, date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.bls.gov"
ARCHIVE_PREFIX = BASE + "/news.release/archives/empsit_"
OUT = Path("validation/pit_batch/bls/BLS_EMPSIT_PIT_BATCH_V1_2026-10-03.json")
START_OBS = "2020-08"
FIRST_RELEASE_DATE = date(2020, 9, 1)
LAST_RELEASE_DATE = date(2026, 10, 20)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GMFQ-PIT-research/1.0; +https://github.com/robybizkit77-blip/global-macro-fx-quant)",
    "Accept": "text/html,application/xhtml+xml",
}
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
    _, month = obs.split("-")
    month_name = list(MONTHS.keys())[int(month)-1]
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows or "Total nonfarm" not in table.get_text(" ", strip=True):
            continue
        header_cells = []
        for r in rows[:8]:
            cells = [norm(c.get_text(" ", strip=True)) for c in r.find_all(["th","td"])]
            if cells:
                header_cells.append(cells)
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


def parse_release_response(url: str, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
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


def candidate_dates() -> list[date]:
    """Employment Situation is normally released in the first part of a month.
    Probe weekdays 1-10 for every month, plus 11-20 around the 2025 shutdown
    period where delayed releases occurred. Each hit is validated from its title.
    """
    out = []
    d = FIRST_RELEASE_DATE
    while d <= LAST_RELEASE_DATE:
        if d.weekday() < 5:
            if d.day <= 10 or (date(2025, 10, 1) <= d <= date(2026, 1, 20) and d.day <= 20):
                out.append(d)
        d += timedelta(days=1)
    return out


def collect_rows() -> tuple[list[dict], list[dict], int]:
    rows_by_obs: dict[str, dict] = {}
    errors = []
    hits = 0
    session = requests.Session()
    session.headers.update(HEADERS)
    for d in candidate_dates():
        url = f"{ARCHIVE_PREFIX}{d:%m%d%Y}.htm"
        try:
            r = session.get(url, timeout=20)
            if r.status_code in (404, 410):
                continue
            if r.status_code == 403:
                errors.append({"source_url": url, "error": "HTTP 403"})
                continue
            r.raise_for_status()
            if "EMPLOYMENT SITUATION" not in r.text.upper():
                continue
            row = parse_release_response(url, r.text)
            if not row["observation_month"] or row["observation_month"] < START_OBS:
                continue
            hits += 1
            obs = row["observation_month"]
            prior = rows_by_obs.get(obs)
            # Preserve the earliest dated release for the observation month.
            if prior is None or (row["release_date"] or "9999") < (prior["release_date"] or "9999"):
                rows_by_obs[obs] = row
        except Exception as exc:
            errors.append({"source_url": url, "error": f"{type(exc).__name__}: {exc}"})
        time.sleep(0.02)
    rows = sorted(rows_by_obs.values(), key=lambda x: (x["observation_month"] or "", x["release_date"] or ""))
    return rows, errors, hits


def main() -> None:
    rows, errors, hits = collect_rows()
    payload = {
        "schema": "GMFQ_BLS_EMPSIT_PIT_BATCH_V1",
        "created_at": date.today().isoformat(),
        "provider": "U.S. Bureau of Labor Statistics",
        "release_family": "The Employment Situation",
        "source_strategy": "DIRECT_DATED_ARCHIVE_DISCOVERY",
        "target_runtime_series": {
            "US_PAYEMS_history_value": "payems_first_release_level_thousands",
            "US_AHE_TOTAL_PRIVATE_history_value": "ahe_total_private_first_release_dollars_per_hour"
        },
        "guardrail": "Only values printed in the dated BLS archived release are eligible. Current revised BLS history is never used to fill missing observations.",
        "start_observation_month": START_OBS,
        "archive_hits": hits,
        "rows_found": len(rows),
        "rows_complete": sum(1 for x in rows if x["parse_complete"]),
        "rows": rows,
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_dates": len(candidate_dates()),
        "archive_hits": hits,
        "rows_found": len(rows),
        "rows_complete": payload["rows_complete"],
        "payems_available": sum(x["payems_first_release_level_thousands"] is not None for x in rows),
        "ahe_available": sum(x["ahe_total_private_first_release_dollars_per_hour"] is not None for x in rows),
        "errors": len(errors),
        "http_403": sum(x["error"] == "HTTP 403" for x in errors),
    }, indent=2))
    if not rows:
        raise SystemExit("No BLS Employment Situation rows recovered from direct dated archives")

if __name__ == "__main__":
    main()
