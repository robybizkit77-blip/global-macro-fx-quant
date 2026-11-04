#!/usr/bin/env python3
"""Official RBNZ B2 public-page daily market benchmark reader (V2 research only).

This extracts the published same-row 2Y/10Y NZFMA government benchmark closes.
It deliberately does not assert XLSX reconciliation, does not call them OIS,
and never modifies canonical Rates, live signals or historical backtests.
"""
from __future__ import annotations
import argparse
import datetime as dt
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

URL = "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates"
SCHEMA = "GMFQ_FXV2_NZD_RBNZ_B2_PUBLIC_HTML_RESEARCH_V1"
NZ = ZoneInfo("Pacific/Auckland")
BOND_2 = "April 2029"
BOND_10 = "April 2037"
ROLL = "2026-10-30"
# Page note published 2 November: 1Y Apr27 -> May28; 2Y May28 -> Apr29;
# 10Y May36 -> Apr37. Revalidate if authority changes its benchmark again.
EXPECTED_ROLL_NOTE_DATE = dt.date(2026, 11, 2)
ENGLISH = {
    "Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
    "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12,
}
DATE_RE = re.compile(r"^(\d{1,2}) ([A-Za-z]{3}) (\d{4})$")
SPACED = re.compile(r"\s+")

class B2Tables(HTMLParser):
    """Collect tabular visible cells without executing scripts."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.cells = None
        self.cell = None
        self.table = None
        self.tables = []
        self.all_text = []
    def handle_starttag(self, name, attrs):
        if name == "table":
            self.depth += 1
            if self.depth == 1:
                self.table = []
        if self.depth and name == "tr":
            self.cells = []
        elif self.depth and name in ("td","th") and self.cells is not None:
            self.cell = []
    def handle_data(self, data):
        if data.strip():
            self.all_text.append(data.strip())
        if self.cell is not None:
            self.cell.append(data)
    def handle_endtag(self, name):
        if name in ("td","th") and self.cell is not None:
            self.cells.append(SPACED.sub(" ", "".join(self.cell)).strip())
            self.cell = None
        elif name == "tr" and self.cells is not None and self.table is not None:
            if self.cells: self.table.append(self.cells)
            self.cells = None
        elif name == "table" and self.depth:
            if self.depth == 1 and self.table:
                self.tables.append(self.table)
                self.table = None
            self.depth -= 1

def must(ok, why):
    if not ok:
        raise ValueError("RBNZ_B2_PUBLIC_HTML_GUARD: " + why)

def parse_date(s: str) -> dt.date | None:
    hit = DATE_RE.fullmatch(SPACED.sub(" ", s.strip()))
    if not hit or hit[2].title() not in ENGLISH:
        return None
    return dt.date(int(hit[3]),ENGLISH[hit[2].title()],int(hit[1]))

def validate_layout(rows: list[list[str]]) -> bool:
    # One header row must unambiguously mark 2Y and 10Y in the *government*
    # bond group, after the 30/60/90-day bank bills.
    for row in rows:
        if len(row) != 13:
            continue
        low = [x.lower().strip() for x in row]
        if (low[0] == "date" and "official cash rate" in low[1]
            and ("2 year" in low[9] or low[9] == "2y")
            and ("10 year" in low[11] or low[11] == "10y")
            and "30 days" in low[5] and "90 days" in low[7]):
            return True
    return False

def parse(html: str, *, now_nz: dt.datetime) -> dict:
    must(now_nz.tzinfo is not None, "aware NZ time required")
    now = now_nz.astimezone(NZ).date()
    parser = B2Tables()
    parser.feed(html)
    txt = SPACED.sub(" ", " ".join(parser.all_text))
    must("Wholesale interest rates (B2)" in txt, "official B2 title missing")
    must("Secondary market government bond closing yields" in txt,
         "official government bond group missing")
    must(BOND_2.lower() in txt.lower() and BOND_10.lower() in txt.lower(),
         "current benchmark names not present")
    # A later 'Changes to the ... benchmarks' note must be reviewed before
    # continuing with the April-2029/2037 bond identifiers.
    note=re.search(r"Changes to the 1, 2 and 10-year bond benchmarks\s+(\d{1,2}) "
                   r"([A-Za-z]+) (\d{4})",txt,re.I)
    must(bool(note), "current official bond-roll note missing")
    note_date = dt.datetime.strptime(" ".join(note.groups()),"%d %B %Y").date()
    must(note_date == EXPECTED_ROLL_NOTE_DATE, "new bond roll note requires review")
    published=re.search(r"Released:\s+(\d{1,2}) ([A-Za-z]+) (\d{4})",txt)
    must(bool(published), "official release date missing")
    release=dt.datetime.strptime(" ".join(published.groups()),"%d %B %Y").date()
    must(release<=now, "source release date in the future")

    candidates=[]
    for rows in parser.tables:
        if not validate_layout(rows):
            continue
        parsed = []
        for rec in rows:
            if len(rec)!=13:
                continue
            day=parse_date(rec[0])
            if not day: continue
            try:
                # These are government yields; column 12 is a *swap* spread!
                y2=float(rec[9]);y10=float(rec[11])
            except ValueError:
                continue
            must(math.isfinite(y2) and math.isfinite(y10) and
                 -5 < y2 < 25 and -5 < y10 < 25,"implausible 2Y or 10Y")
            must(day<=now and day<=release, "market row dated after publication")
            parsed.append((day,round(y2,4),round(y10,4)))
        if parsed:
            candidates.append(parsed)
    must(len(candidates)==1,"ambiguous or missing B2 daily market table")
    values=candidates[0]
    must(len(values)>=2, "not enough B2 same-row observations")
    must(len({x[0] for x in values})==len(values),"duplicate daily B2 row")
    values.sort(key=lambda x:x[0])
    last=values[-1]
    must(last[0] >= dt.date.fromisoformat(ROLL), "last observation before benchmark roll")
    must((now-last[0]).days<=9, "last row too old for daily B2")
    # If a source serves an earlier page, never call it a current release.
    must(release >= last[0], "release older than last row")
    post=[x for x in values if x[0] >= dt.date.fromisoformat(ROLL)]
    return {
        "schema":SCHEMA,"status":"OFFICIAL_PUBLIC_HTML_TABLE_CAPTURED_RESEARCH_ONLY",
        "source": "Reserve Bank of New Zealand · B2 Wholesale Interest Rates",
        "source_url":URL,
        "as_of":last[0].isoformat(),"2Y":last[1],"10Y":last[2],
        "curve_bp":round((last[2]-last[1])*100,2),
        "release_date":release.isoformat(),
        "benchmark_roll_date":ROLL,
        "benchmark_2Y":BOND_2, "benchmark_10Y":BOND_10,
        "benchmark_note_date":note_date.isoformat(),
        "post_roll_table_rows":[
            {"date":day.isoformat(),"2Y":y2,"10Y":y10}
            for day,y2,y10 in post[-12:]
        ],
        "authority":"Reserve Bank of New Zealand",
        "official_html_observed":True,"independent_xlsx_reconciled":False,
        "eligible_for_core":False,"eligible_for_fx_pair_engine":False,
        "eligible_for_backtests":False,
        "notes":"Official RBNZ public HTML summary only, not XLSX-verified. Indicative NZFMA government benchmark closes, not OIS. No cross-roll price change is valid.",
    }

def fetch() -> str:
    request=Request(URL,headers={
        "User-Agent":"GlobalMacroFXQuant-RBNZ-B2-Research/1.0 (contact via project GitHub)",
        "Accept":"text/html,application/xhtml+xml",
        "Cache-Control":"no-cache",
    })
    with urlopen(request,timeout=25) as r:
        must(r.status==200,"RBNZ public table HTTP "+str(r.status))
        body=r.read(3_000_000)
    must(1000 < len(body) < 3_000_000,"unusual public page byte length")
    return body.decode("utf-8",errors="strict")

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--input",type=Path,help="offline fixture")
    ap.add_argument("--as-of-nz",help="aware NZ timestamp only for deterministic test runs")
    args=ap.parse_args()
    now=dt.datetime.fromisoformat(args.as_of_nz) if args.as_of_nz else dt.datetime.now(NZ)
    record=parse(args.input.read_text("utf-8") if args.input else fetch(),now_nz=now)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("FXV2_NZD_B2_LIVE_TABLE",json.dumps({
        "as_of":record["as_of"],"release_date":record["release_date"],
        "2Y":record["2Y"],"10Y":record["10Y"],
        "canonical_rates_untouched":True,"independent_xlsx_reconciled":False,
    }))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
