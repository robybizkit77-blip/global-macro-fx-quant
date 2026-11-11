#!/usr/bin/env python3
"""Source-verified G8 macro actuals for the existing NEWS_PULSE (research only).

No new collector or schedule. Reads SHA-validated immutable issuer ledgers
already populated by the Calendar/News pipeline. Every item has a runner
first-observation clock; market reactions and survey surprises are unproven.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.freeze_pre_release_consensus_v1 import (
    LEDGER as FROZEN_V1, read_existing,
)
from validation.macro.capture_official_postrelease_actuals_v1 import (
    OUT as ACTUAL_V1, validate_actual_log,
)
from validation.macro.freeze_exact_metric_forecasts_v9 import (
    LEDGER as METRIC_FORECAST_V9, read_rows,
)
from validation.macro.capture_uk_ch_gdp_official_firstseen_v11 import (
    OUT as GDP_V11, OFFICIAL as OFFICIAL_SEED, validate_actuals,
)

ROME = ZoneInfo("Europe/Rome")
QUALITY_V1 = "OFFICIAL_PAGE_FIRST_OBSERVATION_NOT_FIRST_RELEASE_PIT"
QUALITY_V11 = "ISSUER_GDP_FIRST_RUNNER_OBSERVATION_NOT_PUBLISHER_PIT"
CCY = frozenset({"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"})
KINDS = frozenset({"INFLATION", "LABOUR", "LABOUR_COST", "GROWTH"})
LABELS = {
    "USD|2026-10-30|LABOUR_COST|Employment Cost Index":
        "USA · costo del lavoro civile, trimestrale destagionalizzato",
    "CAD|2026-10-30|GROWTH|Gross domestic product by industry":
        "Canada · PIL reale per industria, mensile destagionalizzato",
    "UK_REAL_GDP_PRELIM_QOQ_SA":
        "Regno Unito · PIL reale preliminare, trimestre su trimestre",
    "CH_REAL_GDP_FLASH_QOQ":
        "Svizzera · PIL flash, trimestre su trimestre",
}

def stamp(raw):
    if type(raw) is not str or not raw.endswith("Z"):
        raise ValueError("Actual observation requires UTC Z timestamp")
    seen = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if seen.tzinfo is None or seen.utcoffset() != timezone.utc.utcoffset(seen):
        raise ValueError("Actual observation is not UTC")
    return seen

def number(v):
    return f"{v:+.1f}".replace(".", ",") + "%"

def signed_pp(v):
    return f"{v:+.1f}".replace(".", ",") + " punti percentuali"

def event_info(key):
    parts=key.split("|", 3) if type(key) is str else []
    if len(parts)!=4 or parts[0] not in CCY or parts[2] not in KINDS:
        raise ValueError("Unknown G8 event identity")
    released=date.fromisoformat(parts[1])
    return parts[0],released,parts[2]

def build(now, *, v1_forecasts=None, v1_actuals=None,
          v9_forecasts=None, v11_actuals=None, official_seed=None):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Offset-aware publication clock required")
    now=now.astimezone(timezone.utc)
    day=now.astimezone(ROME).date()
    frozen = read_existing(FROZEN_V1) if v1_forecasts is None else v1_forecasts
    old = read_existing(ACTUAL_V1) if v1_actuals is None else v1_actuals
    metric = read_rows(METRIC_FORECAST_V9) if v9_forecasts is None else v9_forecasts
    gdp = read_existing(GDP_V11) if v11_actuals is None else v11_actuals
    seed = json.loads(OFFICIAL_SEED.read_text(encoding="utf-8")) if official_seed is None else official_seed
    # Fail closed on a broken SHA chain, wrong event, wrong metric, forged
    # timestamp or wrong issuer URL, before considering any output.
    validate_actual_log(old, frozen)
    validate_actuals(gdp, seed, metric)
    items=[]
    def append(row, observed_raw, label, comparison, quality, metric_id=None):
        ccy,released,kind=event_info(row["event_key"])
        seen=stamp(observed_raw)
        if not (released <= day and 0 <= (day-released).days <= 7 and
                seen <= now and seen.astimezone(ROME).date() <= day):
            return
        value=row["actual_percent"]
        remark=("Confronto con una previsione secondaria congelata prima del dato, "
                "NON con un consenso survey certificato. "
                if comparison is not None else
                "Previsione pre-evento con provenienza sufficiente non disponibile. ")
        if comparison is not None:
            remark += ("Scarto descrittivo " +
                       signed_pp(value-comparison) + ". ")
        note=("Non attribuiamo causalmente il movimento di tassi, OIS o FX "
              "alla pubblicazione senza quotazioni pre/post sincronizzate. ")
        if ccy=="CHF":
            note+="L'aggiustamento della serie GDP flash va verificato separatamente. "
        items.append({
            "category":"MACRO_OFFICIAL_ACTUAL",
            "ccy":ccy,
            "event_type":kind,
            "event_key":row["event_key"],
            "metric_id":metric_id,
            "as_of":released.isoformat(),
            "title":f"{label}: {number(value)}",
            "detail":(f"Fonte ufficiale per {row['reference_period']}: "
                      f"{number(value)}. "+remark+note+
                      f"Prima osservazione del nostro runner: {observed_raw}."),
            "source":row["publisher"],
            "source_url":row["source_url"],
            "first_runner_observed_at_utc":observed_raw,
            "quality":quality,
            "confidence":"A",
            "importance":"HIGH",
            "_date":released,
        })
    for row in old:
        append(row, row["captured_at_utc"],
               LABELS[row["event_key"]],
               row["frozen_secondary_consensus_percent"],
               QUALITY_V1)
    for row in gdp:
        append(row, row["observed_at_utc"],
               LABELS[row["metric_id"]],
               row["v9_secondary_forecast_pct"],
               QUALITY_V11,metric_id=row["metric_id"])
    return sorted(items,key=lambda x:(x["as_of"],x["first_runner_observed_at_utc"]),reverse=True)
