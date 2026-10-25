#!/usr/bin/env python3
"""Official-source headline lane. No paraphrases, market inference or fake dates.

Feed data is untrusted: accept only HTTPS article URLs on the publisher's
approved host, a real publication timestamp and a recent observation.
A failed feed never becomes an empty verified feed.
"""
from __future__ import annotations

import datetime as dt
import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
RSS_SOURCES = (
    {
        "id": "FED_PRESS",
        "name": "Federal Reserve Board",
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "hosts": ("www.federalreserve.gov", "federalreserve.gov"),
        "ccy": "USD",
    },
    {
        "id": "ECB_PRESS",
        "name": "Banca centrale europea",
        "url": "https://www.ecb.europa.eu/rss/press.html",
        "hosts": ("www.ecb.europa.eu", "ecb.europa.eu", "www.ecb.int", "ecb.int"),
        "ccy": "EUR",
    },
)
USER_AGENT = "GMFQ-official-news/1.0 (public RSS; source attribution)"
MAX_BYTES = 2_000_000
MAX_DAYS = 10
MAX_ITEMS = 10


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def field(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in element:
        if local_name(child.tag) in names:
            value = child.get("href") if local_name(child.tag) == "link" and child.get("href") else child.text
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def published_in_utc(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        stamp = parsedate_to_datetime(value)
    except (ValueError, TypeError, IndexError):
        try:
            stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    return stamp.astimezone(dt.timezone.utc)


def trustworthy_url(value: str, source: dict) -> str | None:
    try:
        target = urllib.parse.urljoin(source["url"], value)
        url = urllib.parse.urlsplit(target)
    except (ValueError, TypeError):
        return None
    if url.scheme != "https" or url.hostname not in source["hosts"]:
        return None
    if url.username or url.password or url.port not in (None, 443):
        return None
    if not url.path or url.path == "/":
        return None
    return urllib.parse.urlunsplit((url.scheme, url.netloc, url.path, url.query, ""))


def clean_title(value: str) -> str:
    value = html.unescape(value)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", value)).strip()[:190]


def extract_items(payload: bytes, source: dict, now: dt.datetime) -> list[dict]:
    if len(payload) > MAX_BYTES:
        raise ValueError("RSS_FEED_OVERSIZE")
    root = ET.fromstring(payload)
    if local_name(root.tag) not in ("rss", "feed", "RDF"):
        raise ValueError("RSS_UNSUPPORTED_ROOT")
    cutoff = now - dt.timedelta(days=MAX_DAYS)
    observations = []
    for item in root.iter():
        if local_name(item.tag) not in ("item", "entry"):
            continue
        title = clean_title(field(item, ("title",)))
        raw_link = field(item, ("link",))
        link = trustworthy_url(raw_link, source)
        stamp = published_in_utc(field(item, ("pubDate", "published", "updated", "date")))
        if (not title or len(title) < 8 or not link or not stamp
                or stamp > now + dt.timedelta(minutes=5) or stamp < cutoff):
            continue
        observations.append({
            "id": source["id"] + ":" + link,
            "ccy": source["ccy"],
            "title": title,
            "source": source["name"],
            "source_id": source["id"],
            "category": "OFFICIAL_INSTITUTION_RELEASE",
            "published_at_utc": stamp.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "url": link,
            "quality": "OFFICIAL_RSS_DATED_LINK",
            "interpretation": "NON_VERIFIED_NO_MARKET_IMPACT_CLAIM",
        })
    return observations


def collect(now: dt.datetime | None = None, transport=None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware collection time is required")
    now = now.astimezone(dt.timezone.utc)
    if transport is None:
        def transport(source):
            req = urllib.request.Request(source["url"], headers={
                "User-Agent": USER_AGENT, "Accept": "application/rss+xml,application/xml,text/xml",
            })
            with urllib.request.urlopen(req, timeout=8) as response:
                # Bounded read, never include articles or full copyrighted text.
                return response.read(MAX_BYTES + 1)

    stories = []
    source_status = []
    for source in RSS_SOURCES:
        try:
            payload = transport(source)
            items = extract_items(payload, source, now)
            state = "OK_RECENT_ITEMS" if items else "OK_NO_RECENT_ITEMS"
            stories.extend(items)
        except Exception as exc:
            items = []
            state = "FETCH_OR_PARSE_FAILED"
            failure_type = type(exc).__name__
        info = {
            "source_id": source["id"], "source": source["name"], "ccy": source["ccy"],
            "feed_url": source["url"], "status": state, "accepted_items": len(items),
        }
        if state == "FETCH_OR_PARSE_FAILED":
            info["failure_type"] = failure_type
        source_status.append(info)
    unique = {item["url"]: item for item in stories}
    items = sorted(unique.values(),
                   key=lambda x: (x["published_at_utc"], x["source_id"], x["url"]),
                   reverse=True)[:MAX_ITEMS]
    failing = sum(x["status"] == "FETCH_OR_PARSE_FAILED" for x in source_status)
    if failing == len(source_status):
        state = "SOURCES_UNAVAILABLE"
    elif failing:
        state = "PARTIAL_SOURCES"
    elif not items:
        state = "VERIFIED_NO_RECENT_RELEASES"
    else:
        state = "VERIFIED_OFFICIAL_RELEASES"
    return {
        "schema": "GMFQ_OFFICIAL_RSS_HEADLINES_V1",
        "status": state,
        "last_attempt_day_rome": now.astimezone(ROME).date().isoformat(),
        "source_count": len(RSS_SOURCES),
        "source_failures": failing,
        "sources": source_status,
        "headlines": items,
        "latest_published_at_utc": items[0]["published_at_utc"] if items else None,
        "scope": "OFFICIAL_FED_ECB_PRESS_ONLY_NOT_GENERAL_MARKET_NEWS",
        "core_effect": "NONE",
    }
