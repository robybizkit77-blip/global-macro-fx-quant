#!/usr/bin/env python3
"""Refresh upcoming BEA, ABS, SECO and FSO schedules from the original publishers."""

import json
import re
from datetime import date, datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SEED = "live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json"
BEA = "https://www.bea.gov/news/schedule?output=1"
BEA_NEXT = "https://www.bea.gov/news/schedule/next-year?output=1"
ABS = ("https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/"
       "consumer-price-index-australia")
SECO_GDP = "https://www.seco.admin.ch/en/gross-domestic-product"
SECO_FLASH = "https://www.seco.admin.ch/en/gdp-flash"
FSO_CPI = "https://statistik.admin.ch/en/rss/agenda?prodima=900086"
SYDNEY = ZoneInfo("Australia/Sydney")
NEW_YORK = ZoneInfo("America/New_York")
ZURICH = ZoneInfo("Europe/Zurich")
ROME = ZoneInfo("Europe/Rome")
LONDON = ZoneInfo("Europe/London")
TOKYO = ZoneInfo("Asia/Tokyo")
LUXEMBOURG = ZoneInfo("Europe/Luxembourg")
ONS_CPI = "https://www.ons.gov.uk/releasecalendar?keywords=consumer+price+inflation&limit=100&release-type=type-upcoming"
JP_CPI = "https://www.stat.go.jp/english/data/cpi/1582.html"
EU_CAL = "https://ec.europa.eu/eurostat/news/euro-indicators/release-calendar"
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"

GDP = re.compile(r"GDP \((Advance|Second|Third) Estimate\)(?:, .+| and .+)?")
PERIOD = re.compile(r"(?:[1-4](?:st|nd|rd|th) Quarter(?: and Year)?|[A-Z][a-z]+) \d{4}")


def plain(markup):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", markup)).split())


def fetch(url):
    request = Request(url, headers={"User-Agent": "FXQuant/1.0 (official release calendars)",
                                    "Accept": "application/rss+xml" if url == FSO_CPI else "text/html"})
    with urlopen(request, timeout=15) as response:
        served = urlsplit(response.geturl())
        if served.scheme != "https" or served.hostname != urlsplit(url).hostname:
            raise ValueError("unexpected publisher URL")
        blob = response.read(2_000_001)
    if len(blob) > 2_000_000:
        raise ValueError("publisher page exceeds expected size")
    return blob.decode("utf-8")


def event(ccy, when, kind, title, period, family, source, *, quality="OFFICIAL_CALENDAR"):
    return {
        "ccy": ccy, "date": when.date().isoformat(), "time_local": when.strftime("%H:%M"),
        "timezone": when.tzinfo.key, "event_type": kind, "title": title,
        "reference_period": period, "importance": "HIGH", "quality": quality,
        "source_family": family, "source_url": source,
    }


