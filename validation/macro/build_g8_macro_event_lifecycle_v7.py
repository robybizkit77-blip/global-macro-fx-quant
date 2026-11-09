#!/usr/bin/env python3
"""G8 event lifecycle and missing-evidence audit V7.

Read-only operational research audit on the EXISTING Calendar/News refresh clock.
Do not invent consensus, official actuals, release times, post-event markets,
or macro causes. Only ECI USD and GDP CAD have issuer-parsed first-seen actuals.
The other G8 events remain explicitly unsupported until a metric-specific
issuer/consensus mapping and actual parser are verified.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro import build_g8_event_surprise_relative_pairs_v6 as v6
from validation.macro.freeze_pre_release_consensus_v1 import (
    G8,scheduled,exact_event_key,utc_iso,validate_existing,read_existing
)
from validation.macro.capture_official_postrelease_actuals_v1 import (
    validate_actual_log,ECI,GDP,TARGETS
)
from validation.macro.build_macro_event_market_context_v1 import validate_anchors
from validation.refresh_macro_consensus_secondary_v1 import series_compatible

ROOT=v6.ROOT
SCHEMA="GMFQ_G8_MACRO_EVENT_LIFECYCLE_READINESS_V7"
PATHS={
    "official_calendar":"live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json",
    "secondary_consensus":"live_data/sections/MACRO_CONSENSUS_SECONDARY_V1.json",
    "frozen_forecast":"validation/macro/MACRO_PRE_RELEASE_CONSENSUS_LEDGER_V1.jsonl",
    "first_seen_actual":"validation/macro/MACRO_OFFICIAL_ACTUAL_FIRST_SEEN_V1.jsonl",
    "pre_market_anchor":"validation/macro/MACRO_EVENT_PRE_RELEASE_MARKET_ANCHORS_V1.jsonl",
    "canonical_pairs":v6.v5.PAIR_REGISTRY_FILE,
}
ORDER=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
# Parsers require explicit issuer metric, observation period and units.
# An official calendar *release title* alone does not specify CPI YoY/MoM,
# wage series or GDP quarterly vs annual growth, so cannot be an actual.
ISSUER_PARSER_KEYS=frozenset(TARGETS)
HORIZON_DAYS=35

def require(ok,why):
    if not ok:
        raise ValueError("G8_EVENT_LIFECYCLE_V7_REJECTED: "+why)

def sha(b):
    return hashlib.sha256(b).hexdigest()

def load(*,root=ROOT):
    data,hashes={},{}
    for key,rel in PATHS.items():
        b=(root/rel).read_bytes()
        hashes[key]=sha(b)
        if rel.endswith(".jsonl"):
            data[key]=read_existing(root/rel)
        else:
            data[key]=json.loads(b)
    return data,hashes

def aware_rome(now):
    require(isinstance(now,datetime) and now.tzinfo is not None and
            now.utcoffset() is not None,"aware now required")
    return now.astimezone(ZoneInfo("Europe/Rome"))

def candidate_ready(event,candidate,now_utc):
    """A current secondary candidate is *not* a locked forecast."""
    if candidate is None:
        return "NO_MATCHED_PROVIDER_CANDIDATE"
    if not series_compatible(event,{"event":candidate.get("provider_event")}):
        return "PROVIDER_SERIES_NOT_EXACT_ISSUER_METRIC"
    if candidate.get("status")!="AVAILABLE" or not candidate.get("consensus"):
        return "NO_NUMERIC_PROVIDER_FORECAST"
    if candidate.get("confidence_grade")!="B" or candidate.get("date_match_gap_days")!=0:
        return "PROVIDER_FORECAST_DATE_OR_ID_NOT_HIGH_CONFIDENCE"
    stamp=scheduled(event)
    if stamp is None or now_utc>=stamp:
        return "TOO_LATE_TO_FREEZE_FORECAST"
    return "CANDIDATE_AVAILABLE_NOT_YET_FROZEN"

def build(*,now,inputs=None,root=ROOT):
    local=aware_rome(now)
    now_utc=local.astimezone(timezone.utc)
    today=local.date()
    data,hashes=load(root=root) if inputs is None else (inputs,{})
    seed=data["official_calendar"]
    con=data["secondary_consensus"]
    frozen=data["frozen_forecast"]
    actual=data["first_seen_actual"]
    anchors=data["pre_market_anchor"]
    pairs=data["canonical_pairs"]["pairs"]
    require(seed.get("schema")=="GMFQ_MACRO_RELEASE_OFFICIAL_SEED_V1"
            and seed.get("status")=="ACTIVE_VERIFIED_SEED",
            "official schedule contract unknown")
    require(con.get("schema")=="GMFQ_MACRO_CONSENSUS_SECONDARY_V1"
            and con.get("provider")=="FOREX_FACTORY_FAIR_ECONOMY_WEEKLY"
            and con.get("rules",{}).get("actual_not_used_as_pre_release_consensus") is True
            and con.get("rules",{}).get("never_change_release_date") is True,
            "untrusted secondary consensus input")
    validate_existing(frozen)
    validate_actual_log(actual,frozen)
    validate_anchors(anchors,frozen)
    expected={exact_event_key(e):e for e in seed["events"]}
    require(len(expected)==len(seed["events"]),"duplicate issuer schedule event")
    require(set(x["ccy"] for x in seed["events"])==set(ORDER),
            "official calendar lacks historical G8 representation")
    require(len(pairs)==28 and
            all(x["canonical_pair"] for x in pairs.values()),
            "28 canonical FX pairs source unavailable")
    frozen_idx={x["event_key"]:x for x in frozen}
    actual_idx={x["event_key"]:x for x in actual}
    anchor_idx={x["event_key"]:x for x in anchors}
    live_idx={x["event_key"]:x for x in con["events"]}
    require(all(x in expected for x in frozen_idx),"frozen forecast missing issuer identity")
    require(all(x in expected for x in actual_idx),"official actual missing issuer identity")
    require(all(x in expected for x in anchor_idx),"pre-event market anchor missing issuer identity")
    require(len(live_idx)==len(con["events"]),"duplicated candidate consensus keys")
    rows=[]
    for key,e in sorted(expected.items(),key=lambda kv:(
        kv[1]["date"],ORDER.index(kv[1]["ccy"]),kv[1]["event_type"])):
        release_day=date.fromisoformat(e["date"])
        clock=scheduled(e)
        past=release_day<today or (
            clock is not None and now_utc>=clock)
        future=release_day>=today and not past
        frozen_row=frozen_idx.get(key)
        actual_row=actual_idx.get(key)
        anchor_row=anchor_idx.get(key)
        candidate=live_idx.get(key)
        parser=key in ISSUER_PARSER_KEYS
        if frozen_row is not None:
            require(clock is not None,"frozen forecast but missing official clock")
            require(utc_iso(frozen_row["captured_at_utc"])<clock,
                    "post-release frozen consensus admitted")
        if actual_row is not None:
            require(clock is not None and frozen_row is not None,
                    "actual without verified pre-release forecast and clock")
            require(utc_iso(actual_row["captured_at_utc"])>=clock,
                    "actual before scheduled release")
            require(parser,"actual without approved issuer-specific parser")
            require(actual_row["forecast_receipt_sha256"]==
                    frozen_row["record_sha256"],"actual/forecast identity mismatch")
        near=0<=(release_day-today).days<=HORIZON_DAYS
        affected=[p["canonical_pair"] for p in pairs.values()
                  if e["ccy"] in p["canonical_pair"].split("/")]
        require(len(affected)==7,e["ccy"]+" must occur in exactly seven G8 pairs")
        if clock is None:
            state="MISSING_OFFICIAL_INTRADAY_RELEASE_TIME"
            action=("Verificare l'orario ufficiale e l'eventuale ambiguità DST; "
                    "impossibile congelare un consenso rispetto a un clock ignoto.")
        elif actual_row is not None:
            state="FROZEN_FORECAST_AND_FIRST_SEEN_OFFICIAL_ACTUAL"
            action=("Sorpresa descrittiva disponibile. Conservare il primo receipt "
                    "e cercare solo prezzi pre/post con timestamp verificati.")
        elif past and frozen_row is None:
            state="PAST_EVENT_NO_FROZEN_CONSENSUS"
            action=("Non ricostruire un consenso ex-post; attendere il successivo "
                    "rilascio equivalente con metrica esplicita.")
        elif past and not parser:
            state="PAST_FROZEN_EVENT_NO_VERIFIED_ISSUER_PARSER"
            action=("Creare un parser per periodo, metrica e fonte issuer, "
                    "senza inferire l'actual da un RSS generico.")
        elif past:
            state="WAITING_APPROVED_ISSUER_ACTUAL"
            action=("Controllare la pagina issuer e acquisire soltanto il "
                    "valore/periodo certificati dal parser già approvato.")
        elif not future:
            state="RELEASE_DAY_UNTIMED_STATUS_UNKNOWN"
            action="Orario incerto; nessuna pre-release evidenza certificata."
        elif frozen_row is not None:
            state="FROZEN_BEFORE_FUTURE_RELEASE"
            action=("Attendere il rilascio e la fonte issuer per l'actual; "
                    "il consenso congelato non costituisce una sorpresa.")
        else:
            status=candidate_ready(e,candidate,now_utc)
            if status=="CANDIDATE_AVAILABLE_NOT_YET_FROZEN":
                state="READY_TO_FREEZE_FUTURE_CONSENSUS"
                action=("Eseguire il freeze esistente prima dell'orario ufficiale; "
                        "verificare l'unità economica esatta.")
            elif status=="NO_MATCHED_PROVIDER_CANDIDATE":
                state="UPCOMING_NO_VERIFIED_EXACT_CONSENSUS"
                action=("Non attribuire il forecast di una sottoserie al titolo "
                        "generico dell'evento. Cercare un consenso esatto per "
                        "metrica/frequenza e congelarlo prima del rilascio.")
            else:
                state=status
                action=("Correggere la corrispondenza della metrica e del consenso "
                        "secondario prima della pubblicazione; mai retrodatare.")
        if future and clock is not None and not parser:
            action+=(" Parser actual ufficiale per questa serie NON "
                     "ancora validato: occorre implementarlo e testarlo.")
        surprise=(round(actual_row["actual_minus_frozen_consensus_pp"],6)
                  if actual_row is not None else None)
        rows.append({
            "event_key":key,"ccy":e["ccy"],"event_type":e["event_type"],
            "title":e["title"],"reference_period":e["reference_period"],
            "issuer_family":e["source_family"],"issuer_date":e["date"],
            "issuer_time_local":e.get("time_local"),"issuer_timezone":e.get("timezone"),
            "scheduled_release_utc":clock.isoformat().replace("+00:00","Z") if clock else None,
            "days_until_calendar_event":(release_day-today).days,
            "upcoming_within_35_days":near and future,
            "status":state,"next_action_it":action,
            "provider_candidate_status":candidate_ready(e,candidate,now_utc),
            "frozen_consensus_pct":frozen_row["consensus_value_percent"] if frozen_row else None,
            "frozen_captured_at_utc":frozen_row["captured_at_utc"] if frozen_row else None,
            "issuer_actual_pct":actual_row["actual_percent"] if actual_row else None,
            "actual_source_url":actual_row["source_url"] if actual_row else None,
            "issuer_actual_first_seen_at_utc":actual_row["captured_at_utc"] if actual_row else None,
            "actual_metric_unit":actual_row["unit"] if actual_row else None,
            "actual_minus_frozen_consensus_pp":surprise,
            "official_issuer_parser_supported":parser,
            "has_frozen_market_anchor":anchor_row is not None,
            "release_intraday_market_response_verified":False,
            "policy_repricing_verified":False,
            "source_is_first_release_pit_certified":False,
            "fx_signals":0,
            "affected_pair_references":affected,
            "currency_pair_count":len(affected),
        })
    near=[r for r in rows if r["upcoming_within_35_days"]]
    known_all=[r for r in rows if r["scheduled_release_utc"] is not None]
    future={c for c in ORDER if any(r["ccy"]==c for r in near)}
    counts=dict(Counter(r["status"] for r in rows))
    complete=sum(x["actual_minus_frozen_consensus_pp"] is not None for x in rows)
    return {
        "schema":SCHEMA,"run_at_rome":local.isoformat(),
        "calendar_seed_as_of":seed["as_of"],
        "secondary_consensus_generated_at_utc":con.get("generated_at_utc"),
        "source_paths":PATHS,"source_sha256":hashes,
        "coverage":{
            "currencies_in_historical_calendar":8,
            "currencies_with_upcoming_35d":len(future),
            "countries_without_upcoming_35d":sorted(set(ORDER)-future),
            "issuer_calendar_events":len(rows),
            "events_with_verified_scheduled_clock":len(known_all),
            "upcoming_35d":len(near),
            "upcoming_35d_with_frozen_consensus":sum(
                r["frozen_consensus_pct"] is not None for r in near),
            "upcoming_35d_with_approved_actual_parser":sum(
                r["official_issuer_parser_supported"] for r in near),
            "events_with_genuine_frozen_consensus_and_issuer_actual":complete,
            "unverified_intraday_event_reactions":len(rows),
            "new_trading_signals":0,
            "status_counts":counts,
        },
        "priority_queue":sorted(near,key=lambda r:(
            r["scheduled_release_utc"] is None,r["issuer_date"],r["ccy"])),
        "events":rows,
        "ready_for_live_28_pair_signals":False,
        "ready_for_automatic_market_attribution":False,
        "ready_for_historical_PIT_backtest":False,
        "writes_market_model":False,
        "reuses_existing_calendar_news_schedule":True,
        "new_cron_added":False,
        "limits":[
            "Official seed calendar includes all eight G8 historically but NOT full 35-day future G8 coverage.",
            "Only exact frozen pre-release forecasts can become surprises.",
            "The provider's latest forecast is NOT a frozen forecast.",
            "Missing official scheduled local time blocks valid timestamp freeze.",
            "Missing or unsupported issuer actual parser is not a numeric zero.",
            "No post-event market-causality claim from daily ECB fixes or sovereign 2Y levels.",
            "The source of actuals is runner first-seen, not verified first public release.",
        ],
    }

def markdown(book):
    c=book["coverage"]
    lines=[
        "# G8 · Monitor preparazione sorprese macro — V7",
        f"**Verifica:** {book['run_at_rome']} · **Calendario seed:** {book['calendar_seed_as_of']}",
        "",
        f"Eventi calendario {c['issuer_calendar_events']}; prossimi 35 giorni "
        f"{c['upcoming_35d']}; consensi già congelati per questi eventi "
        f"{c['upcoming_35d_with_frozen_consensus']}; parser official actual "
        f"già validati {c['upcoming_35d_with_approved_actual_parser']}. "
        f"Sorprese storiche verificate {c['events_with_genuine_frozen_consensus_and_issuer_actual']}.",
        "",
        "Il calendario copre 8 valute storicamente, NON tutte le otto per "
        "i prossimi 35 giorni. Nessun evento è trattato come trade FX.","",
        "## Eventi da preparare", "",
    ]
    if not book["priority_queue"]:
        lines.append("Nessun evento futuro nel seed selezionato: aggiornare il calendario ufficiale.")
    for e in book["priority_queue"]:
        stamp=e["scheduled_release_utc"] or "ORARIO UFFICIALE MANCANTE"
        lines+=[
          f"### {e['ccy']} · {e['issuer_date']} — {e['title']}",
          f"**Stato:** {e['status']} · {stamp}",
          f"**Cosa manca:** {e['next_action_it']}", "",
        ]
    lines+=["## Sorprese archiviate e non ricostruite", ""]
    for e in book["events"]:
        if e["actual_minus_frozen_consensus_pp"] is not None:
            lines.append(
              f"- {e['ccy']} {e['issuer_date']} {e['title']}: "
              f"consenso {e['frozen_consensus_pct']:+.2f}% → "
              f"actual {e['issuer_actual_pct']:+.2f}% → "
              f"sorpresa {e['actual_minus_frozen_consensus_pp']:+.2f} pp. "
              "Nessun impatto causale sui prezzi dimostrato."
            )
    lines+=["","**Governance:** dati assenti = null, non zero; niente "
            "retrodatazione, nuove schedulazioni, modifiche D/28pair, "
            "né pubblicazione automatica sul sito."]
    return "\n".join(lines)+"\n"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--json-out",type=Path)
    ap.add_argument("--md-out",type=Path)
    ap.add_argument("--github-summary",type=Path)
    a=ap.parse_args()
    result=build(now=datetime.now(timezone.utc))
    for output,content in (
        (a.json_out,json.dumps(result,ensure_ascii=False,indent=2)+"\n"),
        (a.md_out,markdown(result)),
    ):
        if output:
            require(output.resolve().is_relative_to(Path("/tmp")),
                    "all research outputs must stay in /tmp")
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(content,encoding="utf-8")
    if a.github_summary:
        # GITHUB_STEP_SUMMARY is passed as an explicit file location only
        # by the existing Calendar/News refresh runner.
        require(a.github_summary.is_absolute() and
                "step_summary" in a.github_summary.name.lower(),
                "github summary target must be a runner step_summary file")
        with a.github_summary.open("a",encoding="utf-8") as f:
            f.write("### G8 Macro Event Lifecycle V7 — evidence gaps (no signals)\n")
            r=result["coverage"]
            f.write(
              f"- Scheduled seed events: {r['issuer_calendar_events']}; "
              f"next 35d: {r['upcoming_35d']}; "
              f"frozen forecast next 35d: "
              f"{r['upcoming_35d_with_frozen_consensus']}; "
              f"next 35d approved issuer parsers: "
              f"{r['upcoming_35d_with_approved_actual_parser']}.\n"
            )
            for event in result["priority_queue"][:6]:
                f.write(f"- {event['issuer_date']} {event['ccy']} "
                        f"{event['event_type']}: **{event['status']}**. "
                        "No unverified actual or pricing assumed.\n")
    print(json.dumps({
        "status":SCHEMA,
        "coverage":result["coverage"],
        "upcoming":[{"ccy":e["ccy"],"date":e["issuer_date"],
                     "state":e["status"]} for e in result["priority_queue"]],
        "policy_signals":0,
    },ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
