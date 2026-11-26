"""Collect Japan's real GDP from the first ESRI quarterly edition."""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from validation.macro.capture_official_postrelease_actuals_v1 import Pending, retrieve
from validation.macro.capture_uk_ch_gdp_official_firstseen_v11 import source_text
from validation.macro.ons_quarterly_gdp_v1 import (
    ROME, append_edition, archived_growth, load_archive, previous_quarter, quarter_parts,
)

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "validation/macro/ESRI_FIRST_QUARTERLY_GDP_V1.json"
HOST = "www.esri.cao.go.jp"
BASE = f"https://{HOST}/en/sna/data/sokuhou/files/"
CSV_BASE = f"https://{HOST}/jp/sna/data/data_list/sokuhou/files/"
SCHEMA = "GMFQ_ESRI_FIRST_QUARTERLY_GDP_V1"
FIRST = "2026Q3"
MAX_CSV_BYTES = 250_000
CSV_TITLE = "Real, Seasonally Adjusted Series (Quarter-to-Quarter Percent Change)"


def next_quarter(quarter):
    year, n = quarter_parts(quarter)
    return f"{year}Q{n+1}" if n < 4 else f"{year+1}Q1"


def edition_urls(quarter):
    year, n = quarter_parts(quarter)
    code = f"{year % 100:02d}{n}"
    directory = f"{year}/qe{code}"
    return (f"{BASE}{year}/toukei_{year}.html",
            f"{BASE}{directory}/gdemenuea.html",
            f"{CSV_BASE}{directory}/tables/ritu-jk{code}1.csv")


def edition_url(quarter):
    return edition_urls(quarter)[1]


def archive_for(path):
    data = load_archive(path, schema=SCHEMA, minimum=FIRST, url_for=edition_url)
    for row in data["editions"]:
        if (row["csv_url"] != edition_urls(row["quarter"])[2]
                or row["prior_qoq"] is None or not re.fullmatch(r"[0-9a-f]{64}", row["csv_sha256"])):
            raise ValueError("invalid ESRI archive CSV provenance")
    return data


def latest_growth(as_of, *, path=ARCHIVE, live_cutoff=None):
    return archived_growth(as_of, archive_for(path)["editions"],
                           stage="FIRST_PRELIMINARY_ESTIMATE",
                           same_edition_field="prior_value_from_same_esri_edition", live_cutoff=live_cutoff)


def release_date(raw, quarter):
    """The official archive identifies the first edition and its release day."""
    expected = edition_url(quarter).removeprefix(f"https://{HOST}")
    html = raw.decode("utf-8")
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, re.I | re.S)
    matches = [row for row in rows if re.search(
        r"href\s*=\s*[\"']" + re.escape(expected) + r"[\"']", row)]
    if not matches:
        return None
    if len(matches) != 1:
        raise Pending("ESRI_FIRST_EDITION_NOT_UNIQUE")
    row = source_text(matches[0].encode())
    if not re.search(r"\bThe First preliminary Estimates\b", row, re.I):
        raise Pending("ESRI_FIRST_RELEASE_LABEL_NOT_VERIFIED")
    day = re.match(r"([A-Z][a-z]{2}\s+\d{1,2},\s+20\d{2})\b", row)
    if not day:
        raise Pending("ESRI_RELEASE_DATE_NOT_FOUND")
    return datetime.strptime(day.group(1), "%b %d, %Y").date()


