"""Archive UK quarterly first estimates for the observed Macro V3 research feed."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from validation.macro.capture_official_postrelease_actuals_v1 import Pending, retrieve
from validation.macro.capture_uk_ch_gdp_official_firstseen_v11 import source_text, signed_amount
from validation.macro.v3_gdp_q3_official_overlay_v1 import observed_q3_updates

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "validation/macro/ONS_FIRST_QUARTERLY_GDP_V1.json"
HOST = "www.ons.gov.uk"
BASE = f"https://{HOST}/economy/grossdomesticproductgdp/bulletins/gdpfirstquarterlyestimateuk/"
SCHEMA = "GMFQ_ONS_FIRST_QUARTERLY_GDP_V1"
MIN_QUARTER = "2026Q3"
ROME = ZoneInfo("Europe/Rome")
PERIODS = ("January to March", "April to June", "July to September", "October to December")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")


def quarter_parts(quarter):
    if not isinstance(quarter, str) or not re.fullmatch(r"20\d{2}Q[1-4]", quarter):
        raise ValueError("invalid ONS reference quarter")
    return int(quarter[:4]), int(quarter[-1])


def previous_quarter(quarter):
    year, number = quarter_parts(quarter)
    return f"{year}Q{number - 1}" if number > 1 else f"{year - 1}Q4"


def edition_url(quarter):
    year, number = quarter_parts(quarter)
    return BASE + PERIODS[number - 1].lower().replace(" ", "") + str(year)


def reference(quarter):
    year, number = quarter_parts(quarter)
    period = PERIODS[number - 1]
    start, end = period.split(" to ")
    end_names = {end, end[:3]}
    if end == "September":
        end_names.add("Sept")
    periods = "|".join(re.escape(p) for p in sorted({
        f"{a} to {b}" for a in (start, start[:3]) for b in end_names
    }))
    return rf"Quarter\s+{number}\s*\(\s*(?:{periods})\s*\)\s*{year}\b"


def parse_bulletin(raw, today):
    text = source_text(raw)
    heading = re.search(
        r"GDP first quarterly estimate, UK: (" + "|".join(PERIODS) + r") (20\d{2})\b",
        text, re.I,
    )
    if not heading or re.search(r"This release is not yet published", text, re.I):
        raise Pending("ONS_NOT_A_PUBLISHED_FIRST_QUARTERLY_BULLETIN")
    period, year = heading.group(1).title().replace(" To ", " to "), int(heading.group(2))
    number = PERIODS.index(period) + 1
    quarter = f"{year}Q{number}"
    after = text[heading.end():]
    lead = re.search(
        r"\b1\.\s+Main points\b(.*?)\b2\.\s+(?:Headline GDP figures|GDP)\b", after, re.I,
    )
    date_match = re.search(r"\bRelease date:\s*(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\b",
                           after[:lead.start()] if lead else "", re.I)
    if not date_match or date_match.group(2).title() not in MONTHS:
        raise Pending("ONS_FIRST_ESTIMATE_RELEASE_DATE_NOT_IDENTIFIED")
    released = date(int(date_match.group(3)), MONTHS.index(date_match.group(2).title()) + 1,
                    int(date_match.group(1)))
    next_quarter = date(year + (number == 4), 1 if number == 4 else number * 3 + 1, 1)
    if not next_quarter <= released <= today:
        raise Pending("ONS_QUARTER_OR_RELEASE_DATE_OUT_OF_SCOPE")

    signs = r"increased|grown|risen|decreased|fallen|contracted|declined"
    amount = rf"(?:(?P<verb>{signs})\s+by\s+(?P<rate>\d+(?:\.\d+)?)\s*%|been\s+flat|shown\s+no\s+growth|been\s+unchanged|remained\s+unchanged)"
    hits = list(re.finditer(
        r"\bUK real gross domestic product\s*\(GDP\)\s+is estimated to have\s+" +
        amount + r"\s+in\s+" + reference(quarter), lead.group(1), re.I))
    if len(hits) != 1:
        raise Pending("ONS_REAL_GDP_QOQ_NOT_SINGLE_EXACT_MATCH")
    hit = hits[0]
    value = signed_amount(hit.group("verb"), hit.group("rate")) if hit.group("verb") else 0.0
    directions = r"growth|increase|fall|decrease|contraction|decline"
    rate = r"\d+(?:\.\d+)?"
    prior = re.match(
        rf"\s*,?\s*following\s+(?:an?\s+)?(?:(?:un)?revised\s+)?"
        rf"(?:(?P<sign>{directions})\s+of\s+(?P<rate>{rate})\s*%|"
        rf"(?P<leading_rate>{rate})\s*%\s+(?P<trailing_sign>{directions})|no\s+growth)"
        rf"\s+in\s+(?:{reference(previous_quarter(quarter))}|the previous quarter\b)",
        lead.group(1)[hit.end():], re.I,
    )
    prior_value = None
    if prior:
        direction = prior.group("sign") or prior.group("trailing_sign") or "growth"
        amount = prior.group("rate") or prior.group("leading_rate")
        sign = -1 if direction.lower() in ("fall", "decrease", "contraction", "decline") else 1
        prior_value = sign * signed_amount("increased", amount) if amount else 0.0
    return {"quarter": quarter, "publisher_release_day": released.isoformat(),
            "reported_value": value, "prior_qoq": prior_value, "source_url": edition_url(quarter)}


def load_archive(path, *, schema=SCHEMA, minimum=MIN_QUARTER, url_for=edition_url):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != schema or not isinstance(data.get("editions"), list):
        raise ValueError("invalid quarterly GDP archive schema")
    previous = None
    for record in data["editions"]:
        quarter = record["quarter"]
        released = date.fromisoformat(record["publisher_release_day"])
        seen = datetime.fromisoformat(record["first_observed_at_utc"])
        amounts = (record["reported_value"], record["prior_qoq"])
        if (quarter < minimum or record["source_url"] != url_for(quarter)
                or any(type(v) not in (int, float) or not -30 < v < 30
                       for v in amounts if v is not None)
                or amounts[0] is None or seen.utcoffset() is None
                or seen.astimezone(ROME).date() < released
                or not re.fullmatch(r"[0-9a-f]{64}", record["source_html_sha256"])
                or (previous and (quarter <= previous["quarter"]
                                  or released <= date.fromisoformat(previous["publisher_release_day"])))):
            raise ValueError("invalid or out-of-order quarterly GDP archived edition")
        previous = record
    return data


def edition_available(row, as_of, live_cutoff=None):
    """Date-only research is conservative; live may use an actually captured release."""
    day = date.fromisoformat(as_of)
    released = date.fromisoformat(row["publisher_release_day"])
    seen = datetime.fromisoformat(row["first_observed_at_utc"])
    if seen.utcoffset() is None:
        raise ValueError("GDP capture timestamp must have a timezone")
    if live_cutoff is None:
        return released < day and seen.astimezone(ROME).date() <= day
    if live_cutoff.utcoffset() is None or live_cutoff.astimezone(ROME).date() != day:
        raise ValueError("GDP live cutoff must match the research day")
    return released <= day and seen <= live_cutoff


def archived_growth(as_of, editions, *, stage, same_edition_field, live_cutoff=None):
    for row in reversed(editions):
        if not edition_available(row, as_of, live_cutoff):
            continue
        def observation(quarter, value):
            return {
                "reference_quarter": quarter, "publisher_release_day": row["publisher_release_day"],
                "publisher_source": row["source_url"], "reported_value": value,
                "reported_unit": "PERCENT_QOQ_SA", "nonannualized_qoq_descriptive_pct": value,
                "is_growth_strength_score": False,
                "national_definitions_are_not_fully_cross_country_equivalent": True,
                "later_revisions_not_identical_to_first_release": True,
                "historical_pit_training_vintages_certified": False,
            }
        prior = row["prior_qoq"]
        return {
            **observation(row["quarter"], row["reported_value"]),
            "publication_stage": stage,
            "prior_documented_quarter": observation(previous_quarter(row["quarter"]), prior)
            if prior is not None else None,
            same_edition_field: prior is not None,
            "source_first_observed_at_utc": row["first_observed_at_utc"],
            **({"publisher_csv_source": row["csv_url"]} if "csv_url" in row else {}),
        }
    return None


def latest_growth(as_of, *, path=ARCHIVE, live_cutoff=None):
    return archived_growth(as_of, load_archive(path)["editions"], stage="FIRST_QUARTERLY_ESTIMATE",
                           same_edition_field="prior_value_from_same_ons_edition", live_cutoff=live_cutoff)


def append_edition(path, data, record, now):
    data["editions"].append({
        **record, "first_observed_at_utc": now.astimezone(timezone.utc).isoformat(),
    })
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def collect(now, *, path=ARCHIVE, fetch=retrieve, apply=False):
    data = load_archive(path)
    latest = data["editions"][-1] if data["editions"] else None
    today = now.astimezone(ROME).date()
    try:
        raw, final = fetch(BASE + "latest", HOST)
        item = parse_bulletin(raw, today)
        if final not in (BASE + "latest", item["source_url"]):
            raise Pending("ONS_LATEST_REDIRECT_NOT_A_FIRST_ESTIMATE")
        dated, final = fetch(item["source_url"], HOST)
        if final != item["source_url"] or parse_bulletin(dated, today) != item:
            raise Pending("ONS_DATED_EDITION_DOES_NOT_MATCH_LATEST")
        if item["quarter"] < MIN_QUARTER or latest and item["quarter"] < latest["quarter"]:
            raise Pending("ONS_LATEST_REGRESSED")
        if latest and item["quarter"] == latest["quarter"]:
            if any(latest[key] != value for key, value in item.items()):
                raise Pending("ONS_EDITION_VALUES_CHANGED_ARCHIVE_RETAINED")
            return {"status": "VERIFIED_ALREADY_ARCHIVED", **item}
        if latest and item["publisher_release_day"] <= latest["publisher_release_day"]:
            raise Pending("ONS_RELEASE_DATE_REGRESSED")
        if item["quarter"] == MIN_QUARTER and latest is None:
            seed = observed_q3_updates(today.isoformat()).get("GBP")
            if not seed or any(item[key] != seed[key] for key in ("reported_value", "publisher_release_day")):
                raise Pending("ONS_BASELINE_FIRST_ESTIMATE_MISMATCH")
    except (OSError, ValueError, Pending) as error:
        return {"status": "SOURCE_UNAVAILABLE_ARCHIVE_RETAINED", "reason": str(error),
                "last_archived_quarter": latest["quarter"] if latest else None}
    if apply:
        append_edition(path, data, {**item, "source_html_sha256": sha256(dated).hexdigest()}, now)
    return {"status": "ARCHIVED" if apply else "VERIFIED_PREVIEW", **item}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(collect(datetime.now(timezone.utc), apply=args.apply), sort_keys=True))


if __name__ == "__main__":
    main()
