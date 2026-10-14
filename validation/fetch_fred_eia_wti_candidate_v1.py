#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

URL = "https://www.eia.gov/dnav/pet/hist/RWTCD.htm"
ROW_RE = re.compile(r"^(\d{4})\s+([A-Za-z]{3})\s*-\s*(\d{1,2})\s+to\s+([A-Za-z]{3})\s*-\s*(\d{1,2})$")
MONTHS = {m: i for i, m in enumerate(("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"), 1)}


class TableRows(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_tr = False
        self.in_td = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "tr":
            self.in_tr = True
            self.row = []
        elif tag in ("td", "th") and self.in_tr:
            self.in_td = True
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_td:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("td", "th") and self.in_td:
            text = " ".join(" ".join(self.cell_parts).replace("\xa0", " ").split())
            self.row.append(text)
            self.in_td = False
            self.cell_parts = []
        elif tag == "tr" and self.in_tr:
            if self.row:
                self.rows.append(self.row)
            self.in_tr = False
            self.row = []


def fetch_html() -> str:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (GMFQ source audit)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def parse_daily_rows(text: str, as_of: str) -> list[dict]:
    parser = TableRows()
    parser.feed(text)
    cutoff = date.fromisoformat(as_of)
    start_floor = date(2016, 1, 1)
    out: dict[str, float] = {}

    for cells in parser.rows:
        if len(cells) < 2:
            continue
        label = " ".join(cells[0].split())
        match = ROW_RE.match(label)
        if not match:
            continue
        year = int(match.group(1))
        mon = MONTHS.get(match.group(2).title())
        day = int(match.group(3))
        if not mon:
            continue
        try:
            monday = date(year, mon, day)
        except ValueError:
            continue
        for offset, cell in enumerate(cells[1:6]):
            obs_date = monday + timedelta(days=offset)
            if obs_date < start_floor or obs_date > cutoff:
                continue
            value_text = cell.strip().replace(",", "")
            if not value_text or value_text in {"-", "--", "NA", "N/A", "W"}:
                continue
            try:
                value = float(value_text)
            except ValueError:
                continue
            out[obs_date.isoformat()] = value

    return [{"date": d, "value": out[d]} for d in sorted(out)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    date.fromisoformat(args.as_of)

    text = fetch_html()
    rows = parse_daily_rows(text, args.as_of)
    if len(rows) < 500:
        raise SystemExit(f"WTI official EIA history too short: {len(rows)}")
    dates = [x["date"] for x in rows]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SystemExit("WTI source dates are not strictly unique/monotonic")
    if dates[0] > "2016-01-31":
        raise SystemExit(f"WTI source history starts too late: {dates[0]}")
    if rows[-1]["value"] <= 0:
        raise SystemExit("WTI latest value is non-positive")

    candidate = {
        "schema": "GMFQ_RISK_WTI_CANDIDATE_V1",
        "status": "GREEN_OFFICIAL_SOURCE_CANDIDATE",
        "as_of": args.as_of,
        "source": {
            "publisher": "U.S. Energy Information Administration",
            "series_name": "Cushing, OK WTI Spot Price FOB (Dollars per Barrel)",
            "series_id": "RWTC",
            "legacy_api_series_id": "PET.RWTC.D",
            "fred_mirror_series_id": "DCOILWTICO",
            "transport": "EIA official daily history page",
            "source_url": URL,
            "frequency": "Daily",
        },
        "observation_count": len(rows),
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
        "last_value": rows[-1]["value"],
        "observations": rows,
    }
    Path(args.out).write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt = {k: v for k, v in candidate.items() if k != "observations"}
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