def parse_csv(raw, quarter):
    rows = list(csv.reader(io.StringIO(raw.decode("cp932"))))
    if not any(row and row[0].strip() == CSV_TITLE for row in rows[:8]):
        raise Pending("ESRI_REAL_QOQ_CSV_TITLE_MISMATCH")
    if not any(len(row) > 1 and not row[0].strip() and row[1].strip() == "GDP(Expenditure Approach)"
               for row in rows[:12]):
        raise Pending("ESRI_GDP_AGGREGATE_COLUMN_NOT_FOUND")
    series = {}
    year = None
    for row in rows:
        if len(row) < 2:
            continue
        period = re.fullmatch(r"(?:(\d{4})/\s*)?(1|4|7|10)\s*-\s*(3|6|9|12)\.", row[0].strip())
        if not period:
            continue
        y, start, end = period.groups()
        if y:
            year = int(y)
        if year is None or int(end) != int(start) + 2:
            raise Pending("ESRI_REFERENCE_QUARTER_FORMAT_MISMATCH")
        key = f"{year}Q{(int(start)+2)//3}"
        raw_value = row[1].strip()
        if not raw_value:
            continue
        if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", raw_value) or key in series:
            raise Pending("ESRI_GDP_PRINT_INVALID_OR_REPEATED")
        value = float(raw_value)
        if not -30 < value < 30:
            raise Pending("ESRI_GDP_PRINT_OUT_OF_RANGE")
        series[key] = value
    prior = previous_quarter(quarter)
    if not series or next(reversed(series)) != quarter or prior not in series:
        raise Pending("ESRI_CSV_CURRENT_AND_PREVIOUS_QUARTERS_NOT_VERIFIED")
    return series[quarter], series[prior]


def fetch_csv(url):
    request = Request(url, headers={"Accept": "text/csv", "User-Agent": "GMFQ research source audit/1.0"})
    with urlopen(request, timeout=12) as response:
        raw = response.read(MAX_CSV_BYTES + 1)
        if response.status != 200 or response.geturl() != url or not 0 < len(raw) <= MAX_CSV_BYTES:
            raise Pending("ESRI_CSV_TRANSPORT_NOT_VERIFIED")
        return raw


def collect(now, *, path=ARCHIVE, fetch=retrieve, csv_fetch=fetch_csv, apply=False):
    data = archive_for(path)
    latest = data["editions"][-1]["quarter"] if data["editions"] else None
    quarter = next_quarter(latest) if latest else FIRST
    y, n = quarter_parts(next_quarter(quarter))
    period_closed = date(y, 3*n - 2, 1)
    today = now.astimezone(ROME).date()
    pending = {"status": "AWAITING_ESRI_FIRST_ESTIMATE", "next_quarter": quarter, "last_archived_quarter": latest}
    if today < period_closed:
        return pending
    index, edition, table = edition_urls(quarter)
    try:
        raw_index, final = fetch(index, HOST)
        if final != index:
            raise Pending("ESRI_ARCHIVE_URL_CHANGED")
        released = release_date(raw_index, quarter)
        if released is None or released > today:
            return pending
        if released < period_closed or (latest and released.isoformat() <= data["editions"][-1]["publisher_release_day"]):
            raise Pending("ESRI_RELEASE_DATE_INVALID")
        raw_edition, final = fetch(edition, HOST)
        if final != edition or "The 1st preliminary" not in source_text(raw_edition):
            raise Pending("ESRI_EDITION_IDENTITY_MISMATCH")
        if table.removeprefix(f"https://{HOST}") not in raw_edition.decode("utf-8"):
            raise Pending("ESRI_REAL_QOQ_TABLE_NOT_LINKED")
        raw = csv_fetch(table)
        value, prior = parse_csv(raw, quarter)
    except (OSError, Pending, ValueError, csv.Error) as error:
        return {"status": "SOURCE_UNAVAILABLE_ARCHIVE_RETAINED", "reason": str(error),
                "last_archived_quarter": latest}
    row = {"quarter": quarter, "publisher_release_day": released.isoformat(),
           "reported_value": value, "prior_qoq": prior, "source_url": edition,
           "csv_url": table, "source_html_sha256": sha256(raw_edition).hexdigest(),
           "csv_sha256": sha256(raw).hexdigest()}
    if apply:
        append_edition(path, data, row, now)
    return {"status": "ARCHIVED" if apply else "VERIFIED_PREVIEW", **row}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    print(json.dumps(collect(datetime.now(timezone.utc), apply=a.apply), sort_keys=True))


if __name__ == "__main__":
    main()
