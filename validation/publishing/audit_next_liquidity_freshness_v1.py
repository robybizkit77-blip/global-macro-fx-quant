#!/usr/bin/env python3
"""Read-only, source-first G8 liquidity/credit freshness audit for FX Quant Next.

A source contract is not proof of a successful scheduled acquisition.
Observations are economic periods, not verified first-publication timestamps.
The separate Credit Transmission V4 research is NOT promoted to the site.
"""
from __future__ import annotations
import argparse
import calendar
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "live_data/sections/NATIVE_LIQ_DATA.json"
RESEARCH = ROOT / "live_data/sections/MACRO_SERIES.json"
POLICY = ROOT / "validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json"
CCY = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
ROLES = ("liquidity", "credit", "conditions")
GATE = ROOT / "site/fx-quant-v2/next/liquidity-source-policy-gate-v1.js"

def observed_date(raw):
    if not raw:
        return None
    s = str(raw).strip()
    try:
        if len(s) == 7 and s[4:6] == "-Q":
            y, q = int(s[:4]), int(s[-1])
            m = q * 3
            return date(y, m, calendar.monthrange(y, m)[1])
        if len(s) == 7 and s[4] == "-":
            y, m = map(int, s.split("-"))
            return date(y, m, calendar.monthrange(y, m)[1])
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return date.fromisoformat(s[:10])
        for fmt in ("%d %b %Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
    except (ValueError, OverflowError):
        return None
    return None

def threshold(mapping):
    freq = str((mapping or {}).get("frequency", "")).upper()
    if "QUART" in freq:
        return 135
    if "MONTH" in freq:
        return 75
    if "WEEK" in freq:
        return 21
    if "DAILY" in freq:
        return 8
    return 75  # conservative when cadence is not mapped

def compare_labeled_sloos(runtime, research):
    base = (runtime.get("USD") or {}).get("conditions") or {}
    candidates = [x for x in research.get("USD", [])
                  if x.get("id") == "US_SLOOS_CI_LARGE_MIDDLE_history_value"]
    other = candidates[0] if len(candidates) == 1 else None
    same_period = bool(other and observed_date(base.get("last_date"))
                       and observed_date(base.get("last_date")) == observed_date(other.get("last_date")))
    values_numeric = (type(base.get("last_value")) in (int, float) and
                      other is not None and type(other.get("last_value")) in (int, float))
    mismatch = same_period and values_numeric and abs(base["last_value"] - other["last_value"]) > 0.000001
    return {
        "same_period": same_period,
        "same_series_id_proven": False,
        "different_labeled_values": bool(mismatch),
        "runtime_value": base.get("last_value") if mismatch else None,
        "research_value": other.get("last_value") if mismatch else None,
        "runtime_date": base.get("last_date"),
        "research_date": other.get("last_date") if other else None,
        "resolution": "WITHHELD_PENDING_EXACT_VARIANT" if mismatch else "NO_OBSERVED_LABEL_CONFLICT",
    }

def audit(*, today=None, root=ROOT):
    today = today or datetime.now(ZoneInfo("Europe/Rome")).date()
    policy = json.loads((root / POLICY.relative_to(ROOT)).read_text(encoding="utf-8"))
    runtime = json.loads((root / RUNTIME.relative_to(ROOT)).read_text(encoding="utf-8"))
    research = json.loads((root / RESEARCH.relative_to(ROOT)).read_text(encoding="utf-8"))
    assert set(runtime) == set(CCY), "Unexpected canonical liquidity country map"
    assert set(research) == set(CCY), "Unexpected G8 research country map"
    assert policy["policy"].get("fail_closed") is True, "Source policy no longer fail-closed"
    assert policy["policy"].get("no_proxy_substitution") is True, "Proxy substitution forbidden"
    source_registry = policy.get("mapped", {})
    items = []
    for currency in CCY:
        for role in ROLES:
            row = runtime[currency].get(role) or {}
            mapped = source_registry.get(f"{currency}.{role}")
            end = observed_date(row.get("last_date"))
            age = (today - end).days if end else None
            available = (bool(row.get("label")) and end is not None and
                         type(row.get("last_value")) in (int, float))
            freshness = (
                "MISSING_SERIES" if not available else
                "FUTURE_PERIOD_WITHHELD" if age < 0 else
                "HISTORICAL_NOT_CURRENT" if age > threshold(mapped) else
                "DATED_PERIOD_RELEASE_UNVERIFIED"
            )
            items.append({
                "ccy": currency, "role": role,
                "label": row.get("label"), "period": row.get("last_date"),
                "period_age_days": age, "freshness": freshness,
                "source_registered": mapped is not None,
                "source_mapping_ready_at_registry_snapshot": bool(mapped and mapped.get("automation_ready") is True),
                "registry_status": mapped.get("status") if mapped else "NO_APPROVED_MAPPING",
                "release_timestamp_verified": False,
                "eligible_to_claim_current_fx_transmission": False
            })
    conflict = compare_labeled_sloos(runtime, research)
    assert conflict["different_labeled_values"], (
        "SLOOS label-period discrepancy changed: review sources/variant before clearing quarantine"
    )
    assert "VARIANT_NOT_ALIGNED" in (
        root / GATE.relative_to(ROOT)).read_text(encoding="utf-8"), "SLOOS quarantine missing"
    cad = [x for x in research["CAD"] if x.get("id") == "CA_BUSINESS_LOANS_OUTSTANDING_history_value"]
    assert len(cad) == 1 and not runtime["CAD"].get("credit"), (
        "CAD research-only credit/canonical gap changed: review promotion before claiming source certification"
    )
    count = lambda key, expected: sum(i.get(key) == expected for i in items)
    return {
        "schema": "GMFQ_NEXT_LIQUIDITY_FRESHNESS_AUDIT_V1",
        "audit_date_rome": today.isoformat(),
        "registry_as_of": policy.get("as_of"),
        "source_period_is_not_release_date": True,
        "not_fx_signal_or_new_source_fetch": True,
        "canonical_runtime_modified": False,
        "channels": len(items),
        "historical_periods": count("freshness", "HISTORICAL_NOT_CURRENT"),
        "missing_series": count("freshness", "MISSING_SERIES"),
        "not_source_mapping_ready": sum(not x["source_mapping_ready_at_registry_snapshot"] for x in items),
        "sloos_variant": conflict,
        "cad_research_candidate_not_promoted": True,
        "research_source_cannot_override_canonical": True,
        "records": items,
        "status": "SOURCE_GAPS_EXPLICIT_NOT_LIVE_CERTIFIED",
    }

def markdown(report):
    lines = [
        "# FX Quant Next — Liquidità & Credito · audit fonti G8",
        f"**Data audit Europe/Rome:** {report['audit_date_rome']} · **Registro:** {report['registry_as_of']}",
        "",
        "La data dell'osservazione non certifica la data di rilascio. Questo audit NON acquisisce nuove osservazioni e NON modifica il motore FX.",
        "",
        f"**Canali:** {report['channels']} · storici: {report['historical_periods']} · assenti: {report['missing_series']} · mappatura/automazione non pronta nello snapshot: {report['not_source_mapping_ready']}",
        "",
        "## Criticità da risolvere",
        "- **USD SLOOS:** divergenza tra valori con la stessa etichetta/periodo; variante esatta non accertata. Dato sospeso nella pagina Next.",
        "- **CAD credito:** presente solo una candidata nel dataset di ricerca; non promossa al feed operativo.",
        "- **Acquisizione:** una mappatura fonte pronta non dimostra aggiornamento eseguito; non presentare i feed come live.",
        "",
        "## G8 · ultimo periodo economico per canale",
    ]
    for c in CCY:
        rows = [x for x in report["records"] if x["ccy"] == c]
        compact = " · ".join(
            f"{x['role']} {x['period'] or 'ASSENTE'} ({x['freshness']}; mappatura {'ready' if x['source_mapping_ready_at_registry_snapshot'] else 'pending'})"
            for x in rows)
        lines.append(f"- **{c}:** {compact}")
    return "\n".join(lines) + "\n"

def selftest():
    assert observed_date("2026-08") == date(2026, 8, 31)
    assert observed_date("2026-Q3") == date(2026, 9, 30)
    assert observed_date("2026-09-21T00:00:00Z") == date(2026, 9, 21)
    assert observed_date("31 Jul 2026") == date(2026, 7, 31)
    assert observed_date("31/07/2026") == date(2026, 7, 31)
    assert observed_date("impossibile") is None
    assert threshold({"frequency": "QUARTERLY"}) == 135
    assert threshold({"frequency": "WEEKLY"}) == 21
    data = audit(today=date(2026, 11, 14))
    assert data["channels"] == 24 and data["missing_series"] >= 3
    assert data["sloos_variant"]["resolution"] == "WITHHELD_PENDING_EXACT_VARIANT"
    assert data["cad_research_candidate_not_promoted"]
    assert data["not_fx_signal_or_new_source_fetch"]
    print("NEXT_LIQUIDITY_FRESHNESS_AUDIT_SELFTEST_PASS")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--json-out", type=Path)
    p.add_argument("--md-out", type=Path)
    args = p.parse_args()
    if args.selftest:
        selftest()
        return
    receipt = audit()
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.md_out:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(markdown(receipt), encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k not in ("records", "sloos_variant")}, ensure_ascii=False))

if __name__ == "__main__":
    main()
