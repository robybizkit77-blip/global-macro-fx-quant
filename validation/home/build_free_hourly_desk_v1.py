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
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

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
PAIR_LABELS = {"EURUSD": "EUR/USD", "USDJPY": "USD/JPY", "AUDCAD": "AUD/CAD"}
CROSS_CATEGORY = {
    "MARKET_FX_ECB_FIXING": "FOREX",
    "MARKET_EQUITY_CLOSE": "AZIONI",
    "MARKET_CREDIT_OAS": "CREDITO",
    "MARKET_VOLATILITY_CLOSE": "VOLATILITÀ",
    "MACRO_OFFICIAL_ACTUAL": "MACRO"
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


def compact_news(row):
    return {
        "headline": row["headline"], "analysis": row["analysis"],
        "kind": row["kind"], "published_date": row["published_date"],
        "event_date": row["event_date"], "market_area": row["market_area"],
        "sources": row["sources"]
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
    fx_eur = lookup("MARKET_FX_ECB_FIXING", lambda x: x.get("pair") == "EURUSD")
    fx_jpy = lookup("MARKET_FX_ECB_FIXING", lambda x: x.get("pair") == "USDJPY")
    fx_audcad = lookup("MARKET_FX_ECB_FIXING", lambda x: x.get("pair") == "AUDCAD")
    eur_change = signed_from_title(fx_eur.get("title")) if fx_eur else None
    jpy_change = signed_from_title(fx_jpy.get("title")) if fx_jpy else None
    audcad_change = signed_from_title(fx_audcad.get("title")) if fx_audcad else None
    fx_same_day = fx_eur and fx_jpy and fx_eur["as_of"] == fx_jpy["as_of"]
    usd_cross_support = fx_same_day and safe_number(eur_change) and safe_number(jpy_change) and eur_change < 0 and jpy_change > 0
    stock = lookup("MARKET_EQUITY_CLOSE", lambda x: "S&P" in x["title"])
    nasdaq = lookup("MARKET_EQUITY_CLOSE", lambda x: "Nasdaq" in x["title"])
    vix = lookup("MARKET_VOLATILITY_CLOSE")
    hy = lookup("MARKET_CREDIT_OAS", lambda x: "HY" in x["title"])
    ig = lookup("MARKET_CREDIT_OAS", lambda x: "IG" in x["title"])
    equities_up = (stock and nasdaq and stock["as_of"] == nasdaq["as_of"] and
                   safe_number(signed_from_title(stock["title"])) and
                   safe_number(signed_from_title(nasdaq["title"])) and
                   signed_from_title(stock["title"]) > 0 and signed_from_title(nasdaq["title"]) > 0)
    credit_tighter = (hy and ig and hy["as_of"] == ig["as_of"] and
                      safe_number(signed_from_title(hy["title"])) and
                      safe_number(signed_from_title(ig["title"])) and
                      signed_from_title(hy["title"]) < 0 and signed_from_title(ig["title"]) < 0)
    vix_up = bool(vix and safe_number(signed_from_title(vix["title"])) and signed_from_title(vix["title"]) > 0)
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
        stamped = clock(h.get("published_at_utc"))
        if stamped and stamped <= now + timedelta(minutes=5) and 0 <= (today-stamped.astimezone(ROME).date()).days <= 7:
            official.append(h)
    official.sort(key=lambda x: x["published_at_utc"], reverse=True)
    recent = official[:6]
    calendar = read_json(sections / "CALENDAR_OPERATIONAL_VIEW.json", {}) or {}
    forthcoming = [
        x for x in calendar.get("events", [])
        if isinstance(x, dict) and x.get("status") == "UPCOMING" and
        x.get("importance") == "HIGH" and day(x.get("date")) and
        0 < (day(x["date"]) - today).days <= 6 and
        x.get("quality", "").startswith("OFFICIAL")
    ]
    forthcoming.sort(key=lambda x: x["date"])

    # V3 logic: what the available observations imply, then a contradiction,
    # not a disconnected 2Y/10Y inventory.
    monetary = ("I rendimenti governativi a breve scadenza salgono più rapidamente negli Stati Uniti "
                "che nell'area euro: il differenziale si è mosso a favore del dollaro."
                if comparative and relative_bp > 2 else
                "I rendimenti governativi a breve scadenza si muovono relativamente più a favore "
                "dell'area euro, riducendo il sostegno dei tassi al dollaro."
                if comparative and relative_bp < -2 else
                "Il front-end USA ed europeo mostra una variazione relativa contenuta nella stessa finestra osservata."
                if comparative else
                "Il fronte monetario va letto in termini relativi, confrontando aspettative di politica "
                "monetaria e rendimento a breve delle diverse aree.")
    risk = ("Azionario e credito mostrano un recupero nella chiusura precedente, ma la volatilità "
            "è aumentata in una rilevazione successiva. La propensione al rischio resta disomogenea."
            if equities_up and credit_tighter and vix_up else
            "Le ultime chiusure di azioni e credito mostrano un miglioramento concorde; "
            "la sua persistenza dipenderà anche dalla volatilità."
            if equities_up and credit_tighter else
            "L'aumento della volatilità merita attenzione accanto ai mercati del credito: "
            "può segnalare una protezione più costosa senza dimostrare vendite forzate."
            if vix_up else
            "Azioni, credito e volatilità restano le conferme da confrontare per identificare "
            "l'effettiva ampiezza della propensione al rischio.")
    commodity_reading = ("Oro in rialzo e petrolio in calo negli ultimi futures rilevati offrono due "
                         "segnali differenti: ricerca di protezione e domanda energetica sono ipotesi "
                         "da verificare, non flussi già dimostrati."
                         if gold and oil and gold["change_1d_pct"] > 0 and oil["change_1d_pct"] < 0 else
                         "Oro e petrolio aggiungono due prospettive distinte sui tassi reali e "
                         "sulla domanda globale."
                         if gold and oil else
                         "Le materie prime contano soprattutto attraverso inflazione attesa, "
                         "domanda globale e differenze fra valute importatrici ed esportatrici.")
    fx_interpretation = (
        "Negli ultimi fixing BCE il dollaro si è rafforzato sia contro euro sia contro yen. "
        + ("Il movimento contro l'euro è coerente con il differenziale dei 2Y USA–Eurozona, "
           "ma questa coincidenza non dimostra causalità. "
           if comparative and relative_bp > 2 else
           "La forza cross va letta assieme ai tassi e al rischio globale. ")
        + "Per USD/JPY conta anche la traiettoria attesa della BoJ; per EUR/USD la differenza fra Fed e BCE."
        if usd_cross_support else
        "Il Forex va interpretato per coppie: per EUR/USD conta il confronto Fed–BCE, "
        "per USD/JPY quello Fed–BoJ e la componente di rischio globale. "
        + ("Negli ultimi fixing EUR/USD è sceso, ma distinguere forza USD da debolezza EUR "
           "richiede il confronto con altri cross." if safe_number(eur_change) and eur_change < 0 else
           "Il prezzo resta la conferma della tesi relativa, non la sua origine.")
    )
    headline = (
        "Il dollaro trova sostegno nei tassi relativi, mentre il rischio globale resta misto"
        if comparative and relative_bp > 2 and usd_cross_support and vix_up else
        "Mercati tra ripresa dell'azionario e cautela sulla volatilità"
        if equities_up and credit_tighter and vix_up else
        "Aspettative monetarie, qualità del rischio e forza relativa delle valute"
    )
    lead = (monetary + " " + risk)
    judgment = (monetary + " " + risk + " " + commodity_reading)
    contradiction = ("La prova contraria a un dollaro sostenuto dai tassi sarebbe un indebolimento "
                     "dei cross USD mentre il differenziale governativo resta favorevole. "
                     "I diversi orari di rilevazione fra azioni, credito e VIX impediscono "
                     "di trattarli come una sola reazione intraday."
                     if comparative and relative_bp > 2 else
                     "Una ripresa delle azioni senza conferma del credito o con volatilità in aumento "
                     "renderebbe più fragile l'interpretazione risk-on. Le ultime chiusure "
                     "rappresentano osservazioni datate, non flussi attribuibili a specifici operatori.")
    if forthcoming:
        ev = forthcoming[0]
        catalyst = ("Il prossimo catalizzatore sul calendario è " + str(ev["title"]) +
                    " (" + str(ev.get("ccy") or "macro") + ", " + ev["date"] +
                    "): conteranno sorpresa rispetto alle attese, composizione e risposta dei tassi relativi.")
    else:
        catalyst = ("Il prossimo dato o intervento di banca centrale potrà rimettere in discussione "
                    "le aspettative monetarie relative e il comportamento delle coppie FX.")
    watch = catalyst + " Il confronto con credito, volatilità e fixing successivi aiuterà a distinguere un movimento persistente da uno temporaneo."

    # Source-linked evidence / official headlines, without pretending to have
    # read the body of RSS links. Narrative is based only on their titles.
    news = []
    def add(headline, analysis, kind, published, event, area, sources):
        urls = list(dict.fromkeys(u for u in sources if valid_url(u)))
        if not urls or len(news) >= 6 or not day(published) or not day(event):
            return
        news.append(compact_news(dict(headline=headline, analysis=analysis, kind=kind,
            published_date=published, event_date=event, market_area=area, sources=urls)))

    if usd_cross_support and fx_eur and fx_jpy and valid_url(fx_eur.get("source_url")):
        add("Forza del dollaro sui cross EUR/USD e USD/JPY",
            "Due fixing BCE consecutivi indicano un USD più forte contro euro e yen. "
            "Il canale dei tassi USA–Eurozona può contribuire, mentre la BoJ e il rischio "
            "globale restano determinanti per il confronto con lo yen.",
            "FOLLOW_UP", fx_eur["as_of"], fx_eur["as_of"], "FOREX", [fx_eur["source_url"]])
    elif fx_eur and valid_url(fx_eur.get("source_url")):
        add(str(fx_eur["title"]),
            "Il movimento relativo di EUR/USD va letto fra aspettative Fed e BCE "
            "e confrontato con gli altri cambi per distinguere forza del dollaro "
            "da debolezza dell'euro. Il dato è un fixing BCE, non una reazione intraday.",
            "FOLLOW_UP", fx_eur["as_of"], fx_eur["as_of"], "FOREX", [fx_eur["source_url"]])
    if equities_up and credit_tighter and stock and hy and valid_url(stock.get("source_url")) and valid_url(hy.get("source_url")):
        add("Azionario e credito recuperano, ma la volatilità richiede prudenza",
            "S&P 500 e Nasdaq avanzano nell'ultima chiusura comune; gli spread HY e IG si "
            "restringono nella medesima seduta. Il VIX più recente cresce: "
            "un miglioramento del credito non equivale da solo a risk-on stabile.",
            "FOLLOW_UP", stock["as_of"], stock["as_of"], "AZIONI / CREDITO",
            [stock["source_url"], hy["source_url"], vix.get("source_url") if vix else None])
    elif vix and valid_url(vix.get("source_url")):
        add(str(vix["title"]),
            "La volatilità azionaria aumenta, mentre una lettura completa dello stress "
            "richiede il confronto con credito e valute cicliche. Nessun flusso "
            "o acquisto di protezione specifico è deducibile da questo solo livello.",
            "FOLLOW_UP", vix["as_of"], vix["as_of"], "RISCHIO", [vix["source_url"]])
    if gold and oil:
        oil_label = "WTI" if wti else "Brent"
        add("Oro e petrolio divergono nelle rilevazioni dei futures" if gold["change_1d_pct"] * oil["change_1d_pct"] < 0 else
            "Oro e petrolio: segnali da distinguere nella lettura macro",
            "I prezzi futures osservati offrono un confronto fra oro e " + oil_label +
            ". Le differenze possono riflettere tassi reali, domanda energetica e rischio "
            "globale, ma non dimostrano quali operatori abbiano comprato o venduto. "
            "Serie di fonte secondaria, trattate come proxy direzionali.",
            "FOLLOW_UP", min(gold["proxy_as_of"], oil["proxy_as_of"]),
            min(gold["proxy_as_of"], oil["proxy_as_of"]), "COMMODITIES",
            [gold["source_endpoint"], oil["source_endpoint"]])
    macro = lookup("MACRO_OFFICIAL_ACTUAL")
    if macro and valid_url(macro.get("source_url")):
        add(str(macro["title"]),
            "La composizione di headline e core aiuta a giudicare persistenza dei prezzi "
            "e possibili conseguenze per le aspettative Fed. Il dato pubblicato "
            "resta distinto dalla sorpresa rispetto al consenso e dalla successiva reazione FX.",
            "FOLLOW_UP", macro["as_of"], macro["as_of"], "MACRO", [macro["source_url"]])
    for h in recent:
        if len(news) >= 6:
            break
        title = str(h["title"])
        ctx = h.get("desk_context") or {}
        why = ctx.get("why_watch") or "Pubblicazione istituzionale da approfondire."
        next_check = ctx.get("verify_next") or "Leggere l'atto originale e i dati relativi."
        # The publication headline is factual; any policy direction is NOT implied.
        when = clock(h["published_at_utc"]).astimezone(ROME).date().isoformat()
        kind = "NEWS" if (today-day(when)).days <= 1 else "FOLLOW_UP"
        add(title, why + " " + next_check, kind, when, when,
            "ENERGIA" if h.get("ccy") == "ENERGY" else "BANCHE CENTRALI",
            [h["url"]])
    if not news:
        raise ValueError("No source-linked news or background facts for publication")
    citations = sorted({u for item in news for u in item["sources"]})
    # Core source fingerprint does not use the collection time. A new edition
    # is legitimate only if an observation / RSS title / calendar fact changes.
    material = {
        "pulse": sorted([(x.get("category"), x.get("title"), x.get("as_of"))
                         for x in items]),
        "commodities": [(k, v.get("proxy_as_of"), v.get("change_1d_pct"))
                        for k, v in [("gold", gold), ("wti", wti), ("brent", brent)] if v],
        "rss": [(x.get("url"), x.get("published_at_utc")) for x in recent],
        "next_event": (forthcoming[0].get("date"), forthcoming[0].get("title")) if forthcoming else None,
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
    changes = ("Sono entrate nuove osservazioni o pubblicazioni rispetto alla precedente edizione. "
               "La direzione relativa di tassi, Forex, credito e materie prime viene ricomposta "
               "in un solo quadro economico, senza attribuire automaticamente causalità."
               if previous and previous.get("schema") == SCHEMA else
               "Prima sintesi del motore indipendente: le osservazioni provengono da sedute e "
               "fonti diverse, perciò il giudizio distingue quadro di fondo da novità effettive.")
    history = []
    if isinstance(previous, dict) and previous.get("schema") == SCHEMA:
        history = [{"generated_at_utc": previous.get("generated_at_utc"),
                    "headline": previous.get("headline"), "material_digest": previous.get("material_digest")}] + previous.get("history", [])
    return {
        "schema": SCHEMA, "status": "ACTIVE", "generated_at_utc": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "edition_time_rome": now.astimezone(ROME).strftime("%Y-%m-%d %H:%M"),
        "material_digest": signature, "editorial_contract": "V3_ECONOMIC_METHOD_ADAPTED_WITHOUT_LLM",
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
