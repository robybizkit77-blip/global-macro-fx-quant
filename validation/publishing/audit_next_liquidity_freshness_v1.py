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
    # Compare the native date against the research history, not against a
    # different/latest quarter. Matching values alone never certify the mapping.
    overlap = [(d, v) for d, v in zip(other.get("dates", []), other.get("values", []))
               if observed_date(d) == observed_date(base.get("last_date"))] if other else []
    matched = len(overlap) == 1 and type(overlap[0][1]) in (int, float) and values_numeric
    overlap_value = overlap[0][1] if matched else None
    return {
        "same_period": same_period,
        "native_period_overlap_found": matched,
        "native_period_overlap_value": overlap_value,
        "native_period_overlap_agrees": bool(matched and abs(overlap_value-base["last_value"]) <= 0.000001),
        "same_series_id_proven": False,
        "different_labeled_values": bool(mismatch),
        "runtime_value": base.get("last_value") if mismatch else None,
        "research_value": other.get("last_value") if mismatch else None,
        "runtime_date": base.get("last_date"),
        "research_date": other.get("last_date") if other else None,
        "resolution": "WITHHELD_PENDING_EXACT_VARIANT",
    }

def separate_source_inventory(root, today, runtime):
    """Inventory research inputs separately from native series, not scheduled or HTTP certification."""
    base = root / "site/fx-quant-v2/next"
    def sidecar(name):
        text = (base / name).read_text(encoding="utf-8")
        prefix = "const data=" if "const data=" in text else "window.FXQuantNZDRBNZLiquidity = "
        return json.JSONDecoder().raw_decode(text.split(prefix, 1)[1].lstrip())[0]
    us=sidecar("us-h8-bank-credit-research-v1.js")
    eu=sidecar("eur-ecb-nfc-credit-research-v1.js")
    gb=sidecar("gbp-boe-reserves-research-v1.js")
    gc=sidecar("gbp-boe-secured-credit-research-v1.js")
    jp=sidecar("jpy-boj-bank-credit-research-v1.js")
    ca=sidecar("cad-official-credit-research-v1.js")
    au=sidecar("aud-rba-business-credit-growth-research-v1.js")
    ab=sidecar("aud-rba-es-balances-research-v1.js")
    nz=sidecar("nzd-rbnz-liquidity-research-v1.js")
    residual=json.loads((root/"live_data/sections/ESTIMATED_RESIDUAL_GAPS.json").read_text())["lanes"]
    records=[]
    def add(ccy,role,period,source,frequency,kind,expected=True):
        end=observed_date(period)
        age=(today-end).days if end else None
        status=("MISSING_OR_UNVERIFIED" if not expected or age is None or age<0 else "OBSERVED")
        records.append(dict(ccy=ccy,role=role,period=period,source=source,
                            frequency=frequency,kind=kind,observation_age_days=age,
                            status=status,scheduled_execution_certified=False))
    def series(ccy,role,x,expected_id,frequency,kind="OFFICIAL_RESEARCH",period_key="latest_observation"):
        add(ccy,role,x.get(period_key),expected_id,frequency,kind,
            x.get("series_id")==expected_id and x.get("frequency")==frequency
            and x.get("eligible_for_fx_core") is False)
    def proxy(ccy,role,key,source):
        x=residual.get(key,{})
        add(ccy,role,x.get("proxy_as_of"),source,"M","OFFICIAL_DIMENSIONAL_PROXY",
            x.get("official_canonical_untouched") is True and x.get("proxy_value") is not None)
    series("USD","liquidity",us.get("money_stock",{}),"M2SL","M")
    series("USD","credit",us,"TOTBKCR","W")
    sl=us.get("lending_standards",{})
    sl_date=(sl.get("observations") or [[None]])[-1][0]
    add("USD","conditions",sl_date,"DRTSCILM","Q","OFFICIAL_SURVEY",sl.get("series_id")=="DRTSCILM")
    series("EUR","liquidity",eu.get("excess_liquidity",{}),"ILM.D.U2.C.EXLIQ.U2.EUR","D")
    series("EUR","credit",eu,"BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E","M")
    bls=eu.get("lending_conditions",{})
    if bls.get("positive_means")=="tightening" and bls.get("reference_period_is_previous_quarter") is True:
        series("EUR","conditions",bls,"BLS.Q.U2.ALL.O.E.Z.B3.ST.S.WFNET","Q","OFFICIAL_SURVEY")
    else:
        add("EUR","conditions",runtime["EUR"].get("conditions",{}).get("last_date"),"Native BLS (reference period not aligned)","Q","NATIVE_VARIANT_UNVERIFIED",False)
    series("GBP","liquidity",gb,"RPWB56A","W",period_key="source_period")
    series("GBP","credit",gc,"LPMVTYI","M",period_key="last_observation")
    series("GBP","conditions",gc.get("lending_conditions",{}),"BOE_CCS_CORPORATE_AVAILABILITY_ACTUAL","Q","OFFICIAL_SURVEY")
    proxy("JPY","liquidity","JPY.reserve_balances","BoJ monetary base end-month reserves")
    series("JPY","credit",jp,"DLCLAEDBLTTO","M",period_key="last_observation")
    tk=jp.get("tankan",{})
    add("JPY","conditions",tk.get("latest_observation"),"BoJ Tankan","Q","OFFICIAL_SURVEY",tk.get("scope")=="all enterprises, all industries" and tk.get("positive_lending_means")=="accommodative")
    proxy("CHF","liquidity","CHF.sight_deposits","SNB sight deposits")
    proxy("CHF","credit","CHF.credit","SNB foreign credit limits (not drawn loans)")
    series("CHF","conditions",residual.get("CHF.credit",{}).get("lending_rate_proxy",{}),"EPB@SNB.zikredlauf{FI,L16M,MP0}","M","OFFICIAL_COST_PROXY")
    series("CAD","liquidity",ca.get("settlement_balances",{}),"BOC_LYNX_ACTUAL_DAILY","D")
    series("CAD","credit",ca,"V122667770","M")
    series("CAD","conditions",ca.get("lending_conditions",{}),"SLOS_BUS_LEND","Q","OFFICIAL_SURVEY")
    add("AUD","liquidity",ab.get("source_period"),"RBA weekly ES balances","W","OFFICIAL_RESEARCH",ab.get("schema")=="GMFQ_NEXT_AUD_RBA_ES_BALANCES_V1")
    add("AUD","credit",au.get("observation_period"),"RBA adjusted business credit growth","M","OFFICIAL_RESEARCH",au.get("breaks_adjusted") is True and au.get("is_credit_stock") is False)
    series("AUD","conditions",au.get("lending_rate_proxy",{}),"RBA_F7_BUSINESS_LENDING_RATES_SUMMARY","M","OFFICIAL_COST_PROXY")
    for role,key,src in (("liquidity","liquidity","RBNZ D10"),("credit","credit","RBNZ C50")):
        add("NZD",role,nz.get("period"),src,"M","OFFICIAL_RESEARCH",nz.get("history",{}).get(nz.get("period"),{}).get(key,0)>0)
    series("NZD","conditions",nz.get("credit_conditions",{}),"RBNZ_C60_ACTUAL_CREDIT_AVAILABILITY","H","OFFICIAL_SURVEY")
    assert len(records)==24 and len({(x["ccy"],x["role"]) for x in records})==24
    return {"records":records,"observed_separate_sources":sum(x["status"]=="OBSERVED" for x in records),
            "native_variant_gaps":sum(x["kind"]=="NATIVE_VARIANT_UNVERIFIED" for x in records),
            "scope":"OBSERVATION_INVENTORY_NOT_LIVE_OR_SCHEDULE_CERTIFICATION"}


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
    assert conflict["native_period_overlap_found"], (
        "SLOOS native observation cannot be reconciled with the research history"
    )
    assert conflict["same_series_id_proven"] is False and conflict["resolution"] == "WITHHELD_PENDING_EXACT_VARIANT"
    assert source_registry.get("USD.conditions", {}).get("automation_ready") is not True or conflict["same_series_id_proven"] is False
    assert "VARIANT_NOT_ALIGNED" in (
        root / GATE.relative_to(ROOT)).read_text(encoding="utf-8"), "SLOOS quarantine missing"
    cad = [x for x in research["CAD"] if x.get("id") == "CA_BUSINESS_LOANS_OUTSTANDING_history_value"]
    assert len(cad) == 1, "Canadian macro identity must remain unique"
    cad_mapping=source_registry.get("CAD.credit", {})
    cad_ready=cad_mapping.get("automation_ready") is True
    native_cad=runtime["CAD"].get("credit")
    if cad_ready:
        assert cad_mapping.get("series_key")=="V122667770"
        assert cad_mapping.get("macro_series_id")==cad[0]["id"]
        assert cad[0]["current_vintage_provenance"]["source_series_id"]=="V122667770"
        assert cad[0]["current_vintage_provenance"]["source_series_first_release_PIT_certified"] is False
        assert cad[0]["unit"]=="CAD millions" and cad[0]["frequency"]=="M"
        assert native_cad and len(native_cad["dates"])>=24
        assert all(native_cad[k]==cad[0][k] for k in ("dates","values","last_date","last_value"))
    else:
        assert native_cad is None, "unapproved Canadian credit must remain absent"
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
        "cad_research_candidate_not_promoted": not cad_ready,
        "research_source_cannot_override_canonical": True,
        "records": items,
        "separate_source_inventory": separate_source_inventory(root,today,runtime),
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
        "- **USD SLOOS:** la mappatura del feed storico resta sospesa in attesa di certificazione della variante; l’accordo sul periodo comune non certifica da solo la fonte. La scheda USD mostra separatamente DRTSCILM quando verificata.",
        ("- **CAD credito:** candidata nel dataset di ricerca; non promossa al feed operativo." if report["cad_research_candidate_not_promoted"] else "- **CAD credito:** identità V122667770 e parità archivio nativo/macro verificate; continuità non certificata."),
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
    inv=report["separate_source_inventory"]
    lines += ["", "## Fonti separate effettivamente presenti nel codice Next",
              f"**Canali osservati:** {inv['observed_separate_sources']}/24. Non certifica nuova release, esecuzione programmata o consegna HTTP.", ""]
    for c in CCY:
        rows=[x for x in inv["records"] if x["ccy"]==c]
        lines.append(f"- **{c}:** "+" · ".join(f"{x['role']} {x['period'] or 'ASSENTE'} [{x['kind']}; {x['status']}; {x['source']}]" for x in rows))
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
    sample_runtime={"USD":{"conditions":{"last_date":"2026-07-01","last_value":0}}}
    sample_research={"USD":[{"id":"US_SLOOS_CI_LARGE_MIDDLE_history_value",
        "last_date":"2026-10-01","last_value":1.7,"dates":["2026-07-01","2026-10-01"],"values":[0,1.7]}]}
    comparison=compare_labeled_sloos(sample_runtime,sample_research)
    assert comparison["native_period_overlap_agrees"] and not comparison["same_period"]
    assert comparison["resolution"]=="WITHHELD_PENDING_EXACT_VARIANT"
    sample_research["USD"][0]["values"][0]=2
    assert not compare_labeled_sloos(sample_runtime,sample_research)["native_period_overlap_agrees"]
    assert compare_labeled_sloos(sample_runtime,sample_research)["resolution"]=="WITHHELD_PENDING_EXACT_VARIANT"
    data = audit(today=date(2026, 11, 24))
    assert data["channels"] == 24 and data["missing_series"] == sum(x["freshness"]=="MISSING_SERIES" for x in data["records"])
    assert data["sloos_variant"]["resolution"] == "WITHHELD_PENDING_EXACT_VARIANT"
    cad_record=next(x for x in data["records"] if x["ccy"]=="CAD" and x["role"]=="credit")
    assert data["cad_research_candidate_not_promoted"] == (not cad_record["source_mapping_ready_at_registry_snapshot"])
    assert data["not_fx_signal_or_new_source_fetch"]
    inventory=data["separate_source_inventory"]
    assert len(inventory["records"])==24
    assert not any(x["scheduled_execution_certified"] for x in inventory["records"])
    eur=next(x for x in inventory["records"] if x["ccy"]=="EUR" and x["role"]=="conditions")
    assert (eur["status"],eur["kind"]) in (("MISSING_OR_UNVERIFIED","NATIVE_VARIANT_UNVERIFIED"),("OBSERVED","OFFICIAL_SURVEY"))
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
