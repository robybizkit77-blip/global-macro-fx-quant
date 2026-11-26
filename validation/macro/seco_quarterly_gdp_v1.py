"""Archive dated Swiss real GDP flash releases and their comparable prior quarter."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re

from validation.macro.capture_official_postrelease_actuals_v1 import Pending, retrieve
from validation.macro.capture_uk_ch_gdp_official_firstseen_v11 import signed_amount, source_text
from validation.macro.esri_quarterly_gdp_v1 import next_quarter
from validation.macro.ons_quarterly_gdp_v1 import (
    MONTHS, ROME, append_edition, previous_quarter, quarter_parts,
)
from validation.macro.v3_gdp_q3_official_overlay_v1 import (
    SECO_METHODOLOGY, observed_q3_updates,
)

ARCHIVE = Path(__file__).with_name("SECO_FLASH_QUARTERLY_GDP_V1.json")
SCHEMA = "GMFQ_SECO_FLASH_QUARTERLY_GDP_V1"
FIRST = "2026Q3"
HOST = "www.seco.admin.ch"
INDEX_HOST = "www.kmu.admin.ch"
INDEX = f"https://{INDEX_HOST}/en/news-state-secretariat-for-economic-affairs-seco"
ARTICLE_PATH = r"/en/newnsb/[A-Za-z0-9_-]+"
ARTICLE_BASE = f"https://{HOST}"
ORDINALS = ("first", "second", "third", "fourth")
UNIT = "PERCENT_QOQ_SA_CALENDAR_SPORTS"
FLASH = "PRELIMINARY_FLASH"
DETAIL = "QUARTERLY_NATIONAL_ACCOUNTS"
RELEASE_FIELDS = ("quarter", "publisher_release_day", "reported_value",
                  "publication_stage", "source_url", "source_html_sha256")
AMOUNT = (
    r"(?:(?P<verb>grew|grown|rose|risen|increased|fell|fallen|decreased|"
    r"contracted|declined|shrunk|shrank)\s+(?:by\s+)?(?P<rate>\d+(?:\.\d+)?)\s*%"
    r"|(?:been|remained) (?:flat|unchanged|stable)|stagnated|shown no growth)"
)


def period(quarter):
    year, number = quarter_parts(quarter)
    return f"{ORDINALS[number-1]} quarter of {year}"


def quarter_end_exclusive(quarter):
    year, number = quarter_parts(next_quarter(quarter))
    return date(year, 3*number - 2, 1)


def headline(quarter, stage):
    if stage == FLASH:
        return f"GDP flash for the {period(quarter)}:"
    return f"Gross domestic product in the {period(quarter)}:"


def discover(raw, quarter, stage):
    name = f"More about «{headline(quarter, stage)}"
    links = set()
    for tag in re.findall(r"<a\b[^>]+>", raw.decode("utf-8"), re.I):
        label = re.search(r'\baria-label="([^"]+)"', tag)
        if label and unescape(label[1]).casefold().startswith(name.casefold()):
            href = re.search(r'\bhref="([^"]+)"', tag)
            if not href or not re.fullmatch(ARTICLE_PATH, href[1]):
                raise Pending("SECO_NEWS_INDEX_ARTICLE_PATH_INVALID")
            links.add(ARTICLE_BASE + href[1])
    if len(links) > 1:
        raise Pending("SECO_NEWS_INDEX_EDITION_NOT_UNIQUE")
    return next(iter(links), None)


def parse_article(raw, quarter, stage):
    html = raw.decode("utf-8")
    title = re.search(r"<h1\b[^>]*>(.*?)</h1>", html, re.I | re.S)
    if not title or not source_text(title[0].encode()).casefold().startswith(
        headline(quarter, stage).casefold()
    ):
        raise Pending("SECO_EDITION_HEADLINE_MISMATCH")
    published = re.findall(r"Published on (\d{1,2}) ([A-Za-z]+) (20\d{2})\s*</", html[:title.start()])
    if len(published) != 1 or published[0][1] not in MONTHS:
        raise Pending("SECO_EDITION_PUBLICATION_DAY_MISSING")
    dd, month, yy = published[0]
    released = date(int(yy), MONTHS.index(month)+1, int(dd))
    paragraphs = re.search(r"<p\b[^>]*>(.*?)</p>", html[title.end():], re.I | re.S)
    lead = source_text(paragraphs[0].encode()) if paragraphs else ""
    dateline = re.match(r"Bern,\s*(\d{2}\.\d{2}\.20\d{2})\s*[—–-]\s*(.*)", lead)
    if not dateline or datetime.strptime(dateline[1], "%d.%m.%Y").date() != released:
        raise Pending("SECO_EDITION_DATELINE_MISMATCH")
    reference = period(quarter)
    if stage == FLASH:
        pattern = (
            r"According to the early estimate of Switzerland.s quarterly real GDP"
            r"[^()]{0,90}\(['‘]GDP flash['’]\),\s*(?:the Swiss economy|Swiss economic output|Swiss GDP)"
            rf"\s+is estimated to have\s+{AMOUNT}\s+in the {reference}\b"
        )
    else:
        text = source_text(raw)
        if not re.search(
            r"quarter-on-quarter growth rates in real terms, seasonally adjusted", text, re.I
        ):
            raise Pending("SECO_DETAILED_REAL_SEASONAL_QOQ_NOT_VERIFIED")
        pattern = (
            rf"In the {reference},\s+Switzerland.s (?:gross domestic product\s*\(GDP\)|GDP)"
            rf"\s+adjusted for sporting events\s+{AMOUNT}(?=\s|[.,(;¹²]|$)"
        )
    match = re.match(pattern, dateline[2], re.I)
    if not match:
        raise Pending("SECO_REAL_SPORT_ADJUSTED_GDP_HEADLINE_VALUE_NOT_VERIFIED")
    value = signed_amount(match["verb"], match["rate"]) if match["verb"] else 0.0
    return released, value


def release_record(fetch, url, quarter, stage):
    raw, final = fetch(url, HOST)
    if final != url:
        raise Pending("SECO_DATED_ARTICLE_REDIRECT")
    released, value = parse_article(raw, quarter, stage)
    return {
        "quarter": quarter, "publisher_release_day": released.isoformat(), "reported_value": value,
        "publication_stage": stage, "source_url": url, "source_html_sha256": sha256(raw).hexdigest(),
    }


def validate_release(row, quarter, stage):
    value = row["reported_value"]
    day = date.fromisoformat(row["publisher_release_day"])
    if (row["quarter"] != quarter or row["publication_stage"] != stage
            or day < quarter_end_exclusive(quarter) or type(value) not in (int, float)
            or not -30 < value < 30
            or not re.fullmatch(re.escape(ARTICLE_BASE) + ARTICLE_PATH, row["source_url"])
            or not re.fullmatch(r"[a-f0-9]{64}", row["source_html_sha256"])):
        raise ValueError("invalid archived SECO release")
    return day


def archive_for(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA or not isinstance(data.get("editions"), list):
        raise ValueError("invalid SECO archive")
    quarter = FIRST
    last_day = date.min
    previous = None
    for row in data["editions"]:
        release_day = validate_release(row, quarter, FLASH)
        prior = row["prior"]
        prior_stage = prior["publication_stage"]
        if prior_stage != DETAIL and (
            previous is None or prior != {field: previous[field] for field in RELEASE_FIELDS}
        ):
            raise ValueError("SECO prior flash differs from its archived edition")
        prior_day = validate_release(prior, previous_quarter(quarter), prior_stage)
        seen = datetime.fromisoformat(row["first_observed_at_utc"])
        if (release_day <= last_day or release_day <= prior_day
                or seen.utcoffset() is None or seen.astimezone(ROME).date() < release_day):
            raise ValueError("invalid archived SECO edition chronology")
        quarter, last_day = next_quarter(quarter), release_day
        previous = row
    return data


def observation(row):
    return {
        "reference_quarter": row["quarter"], "publisher_release_day": row["publisher_release_day"],
        "publisher_source": row["source_url"], "reported_value": row["reported_value"],
        "reported_unit": UNIT, "publication_stage": row["publication_stage"],
        "nonannualized_qoq_descriptive_pct": row["reported_value"], "is_growth_strength_score": False,
        "national_definitions_are_not_fully_cross_country_equivalent": True,
        "later_revisions_not_identical_to_first_release": True,
        "historical_pit_training_vintages_certified": False,
    }


def latest_growth(as_of, *, path=ARCHIVE, live_cutoff=None):
    from validation.macro.ons_quarterly_gdp_v1 import edition_available
    for row in reversed(archive_for(path)["editions"]):
        if edition_available(row, as_of, live_cutoff):
            return {
                **observation(row), "prior_documented_quarter": observation(row["prior"]),
                "publisher_methodology": SECO_METHODOLOGY,
                "comparison_uses_distinct_publisher_editions": True,
                "source_first_observed_at_utc": row["first_observed_at_utc"],
            }
    return None


def collect(now, *, path=ARCHIVE, fetch=retrieve, apply=False):
    data = archive_for(path)
    last = data["editions"][-1] if data["editions"] else None
    quarter = next_quarter(last["quarter"]) if last else FIRST
    previous = previous_quarter(quarter)
    today = now.astimezone(ROME).date()
    state = {"next_quarter": quarter, "last_archived_quarter": last["quarter"] if last else None}
    waiting = {"status": "AWAITING_SECO_FLASH", **state}
    if today < quarter_end_exclusive(quarter):
        return waiting
    try:
        index, final = fetch(INDEX, INDEX_HOST)
        if final not in (INDEX, INDEX + "/"):
            raise Pending("SECO_NEWS_INDEX_REDIRECT")
        flash = discover(index, quarter, FLASH)
        if flash is None:
            return waiting
        row = release_record(fetch, flash, quarter, FLASH)
        released = validate_release(row, quarter, FLASH)
        if released > today:
            return waiting
        prior_fallback_reason = None
        try:
            detail = discover(index, previous, DETAIL)
            if detail is None:
                raise Pending("SECO_COMPARABLE_PREVIOUS_QUARTER_NOT_IN_NEWS_INDEX")
            prior = release_record(fetch, detail, previous, DETAIL)
            if validate_release(prior, previous, DETAIL) >= released:
                raise Pending("SECO_COMPARABLE_PREVIOUS_QUARTER_PUBLISHED_AFTER_FLASH")
        except (OSError, ValueError, Pending) as error:
            if last is None:
                raise
            # Use the same-basis prior flash when the details are not verifiable.
            prior = {field: last[field] for field in RELEASE_FIELDS}
            prior_fallback_reason = str(error)
        if last and last["publisher_release_day"] >= released.isoformat():
            raise Pending("SECO_INVALID_RELEASE_CHRONOLOGY")
        if last is None:
            seed = observed_q3_updates(today.isoformat()).get("CHF")
            if seed is None:
                raise Pending("SECO_BASELINE_NOT_YET_ELIGIBLE")
            for actual, known in ((row, seed), (prior, seed["prior_documented_quarter"])):
                actual_id = actual["source_url"].rsplit("/", 1)[-1]
                expected_id = known["publisher_source"].rsplit("/", 1)[-1]
                if actual_id != expected_id or any(
                    actual[key] != known[key] for key in ("reported_value", "publisher_release_day")
                ):
                    raise Pending("SECO_BASELINE_RELEASE_MISMATCH")
    except (OSError, ValueError, Pending) as error:
        return {"status": "SOURCE_UNAVAILABLE_ARCHIVE_RETAINED", "reason": str(error), **state}
    row["prior"] = prior
    if apply:
        append_edition(path, data, row, now)
    receipt = {"status": "ARCHIVED" if apply else "VERIFIED_PREVIEW", **row}
    if prior_fallback_reason is not None:
        receipt["prior_fallback_reason"] = prior_fallback_reason
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(collect(datetime.now(timezone.utc), apply=args.apply), sort_keys=True))


if __name__ == "__main__":
    main()
