#!/usr/bin/env python3
"""Official-source headline lane. No paraphrases, market inference or fake dates.

Feed data is untrusted: accept only HTTPS article URLs on the publisher's
approved host, a real publication timestamp and a recent observation.
A failed feed never becomes an empty verified feed.
"""
from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor
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
    {
        "id": "BOE_NEWS", "name": "Bank of England",
        "url": "https://www.bankofengland.co.uk/rss/news",
        "hosts": ("www.bankofengland.co.uk", "bankofengland.co.uk"),
        "ccy": "GBP",
    },
    {
        "id": "BOJ_NEWS", "name": "Bank of Japan",
        "url": "https://www.boj.or.jp/en/rss/whatsnew.xml",
        "hosts": ("www.boj.or.jp", "boj.or.jp"),
        "ccy": "JPY",
    },
    {
        "id": "SNB_POLICY", "name": "Swiss National Bank",
        "url": "https://www.snb.ch/public/rss/en/mopo",
        "hosts": ("www.snb.ch", "snb.ch"),
        "ccy": "CHF",
    },
    {
        "id": "BOC_PRESS", "name": "Bank of Canada",
        "url": "https://www.bankofcanada.ca/content_type/press/feed/",
        "hosts": ("www.bankofcanada.ca", "bankofcanada.ca"),
        "ccy": "CAD",
    },
    {
        "id": "RBA_PRESS", "name": "Reserve Bank of Australia",
        "url": "https://www.rba.gov.au/rss/rss-cb-media-releases.xml",
        "hosts": ("www.rba.gov.au", "rba.gov.au"),
        "ccy": "AUD",
    },
    {
        "id": "RBNZ_NEWS", "name": "Reserve Bank of New Zealand",
        "url": "https://www.rbnz.govt.nz/feeds/news",
        "hosts": ("www.rbnz.govt.nz", "rbnz.govt.nz"),
        "ccy": "NZD",
    },
    {
        "id": "EIA_ENERGY", "name": "U.S. Energy Information Administration",
        "url": "https://www.eia.gov/rss/todayinenergy.xml",
        "hosts": ("www.eia.gov", "eia.gov"),
        "ccy": "ENERGY",
    },
)
USER_AGENT = "GMFQ-official-news/1.0 (public RSS; source attribution)"
MAX_BYTES = 2_000_000
MAX_DAYS = 10
MAX_ITEMS = 18
MAX_ITEMS_PER_SOURCE = 2


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



