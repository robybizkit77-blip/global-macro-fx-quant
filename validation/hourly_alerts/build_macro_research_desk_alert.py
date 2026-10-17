#!/usr/bin/env python3
"""Turn a certified hourly receipt into a fail-closed Desk alert outbox.

This module never changes the canonical runtime.  A significant alert needs a
separately audited event record *and* a complete certified Macro -> OIS/2Y ->
FX audit.  In every other case it emits the exact requested fallback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

FALLBACK = "Controllo orario completato: nessuna novità significativa. Nessun setup chiaro."
CERTIFIED_OIS = frozenset(("GBP", "JPY", "CAD", "AUD"))


def utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def event_from_macro_snapshot(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Translate only a fully validated feed event; never infer its economics."""
    macro = snapshot.get("lanes", {}).get("macro", {})
    event = macro.get("event") if isinstance(macro, dict) else None
    if not isinstance(event, dict):
        return None
    source = event.get("source", {})
    if not isinstance(source, dict):
        return None
    actual, consensus, previous = event.get("actual"), event.get("consensus"), event.get("previous")
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (actual, consensus, previous)):
        return None
    indicator = event.get("indicator")
    if not isinstance(indicator, str) or not isinstance(event.get("period"), str):
        return None
    return {
        "event_id": event.get("event_id"), "ois_currency": event.get("currency"),
        "observed_at_utc": event.get("release_timestamp_utc"),
        "source": f"{source.get('authority')} — {source.get('release_url')}",
        "headline_it": f"{event.get('currency')} {indicator}, periodo {event.get('period')}: dato {actual}; consenso {consensus}; precedente {previous}.",
        "macro_assessment_it": "La sorpresa è descrittiva (dato contro consenso); revisioni e fonte ufficiale restano nel record certificato.",
        "market_pricing_it": "Nessuna deduzione automatica: la lettura del pricing richiede una reazione timestampata separata.",
        "risk_it": "Rischio: revisioni, qualità del consenso e conferma tassi/FX possono cambiare l'interpretazione.",
    }


def required_lane(snapshot: dict[str, Any], name: str) -> dict[str, Any] | None:
    value = snapshot.get("lanes", {}).get(name)
    return value if isinstance(value, dict) and value.get("alert_eligible") is True else None


def valid_event(event: dict[str, Any], generated: datetime, seen: set[str]) -> str | None:
    """Return a rejection reason, never infer missing event provenance."""
    required = ("event_id", "headline_it", "source", "observed_at_utc", "macro_assessment_it")
    if any(not isinstance(event.get(k), str) or not event[k].strip() for k in required):
        return "Evento privo di identificativo, fonte, timestamp o assessment macro verificabile."
    if event["event_id"] in seen:
        return "Evento già consegnato: nessuna notizia riciclata."
    observed = utc(event["observed_at_utc"])
    if observed is None or observed > generated or generated - observed > timedelta(hours=6):
        return "Evento fuori dalla finestra oraria verificabile."
    ccy = event.get("ois_currency")
    if ccy not in CERTIFIED_OIS:
        return "OIS non certificato per la valuta dell'evento."
    return None


def complete_audit(snapshot: dict[str, Any], event: dict[str, Any]) -> tuple[bool, str]:
    macro = required_lane(snapshot, "macro")
    fx = required_lane(snapshot, "fx")
    ois = snapshot.get("lanes", {}).get("ois", {}).get(event.get("ois_currency"))
    bond = snapshot.get("lanes", {}).get("g8_bonds", {}).get(event.get("ois_currency"))
    if not macro:
        return False, "Macro non certificata come trigger orario."
    if not isinstance(ois, dict) or ois.get("alert_eligible") is not True:
        return False, "OIS certificato non disponibile o stale."
    if not isinstance(bond, dict) or bond.get("alert_eligible") is not True:
        return False, "Osservazione governativa 2Y non certificata o stale."
    if not fx:
        return False, "FX non certificato o stale."
    return True, "Audit Macro → OIS/2Y → FX completo."


