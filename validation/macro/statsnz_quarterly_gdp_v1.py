"""Stats NZ production GDP: dated release, same-edition prior, research only."""
from datetime import date, datetime, timezone
from hashlib import sha256
import argparse
import json
import re

from validation.macro.capture_official_postrelease_actuals_v1 import Pending, retrieve
from validation.macro.capture_uk_ch_gdp_official_firstseen_v11 import source_text
from validation.macro.ons_quarterly_gdp_v1 import (
    ROOT, ROME, append_edition, archived_growth, load_archive, previous_quarter, quarter_parts,
)
from validation.macro.abs_quarterly_gdp_v1 import next_quarter

HOST = "www.stats.govt.nz"
BASE = f"https://{HOST}/information-releases/gross-domestic-product-"
ARCHIVE = ROOT / "validation/macro/STATSNZ_QUARTERLY_GDP_V1.json"
SCHEMA = "GMFQ_STATSNZ_QUARTERLY_GDP_V1"
FIRST = "2026Q3"
UNIT = "PERCENT_QOQ_SA_CHAIN_VOLUME_PRODUCTION"
MONTHS = ("March", "June", "September", "December")
CALENDAR_MONTHS = "January February March April May June July August September October November December".split()


def label(quarter):
    y, q = quarter_parts(quarter)
    return f"{MONTHS[q-1]} {y}"


def edition_url(quarter):
    return BASE + label(quarter).lower().replace(" ", "-") + "-quarter/"


