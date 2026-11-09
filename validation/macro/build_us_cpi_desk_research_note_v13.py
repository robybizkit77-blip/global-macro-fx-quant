#!/usr/bin/env python3
"""CPI official desk readout (research only): exact observations, not a signal.

Reads existing immutable V9 secondary forecasts and V10 BLS actuals. Optional
dated Treasury, ECB-fixing and Fed-futures data are context only: absent
synchronized intraday quotes they NEVER prove event reaction or policy
repricing. The note is a GitHub artifact, not an operational site data feed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from validation.macro.capture_us_cpi_exact_actuals_v10 import (
    KEY, METRICS, OUT, ROOT, expected_release, validate_actual_log
)
from validation.macro.freeze_exact_metric_forecasts_v9 import (
    LEDGER, read_rows, validate_existing as validate_forecasts
)

SCHEMA = "GMFQ_US_CPI_DESK_RESEARCH_READOUT_V13"
RATES = ROOT / "live_data/sections/NATIVE_RATES_DATA.json"
FX = ROOT / "live_data/sections/ECB_G8_PRICE_HISTORY.json"
OIS = ROOT / "live_data/sections/OIS_OPERATIONAL_VIEW.json"
METRIC_LABELS = {
    "US_CPI_U_HEADLINE_MOM_SA": "Headline mensile (SA)",
    "US_CPI_U_HEADLINE_YOY_NSA": "Headline annuale (NSA)",
    "US_CPI_U_CORE_MOM_SA": "Core mensile (SA)",
    "US_CPI_U_CORE_YOY_NSA": "Core annuale (NSA)",
}


def pct(x):
    return f"{x:+.2f}".replace(".", ",") + "%"


def pp(x):
    return f"{x:+.2f}".replace(".", ",") + " pp"


def market_context(rates, fx, ois, now):
    """Explicit daily-only observations, never a post-release measurement."""
    day = now.date().isoformat()
    us = (rates or {}).get("USD", {})
    rday = us.get("date")
    rate = None
    if (isinstance(rday, str) and rday <= day and
            us.get("quality") == "FULL_CURRENT_OFFICIAL" and
            all(type(us.get(k)) in (float, int) for k in ("2Y", "10Y"))):
        rate = {
            "as_of_date": rday, "yield_2y_percent": us["2Y"],
            "yield_10y_percent": us["10Y"], "source": us.get("source"),
            "evidence": "DAILY_OFFICIAL_SNAPSHOT_NOT_INTRADAY_CPI_REACTION",
        }
    fixing = None
    if fx and fx.get("base") == "EUR" and isinstance(fx.get("rows"), list):
        rows = [
            row for row in fx["rows"]
            if isinstance(row, dict) and
            isinstance(row.get("Date"), str) and row["Date"] <= day and
            type(row.get("USD")) in (int, float) and row["USD"] > 0
        ]
        if rows:
            row = max(rows, key=lambda x: x["Date"])
            fixing = {
                "as_of_date": row["Date"], "eurusd": row["USD"],
                "source": fx.get("source"),
                "evidence": "ECB_DAILY_REFERENCE_FIXING_NOT_CPI_EVENT_WINDOW",
            }
    us_ois = (ois or {}).get("currencies", {}).get("USD", {})
    status = us_ois.get("operational_status") or "NOT_AVAILABLE"
    policy = {
        "status": status, "as_of_date": us_ois.get("as_of"),
        "source_quality": us_ois.get("quality"),
        "intraday_policy_repricing_certified": False,
        "note": ("This pipeline has no timestamp-synchronized Fed OIS/futures "
                 "before/after BLS release. Source levels cannot prove repricing."),
    }
    return {
        "treasury": rate, "ecb_eurusd_fixing": fixing, "fed_pricing": policy,
        "synchronized_release_window_quotes_verified": 0,
        "market_causality_established": False,
        "equity_gold_event_reaction": "NOT_MEASURED",
    }


def build(forecasts, actuals, *, rates=None, fx=None, ois=None, now=None):
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("UTC-aware build time is required")
    now = now.astimezone(timezone.utc)
    validate_forecasts(forecasts)
    validate_actual_log(actuals, forecasts)
    if actuals and now < max(datetime.fromisoformat(
            row["observed_at_utc"].replace("Z", "+00:00")) for row in actuals):
        raise ValueError("Cannot report official actual before observation time")
    found = {r["metric_id"]: r for r in forecasts if r["event_key"] == KEY}
    observed = {r["metric_id"]: r for r in actuals}
    release = expected_release()
    stage = ("FOUR_OFFICIAL_METRICS_VALIDATED_RESEARCH_ONLY" if actuals else
             "AWAITING_BLS_RELEASE_NO_ACTUAL" if now < release else
             "AWAITING_VALIDATED_V10_ACTUAL_OR_ARCHIVE")
    metrics = []
    for mid in METRICS:
        f = found.get(mid)
        a = observed.get(mid)
        metrics.append({
            "metric_id": mid, "label": METRIC_LABELS[mid],
            "reference_period": "October 2026",
            "actual_percent": a["actual_percent"] if a else None,
            "secondary_forecast_percent": f["forecast_value_percent"] if f else None,
            "delta_vs_secondary_forecast_pp":
                a["actual_minus_v9_provider_observation_pp"] if a else None,
            "secondary_forecast_capture_utc": f["captured_at_utc"] if f else None,
            "secondary_is_survey_consensus_certified": False,
            "delta_is_market_surprise_certified": False,
        })
    if not actuals:
        observation = "Il CPI di ottobre non risulta ancora acquisito come quattro actual ufficiali V10."
        implication = ("Non attribuire una sorpresa d'inflazione né una reazione dei mercati "
                       "in assenza del comunicato e di osservazioni sincronizzate.")
    else:
        hm = observed["US_CPI_U_HEADLINE_MOM_SA"]["actual_percent"]
        cm = observed["US_CPI_U_CORE_MOM_SA"]["actual_percent"]
        hd = observed["US_CPI_U_HEADLINE_MOM_SA"]["actual_minus_v9_provider_observation_pp"]
        cd = observed["US_CPI_U_CORE_MOM_SA"]["actual_minus_v9_provider_observation_pp"]
        observation = (f"Headline mensile {pct(hm)}, core mensile {pct(cm)}. "
                       "I tassi annuali sono riportati separatamente: non confrontarli "
                       "con forecast mensili.")
        if hd is None or cd is None:
            implication = ("Il confronto con forecast mensili secondari è incompleto; "
                           "nessuna sorpresa certificata.")
        elif hd > 0 and cd > 0:
            implication = ("Entrambe le letture mensili superano i forecast secondari: "
                           "questo può alimentare una lettura più prudente sull'inflazione, "
                           "ma NON prova il repricing Fed.")
        elif hd < 0 and cd < 0:
            implication = ("Entrambe le letture mensili sono inferiori ai forecast secondari: "
                           "può rafforzare l'ipotesi di disinflazione, senza dimostrare "
                           "un taglio Fed o la risposta effettiva dei mercati.")
        else:
            implication = ("Il confronto mensile è misto oppure contiene una corrispondenza "
                           "esatta ai forecast secondari: serve la composizione prima "
                           "di formulare una view di politica monetaria.")
    return {
        "schema": SCHEMA,
        "event_key": KEY,
        "as_of_utc": now.isoformat().replace("+00:00", "Z"),
        "official_scheduled_release_utc":
            release.isoformat().replace("+00:00", "Z"),
        "status": stage,
        "actual_source_url": actuals[0]["source_url"] if actuals else None,
        "actual_source_sha256": actuals[0]["source_html_sha256"] if actuals else None,
        "first_runner_observed_at_utc":
            actuals[0]["observed_at_utc"] if actuals else None,
        "publisher_first_delivery_time_certified": False,
        "metric_count": len(actuals),
        "metrics": metrics,
        "desk_observation": observation,
        "economic_hypothesis": implication,
        "evidence_limits": [
            "Un mese di CPI non dimostra accelerazione, decelerazione o persistenza: servono dati precedenti confrontabili e revisioni.",
            "Senza breakdown ufficiale di shelter, servizi, beni ed energia non attribuire il dato a domanda o offerta.",
            "Forecast secondario first-seen non equivale a survey consensus certificato.",
            "Il market pricing e il comportamento degli operatori richiedono evidenze indipendenti e timestamp pre/post evento.",
        ],
        "market_context": market_context(rates, fx, ois, now),
        "thesis_strength": "NON_CALIBRATED_RESEARCH_ONLY",
        "trade_attractiveness": "NOT_ASSESSED_NO_VERIFIED_EVENT_WINDOW",
        "FX_signal": None,
        "eligible_for_Core_Beta_Forward": False,
        "writes_live_data": False,
    }


def markdown(note):
    lines = [
        "# CPI USA ottobre 2026 — lettura del desk (ricerca, non segnale)",
        f"**As-of UTC:** {note['as_of_utc']}  ",
        f"**Stato:** {note['status']}  ",
        "**Fonte ufficiale:** " + (
            note["actual_source_url"] or "actual non ancora osservati nel registro"),
        "",
        "## Cosa sappiamo davvero",
        note["desk_observation"], "",
        "| Misura esatta | Actual BLS | Forecast secondario | Differenza |",
        "|---|---:|---:|---:|",
    ]
    for m in note["metrics"]:
        lines.append(
            f"| {m['label']} | "
            f"{pct(m['actual_percent']) if m['actual_percent'] is not None else 'non osservato'} | "
            f"{pct(m['secondary_forecast_percent']) if m['secondary_forecast_percent'] is not None else 'non disponibile'} | "
            f"{pp(m['delta_vs_secondary_forecast_pp']) if m['delta_vs_secondary_forecast_pp'] is not None else '—'} |"
        )
    lines += [
        "",
        "## Perché conta — lettura condizionata",
        note["economic_hypothesis"],
        "",
        "## Il mercato lo conferma?",
        "**Non verificato con finestre intraday sincronizzate.** I seguenti sono soltanto riferimenti giornalieri:",
    ]
    context = note["market_context"]
    if context["treasury"]:
        r = context["treasury"]
        lines.append(
            f"- Treasury USA {r['as_of_date']}: 2Y {pct(r['yield_2y_percent'])}, "
            f"10Y {pct(r['yield_10y_percent'])} (non reazione al CPI).")
    else:
        lines.append("- Treasury 2Y/10Y: nessun snapshot giornaliero ufficiale utilizzabile.")
    if context["ecb_eurusd_fixing"]:
        r = context["ecb_eurusd_fixing"]
        lines.append(
            f"- Fixing BCE {r['as_of_date']}: EUR/USD {r['eurusd']:.4f} "
            "(non reazione intraday al CPI).")
    else:
        lines.append("- Fixing EUR/USD BCE: non disponibile.")
    lines += [
        "- Pricing Fed: stato operativo **" + context["fed_pricing"]["status"]
        + "**; variazione OIS/futures dovuta al CPI **non certificata**.",
        "- S&P 500, Nasdaq e oro: reazione all'evento non misurata da questa pipeline.",
        "",
        "## Cosa confermerebbe / indebolirebbe la tesi",
        "Conferma: composizione ufficiale e ulteriori osservazioni d'inflazione coerenti, "
        "più prezzi verificati pre/post evento. "
        "Indebolisce: divergenza tra componenti, revisioni o mancato repricing "
        "nonostante un dato interpretabile come restrittivo/espansivo.",
        "",
        "## Limiti essenziali",
        *("- " + x for x in note["evidence_limits"]),
        "",
        "**Thesis Strength:** non calibrata. "
        "**Trade Attractiveness:** non valutabile da questo solo rapporto.",
        "**Effetto sui modelli, segnali, 28 coppie e sito:** nessuno.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--forecast", type=Path, default=LEDGER)
    parser.add_argument("--actual", type=Path, default=OUT)
    parser.add_argument("--rates", type=Path, default=RATES)
    parser.add_argument("--fx", type=Path, default=FX)
    parser.add_argument("--ois", type=Path, default=OIS)
    parser.add_argument("--json-out", type=Path, default=Path("/tmp/g8-us-cpi-desk-v13.json"))
    parser.add_argument("--md-out", type=Path, default=Path("/tmp/g8-us-cpi-desk-v13.md"))
    parser.add_argument("--github-summary", type=Path)
    args = parser.parse_args()
    for dest in (args.json_out, args.md_out):
        if not dest.resolve().is_relative_to(Path("/tmp")):
            raise ValueError("Research outputs must be under /tmp, not the repo")
    def json_or_empty(path):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    note = build(read_rows(args.forecast), read_rows(args.actual),
                 rates=json_or_empty(args.rates),
                 fx=json_or_empty(args.fx),
                 ois=json_or_empty(args.ois))
    content = markdown(note)
    args.json_out.write_text(json.dumps(note, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    args.md_out.write_text(content, encoding="utf-8")
    if args.github_summary:
        with args.github_summary.open("a", encoding="utf-8") as out:
            out.write("\n" + content + "\n")
    print(json.dumps({
        "status": note["status"], "metric_count": note["metric_count"],
        "market_intraday_evidence": 0, "writes_live_data": False,
        "eligible_for_Core_Beta_Forward": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
