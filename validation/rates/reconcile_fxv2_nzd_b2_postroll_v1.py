#!/usr/bin/env python3
"""Reconcile the same RBNZ B2 edition in HTML and XLSX for pair research."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from openpyxl import load_workbook

from collect_rbnz_b2_daily_web_v1 import (
    BOND_2, BOND_10, NZ, ROLL, SCHEMA as WEB_SCHEMA, URL, USER_AGENT,
    must, parse,
)

SCHEMA = "GMFQ_NZD_RBNZ_B2_RECONCILED_RESEARCH_V1"
XLSX_URL = "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close.xlsx"
GOV_GROUP = "Secondary market government bond closing yields"
SERIES = (
    ("2 year", "%pa", "INM.DG102.NZZCF"),
    ("10 year", "%pa", "INM.DG110.NZZCF"),
    (BOND_2, "%", "INM.DG19.NS2904ZC"),
    (BOND_10, "%", "INM.DG19.NS3704ZC"),
)
LIMIT = 5_000_000
DEFAULT_OUTPUT = Path("site/fx-quant-v2/nzd-rbnz-b2-reconciled-research.json")


def workbook_observations(raw: bytes, release: str) -> list[dict]:
    must(raw.startswith(b"PK\x03\x04") and 1000 <= len(raw) < LIMIT,
         "official daily XLSX size or signature")
    wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    try:
        description = wb["Table Description"]
        description.reset_dimensions()
        meta = dict(description.iter_rows(max_row=4, max_col=2, values_only=True))
        publication = meta.get("Published Date")
        must(meta.get("Published By") == "Reserve Bank of New Zealand"
             and meta.get("Table") == "Daily wholesale interest rates (% pa) - B2"
             and isinstance(publication, datetime) and publication.date().isoformat() == release,
             "official daily workbook has a different release from the web table")

        sheet = wb["Data"]
        # The official workbook's declared sheet dimension is A1:A1.
        sheet.reset_dimensions()
        group, label, _, units, ids = sheet.iter_rows(max_row=5, max_col=100, values_only=True)
        indexes = []
        for series in SERIES:
            matching = [i for i, cells in enumerate(zip(group, label, units, ids))
                        if cells == (GOV_GROUP, *series)]
            must(len(matching) == 1, "government maturity/bond, unit or series ID changed: " + series[0])
            indexes.append(matching[0])

        observations = []
        previous_day = ""
        for row in sheet.iter_rows(min_row=6, max_col=max(indexes) + 1, values_only=True):
            if not isinstance(row[0], datetime):
                continue
            day = row[0].date().isoformat()
            if day < ROLL:
                continue
            must(previous_day < day <= release and row[0].weekday() < 5,
                 "post-roll XLSX rows have unexpected order, duplicate or future date")
            previous_day = day
            values = [row[i] for i in indexes]
            if all(v is None for v in values):
                continue
            must(all(type(v) in (int, float) and math.isfinite(v) and -5 < v < 25 for v in values),
                 "missing or invalid government closing yield on " + day)
            y2, y10, bond2, bond10 = values
            must(y2 == bond2 and y10 == bond10, "post-roll benchmark and named bond disagree on " + day)
            observations.append({"date": day, "2Y": y2, "10Y": y10})
        return observations
    finally:
        wb.close()


def reconcile(web: dict, html: bytes, xlsx: bytes, previous: dict | None = None) -> dict:
    must(web["schema"] == WEB_SCHEMA, "wrong daily HTML source schema")
    publication = web["release_date"]
    observations = workbook_observations(xlsx, publication)
    web_rows = web["post_roll_table_rows"]
    matched = [row["date"] for row in web_rows]
    by_date = {row["date"]: row for row in observations}
    must(len(matched) >= 6 and all(by_date.get(row["date"]) == row for row in web_rows),
         "web and workbook need at least six exact matching post-roll observations")
    must(observations[0]["date"] == ROLL and observations[-1]["date"] == web["as_of"],
         "workbook roll anchor or latest observation disagrees with the current edition")
    if previous:
        must(previous.get("schema") == SCHEMA and previous["publication_date"] <= publication
             and previous["last_observation_date"] <= web["as_of"],
             "previous research receipt invalid or source rollback")
        must(all(by_date.get(row["date"]) == row for row in previous["observations"]),
             "published observations were revised or removed; review the source edition")
        if previous["publication_date"] == publication:
            must(previous["observations"] == observations, "same-edition observation change")
            return previous
    return {
        "schema": SCHEMA,
        "status": "RBNZ_B2_HTML_XLSX_AGREE_POSTROLL_RESEARCH_ONLY",
        "source": "Reserve Bank of New Zealand B2 · NZFMA indicative government bond closing yields",
        "source_url": URL,
        "xlsx_url": XLSX_URL,
        "html_sha256": hashlib.sha256(html).hexdigest(),
        "xlsx_sha256": hashlib.sha256(xlsx).hexdigest(),
        "publication_date": publication,
        "last_observation_date": web["as_of"],
        "benchmark_roll_date": ROLL,
        "benchmark_2Y": BOND_2,
        "benchmark_10Y": BOND_10,
        "html_xlsx_matched_dates": matched,
        "observations": observations,
        "research_only": True,
        "no_interpolation": True,
        "eligible_for_core": False,
        "eligible_for_fx_pair_engine": False,
        "eligible_for_backtests": False,
        "eligible_for_automatic_promotion": False,
    }


def download(url: str, content_type: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": content_type})
    with urlopen(request, timeout=25) as response:
        must(response.status == 200 and response.headers.get_content_type() == content_type,
             "unexpected RBNZ source response for " + url)
        payload = response.read(LIMIT)
    must(1000 <= len(payload) < LIMIT, "RBNZ source response length")
    return payload


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--html", type=Path, help="local copy of the official HTML edition")
    p.add_argument("--xlsx", type=Path, help="local copy of the official daily workbook edition")
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--web-receipt", type=Path)
    args = p.parse_args()
    if bool(args.html) != bool(args.xlsx):
        p.error("--html and --xlsx are used together")
    html = args.html.read_bytes() if args.html else download(URL, "text/html")
    web = parse(html.decode("utf-8"), now_nz=datetime.now(NZ))
    if args.web_receipt:
        args.web_receipt.write_text(json.dumps(web, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    xlsx = (args.xlsx.read_bytes() if args.xlsx else download(
        XLSX_URL, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
    previous = json.loads(args.output.read_text()) if args.output.is_file() else None
    doc = reconcile(web, html, xlsx, previous)
    if doc != previous:
        args.output.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("NZD_B2_RECONCILED_RESEARCH_PASS", json.dumps({
        "publication_date": doc["publication_date"],
        "last_observation_date": doc["last_observation_date"],
        "same_edition_rows": len(doc["html_xlsx_matched_dates"]),
        "post_roll_observations": len(doc["observations"]),
        "published_file_changed": doc != previous,
    }))


if __name__ == "__main__":
    main()
