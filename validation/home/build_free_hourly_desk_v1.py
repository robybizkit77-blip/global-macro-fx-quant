#!/usr/bin/env python3
"""FX Quant Next FREE hourly cross-asset research.

No paid API, LLM, credentials or ChatGPT connection. Uses existing source-dated
market datasets plus the repository's independently verified public RSS collector.
Market *interpretation* is conditional and labelled, not fabricated news.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from datetime import datetime, time, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from validation.collect_official_news_rss_v1 import collect as collect_official_rss  # noqa: E402

SCHEMA = "GMFQ_NEXT_FREE_HOURLY_DESK_V1"
ROME = ZoneInfo("Europe/Rome")
ALLOWED_CATEGORIES = {
    "FUTURES_IMPLIED_REPRICING", "OIS_REPRICING", "OIS_PROXY_REPRICING",
    "MARKET_GOVERNMENT_RATES", "MARKET_FX_ECB_FIXING",
    "MARKET_VOLATILITY_CLOSE", "MARKET_EQUITY_CLOSE",
    "MARKET_CREDIT_OAS", "MACRO_OFFICIAL_ACTUAL", "MACRO_UPDATE"
}
ECB_FIXING = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
MONTHS = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"
)
COUNTRIES = {
    "USD": "negli Stati Uniti", "EUR": "nell’area euro", "GBP": "nel Regno Unito",
    "JPY": "in Giappone", "AUD": "in Australia", "NZD": "in Nuova Zelanda",
    "CAD": "in Canada", "CHF": "in Svizzera"
}


def read_json(path, fallback=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback


def day(s):
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
        return d if d.isoformat() == s else None
    except (TypeError, ValueError):
        return None


def clock(s):
    if not isinstance(s, str):
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo and d.utcoffset() is not None else None
    except ValueError:
        return None


def valid_url(s):
    if not isinstance(s, str) or len(s) > 2000:
        return False
    try:
        u = urlsplit(s)
        return u.scheme == "https" and "." in (u.hostname or "") and not u.username and not u.password
    except ValueError:
        return False


def safe_number(v):
    return type(v) in (int, float) and math.isfinite(v)


def signed_from_title(title, unit=None):
    match = re.search(r"([+\-−]\d+(?:[.,]\d+)?)\s*(pb|bp|%|punti)", str(title))
    if not match or (unit and match.group(2) != unit):
        return None
    try:
        return float(match.group(1).replace("−", "-").replace(",", "."))
    except ValueError:
        return None


def sentence_join(parts):
    return " ".join(str(x).strip() for x in parts if x)


def short_date(d):
    return f"{d.day} {MONTHS[d.month-1]}"


def signed(value, places=2):
    sign = "+" if value > 0 else "−" if value < 0 else ""
    return sign + f"{abs(value):.{places}f}".replace(".", ",")


def official_fx_fixing(feed, now):
    if not isinstance(feed, dict) or (
        feed.get("schema"), feed.get("status"), feed.get("base"), feed.get("source_url")
    ) != ("GMFQ_ECB_G8_PRICE_HISTORY_V1", "CURRENT_OFFICIAL_HISTORY", "EUR", ECB_FIXING):
        return None
    local = now.astimezone(ROME)
    rows = feed.get("rows")
    if not isinstance(rows, list) or len(rows) < 2:
        return None
    for row in rows[-2:]:
        if not isinstance(row, dict) or not day(row.get("Date")) or not all(
            safe_number(row.get(c)) and row[c] > 0 for c in ("USD", "JPY")
        ):
            return None
    previous, latest = rows[-2:]
    start, end = day(previous["Date"]), day(latest["Date"])
    if not (start < end <= local.date() and (local.date()-end).days <= 7
            and feed.get("last_as_of") == latest["Date"]):
        return None
    usd_eur = (previous["USD"] / latest["USD"] - 1) * 100
    usd_jpy = ((latest["JPY"] / latest["USD"]) / (previous["JPY"] / previous["USD"]) - 1) * 100
    eur_usd = (latest["USD"] / previous["USD"] - 1) * 100
    eps = .005
    state = ("strong" if usd_eur > eps and usd_jpy > eps else
             "weak" if usd_eur < -eps and usd_jpy < -eps else
             "flat" if abs(usd_eur) <= eps and abs(usd_jpy) <= eps else "mixed")
    return {"date": end.isoformat(), "previous": start.isoformat(), "state": state,
            "eur_usd_pct": eur_usd, "usd_jpy_pct": usd_jpy, "usd_eur_pct": usd_eur}


def closing_risk(feed, today):
    streams = feed.get("streams") if isinstance(feed, dict) else None
    closes = []
    for key, label, unit, decimals in (("SP500", "S&P 500", "%", 2),
                                        ("NASDAQCOM", "Nasdaq Composite", "%", 2),
                                        ("VIX", "VIX", " punti", 2),
                                        ("HY_OAS", "spread high yield", " pb", 0)):
        row = streams.get(key) if isinstance(streams, dict) else None
        observed = day(row.get("date")) if isinstance(row, dict) else None
        if not (observed and 0 <= (today-observed).days <= 7 and
                row.get("quality") == "PUBLISHED_SOURCE_RESEARCH_ONLY" and
                row.get("not_intraday") is True and valid_url(row.get("source_url")) and
                all(safe_number(row.get(k)) for k in ("value", "previous"))):
            continue
        delta = row["value"]-row["previous"]
        if key in ("SP500", "NASDAQCOM"):
            if not row["previous"]:
                continue
            delta = delta / abs(row["previous"]) * 100
        if key == "HY_OAS":
            delta *= 100
        closes.append({"date": observed.isoformat(), "label": label, "change": delta,
                       "display": signed(delta, decimals) + unit, "url": row["source_url"]})
    latest = max((x["date"] for x in closes), default=None)
    # One equity close for the latest date, with S&P 500 as the tie-break.
    recent = [x for x in closes if x["date"] == latest]
    if any(x["label"] == "S&P 500" for x in recent):
        recent = [x for x in recent if x["label"] != "Nasdaq Composite"]
    return recent


def next_event(events, now):
    today = now.astimezone(ROME).date()
    upcoming = []
    for row in events:
        if not isinstance(row, dict):
            continue
        d = day(row.get("date"))
        title = row.get("title")
        if not (d and abs((d-today).days) <= 6 and isinstance(title, str) and title.strip()
                and row.get("status") == "UPCOMING" and row.get("importance") == "HIGH"
                and str(row.get("quality", "")).startswith("OFFICIAL")
                and row.get("ccy") in COUNTRIES):
            continue
        try:
            when = datetime.combine(d, time.fromisoformat(row["time_local"]),
                                    ZoneInfo(row["timezone"])).astimezone(ROME)
        except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
            continue
        if when > now and (when.date()-today).days <= 6:
            upcoming.append((when, row))
    return min(upcoming, key=lambda item: item[0], default=None)


def catalyst_text(event):
    if not event:
        return "", ""
    when, row = event
    ccy, title = row["ccy"], row["title"]
    country = COUNTRIES[ccy]
    when_text = f"{short_date(when.date())} alle {when:%H:%M} italiane"
    if re.search(r"consumer price index|\bCPI\b", title, re.I):
        if ccy == "JPY":
            return (f"Il {when_text} escono i prezzi al consumo in Giappone.",
                    "Per lo yen conta se il dato sposta le attese sui tassi della BoJ.")
        return (f"Il {when_text} escono i prezzi al consumo {country}.",
                f"Per {ccy} conta come il dato modifica le attese sui tassi.")
    if row.get("event_type") == "LABOUR":
        return (f"Il {when_text} escono i dati sul lavoro {country}.",
                f"Per {ccy} conta se occupazione e salari cambiano le aspettative monetarie.")
    return (f"Il {when_text} è in programma {title} ({ccy}).",
            f"Da verificare la risposta dei tassi e di {ccy}.")


def australia_labour_reading(title, series):
    detail = re.search(r"destagionalizzato, (\w+) (\d{4}): (\d+(?:[.,]\d+)?)%$", title)
    if not detail or detail[1] not in MONTHS:
        return "Dall’Australia è arrivato un nuovo dato sul lavoro."
    period = f"{detail[2]}-{MONTHS.index(detail[1])+1:02}"
    current = day(period + "-01")
    if current and isinstance(series, dict) and isinstance(series.get("AUD"), list):
        previous = (current-timedelta(days=1)).strftime("%Y-%m")
        row = next((row for row in series["AUD"] if isinstance(row, dict) and
                    row.get("id") == "AU_UNEMP_RATE_history_value" and
                    row.get("unit") == "%" and row.get("frequency") == "M"), {})
        dates, values = row.get("dates"), row.get("values")
        if (isinstance(dates, list) and isinstance(values, list) and len(dates) == len(values) >= 2
                and [str(d)[:7] for d in dates[-2:]] == [previous, period]
                and all(safe_number(v) for v in values[-2:])
                and values[-1] == float(detail[3].replace(",", "."))):
            move = ("aumentata" if values[-1] > values[-2] else
                    "diminuita" if values[-1] < values[-2] else "rimasta stabile")
            return f"In Australia la disoccupazione è {move} a {detail[1]}."
    return f"L’Australia ha pubblicato il dato sulla disoccupazione di {detail[1]}."


def macro_opening(row, series):
    if not row:
        return ""
    if row.get("metric_id") == "AU_UNEMP_RATE_SA":
        return australia_labour_reading(row["title"], series)
    country = COUNTRIES.get(row.get("ccy"))
    if not country:
        return ""
    topic = {"LABOUR": "i dati sul lavoro", "INFLATION": "i dati sui prezzi",
             "GDP": "i dati sulla crescita"}.get(row.get("event_type"))
    return f"Sono usciti {topic} {country}." if topic else ""


def risk_opening(closes):
    if not closes:
        return ""
    changes = {row["label"]: row["change"] for row in closes}
    shares = changes.get("S&P 500", changes.get("Nasdaq Composite", 0))
    equity = "il Nasdaq Composite" if "Nasdaq Composite" in changes else "Wall Street"
    credit = changes.get("spread high yield", 0)
    vol = changes.get("VIX", 0)
    date_label = short_date(day(closes[0]["date"]))
    if shares < -.005 and credit > .5:
        return (f"Alla chiusura del {date_label}, {equity} ha perso terreno e il premio "
                "sul debito più rischioso è salito.")
    if shares > .005 and credit < -.5:
        return (f"Alla chiusura del {date_label}, {equity} ha guadagnato terreno e il premio sul debito "
                "più rischioso si è ridotto.")
    if abs(credit) > .5:
        move = "aumentato" if credit > 0 else "diminuito"
        return f"Alla chiusura del {date_label}, il premio richiesto sul debito più rischioso è {move}."
    if abs(shares) > .005:
        move = "ha guadagnato terreno" if shares > 0 else "ha perso terreno"
        return f"Alla chiusura del {date_label}, {equity} {move}."
    if abs(vol) > .005:
        move = "salita" if vol > 0 else "scesa"
        return f"La volatilità azionaria è {move} alla chiusura del {date_label}."
    return ""


def compact_news(row):
    return {
        "headline": row["headline"], "analysis": row["analysis"],
        "kind": row["kind"], "published_date": row["published_date"],
        "event_date": row["event_date"], "market_area": row["market_area"],
        "sources": row["sources"], "evidence": row["evidence"]
    }


def build(root: Path, now: datetime, previous=None, rss=None):
    if not now.tzinfo or now.utcoffset() is None:
        raise ValueError("An aware UTC clock is required")
    today = now.astimezone(ROME).date()
    sections = root / "live_data" / "sections"
    pulse = read_json(sections / "NEWS_PULSE_OPERATIONAL.json")
    if not isinstance(pulse, dict) or not isinstance(pulse.get("items"), list):
        raise ValueError("Source-dated market pulse missing")
    asof = day(pulse.get("content_as_of"))
    if not asof or asof > today or (today-asof).days > 7:
        raise ValueError("Market pulse out of the 7-day research window")
    items = [x for x in pulse["items"]
             if isinstance(x, dict) and x.get("category") in ALLOWED_CATEGORIES
             and day(x.get("as_of")) and 0 <= (today-day(x["as_of"])).days <= 7
             and isinstance(x.get("title"), str) and x["title"].strip()]
    if len(items) < 4:
        raise ValueError("At least four usable source-dated market observations required")
    lookup = lambda cat, pred=lambda x: True: next((x for x in items if x.get("category") == cat and pred(x)), None)
    usd = lookup("MARKET_GOVERNMENT_RATES", lambda x: x.get("ccy") == "USD")
    eur = lookup("MARKET_GOVERNMENT_RATES", lambda x: x.get("ccy") == "EUR")
    u2 = signed_from_title(usd.get("title")) if usd else None
    e2 = signed_from_title(eur.get("title")) if eur else None
    comparative = (usd and eur and usd["as_of"] == eur["as_of"] and
                   safe_number(u2) and safe_number(e2))
    relative_bp = (u2 - e2) if comparative else None
    fx = official_fx_fixing(read_json(sections / "ECB_G8_PRICE_HISTORY.json"), now)
    risk_closes = closing_risk(read_json(root / "site/fx-quant-v2/cross-asset-live-data.json"), today)
    def published_macro(row):
        first_seen = row.get("first_runner_observed_at_utc")
        observed = clock(first_seen)
        return valid_url(row.get("source_url")) and (not first_seen or observed is not None and observed <= now)
    macro = lookup("MACRO_OFFICIAL_ACTUAL", published_macro)
    same_day_macro = macro if macro and macro["as_of"] == today.isoformat() else None
    gaps = read_json(sections / "ESTIMATED_RESIDUAL_GAPS.json", {}) or {}
    lanes = gaps.get("lanes") or {}
    def commodity(symbol):
        x = lanes.get(symbol+".market_proxy")
        if not isinstance(x, dict) or x.get("status") != "MARKET_PROXY_ACTIVE_SECONDARY":
            return None
        d = day(x.get("proxy_as_of"))
        return x if d and 0 <= (today-d).days <= 4 and safe_number(x.get("change_1d_pct")) and valid_url(x.get("source_endpoint")) else None
    gold, wti, brent = commodity("GOLD"), commodity("WTI"), commodity("BRENT")
    oil = wti or brent
    rss = rss if rss is not None else collect_official_rss(now=now)
    rss_headlines = rss.get("headlines", []) if isinstance(rss, dict) else []
    official = []
    for h in rss_headlines:
        if not isinstance(h, dict) or not valid_url(h.get("url")):
            continue
        if (h.get("desk_context") or {}).get("topic") == "INSTITUTIONAL":
            continue
        stamped = clock(h.get("published_at_utc"))
        if stamped and stamped <= now + timedelta(minutes=5) and 0 <= (today-stamped.astimezone(ROME).date()).days <= 7:
            official.append(h)
    official.sort(key=lambda x: x["published_at_utc"], reverse=True)
    recent = official[:6]
    calendar = read_json(sections / "CALENDAR_OPERATIONAL_VIEW.json", {}) or {}
    catalyst = next_event(calendar.get("events", []), now)
    event_sentence, event_relevance = catalyst_text(catalyst)

    series = (read_json(sections / "MACRO_SERIES.json")
              if same_day_macro and same_day_macro.get("metric_id") == "AU_UNEMP_RATE_SA" else None)
    macro_fact = macro_opening(same_day_macro, series)
    fx_fact, fx_reading = "", ""
    if fx:
        fx_word = {"strong": "Dollaro in rialzo", "weak": "Dollaro in calo",
                   "flat": "Dollaro stabile", "mixed": "Dollaro misto"}[fx["state"]]
        fx_headline = fx_word
        fixing_date = short_date(day(fx["date"]))
        fx_fact = (f"Al fixing BCE del {fixing_date}, EUR/USD ha segnato {signed(fx['eur_usd_pct'])}% "
                   f"e USD/JPY {signed(fx['usd_jpy_pct'])}%.")
        if fx["state"] == "mixed":
            direction = lambda value: "guadagnato" if value > .005 else "ceduto" if value < -.005 else "tenuto"
            fx_reading = (f"Il {fixing_date} il dollaro ha "
                          f"{direction(fx['usd_eur_pct'])} contro l’euro e {direction(fx['usd_jpy_pct'])} contro lo yen.")
        elif fx["state"] == "flat":
            fx_reading = f"Il {fixing_date} il dollaro è rimasto stabile contro euro e yen."
        else:
            verb = "guadagnato" if fx["state"] == "strong" else "ceduto"
            fx_reading = f"Il {fixing_date} il dollaro ha {verb} contro euro e yen."
    risk_fact = ""
    if risk_closes:
        risk_date = short_date(day(risk_closes[0]["date"]))
        moves = [f"{row['label']} {row['display']}" for row in risk_closes]
        risk_fact = f"Alla chiusura del {risk_date}, " + ", ".join(moves[:-1]) + (" e " if len(moves)>1 else "") + moves[-1] + "."
    risk_story = risk_opening(risk_closes)
    vix = next((row for row in risk_closes if row["label"] == "VIX"), None)
    vix_alert = lookup("MARKET_VOLATILITY_CLOSE", lambda row: vix is not None
                       and row["as_of"] == vix["date"] and row.get("source_url") == vix["url"]
                       and row.get("importance") == "HIGH"
                       and row.get("quality") == "PUBLISHED_SOURCE_RESEARCH_ONLY")
    lead_with_volatility = False
    if vix_alert and (not fx or vix["date"] >= fx["date"]):
        pulse_change = signed_from_title(vix_alert["title"], "punti")
        lead_with_volatility = pulse_change is not None and abs(pulse_change - vix["change"]) < .0051

    if macro_fact and (not fx or fx["date"] < today.isoformat()):
        headline = macro_fact.rstrip(".")
        lead_with_volatility = False
    elif lead_with_volatility:
        direction = "in rialzo" if vix["change"] > 0 else "in calo"
        headline = f"Volatilità {direction}"
        if fx and fx["date"] == vix["date"]:
            headline += f", {fx_headline.lower()}"
    elif fx:
        headline = fx_headline
    elif risk_closes:
        headline = f"Mercati alla chiusura del {short_date(day(risk_closes[0]['date']))}"
    else:
        headline = f"Mercati, le ultime osservazioni al {short_date(asof)}"

    lead_parts = (macro_fact, fx_reading, risk_story)
    if lead_with_volatility:
        risk_date = short_date(day(vix["date"]))
        vix_direction = "è salita" if vix["change"] > 0 else "è scesa"
        volatility_first = f"La volatilità azionaria {vix_direction} alla chiusura del {risk_date}."
        lead_parts = (volatility_first, fx_reading, macro_fact, risk_story if risk_story != volatility_first else "")
    lead = sentence_join(lead_parts) or (
        f"Il quadro di mercato resta quello del {short_date(asof)}, in attesa della prossima seduta."
    )
    monetary = monetary_evidence = ""
    if comparative:
        if abs(relative_bp) < .05:
            change = "è rimasto invariato"
        else:
            favored = "degli USA" if relative_bp > 0 else "dell’area euro"
            change = f"si è mosso di {abs(relative_bp):.1f}".replace(".", ",") + f" punti base a favore {favored}"
        rates_date = short_date(day(usd["as_of"]))
        monetary_evidence = f"Sui dati del {rates_date} il differenziale governativo USA–area euro a due anni {change}."
        if abs(relative_bp) >= .05:
            favored = "degli Stati Uniti" if relative_bp > 0 else "dell’area euro"
            monetary = f"Nella seduta del {rates_date}, il confronto tra i rendimenti governativi a breve si è mosso a favore {favored}."
    fx_interpretation = sentence_join((event_sentence, event_relevance))
    if not fx_interpretation and lead_with_volatility and vix["change"] > 0 and (
        fx and fx["date"] == vix["date"] and fx["state"] == "mixed" and fx["usd_jpy_pct"] < -.005
    ):
        fx_interpretation = ("Se la volatilità resta alta, segui la tenuta dello yen contro il dollaro. "
                             "Un rafforzamento anche contro l’euro darebbe più peso alla lettura sullo yen.")
    fx_interpretation = fx_interpretation or (
        "Da seguire se euro e yen si muovono nella stessa direzione contro il dollaro."
    )
    watch = ("Dopo il dato, guarda se il cambio segue lo spostamento delle attese sui tassi.") if catalyst else (
        "Nella prossima seduta, guarda se il movimento del dollaro si estende oltre le coppie che lo hanno guidato."
    )
    risk_by_label = {row["label"]: row["change"] for row in risk_closes}
    if risk_by_label.get("VIX", 0) < 0 < risk_by_label.get("spread high yield", 0):
        contradiction = "Il VIX è sceso mentre il credito high yield ha chiesto uno spread più ampio. La tensione nel credito merita una verifica a parte."
    elif fx and fx["state"] == "mixed":
        contradiction = "Un movimento esteso del dollaro richiederebbe conferma sia contro euro sia contro yen."
    else:
        contradiction = "La tenuta del movimento dipende anche dal sostegno dei tassi a breve."
    judgment = sentence_join((lead, monetary))
    commodity_reading = ""

    # Source-linked evidence / official headlines, without pretending to have
    # read the body of RSS links. Narrative is based only on their titles.
    news = []
    def add(headline, analysis, kind, published, event, area, sources, evidence=""):
        urls = list(dict.fromkeys(u for u in sources if valid_url(u)))
        if not urls or len(news) >= 6 or not day(published) or not day(event):
            return
        news.append(compact_news(dict(headline=headline, analysis=analysis, kind=kind,
            published_date=published, event_date=event, market_area=area, sources=urls, evidence=evidence)))

    if fx:
        rates_sources = [usd.get("source_url"), eur.get("source_url")] if comparative else []
        rates_details = monetary_evidence if len(rates_sources) == 2 and all(map(valid_url, rates_sources)) else ""
        fx_watch = (sentence_join((event_sentence, event_relevance))
                    if catalyst and catalyst[1]["ccy"] in ("JPY", "EUR", "USD") else
                    "La prossima verifica è capire se il movimento si estende agli altri cambi.")
        add(fx_headline, sentence_join((fx_reading, fx_watch)), "FOLLOW_UP", fx["date"], fx["date"],
            "FOREX", [ECB_FIXING] + (rates_sources if rates_details else []),
            sentence_join((fx_fact, rates_details)))
    if macro:
        country = COUNTRIES.get(macro.get("ccy"), "")
        macro_lead = macro_opening(macro, series) or (f"Aggiornamento macro {country}." if country else "")
        if macro_lead:
            macro_headline = macro_lead.rstrip(".")
            if macro.get("metric_id") == "AU_UNEMP_RATE_SA":
                macro_watch = "Per il dollaro australiano conta se, dopo il dato, cambiano le attese sui tassi."
            else:
                macro_watch = f"Il punto da seguire è se cambiano le attese sui tassi {country}."
            add(macro_headline, macro_watch, "FOLLOW_UP", macro["as_of"], macro["as_of"], "MACRO",
                [macro["source_url"]], macro["title"])
    if risk_closes:
        risk_date = risk_closes[0]["date"]
        credit = risk_by_label.get("spread high yield", 0)
        shares = risk_by_label.get("S&P 500", risk_by_label.get("Nasdaq Composite", 0))
        equity = "Il Nasdaq Composite" if "Nasdaq Composite" in risk_by_label else "Wall Street"
        risk_headline = ("Azioni in calo e credito più cauto" if shares < -.005 and credit > .5 else
                         "Più cautela sul credito" if credit > .5 else
                         "Si riduce il premio sul debito più rischioso" if credit < -.5 else
                         f"{equity} sale" if shares > .005 else
                         f"{equity} scende" if shares < -.005 else "Il quadro del rischio")
        risk_watch = ("La volatilità in Borsa è scesa. Da seguire se la cautela nel credito si estende alle prossime sedute."
                      if risk_by_label.get("VIX", 0) < -.005 and credit > .5 else
                      "Da seguire se il movimento prosegue anche alla prossima chiusura.")
        add(risk_headline, sentence_join((risk_story, risk_watch)), "FOLLOW_UP", risk_date, risk_date,
            "RISCHIO", [row["url"] for row in risk_closes], risk_fact)
    if gold and oil:
        oil_label = "WTI" if wti else "Brent"
        gold_date, oil_date = gold["proxy_as_of"], oil["proxy_as_of"]
        commodity_date = max(gold_date, oil_date)
        gold_change, oil_change = gold["change_1d_pct"], oil["change_1d_pct"]
        movement = lambda delta: "sale" if delta > .005 else "scende" if delta < -.005 else "resta stabile"
        latest_moves = []
        if gold_date == commodity_date:
            latest_moves.append(f"l’oro {movement(gold_change)}")
        if oil_date == commodity_date:
            latest_moves.append(f"il {oil_label} {movement(oil_change)}")
        commodity_reading = (
            f"Nei proxy futures del {short_date(day(commodity_date))} "
            + " e ".join(latest_moves) + "."
        )
        if gold_date == oil_date:
            commodity_headline = (f"Oro e petrolio in {'calo' if gold_change < 0 else 'rialzo'}"
                                  if abs(gold_change) > .005 and abs(oil_change) > .005 and gold_change * oil_change > 0 else
                                  f"L’oro {movement(gold_change)}, il petrolio {movement(oil_change)}")
        elif gold_date > oil_date:
            commodity_headline = f"L’oro {movement(gold_change)}"
        else:
            commodity_headline = f"Il petrolio {movement(oil_change)}"
        commodity_watch = ("Se il movimento del petrolio prosegue, guarda come reagisce il dollaro canadese."
                           if oil_date == commodity_date else
                           "Per capire se il movimento dell’oro dura, vale la pena seguire anche la direzione del dollaro.")
        commodity_evidence = (
            f"Proxy futures da fonte secondaria. Oro {signed(gold_change)}% al {short_date(day(gold_date))}. "
            f"{oil_label} {signed(oil_change)}% al {short_date(day(oil_date))}."
        )
        add(commodity_headline, commodity_watch, "FOLLOW_UP", commodity_date, commodity_date,
            "COMMODITIES", [gold["source_endpoint"], oil["source_endpoint"]], commodity_evidence)
    for h in recent:
        if len(news) >= 6:
            break
        title = str(h["title"])
        ctx = h.get("desk_context") or {}
        topic = ctx.get("topic")
        why = {
            "CB_POLICY": "Da capire se il messaggio cambia le attese sui tassi e come risponde la valuta.",
            "MACRO_EXPECTATIONS": "Da seguire se le prospettive per crescita e prezzi cambiano le attese sui tassi.",
            "CB_COMMUNICATION": "Conta se dalle parole emerge un cambiamento di posizione sui tassi.",
            "ENERGY_FUNDAMENTALS": "Per il petrolio, il passaggio da seguire è se cambiano le scorte o le forniture.",
            "ENERGY_STRUCTURE": "Questo approfondimento aiuta a leggere come cambia l’offerta di energia.",
        }.get(topic, ctx.get("why_watch") or "Il documento originale offre il contesto per approfondire la notizia.")
        if topic == "ENERGY_STRUCTURE" and "middle east chokepoints" in title.lower():
            why = "Più petrolio è transitato per queste rotte nel terzo trimestre. Il dato aiuta a capire da quali passaggi dipendono le forniture."
        # The publication headline is factual; any policy direction is NOT implied.
        when = clock(h["published_at_utc"]).astimezone(ROME).date().isoformat()
        kind = "NEWS" if (today-day(when)).days <= 1 else "FOLLOW_UP"
        add(title, why, kind, when, when,
            "ENERGIA" if h.get("ccy") == "ENERGY" else "BANCHE CENTRALI",
            [h["url"]])
    if not news:
        raise ValueError("No source-linked news or background facts for publication")
    changes = sentence_join((commodity_reading, monetary)) or risk_story or macro_fact or fx_reading or lead
    citations = sorted({u for item in news for u in item["sources"]})
    # Core source fingerprint does not use the collection time. A new edition
    # is legitimate only if an observation / RSS title / calendar fact changes.
    material = {
        "pulse": sorted([(x.get("category"), x.get("title"), x.get("as_of"))
                         for x in items]),
        "commodities": [(k, v.get("proxy_as_of"), v.get("change_1d_pct"))
                        for k, v in [("gold", gold), ("wti", wti), ("brent", brent)] if v],
        "rss": [(x.get("url"), x.get("published_at_utc")) for x in recent],
        "news_reading": [(item["headline"], item["analysis"], item["evidence"], item["sources"]) for item in news],
        "session_reading": {"fx": fx, "risk": risk_closes, "headline": headline, "lead": lead,
                            "fx_implications": fx_interpretation, "what_changed": changes,
                            "catalyst": (catalyst[0].isoformat(), catalyst[1]["title"]) if catalyst else None},
    }
    signature = hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if isinstance(previous, dict) and previous.get("schema") == SCHEMA and previous.get("material_digest") == signature:
        return previous  # exact bytes preserved: no new "hourly news" on old data
    old_news = previous.get("news", []) if isinstance(previous, dict) else []
    old_sig = {(x.get("headline"), x.get("event_date"))
               for x in old_news if isinstance(x, dict)}
    for entry in news:
        if (entry["headline"], entry["event_date"]) in old_sig and entry["kind"] == "NEWS":
            entry["kind"] = "FOLLOW_UP"
    history = []
    if isinstance(previous, dict) and previous.get("schema") == SCHEMA:
        history = [{"generated_at_utc": previous.get("generated_at_utc"),
                    "headline": previous.get("headline"), "material_digest": previous.get("material_digest")}] + previous.get("history", [])
    return {
        "schema": SCHEMA, "status": "ACTIVE", "generated_at_utc": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "edition_time_rome": now.astimezone(ROME).strftime("%Y-%m-%d %H:%M"),
        "material_digest": signature, "editorial_contract": "V3_SOURCE_DATED_SESSION_READING",
        "engine": "FREE_DETERMINISTIC_CROSS_ASSET_RESEARCH", "headline": headline,
        "lead": lead, "news": news, "desk_judgment": judgment, "fx_implications": fx_interpretation,
        "what_changed": changes, "contrary_evidence": contradiction, "watch": watch,
        "provenance": {"web_source_urls": citations, "method": "FREE_OFFICIAL_RSS_AND_SOURCE_DATED_MARKET_DATA",
                       "source_vintages": {"news": pulse.get("content_as_of"), "rss_checked_at_utc": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                                           "commodities": gold.get("proxy_as_of") if gold else (oil or {}).get("proxy_as_of")},
                       "no_paid_api": True, "no_ai_model": True, "chatgpt_automation_unchanged": True},
        "history": history[:24],
    }



def make_check_receipt(now: datetime, edition: dict, previous=None):
    """Independent verification receipt. Never mutate the substantive edition."""
    if not now.tzinfo or now.utcoffset() is None:
        raise ValueError("Check time requires an aware clock")
    if edition.get("schema") != SCHEMA or edition.get("status") != "ACTIVE":
        raise ValueError("Receipt requires a validated active edition")
    return {
        "schema": "GMFQ_NEXT_HOURLY_CHECK_V1",
        "status": "VERIFIED",
        "checked_at_utc": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "edition_generated_at_utc": edition["generated_at_utc"],
        "material_digest": edition["material_digest"],
        "edition_changed": not (isinstance(previous, dict)
                                and previous.get("schema") == SCHEMA
                                and previous.get("material_digest") == edition["material_digest"]),
        "meaning": "Successful source-build verification; not a claim that every source published new data",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--check-output")  # optional separate hourly verification receipt
    parser.add_argument("--previous")
    parser.add_argument("--rss-json")  # for offline deterministic fixtures
    parser.add_argument("--now")
    args = parser.parse_args(argv)
    now = clock(args.now) if args.now else datetime.now(timezone.utc)
    if not now:
        raise ValueError("Timezone-aware --now required")
    prior = read_json(args.previous) if args.previous else None
    rss = read_json(args.rss_json) if args.rss_json else None
    edition = build(Path(args.root), now, previous=prior, rss=rss)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(edition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.check_output:
        receipt = make_check_receipt(now, edition, previous=prior)
        check_path = Path(args.check_output)
        check_path.parent.mkdir(parents=True, exist_ok=True)
        check_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("FREE_HOURLY_CHECK", json.dumps({
            "checked_at_utc": receipt["checked_at_utc"],
            "edition_changed": receipt["edition_changed"],
            "edition_at_utc": receipt["edition_generated_at_utc"]}))

    print("FREE_HOURLY_DESK", json.dumps({
        "status": edition["status"], "date": edition["generated_at_utc"],
        "stories": len(edition["news"]), "digest": edition["material_digest"],
        "no_paid_api": True, "chatgpt_alerts_modified": False
    }))


if __name__ == "__main__":
    main()