def parse_bulletin(raw, quarter, today):
    text = source_text(raw).replace("\u2212", "-")
    # Page title and publication date need not be adjacent in the HTML.
    title = r"Gross domestic product:\s*" + re.escape(label(quarter)) + r"\s+quarter\b"
    titles = list(re.finditer(title, text, re.I))
    heading = None
    for match in titles:
        candidate = re.search(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\s*,?\s+\d{1,2}:\d{2}", text[match.end():match.end()+400], re.I)
        if candidate and candidate[2].title() in CALENDAR_MONTHS:
            heading = candidate
            break
    if not heading or heading[2].title() not in CALENDAR_MONTHS:
        raise Pending("STATSNZ_GDP_DATED_EDITION_IDENTITY")
    released = date(int(heading[3]), CALENDAR_MONTHS.index(heading[2].title())+1, int(heading[1]))
    ny, nq = quarter_parts(next_quarter(quarter))
    if not date(ny, 3*nq-2, 1) <= released <= today:
        raise Pending("STATSNZ_GDP_RELEASE_DATE_RANGE")
    if not re.search(r"seasonally adjusted chain.volume terms", text, re.I):
        raise Pending("STATSNZ_REAL_SA_UNIT_MISSING")
    # The release's production GDP paragraph explicitly states both rates.
    # Avoid dependence on graph/table widget DOM serialization.
    number = r"[+-]?\d+(?:\.\d+)?"
    direction = r"(rose|fell|increased|decreased)"
    narrative = re.findall(
        r"\bEconomic activity\s+" + direction + r"\s+(" + number +
        r")\s+percent in the " + re.escape(label(quarter)) +
        r" quarter as measured by gross domestic product\.\s+This follows a\s+(" +
        number + r")\s+percent\s+(rise|fall|increase|decrease)\s+in the " +
        re.escape(label(previous_quarter(quarter))) + r" quarter\.", text, re.I)
    if len(narrative) != 1:
        raise Pending("STATSNZ_PRODUCTION_GDP_TWO_QUARTER_NARRATIVE_NOT_UNIQUE")
    verb, rate, previous_rate, previous_verb = narrative[0]
    current = abs(float(rate)) * (-1 if verb.lower() in ("fell", "decreased") else 1)
    prior = abs(float(previous_rate)) * (-1 if previous_verb.lower() in ("fall", "decrease") else 1)
    if not all(-30 < x < 30 for x in (prior,current)):
        raise Pending("STATSNZ_GDP_OUT_OF_RANGE")
    # Cross-check the headline production GDP, not expenditure GDP.
    hit = re.search(r"In the " + re.escape(label(quarter)) + r" quarter,\s*compared with the " +
                    re.escape(label(previous_quarter(quarter))) + r" quarter:\s*GDP\s+"
                    r"(?:(rose|fell|increased|decreased)\s+("+number+r")\s+percent|"
                    r"(?:was unchanged|remained unchanged|was flat))", text, re.I)
    if not hit:
        raise Pending("STATSNZ_GDP_HEADLINE_MISSING")
    headline = float(hit[2]) * (-1 if hit[1].lower() in ("fell","decreased") else 1) if hit[1] else 0.0
    if headline != current:
        raise Pending("STATSNZ_GDP_HEADLINE_TABLE_DISAGREEMENT")
    return dict(quarter=quarter,publisher_release_day=released.isoformat(),
                reported_value=current,prior_qoq=prior,source_url=edition_url(quarter))


def archive_for(path):
    data = load_archive(path,schema=SCHEMA,minimum=FIRST,url_for=edition_url)
    if any(r["prior_qoq"] is None for r in data["editions"]):
        raise ValueError("Stats NZ archive requires same-edition prior")
    return data


def latest_growth(as_of, *, path=ARCHIVE, live_cutoff=None):
    value = archived_growth(as_of,archive_for(path)["editions"],
                            stage="QUARTERLY_NATIONAL_ACCOUNTS",
                            same_edition_field="prior_value_from_same_publisher_edition", live_cutoff=live_cutoff)
    if value is not None:
        value["reported_unit"] = UNIT
        value["prior_documented_quarter"]["reported_unit"] = UNIT
    return value


def render_bulletin(url):
    # Stats NZ may serve a JavaScript shell to ordinary HTTP clients.
    # Render the exact official edition, not a search snippet or proxy.
    from playwright.sync_api import sync_playwright, Error as BrowserError
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(locale="en-NZ")
                response = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                if not response or response.status != 200 or page.url != url:
                    raise Pending("STATSNZ_BROWSER_EDITION_TRANSPORT")
                page.get_by_text("Key facts", exact=True).first.wait_for(timeout=15000)
                page.get_by_text("as measured by gross domestic product.", exact=False).first.wait_for(state="attached", timeout=15000)
                raw = page.content().encode("utf-8")
                if page.url != url or not 16 < len(raw) <= 2_000_000:
                    raise Pending("STATSNZ_BROWSER_EDITION_INVALID")
                return raw
            finally:
                browser.close()
    except BrowserError as exc:
        raise Pending("STATSNZ_BROWSER_SOURCE_UNAVAILABLE") from exc


def official_edition(quarter, today, fetch=retrieve, render=None):
    url = edition_url(quarter)
    raw, final = fetch(url, HOST)
    if final != url:
        raise Pending("STATSNZ_GDP_EDITION_REDIRECT")
    try:
        return parse_bulletin(raw, quarter, today), raw
    except Pending:
        if render is None:
            raise
        # Fallback still requires every original date/unit/table/headline check.
        rendered = render(url)
        return parse_bulletin(rendered, quarter, today), rendered


def collect(now, *, path=ARCHIVE, fetch=retrieve, render=None, apply=False):
    data = archive_for(path)
    latest = data["editions"][-1] if data["editions"] else None
    quarter = next_quarter(latest["quarter"]) if latest else FIRST
    ny,nq = quarter_parts(next_quarter(quarter))
    today = now.astimezone(ROME).date()
    if today < date(ny,3*nq-2,1):
        return {"status":"AWAITING_STATSNZ_QUARTER_CLOSE","next_quarter":quarter}
    url = edition_url(quarter)
    try:
        row, raw = official_edition(quarter,today,fetch,render)
        if latest and row["publisher_release_day"] <= latest["publisher_release_day"]:
            raise Pending("STATSNZ_GDP_RELEASE_DATE_REGRESSED")
    except (OSError, ValueError, Pending) as error:
        return {"status":"SOURCE_UNAVAILABLE_ARCHIVE_RETAINED","next_quarter":quarter,
                "last_archived_quarter":latest["quarter"] if latest else None,"reason":str(error)}
    if apply:
        append_edition(path,data,{**row,"source_html_sha256":sha256(raw).hexdigest()},now)
    return {"status":"ARCHIVED" if apply else "VERIFIED_PREVIEW",**row}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--verify-quarter")
    a=p.parse_args()
    now=datetime.now(timezone.utc)
    if a.verify_quarter:
        if a.apply:
            p.error("verification is read-only")
        row, _ = official_edition(a.verify_quarter, now.astimezone(ROME).date(), render=render_bulletin)
        print(json.dumps(row,sort_keys=True))
    else:
        print(json.dumps(collect(now,render=render_bulletin,apply=a.apply),sort_keys=True))


if __name__ == "__main__":
    main()
