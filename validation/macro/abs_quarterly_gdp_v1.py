"""ABS real quarterly GDP, same-edition prior, research only."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import re

from validation.macro.capture_official_postrelease_actuals_v1 import Pending, retrieve
from validation.macro.capture_uk_ch_gdp_official_firstseen_v11 import source_text
from validation.macro.ons_quarterly_gdp_v1 import (
    ROOT, ROME, append_edition, archived_growth, load_archive, previous_quarter, quarter_parts,
)

ARCHIVE = ROOT / "validation/macro/ABS_QUARTERLY_GDP_V1.json"
SCHEMA = "GMFQ_ABS_QUARTERLY_GDP_V1"
HOST = "www.abs.gov.au"
BASE = f"https://{HOST}/statistics/economy/national-accounts/australian-national-accounts-national-income-expenditure-and-product/"
MONTHS = ("March", "June", "September", "December")
UNIT = "PERCENT_QOQ_SA_CHAIN_VOLUME"
FIRST = "2026Q3"


def next_quarter(quarter):
    y, q = quarter_parts(quarter)
    return f"{y}Q{q+1}" if q < 4 else f"{y+1}Q1"


def edition_url(quarter):
    y, q = quarter_parts(quarter)
    return BASE + MONTHS[q-1][:3].lower() + "-" + str(y)


def parse_bulletin(raw, quarter, today):
    y, q = quarter_parts(quarter)
    text = source_text(raw).replace("\u2212", "-")
    period = MONTHS[q-1] + " " + str(y)
    header = re.search(r"Reference period\s+" + re.escape(period) +
                       r"\s+Released\s+(\d{1,2}/\d{1,2}/20\d{2})\b", text, re.I)
    if not header or "Australian National Accounts: National Income, Expenditure and Product" not in text:
        raise Pending("ABS_GDP_EDITION_IDENTITY_MISMATCH")
    released = datetime.strptime(header.group(1), "%d/%m/%Y").date()
    ny, nq = quarter_parts(next_quarter(quarter))
    if not date(ny, 3*nq-2, 1) <= released <= today:
        raise Pending("ABS_GDP_RELEASE_DATE_OUT_OF_SCOPE")
    # Exact real GDP chart table, not nominal GDP, per capita, annual growth or another chart.
    title = r"Gross domestic product,\s*chain volume measures,\s*seasonally adjusted"
    matches = list(re.finditer(title + r"\s+Quarterly growth\s*\(%\)\s+Through the year\s*\(%\)", text, re.I))
    if len(matches) != 1:
        raise Pending("ABS_REAL_GDP_TABLE_NOT_UNIQUE")
    tail = text[matches[0].end():]
    def label(k):
        year, n = quarter_parts(k)
        return MONTHS[n-1][:3] + "-" + str(year)[-2:]
    num = r"[+-]?\d+(?:\.\d+)?"
    pair = re.findall(r"(?<!\w)" + re.escape(label(previous_quarter(quarter))) +
                      r"\s+(" + num + r")\s+" + num + r"\s+" +
                      re.escape(label(quarter)) + r"\s+(" + num + r")\s+" + num + r"(?![\d.])",
                      tail, re.I)
    if len(pair) != 1:
        raise Pending("ABS_GDP_CONTIGUOUS_QUARTERS_NOT_VERIFIED")
    prior, current = map(float, pair[0])
    if not all(-30 < v < 30 for v in (prior, current)):
        raise Pending("ABS_GDP_QOQ_OUT_OF_RANGE")
    return dict(quarter=quarter, publisher_release_day=released.isoformat(),
                reported_value=current, prior_qoq=prior, source_url=edition_url(quarter))


def archive_for(path):
    data = load_archive(path, schema=SCHEMA, minimum=FIRST, url_for=edition_url)
    if any(row["prior_qoq"] is None for row in data["editions"]):
        raise ValueError("ABS archive requires same-edition prior")
    return data


def latest_growth(as_of, *, path=ARCHIVE):
    value = archived_growth(as_of, archive_for(path)["editions"],
                            stage="QUARTERLY_NATIONAL_ACCOUNTS",
                            same_edition_field="prior_value_from_same_publisher_edition")
    if value is not None:
        value["reported_unit"] = UNIT
        value["prior_documented_quarter"]["reported_unit"] = UNIT
    return value


def collect(now, *, path=ARCHIVE, fetch=retrieve, apply=False):
    data = archive_for(path)
    latest = data["editions"][-1] if data["editions"] else None
    quarter = next_quarter(latest["quarter"]) if latest else FIRST
    ny, nq = quarter_parts(next_quarter(quarter))
    today = now.astimezone(ROME).date()
    if today < date(ny, 3*nq-2, 1):
        return {"status": "AWAITING_ABS_QUARTER_CLOSE", "next_quarter": quarter}
    url = edition_url(quarter)
    try:
        raw, final = fetch(url, HOST)
        if final != url:
            raise Pending("ABS_GDP_EDITION_REDIRECT")
        row = parse_bulletin(raw, quarter, today)
        if latest and row["publisher_release_day"] <= latest["publisher_release_day"]:
            raise Pending("ABS_GDP_RELEASE_DATE_REGRESSED")
    except (OSError, ValueError, Pending) as exc:
        return {"status": "SOURCE_UNAVAILABLE_ARCHIVE_RETAINED",
                "next_quarter": quarter, "reason": str(exc),
                "last_archived_quarter": latest["quarter"] if latest else None}
    if apply:
        append_edition(path, data, {**row, "source_html_sha256": sha256(raw).hexdigest()}, now)
    return {"status": "ARCHIVED" if apply else "VERIFIED_PREVIEW", **row}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--verify-quarter")
    args = p.parse_args()
    now = datetime.now(timezone.utc)
    if args.verify_quarter:
        if args.apply:
            p.error("verification is read-only")
        url = edition_url(args.verify_quarter)
        raw, final = retrieve(url, HOST)
        if final != url:
            raise Pending("ABS_GDP_EDITION_REDIRECT")
        print(json.dumps(parse_bulletin(raw, args.verify_quarter, now.astimezone(ROME).date()), sort_keys=True))
    else:
        print(json.dumps(collect(now, apply=args.apply), sort_keys=True))


if __name__ == "__main__":
    main()