def desk_context(title: str, source: dict) -> dict:
    """Headline-only *watch questions*, never inferred monetary stance.

    Titles are publisher supplied but do not establish the actual policy
    decision, measured macro surprise, direction or asset-price response.
    Prefer an explicit low-priority institutional classification on ambiguity.
    """
    t = title.lower()
    is_energy = source["id"] == "EIA_ENERGY"
    if is_energy:
        if re.search(r"\b(crude oil|oil inventories|petroleum|refiner(?:y|ies)|refining|gasoline|diesel|natural gas storag\w*)\b", t):
            relevance, topic = "MONITOR", "ENERGY_FUNDAMENTALS"
            why = "Titolo relativo a disponibilità, lavorazione o scorte energetiche: possibile contesto per il mercato petrolifero, non prova di un movimento WTI."
            check = "Verificare dati EIA, scorte di greggio e prodotti, margini di raffinazione e prezzo WTI con date compatibili."
        else:
            relevance, topic = "CONTEXT", "ENERGY_STRUCTURE"
            why = "Approfondimento energetico o strutturale: dal titolo non emerge un nuovo segnale sul prezzo del petrolio."
            check = "Leggere la pubblicazione originale; valutare soltanto dopo l'eventuale rilevanza per domanda, offerta e prezzi."
    elif source["id"] == "BOJ_NEWS" and re.search(
            r"\\b(statement on monetary policy|change in the guideline for money market operations)\\b", t):
        # BoJ's actual English release titles differ from the standard
        # "monetary policy statement" wording. This is classification only:
        # the headline NEVER establishes a rate level, vote, bias or surprise.
        relevance, topic = "MONITOR", "CB_POLICY"
        why = "Pubblicazione ufficiale BoJ di politica monetaria: il titolo non conferma l'esito, il voto o il tono della decisione."
        check = "Leggere il documento BoJ; verificare decisione, livello del tasso, voto e Outlook prima di confrontare TONA, 2Y e JPY."
    elif source["id"] == "BOJ_NEWS" and re.search(
            r"\\boutlook for economic activity and prices\\b", t):
        relevance, topic = "MONITOR", "MACRO_EXPECTATIONS"
        why = "Outlook ufficiale BoJ: la sola pubblicazione non dimostra una revisione hawkish o dovish delle proiezioni."
        check = "Leggere stime e revisioni ufficiali; distinguere previsioni e decisione sui tassi, poi verificare TONA, 2Y e JPY."
    elif re.search(r"\b(monetary policy decision|interest rate decision|bank rate decision|policy rate decision|official cash rate|cash rate target|monetary policy statement|snb policy rate)\b", t):
        relevance, topic = "MONITOR", "CB_POLICY"
        why = "Annuncio potenzialmente relativo a una decisione o comunicazione di politica monetaria; direzione della decisione non identificata dal titolo."
        check = "Verificare testo della decisione, confronto con consenso, repricing OIS/futures, rendimento 2Y e variazione FX dopo la pubblicazione."
    elif re.search(r"\b(consumer expectations survey|business outlook survey|inflation expectations|survey of consumer expectations|monetary policy report|inflation report|financial stability report)\b", t):
        relevance, topic = "MONITOR", "MACRO_EXPECTATIONS"
        why = "Pubblicazione collegata alle aspettative o allo scenario macro; il titolo non rivela sorpresa né variazioni dei valori."
        check = "Leggere i numeri e confrontarli con precedente e consenso quando disponibili; poi controllare OIS/futures, 2Y e cambio."
    elif re.search(r"\b(interview|speech|remarks|media roundtable|press conference|testimony)\b", t):
        relevance, topic = "REVIEW", "CB_COMMUNICATION"
        why = "Intervento di una banca centrale: il solo titolo non permette di classificare il tono hawkish o dovish."
        check = "Esaminare il testo integrale; identificare eventuali novità rispetto alla posizione precedente e verificare la reazione del mercato."
    else:
        relevance, topic = "CONTEXT", "INSTITUTIONAL"
        why = "Comunicazione ufficiale non classificabile come catalizzatore macro/FX usando soltanto il titolo."
        check = "Consultare la fonte per chiarire la rilevanza; non dedurre un movimento di mercato."
    return {
        "operational_relevance": relevance, "topic": topic,
        "why_watch": why, "verify_next": check,
        "analysis_basis": "SOURCE_HEADLINE_ONLY",
        "market_direction": "NOT_DETERMINED",
        "market_reaction": "NOT_MEASURED",
    }


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
            "desk_context": desk_context(title, source),
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
                final = urllib.parse.urlsplit(response.geturl())
                # Redirects to a different origin must not be accepted as an
                # official publisher feed (even if its XML is well formed).
                if final.scheme != "https" or final.hostname not in source["hosts"]:
                    raise ValueError("RSS_UNTRUSTED_FEED_REDIRECT")
                # Bounded read, never include articles or full copyrighted text.
                return response.read(MAX_BYTES + 1)

    def read_one(source):
        try:
            payload = transport(source)
            observations = extract_items(payload, source, now)
            root = ET.fromstring(payload)
            entries_seen = sum(local_name(e.tag) in ("item", "entry") for e in root.iter())
            state = "OK_RECENT_ITEMS" if observations else "NO_VERIFIED_RECENT_ITEMS"
            failure_type = None
        except Exception as exc:
            observations = []
            entries_seen = None
            state = "FETCH_OR_PARSE_FAILED"
            failure_type = type(exc).__name__
        info = {
            "source_id": source["id"], "source": source["name"], "ccy": source["ccy"],
            "feed_url": source["url"], "status": state, "accepted_items": len(observations),
            # Zero accepted items is NOT proof that the publisher issued no
            # releases. Its feed may lack usable timestamps or HTTPS links.
            "feed_entries_seen": entries_seen,
            "entries_rejected": (entries_seen - len(observations)
                                 if entries_seen is not None else None),
        }
        if failure_type:
            info["failure_type"] = failure_type
        observations.sort(key=lambda x: (x["published_at_utc"], x["url"]), reverse=True)
        return observations[:MAX_ITEMS_PER_SOURCE], info

    # Independent publisher requests run concurrently: one inaccessible feed
    # cannot serially delay the mandatory daily prebrief by 8 seconds per bank.
    with ThreadPoolExecutor(max_workers=9) as pool:
        fetched = list(pool.map(read_one, RSS_SOURCES))
    stories = [story for accepted, _ in fetched for story in accepted]
    source_status = [receipt for _, receipt in fetched]
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
        "scope": "G8_CENTRAL_BANK_AND_EIA_OFFICIAL_RELEASES_NOT_GENERAL_MARKET_NEWS",
        "core_effect": "NONE",
    }
