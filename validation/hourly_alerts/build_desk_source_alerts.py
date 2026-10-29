#!/usr/bin/env python3
"""Fail-closed, source-attributed public macro headline collector.

NOT a ChatGPT transcript mirror. Publisher reports are attributed, never
silently upgraded to independently confirmed facts or market-price reactions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

SCHEMA = "GMFQ_DESK_MACRO_MARKET_ALERTS_V1"
MAX_HISTORY = 100
MAX_NEW_PER_RUN = 3
MAX_AGE_HOURS = 30
ALLOWED_PUBLISHERS = {"Reuters", "Associated Press", "AP News"}
# Independent of Google News: use these official publisher feeds only if ALL
# primary Google News searches fail. BBC items retain their own attribution.
BBC_FALLBACK_FEEDS = (
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
)
BBC_LINK_HOSTS = {"www.bbc.com", "www.bbc.co.uk", "bbc.com", "bbc.co.uk"}
SEARCHES = (
    '(site:reuters.com OR site:apnews.com) (Hormuz OR tanker OR OPEC OR "oil supply" OR "energy sanctions") when:2d',
    '(site:reuters.com OR site:apnews.com) ("central bank" OR "interest rate" OR inflation OR payrolls OR "bond yields") when:2d',
    '(site:reuters.com OR site:apnews.com) (stocks OR Nasdaq OR semiconductor OR "credit spreads" OR "market volatility") when:2d',
)
PATTERNS = {
    "GEOPOLITICS": re.compile(r'\b(hormuz|tanker|sanction|missile|blockade|strait|war|attack|naval mine)', re.I),
    "CENTRAL_BANK": re.compile(r'\b(federal reserve|fed|ecb|central bank|interest rate|rate hike|rate cut|boe|boj|bank of canada|lagarde|powell)', re.I),
    "MACRO": re.compile(r'\b(inflation|consumer prices|cpi|payrolls|unemployment|gdp|recession|economic growth|jobless)', re.I),
    "CREDIT": re.compile(r'\b(credit spread|bond default|high.yield|credit market|bond yield|treasury yields)', re.I),
    "EQUITY": re.compile(r'\b(stocks|stock market|nasdaq|s&p 500|semiconductor|chipmakers|tech selloff|market volatility)', re.I),
    "COMMODITIES": re.compile(r'\b(opec|crude|oil prices|oil supply|brent|gold prices|natural gas)', re.I),
}
CCYS = {
    "USD": re.compile(r'\b(us|u\.s\.|american|federal reserve|fed|dollar|treasury|wall street|nasdaq)\b', re.I),
    "EUR": re.compile(r'\b(euro|eurozone|european central bank|ecb|lagarde)\b', re.I),
    "GBP": re.compile(r'\b(britain|british|uk|bank of england|boe|pound|sterling)\b', re.I),
    "JPY": re.compile(r'\b(japan|japanese|boj|yen)\b', re.I),
    "CHF": re.compile(r'\b(switzerland|swiss|snb|franc)\b', re.I),
    "CAD": re.compile(r'\b(canada|canadian|boc|loonie)\b', re.I),
    "AUD": re.compile(r'\b(australia|australian|rba|aussie)\b', re.I),
    "NZD": re.compile(r'\b(new zealand|rbnz|kiwi)\b', re.I),
}
UNCONFIRMED = re.compile(r'\b(say|says|said|claim|claims|allege|alleged|reportedly|unconfirmed|according to)\b', re.I)
# Source-only feed: publish market-relevant headlines, not arbitrary geopolitical
# or catalog headlines that happen to contain a broad generic keyword.
MARKET_RELEVANCE = re.compile(
    r'\b(hormuz|oil tankers?|tankers?|opec|oil prices?|oil supply|oil exports?|'
    r'oil sanctions?|energy sanctions?|energy prices?|russia sanctions|'
    r'fed|federal reserve|ecb|european central bank|bank of england|'
    r'bank of japan|bank of canada|central bank|monetary policy|'
    r'interest rates?|rate hikes?|rate cuts?|inflation|cpi|pce|'
    r'unemployment|payrolls|gdp|recession|bond yields?|treasury yields?|'
    r'credit spreads?|nasdaq|stocks|stock markets?|semiconductor|'
    r'brent|crude oil|oil markets?|market volatility)\b', re.I)


def relevant(title):
    if not isinstance(title, str) or len(title.split()) < 5:
        return False
    if re.fullmatch(r'(sanctions and embargoes|stock markets|oil prices|inflation)', title.strip(), re.I):
        return False
    return bool(MARKET_RELEVANCE.search(title))


def priority(item):
    title = item["headline"].lower()
    score = 0
    for expression, weight in (
        (r'hormuz|oil tanker|tankers|naval mine', 20),
        (r'inflation|interest rate|rate hike|rate cut|payrolls|gdp', 13),
        (r'opec|oil supply|energy sanctions|russia sanctions', 12),
        (r'nasdaq|semiconductor|credit spread|stocks', 8),
    ):
        if re.search(expression, title):
            score += weight
    if item["source_label"].startswith("Reuters"):
        score += 1
    return score



def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def get_xml(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "GMFQ-Research-Desk-Feeds/1.0", "Accept": "application/rss+xml,application/xml,text/xml"})
    with urllib.request.urlopen(req, timeout=14) as response:
        payload = response.read(1024 * 1024 + 1)
    if len(payload) > 1024 * 1024:
        raise ValueError("RSS payload exceeds 1 MiB")
    return payload


def feeds():
    for query in SEARCHES:
        yield "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})


def parse_rss(xml):
    root = ET.fromstring(xml)
    if root.tag != "rss":
        raise ValueError("Not an RSS feed")
    output = []
    for entry in root.findall("./channel/item"):
        source = entry.find("source")
        pub = source.text.strip() if source is not None and source.text else ""
        title = (entry.findtext("title") or "").strip()
        date = (entry.findtext("pubDate") or "").strip()
        link = (entry.findtext("link") or "").strip()
        if pub not in ALLOWED_PUBLISHERS or not title or not date:
            continue
        if not link.startswith("https://news.google.com/"):
            continue
        try:
            stamp = parsedate_to_datetime(date)
            if stamp.tzinfo is None:
                continue
        except (ValueError, TypeError, IndexError):
            continue
        if title.endswith(" - " + pub):
            title = title[:-(3 + len(pub))].strip()
        output.append({"title": title[:280], "source": pub,
                       "observed": stamp.astimezone(timezone.utc), "url": link})
    return output


def parse_bbc_rss(xml):
    """Parse only publisher-linked BBC items from the pinned official RSS host.

    A BBC item is never relabelled Reuters/AP. Ignore off-site links and missing
    publisher timestamps. Do not infer that a headline is independently verified.
    """
    root = ET.fromstring(xml)
    if root.tag != "rss":
        raise ValueError("Not a BBC RSS feed")
    output = []
    for entry in root.findall("./channel/item"):
        title = (entry.findtext("title") or "").strip()
        date = (entry.findtext("pubDate") or "").strip()
        link = (entry.findtext("link") or "").strip()
        parts = urllib.parse.urlsplit(link)
        if not title or not date or parts.scheme != "https" or parts.hostname not in BBC_LINK_HOSTS:
            continue
        try:
            stamp = parsedate_to_datetime(date)
            if stamp.tzinfo is None:
                continue
        except (ValueError, TypeError, IndexError):
            continue
        output.append({"title": title[:280], "source": "BBC News",
                       "observed": stamp.astimezone(timezone.utc), "url": link})
    return output


def make_item(record, now):
    title, observed = record["title"], record["observed"]
    if observed > now + timedelta(minutes=10) or now - observed > timedelta(hours=MAX_AGE_HOURS):
        return None
    if not relevant(title):
        return None
    category = next((key for key, rx in PATTERNS.items() if rx.search(title)), None)
    if not category:
        return None
    source = record["source"]
    normalized = re.sub(r'\W+', ' ', title.casefold()).strip()
    event_id = "SRC-" + hashlib.sha256(f"{source}|{normalized}".encode()).hexdigest()[:20]
    is_claim = bool(UNCONFIRMED.search(title))
    lead = f"{source} riporta: {title.rstrip('.')}."
    caveat = (" È una dichiarazione o segnalazione attribuita alla fonte: il fatto sottostante non è confermato indipendentemente da questo feed."
              if is_claim else " È una notizia attribuita alla testata, non una verifica autonoma dell'evento.")
    summary = lead + caveat + " Non sono disponibili da questo feed conferme di reazione OIS, 2Y o FX; nessun setup operativo viene dedotto dal titolo."
    return {"event_id": event_id, "observed_at_utc": iso(observed), "headline": title,
            "summary": summary, "category": category,
            "currencies": [ccy for ccy, rx in CCYS.items() if rx.search(title)],
            "related_pairs": [], "source_label": source + " · notizia attribuita",
            "source_url": record["url"], "verification_level": "PUBLISHER_ATTRIBUTED_ONLY",
            "independently_confirmed": False}


def build(previous, records, now, *, source_scope="REUTERS_AP_GOOGLE_NEWS"):
    if source_scope not in {"REUTERS_AP_GOOGLE_NEWS", "BBC_OFFICIAL_FALLBACK"}:
        raise ValueError("Unknown source scope")
    if not isinstance(previous, dict) or previous.get("schema") != SCHEMA:
        raise ValueError("Existing Desk feed missing or has an unknown schema")
    if not isinstance(previous.get("history"), list) or not isinstance(previous.get("policy"), dict):
        raise ValueError("Existing Desk history/policy invalid")
    # Do not silently keep low-quality items introduced by this source watcher.
    # Never remove external/canonical records (only SOURCE_ATTRIBUTED items).
    old = [row for row in previous["history"]
           if not (isinstance(row, dict)
                   and row.get("verification_level") == "PUBLISHER_ATTRIBUTED_ONLY"
                   and not relevant(row.get("headline", "")))]
    items = [make_item(r, now) for r in records]
    items = sorted((x for x in items if x), key=lambda x: (priority(x), x["observed_at_utc"]), reverse=True)
    seen = {x.get("event_id") for x in old if isinstance(x, dict)}
    fresh = []
    for item in items:
        if item["event_id"] not in seen:
            seen.add(item["event_id"])
            fresh.append(item)
        if len(fresh) >= MAX_NEW_PER_RUN:
            break
    updated = dict(previous)
    policy = dict(previous["policy"])
    policy["source"] = ("INDEPENDENT_REUTERS_AP_NEWS_RSS"
                        if source_scope == "REUTERS_AP_GOOGLE_NEWS"
                        else "REUTERS_AP_NEWS_WITH_BBC_OFFICIAL_RSS_FALLBACK")
    policy["certification"] = "PUBLISHER_ATTRIBUTED_NOT_INDEPENDENTLY_CONFIRMED"
    updated["policy"] = policy
    updated["history"] = (fresh + old)[:MAX_HISTORY]
    updated["state"] = "ACTIVE" if updated["history"] else "EMPTY"
    if fresh or old != previous["history"] or policy != previous["policy"]:
        updated["generated_at_utc"] = iso(now)
        return updated, len(fresh)
    return previous, 0

def run(output, previous):
    current = datetime.now(timezone.utc)
    records = []
    successes = 0
    source_scope = "REUTERS_AP_GOOGLE_NEWS"
    for url in feeds():
        try:
            records.extend(parse_rss(get_xml(url)))
            successes += 1
        except (ValueError, ET.ParseError, urllib.error.URLError, TimeoutError) as exc:
            print(f"RSS_PRIMARY_WITHHELD: {type(exc).__name__}: {exc}", file=sys.stderr)
    if not successes:
        # A network error at Google News must not block a different, direct
        # publisher RSS. Never relabel a BBC story as Reuters or AP.
        source_scope = "BBC_OFFICIAL_FALLBACK"
        for url in BBC_FALLBACK_FEEDS:
            try:
                records.extend(parse_bbc_rss(get_xml(url)))
                successes += 1
            except (ValueError, ET.ParseError, urllib.error.URLError, TimeoutError) as exc:
                print(f"RSS_BACKUP_WITHHELD: {type(exc).__name__}: {exc}", file=sys.stderr)
        if successes:
            print("RSS_INDEPENDENT_BBC_FALLBACK_ACTIVE", file=sys.stderr)
    if not successes:
        # Fail closed. No output file is created, and gh-pages is left intact.
        raise RuntimeError("All primary and independent backup RSS feeds unavailable; do not replace Desk feed")
    existing = json.loads(previous.read_text(encoding="utf-8"))
    updated, count = build(existing, records, current, source_scope=source_scope)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sources_ok": successes, "source_scope": source_scope,
                      "fallback_used": source_scope == "BBC_OFFICIAL_FALLBACK",
                      "items_considered": len(records), "new_events": count,
                      "total_history": len(updated["history"])}))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    run(args.output, args.previous)


if __name__ == "__main__":
    main()