def parse_bea(document, source):
    table = re.search(r'<table\b[^>]*\bid="release-schedule-table"[^>]*>(.*?)</table>',
                      document, re.S | re.I)
    if not table:
        raise ValueError("BEA schedule table missing")
    year = re.search(r">\s*Year\s+(\d{4})\s*</th>", table[1])
    if not year:
        raise ValueError("BEA schedule year missing")
    rows = []
    for body in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table[1], re.S | re.I):
        cells = [plain(cell) for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", body, re.S | re.I)]
        if len(cells) < 3 or cells[1].replace(" ", "") != "News":
            continue
        primary_release = cells[2].split("; ", 1)[0]
        title, sep, period = primary_release.rpartition(", ")
        kind = "INFLATION" if title == "Personal Income and Outlays" else "GROWTH"
        if not sep or (kind == "GROWTH" and not GDP.fullmatch(title)):
            continue
        if not PERIOD.fullmatch(period):
            raise ValueError("BEA reference period missing")
        when = datetime.strptime(f"{year[1]} {cells[0]}", "%Y %B %d %I:%M %p").replace(tzinfo=NEW_YORK)
        rows.append(event("USD", when, kind, title, period, "BEA", source))
    if not rows:
        raise ValueError("BEA GDP/PCE schedule rows missing")
    return int(year[1]), rows


def parse_abs(document):
    rows = []
    for body in re.findall(r'<div\s+class="views-row"\s*>(.*?)</div>', document, re.S | re.I):
        match = re.fullmatch(
            r'\s*Consumer Price Index, Australia,\s*([A-Za-z]+ \d{4})\s*'
            r'<span\s+class="release-date-label">Release date</span>\s*'
            r'<time\b[^>]*\bdatetime="([^"]+)"[^>]*>([^<]+)</time>\s*', body)
        if not match:
            continue
        period, iso, shown = match.groups()
        utc = datetime.fromisoformat(iso)
        if utc.utcoffset() is None:
            raise ValueError("ABS release instant has no offset")
        when = utc.astimezone(SYDNEY)
        clock = re.fullmatch(r"(\d{2}/\d{2}/\d{4} \d{1,2}:\d{2})(am|pm) (AEST|AEDT)", plain(shown))
        if not clock or (datetime.strptime(clock[1] + clock[2].upper(), "%d/%m/%Y %I:%M%p")
                         != when.replace(tzinfo=None) or clock[3] != when.tzname()):
            raise ValueError("ABS displayed release instant disagrees with publisher timestamp")
        rows.append(event("AUD", when, "INFLATION", "Consumer Price Index, Australia", period, "ABS", ABS))
    if not rows:
        raise ValueError("ABS upcoming CPI schedule rows missing")
    return rows


def parse_seco(document, source):
    heading = re.search(
        r'<h2\b[^>]*\bid="Publication-schedule"[^>]*>\s*Publication schedule\s*</h2>',
        document, re.I,
    )
    section = re.split(r"<h2\b", document[heading.end():], maxsplit=1, flags=re.I)[0] if heading else ""
    provisional = re.search(
        r"<h3\b[^>]*>\s*Provisional dates\s*</h3>.*?<ul\b[^>]*>(.*?)</ul>", section, re.S | re.I,
    )
    if not provisional:
        raise ValueError("SECO provisional schedule missing")
    title = {SECO_GDP: "Swiss quarterly GDP", SECO_FLASH: "Swiss GDP flash"}[source]
    rows = []
    for item in re.findall(r"<li\b[^>]*>(.*?)</li>", provisional[1], re.S | re.I):
        row = re.fullmatch(
            r"(Q[1-4] \d{4}) ([A-Z][a-z]+) (\d{1,2} [A-Z][a-z]+ \d{4}), "
            r"(\d{1,2}:\d{2}) ([ap])\.m\.", plain(item),
        )
        if not row:
            raise ValueError("SECO schedule row missing quarter or local clock")
        period, weekday, day, clock, meridiem = row.groups()
        when = datetime.strptime(f"{day} {clock} {meridiem.upper()}M", "%d %B %Y %I:%M %p")
        if when.strftime("%A") != weekday:
            raise ValueError("SECO weekday disagrees with release date")
        rows.append(event("CHF", when.replace(tzinfo=ZURICH), "GROWTH", title, period, "SECO", source,
                          quality="OFFICIAL_PROVISIONAL"))
    if not rows:
        raise ValueError("SECO schedule rows missing")
    return rows


def parse_fso(document):
    try:
        channel = ElementTree.fromstring(document).find("channel")
    except ElementTree.ParseError as error:
        raise ValueError("FSO agenda RSS is not valid XML") from error
    if channel is None or channel.findtext("language") != "en":
        raise ValueError("FSO English agenda channel missing")
    rows = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        match = re.fullmatch(
            r"Swiss Consumer Price Index in ([A-Z][a-z]+?)(?: and annual inflation)? (\d{4})", title,
        )
        if not match:
            continue
        month, year = match.groups()
        period = f"{month} {year}"
        reference = datetime.strptime(period, "%B %Y").date()
        source = (item.findtext("link") or "").strip()
        url = urlsplit(source)
        if (url.scheme, url.netloc) != ("https", "statistik.admin.ch") or not re.fullmatch(
            r"/en/agenda/\d{4}-\d+", url.path
        ) or url.query or url.fragment:
            raise ValueError("FSO release has no official agenda link")
        published = parsedate_to_datetime(item.findtext("pubDate") or "")
        if published.utcoffset() is None:
            raise ValueError("FSO release clock has no UTC offset")
        when = published.astimezone(ZURICH)
        if published.utcoffset() != when.utcoffset() or when.date().replace(day=1) <= reference:
            raise ValueError("FSO release clock disagrees with Zurich time or reference month")
        rows.append(event("CHF", when, "INFLATION", "Swiss Consumer Price Index", period, "FSO", source))
    if not rows:
        raise ValueError("FSO upcoming CPI schedule rows missing")
    return rows



def parse_ons_cpi(document):
    # Only the main bulletin, not time series, PPI or CPIH contribution releases.
    rows = []
    pattern = (r"Consumer price inflation, UK:\s*("+MONTH+r" \d{4})\s*"
               r"Release date:\s*(\d{1,2} "+MONTH+r" \d{4})\s*(\d{1,2}:\d{2})\s*(am|pm)\s*\|\s*Confirmed")
    for period, day, clock, meridiem in re.findall(pattern, plain(document), re.I):
        when = datetime.strptime(f"{day} {clock}{meridiem.upper()}", "%d %B %Y %I:%M%p").replace(tzinfo=LONDON)
        if when.date().replace(day=1) <= datetime.strptime(period, "%B %Y").date():
            raise ValueError("ONS release precedes its reference month")
        rows.append(event("GBP", when, "INFLATION", "Consumer price inflation, UK",
                          period, "ONS", ONS_CPI, quality="OFFICIAL_CONFIRMED"))
    if not rows:
        raise ValueError("ONS confirmed headline CPI schedule missing")
    return rows


def parse_jp_cpi(document):
    # The first two columns are national CPI; never substitute Tokyo CPI.
    rows, reference_year, release_year = [], None, None
    for table in re.findall(r"<table\b[^>]*>(.*?)</table>", document, re.S | re.I):
        if not all(x in plain(table) for x in ("Survey month", "Date of release", "Tokyo")):
            continue
        for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.S | re.I):
            cells = [plain(c) for c in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
            if len(cells) < 4:
                continue
            ref = re.fullmatch(r"("+MONTH+r")(?:,?\s+(20\d{2}))?", cells[0])
            rel = re.fullmatch(r"("+MONTH+r")\s+(\d{1,2})(?:,?\s+(20\d{2}))?", cells[1])
            if not ref or not rel:
                continue
            if ref[2]:
                reference_year = int(ref[2])
            if rel[3]:
                release_year = int(rel[3])
            if reference_year is None or release_year is None:
                raise ValueError("Japan schedule year not explicit")
            period = f"{ref[1]} {reference_year}"
            when = datetime.strptime(f"{rel[1]} {rel[2]} {release_year} 08:30", "%B %d %Y %H:%M").replace(tzinfo=TOKYO)
            refday = datetime.strptime(period, "%B %Y").date()
            if not 0 < (when.date()-refday).days <= 92:
                raise ValueError("Japan CPI month/year relationship invalid")
            rows.append(event("JPY", when, "INFLATION", "Japan Consumer Price Index",
                              period, "Statistics Bureau of Japan", JP_CPI,
                              quality="OFFICIAL_CONFIRMED"))
    if not rows:
        raise ValueError("Japan national CPI schedule missing")
    return rows


def parse_eurostat_flash(document, source):
    # A date-only release is deliberate: no fabricated time when the
    # issuer calendar does not provide one. Client-side shells fail closed.
    rows = []
    pattern = (r"Flash estimate inflation euro area,\s*("+MONTH+r" \d{4})\s*"
               r"(\d{1,2} "+MONTH+r" \d{4})\s*(?:ECFIN\s*)?Data release")
    for period, day in re.findall(pattern, plain(document), re.I):
        when = datetime.strptime(day, "%d %B %Y").replace(tzinfo=LUXEMBOURG)
        refday = datetime.strptime(period, "%B %Y").date()
        if not 0 <= (when.date()-refday).days <= 62:
            raise ValueError("Eurostat flash date disagrees with reference month")
        row = event("EUR", when, "INFLATION", "Euro area flash inflation",
                    period, "Eurostat", source)
        row["time_local"] = None
        rows.append(row)
    if not rows:
        raise ValueError("Eurostat flash CPI calendar rows missing")
    return rows


def eurostat_urls(now):
    start = now.astimezone(LUXEMBOURG).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    following = (start + timedelta(days=32)).replace(day=1)
    return [f"{EU_CAL}?start={int(x.timestamp()*1000)}&type=listMonth" for x in (start, following)]


def identity(row):
    title = row.get("title", "")
    period = row.get("reference_period", "")
    gdp = GDP.fullmatch(title)
    if row.get("source_family") == "BEA" and gdp:
        title = "GDP " + gdp[1]
        quarter = re.fullmatch(r"Q([1-4]) (\d{4})", period)
        if quarter:
            number, year = quarter.groups()
            suffix = {"1": "st", "2": "nd", "3": "rd", "4": "th"}[number]
            period = f"{number}{suffix} Quarter {year}"
        period = period.replace(" and Year ", " ")
    return row.get("source_family"), row.get("ccy"), title, period


def scheduled(row):
    return datetime.fromisoformat(row["date"] + "T" + row["time_local"]).replace(
        tzinfo=ZoneInfo(row["timezone"]))


def upcoming(row, now):
    if row.get("time_local") and row.get("timezone"):
        return scheduled(row) > now
    return date.fromisoformat(row["date"]) >= now.astimezone(ROME).date()


def apply_rows(events, rows, now):
    incoming = {}
    for new in rows:
        if not upcoming(new, now):
            continue
        key = identity(new)
        if key in incoming and incoming[key] != new:
            raise ValueError("conflicting publisher schedules")
        incoming[key] = new
    result = list(events)
    changed = 0
    for key, new in incoming.items():
        matches = [i for i, old in enumerate(events) if identity(old) == key and upcoming(old, now)]
        if len(matches) > 1:
            raise ValueError("multiple upcoming revisions of one calendar event")
        if not matches:
            result.append(new)
            changed += 1
            continue
        i = matches[0]
        old = result[i]
        revision = dict(old, date=new["date"], time_local=new["time_local"], timezone=new["timezone"],
                        source_url=new["source_url"])
        if revision != old:
            result[i] = revision
            changed += 1
    return result, changed


def refresh(path, now, read=fetch):
    if now.utcoffset() is None:
        raise ValueError("an aware refresh clock is required")
    payload = json.loads(path.read_bytes())
    if (payload.get("schema"), payload.get("status")) != (
        "GMFQ_MACRO_RELEASE_OFFICIAL_SEED_V1", "ACTIVE_VERIFIED_SEED"
    ) or not isinstance(payload.get("events"), list):
        raise ValueError("official release seed contract changed")
    events = payload["events"]
    receipts = []
    for name, url in (("BEA", BEA), ("BEA_NEXT", BEA_NEXT), ("ABS", ABS),
                      ("SECO_GDP", SECO_GDP), ("SECO_FLASH", SECO_FLASH), ("FSO_CPI", FSO_CPI),
                      ("ONS_CPI", ONS_CPI), ("JP_CPI", JP_CPI),
                      *((f"EU_FLASH_{i}", url) for i, url in enumerate(eurostat_urls(now)))):
        try:
            document = read(url)
            if name.startswith("BEA"):
                year, rows = parse_bea(document, url)
                expected = now.astimezone(NEW_YORK).year + (name == "BEA_NEXT")
                if year != expected:
                    raise ValueError("BEA schedule year disagrees with requested edition")
            elif name == "ABS":
                rows = parse_abs(document)
            elif name == "FSO_CPI":
                rows = parse_fso(document)
            elif name == "ONS_CPI":
                rows = parse_ons_cpi(document)
            elif name == "JP_CPI":
                rows = parse_jp_cpi(document)
            elif name.startswith("EU_FLASH_"):
                rows = parse_eurostat_flash(document, url)
            else:
                rows = parse_seco(document, url)
            events, count = apply_rows(events, rows, now)
        except (OSError, ValueError) as error:
            receipts.append({"source": name, "status": "SOURCE_BLOCKED_RETAINED",
                             "reason": str(error).replace("\n", " ")[:240]})
            continue
        receipts.append({"source": name, "status": "VERIFIED", "rows": len(rows), "changed": count})
    if events != payload["events"]:
        payload["events"] = events
        payload["as_of"] = max(payload.get("as_of") or "", now.astimezone(ROME).date().isoformat())
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return receipts


if __name__ == "__main__":
    for receipt in refresh(ROOT / SEED, datetime.now(timezone.utc)):
        print("OFFICIAL_RELEASE_DATES", json.dumps(receipt, sort_keys=True), flush=True)
        if receipt["status"] != "VERIFIED":
            print(f"::warning::Official calendar source {receipt['source']} retained prior rows", flush=True)