def significant_text(event: dict[str, Any], snapshot: dict[str, Any]) -> str:
    ccy = event["ois_currency"]
    lanes = snapshot["lanes"]
    ois, bond, fx = lanes["ois"][ccy], lanes["g8_bonds"][ccy], lanes["fx"]
    observed = event["observed_at_utc"]
    # Deliberately descriptive: no invented surprise, price move or trade level.
    return f"""Macro Research Desk Compatto — evento significativo

Evento e novità. {event['headline_it']} L'osservazione è datata {observed}. {event['macro_assessment_it']} Questa nota separa il dato osservato dall'interpretazione: non attribuisce causalità oltre le fonti sotto indicate e non tratta un dato periodico come aggiornamento intraday.

Audit macro → tassi → FX. Macro: {event['source']} (timestamp {observed}). OIS {ccy}: {ois['source']}; as-of {ois['as_of']}, età {ois['age_days']} giorni. Il solo OIS ammesso è quello certificato per {ccy}; nessuna proxy o stima è stata promossa. 2Y governativo {ccy}: {bond['source']}; as-of {bond['as_of']}, età {bond['age_days']} giorni. È un rendimento governativo e non viene mai presentato come OIS. FX G8: {fx['source']}; as-of {fx['as_of']}, età {fx['age_days']} giorni.

Cosa sta cambiando e cosa prezza il mercato. {event.get('market_pricing_it', 'Nessuna inferenza aggiuntiva sul pricing: serve un confronto timestampato con il dato precedente.')} Il passaggio OIS/2Y e la conferma FX sono riportati come audit di disponibilità e freschezza, non come prova automatica di una reazione post-evento.

Lettura operativa. Thesis Strength: {event.get('thesis_strength', 'NON VALUTATA')}. Trade Attractiveness: {event.get('trade_attractiveness', 'NON VALUTATA')}. {event.get('risk_it', 'Rischio: attendere conferma cross-asset e distinguere il segnale da positioning e liquidità.')} Nessun setup è proposto senza convergenza verificata; un conflitto tra Macro, OIS/2Y e FX prevale sulla narrativa.

Disciplina e invalidazione. La tesi deve essere rivalutata se un aggiornamento ufficiale corregge il dato, se l'OIS certificato o il 2Y si muovono in direzione opposta al razionale, oppure se il prezzo FX non conferma nella finestra definita dal desk. Positioning COT, credito, liquidità, curve lunghe e risk sentiment restano layer di conferma o divergenza, non vengono sintetizzati in un voto quando non sono freschi o certificati. Non sono indicati entry, stop o target: il messaggio è ricerca, non una raccomandazione esecutiva. Fonti e as-of sopra sono parte integrante dell'audit."""


def build(snapshot: dict[str, Any], event: dict[str, Any] | None, delivered: set[str]) -> dict[str, Any]:
    generated = utc(snapshot.get("generated_at_utc")) or datetime.now(timezone.utc)
    reason = "Nessun evento certificato fornito."
    if event:
        reason = valid_event(event, generated, delivered) or ""
        if not reason:
            ok, reason = complete_audit(snapshot, event)
            if ok:
                message = significant_text(event, snapshot)
                words = len(message.split())
                if not 250 <= words <= 350:
                    raise ValueError(f"Significant alert must be 250–350 words, got {words}.")
                fingerprint = hashlib.sha256(event["event_id"].encode()).hexdigest()
                return {"schema": "GMFQ_MACRO_RESEARCH_DESK_ALERT_V1", "kind": "SIGNIFICANT",
                        "message": message, "word_count": words, "event_id": event["event_id"],
                        "event_fingerprint": fingerprint, "generated_at_utc": generated.isoformat().replace("+00:00", "Z"),
                        "delivery": {"mode": "CHATGPT_PULL_ONLY", "status": "NOT_DELIVERED_BY_GITHUB"}}
    return {"schema": "GMFQ_MACRO_RESEARCH_DESK_ALERT_V1", "kind": "FALLBACK", "message": FALLBACK,
            "word_count": len(FALLBACK.split()), "withheld_reason": reason,
            "generated_at_utc": generated.isoformat().replace("+00:00", "Z"),
            "delivery": {"mode": "CHATGPT_PULL_ONLY", "status": "NOT_DELIVERED_BY_GITHUB"}}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--event-file", type=Path)
    p.add_argument("--use-certified-macro-event", action="store_true", help="Use the one validated event embedded in the receipt.")
    p.add_argument("--delivered-event-ids", type=Path)
    args = p.parse_args()
    seen = set(load(args.delivered_event_ids)) if args.delivered_event_ids and args.delivered_event_ids.exists() else set()
    snapshot = load(args.snapshot)
    event = load(args.event_file) if args.event_file else (event_from_macro_snapshot(snapshot) if args.use_certified_macro_event else None)
    alert = build(snapshot, event, seen)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(alert, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"kind": alert["kind"], "delivery": alert["delivery"], "reason": alert.get("withheld_reason")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
