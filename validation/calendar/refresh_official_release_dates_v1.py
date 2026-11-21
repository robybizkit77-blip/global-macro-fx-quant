#!/usr/bin/env python3
"""Refresh upcoming BEA, ABS, SECO and FSO schedules from the original publishers."""

import json
import re
from datetime import date, datetime, timezone
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
        if scheduled(new) <= now:
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
                      ("SECO_GDP", SECO_GDP), ("SECO_FLASH", SECO_FLASH), ("FSO_CPI", FSO_CPI)):
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
