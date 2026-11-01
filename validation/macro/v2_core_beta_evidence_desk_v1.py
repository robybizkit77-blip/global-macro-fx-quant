#!/usr/bin/env python3
"""Integrated read-only Macro V2 beta EVIDENCE desk, not a new FX Core.

One reproducible G8 + 28-pair review: own-history economic research,
last published central-bank communication, 6M pricing with source tiers,
dated government 2Y/10Y, and untouched legacy pair context.

It never creates country FX-strength scores or replaces D.json.
No comparison of domestic z-scores across countries is warranted.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import itertools
import json
import math
from datetime import date
from pathlib import Path

from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    G8, run as domestic_run
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "live_data/sections"
SCHEMA = "GMFQ_MACRO_V2_G8_28PAIR_BETA_EVIDENCE_DESK_V1"
RESEARCH_DAY = "2026-10-28"
FRESH_RATE_DAYS = 7

def ensure(ok, why):
    if not ok:
        raise ValueError("CORE_BETA_EVIDENCE_DESK_REJECTED: " + why)

def strict_date(value, label, as_of):
    ensure(isinstance(value, str) and len(value) == 10,
           label + " missing YYYY-MM-DD")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(label + " invalid civil date") from exc
    ensure(d.isoformat() == value and d <= as_of,
           label + " forward or noncanonical date")
    return d

def finite(v):
    return type(v) in (float, int) and math.isfinite(v)

def read(name):
    return json.loads((DATA / (name + ".json")).read_text(encoding="utf-8"))

def build(candidate, legacy, pairs, banks, ois, rates, *, as_of=RESEARCH_DAY):
    day = date.fromisoformat(as_of)
    ensure(day.isoformat() == as_of, "canonical as-of")
    ensure(candidate["schema"] == "GMFQ_MACRO_V2_EXPLICIT_DOMESTIC_CANDIDATE_V1"
           and candidate["safe_to_publish_D"] is False
           and candidate["safe_to_update_pair_theses"] is False
           and candidate["safe_to_use_for_beta"] is False
           and candidate["safe_to_use_for_forward"] is False
           and candidate["summary"]["currencies"] == 8
           and candidate["summary"]["axes"] == 24
           and candidate["summary"]["FX_scores_produced"] == 0,
           "candidate is not verified as nontrading research")
    ensure(set(candidate["countries"]) == set(G8)
           and set(banks) == set(G8) and set(rates) == set(G8)
           and set(ois.get("currencies", {})) == set(G8),
           "eight complete input source currencies")
    core_day = strict_date(legacy.get("asOf"), "legacy baseline", day)
    ensure(candidate["legacy_core_as_of"] == core_day.isoformat(),
           "candidate and legacy macro baseline mismatch")
    ensure(pairs.get("schema") == "GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1"
           and pairs.get("pair_count") == 28
           and pairs.get("macro_baseline_asof") == core_day.isoformat()
           and pairs.get("price_audit", {}).get("status") == "PASS"
           and pairs["price_audit"].get("as_of") == pairs.get("price_asof"),
           "pair source and official price audit baseline must be pinned")
    pday = strict_date(pairs["price_asof"], "pair price as-of", day)
    ensure(pday >= core_day, "pair overlay earlier than model baseline")
    ensure(ois.get("schema") == "GMFQ_OIS_OPERATIONAL_VIEW_V1",
           "known OIS display contract")
    unique = {frozenset((a, b)) for a, b in itertools.combinations(G8, 2)}
    ensure(len(pairs.get("pairs", {})) == 28, "28 original pair contexts")
    universe = {}
    for key, item in pairs["pairs"].items():
        label = item.get("canonical_pair")
        ensure(isinstance(label, str) and len(label) == 7
               and label[3] == "/" and label.replace("/", "") == key,
               "unrecognized canonical pair label")
        a, b = label.split("/")
        ensure(frozenset((a, b)) in unique
               and frozenset((a, b)) not in universe
               and item.get("setup", {}).get("pair") == label,
               "duplicate or invalid legacy pair")
        universe[frozenset((a, b))] = key
    ensure(set(universe) == unique, "complete 28-pair universe required")
    country = {}
    for ccy in G8:
        row = candidate["countries"][ccy]
        cb = banks[ccy]
        rate = rates[ccy]
        curve = ois["currencies"][ccy]
        ensure(isinstance(cb.get("official_bias"), str)
               and cb.get("official_bias").strip(),
               ccy + " must have recorded CB communication context")
        cb_date = strict_date(cb.get("last_date"), ccy + " CB last statement", day)
        ry = strict_date(rate.get("date"), ccy + " bond yields", day)
        oy = strict_date(curve.get("as_of"), ccy + " OIS quote", day)
        ensure(str(rate.get("quality", "")).startswith("FULL_CURRENT_OFFICIAL")
               and finite(rate.get("2Y")) and finite(rate.get("10Y")),
               ccy + " only dated official observed government yields")
        policy_matched = (finite(curve.get("policy_rate"))
                          and finite(cb.get("rate"))
                          and abs(curve["policy_rate"] - cb["rate"]) < 1e-8)
        # A dated official policy decision can advance before the next market
        # close. Keep pre-decision quotes intact, with no fabricated delta
        # against the NEW policy rate. Same-day discrepancies still fail.
        predecision = not policy_matched and oy < cb_date
        ensure(policy_matched or predecision,
               ccy + " policy rate and market bridge disagree at same/newer quote date")
        six = curve.get("horizons", {}).get("6m", {})
        market = None
        market_class = None
        if curve.get("operational_status") == "GREEN_OFFICIAL":
            ensure(curve.get("quality") == "OFFICIAL_CERTIFIED"
                   and curve.get("official_status") == "ACTIVE"
                   and curve.get("backtest_eligible_as_official") is True
                   and finite(six.get("rate"))
                   and finite(six.get("policy_delta_bp")),
                   ccy + " claimed official 6M must be source-certified")
            market = six["rate"]
            market_class = ("PRE_DECISION_OFFICIAL_QUOTE_NO_CURRENT_POLICY_DELTA"
                            if predecision else "OFFICIAL_POLICY_PRICING")
        elif curve.get("operational_status") == "GREEN_ESTIMATED":
            ensure(curve.get("quality") == "ESTIMATED_INFORMATIONAL"
                   and curve.get("backtest_eligible_as_official") is False
                   and finite(six.get("rate")),
                   ccy + " B-grade 6M must remain indicative")
            if curve.get("input_mode") == "LIVE_SECONDARY_CONFLICT_INDICATIVE":
                # A same-contract/day dispute quarantines the source for
                # monetary-policy repricing, even when the specific 6M
                # contract was individually timestamp-verified (EUR).
                keys = curve.get("source_conflict_keys")
                ensure(ccy in ("USD", "EUR", "CHF")
                       and curve.get("method_id") == "TRADINGVIEW_DATED_FUTURES_SSR_V2"
                       and curve.get("source_quality") ==
                           "SECONDARY_CONFLICTED_INDICATIVE_NOT_OIS"
                       and curve.get("source_conflict_status") ==
                           "UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT"
                       and curve.get("conflicted_source_eligible_for_repricing") is False
                       and curve.get("direction_vs_policy") == "WITHHELD"
                       and curve.get("change_1d_available") is False
                       and curve.get("change_1w_available") is False
                       and six.get("policy_delta_bp") is None
                       and six.get("change_1d_bp") is None
                       and six.get("change_1w_bp") is None
                       and isinstance(keys, list) and 1 <= len(keys) <= 3,
                       ccy + " conflicted 6M must never claim policy pricing or repricing")
                seen = set()
                for item in keys:
                    ensure(isinstance(item, dict)
                           and item.get("horizon") in ("3m", "6m", "12m")
                           and item["horizon"] not in seen
                           and isinstance(item.get("event_id"), str)
                           and len(item["event_id"]) == 64
                           and all(ch in "0123456789abcdef" for ch in item["event_id"])
                           and item.get("contract") ==
                               curve.get("horizons", {}).get(item["horizon"], {}).get("contract")
                           and item.get("observation_date") ==
                               curve.get("horizons", {}).get(item["horizon"], {}).get("quote_as_of"),
                           ccy + " malformed historical futures dispute identity")
                    seen.add(item["horizon"])
                if "6m" in seen:
                    ensure(six.get("quote_timestamp_verified") is False
                           and six.get("quote_timestamp_source") ==
                              "QUARANTINED_SAME_CONTRACT_SAME_DAY",
                           ccy + " disputed 6M quote falsely verified")
                else:
                    ensure(six.get("quote_timestamp_verified") is True
                           and six.get("quote_timestamp_source") ==
                              "SSR_DAILY_BAR_DATA_UPDATE_TIME",
                           ccy + " uncontested 6M quote missing timestamp verification")
                # The finite price is only an explicitly DISPUTED futures
                # observation, never a 6M OIS level or a policy forecast.
                market = six["rate"]
                market_class = "CONFLICTED_FUTURES_6M_CONTEXT_ONLY_NO_POLICY_DELTA"
            else:
                ensure(curve.get("input_mode") == "LIVE_SECONDARY_OVERLAY"
                       and curve.get("source_conflict_status") is None
                       and curve.get("source_conflict_keys") is None
                       and six.get("policy_delta_bp") is None
                       and curve.get("policy_repricing_inference_allowed") is False
                       and curve.get("direction_vs_policy") == "WITHHELD"
                       and curve.get("change_1d_available") is False
                       and curve.get("change_1w_available") is False
                       and six.get("raw_level_gap_not_policy_repricing") is True
                       and six.get("quote_timestamp_verified") is True
                       and six.get("quote_timestamp_source") ==
                           "SSR_DAILY_BAR_DATA_UPDATE_TIME",
                       ccy + " non-conflicted B-grade 6M evidence not verified")
                market = six["rate"]
                market_class = "ESTIMATED_FUTURES_6M_CONTEXT_ONLY_NO_POLICY_DELTA"
        elif curve.get("operational_status") == "WITHHELD":
            ensure(curve.get("quality") == "ESTIMATED_INFORMATIONAL"
                   and curve.get("backtest_eligible_as_official") is False
                   and six.get("rate") is None and
                   six.get("policy_delta_bp") is None,
                   ccy + " WITHHELD is never an official policy delta")
            secondary = curve.get("secondary_quote_context", {})
            proxy = curve.get("market_direction_proxy", {})
            if secondary.get("status") == "INDICATIVE_OBSERVATIONS_NON_OIS":
                indicative = secondary.get("horizons", {}).get("6m", {})
                ensure(secondary.get("policy_delta_allowed") is False
                       and secondary.get("cross_date_join_allowed") is False,
                       "CHF-style cross-date indication must not be upgraded")
                if finite(indicative.get("rate_indicative")):
                    market = indicative["rate_indicative"]
                    market_class = "SECONDARY_NON_OIS_6M_CONTEXT_ONLY"
            elif proxy.get("status") == "LIVE_DIRECTIONAL_PROXY_READY":
                ensure(proxy.get("substitutes_for_ois_level") is False
                       and proxy.get("policy_delta_from_proxy_allowed") is False,
                       "NZD bank-bill credit/basis cannot replace OCR OIS")
                bank_bill = proxy.get("horizons", {}).get("6m", {})
                if finite(bank_bill.get("implied_bank_bill_rate")):
                    market = bank_bill["implied_bank_bill_rate"]
                    market_class = "BANK_BILL_BASIS_DIRECTIONAL_CONTEXT_ONLY"
            else:
                market_class = "NO_VERIFIED_6M_POLICY_PRICING"
        else:
            raise ValueError("unknown OIS operational tier for " + ccy)
        e = row["continuous_weight_sensitivity_RESEARCH_ONLY"]
        ensure(e["continuous_weight_math_is_NOT_PIT_or_FX_validation"] is True
               and row["FX_strength_candidate"] is None
               and row["eligible_to_recalculate_28_pairs"] is False,
               "country scenario attempted FX promotion")
        country[ccy] = {
            "currency": ccy,
            "domestic_class_central_50pct": row["domestic_activity_class"],
            "domestic_class_robust_25to75pct":
                e["weight_invariant_domestic_class_RESEARCH_ONLY"],
            "domestic_ambiguity_if_not_robust":
                not e["classification_unchanged_at_every_weight_in_interval"],
            "domestic_z_own_history_only": row["domestic_activity_candidate_z"],
            "domestic_inflation_context_own_history":
                row["domestic_inflation_pressure_class"],
            "macro_source_caveats": row["source_quality_flags"],
            "cb_communicated_bias_snapshot": cb["official_bias"],
            "cb_statement_date": cb_date.isoformat(),
            "cb_WANT_status": "RECORDED_COMMUNICATION_NOT_NEW_DECISION",
            "cb_CAN_status": "NOT_CALIBRATED_FROM_ECONOMIC_LEVELS",
            "six_month_rate_pct_descriptive_only": market,
            "six_month_source_class": market_class,
            "ois_prior_policy_rate_pct_if_pre_decision": curve["policy_rate"] if predecision else None,
            "official_current_cb_rate_pct": cb["rate"],
            "six_month_policy_delta_bp": six["policy_delta_bp"] if market_class in (
                "OFFICIAL_POLICY_PRICING",
                ) else None,
            "six_month_quote_date": oy.isoformat(),
            "six_month_quote_age_days": (day-oy).days,
            "two_year_yield_pct": rate["2Y"],
            "ten_year_yield_pct": rate["10Y"],
            "two_ten_curve_bp_derived": round((rate["10Y"]-rate["2Y"])*100, 2),
            "official_bond_date": ry.isoformat(),
            "bond_age_days": (day-ry).days,
            "bond_freshness": "OBSERVED_RECENT" if (day-ry).days <= FRESH_RATE_DAYS
                              else "HISTORICAL_NOT_CURRENT",
            "trade_signal": None,
            "FX_strength_score": None,
        }
    pitems = []
    for label, row in sorted(pairs["pairs"].items()):
        state = row["setup"]
        pitems.append({
            "pair": row["canonical_pair"],
            "legacy_model_baseline_as_of": core_day.isoformat(),
            "independently_dated_official_price_as_of": pday.isoformat(),
            "existing_legacy_setup_quality_NOT_recalculated": state["quality"],
            "existing_legacy_setup_quality_code": state["qualityCode"],
            "existing_legacy_price_state": state["price"]["state"],
            "economic_source_a": country[label[:3]]["domestic_class_robust_25to75pct"],
            "economic_source_b": country[label[3:]]["domestic_class_robust_25to75pct"],
            "economic_classes_NOT_cross_country_comparable": True,
            "fx_bias_from_beta_candidate": None,
            "trade_entry_from_beta_candidate": None
        })
    out = {
        "schema": SCHEMA, "status": "CONTROLLED_BETA_EVIDENCE_PREVIEW_NOT_LIVE_FX_MODEL",
        "as_of": as_of, "legacy_model_baseline_as_of": core_day.isoformat(),
        "official_price_overlay_as_of": pday.isoformat(),
        "countries": country, "pairs": pitems,
        "summary": {
            "country_count": len(country), "legacy_pair_count": len(pitems),
            "domestic_classes_robust": sum(not x["domestic_ambiguity_if_not_robust"]
                                            for x in country.values()),
            "official_policy_pricing": sum(x["six_month_source_class"] ==
                "OFFICIAL_POLICY_PRICING" for x in country.values()),
            "indicative_policy_pricing": sum(x["six_month_source_class"] ==
                "ESTIMATED_POLICY_PRICING_NOT_OFFICIAL" for x in country.values()),
            "context_only_non_policy_6m": sum(x["six_month_source_class"] in (
                "CONFLICTED_FUTURES_6M_CONTEXT_ONLY_NO_POLICY_DELTA",
                "SECONDARY_NON_OIS_6M_CONTEXT_ONLY",
                "BANK_BILL_BASIS_DIRECTIONAL_CONTEXT_ONLY",
                "ESTIMATED_FUTURES_6M_CONTEXT_ONLY_NO_POLICY_DELTA",
                "PRE_DECISION_OFFICIAL_QUOTE_NO_CURRENT_POLICY_DELTA",
                "PRE_DECISION_ESTIMATED_QUOTE_NO_CURRENT_POLICY_DELTA") for x in country.values()),
            "pre_decision_6m_quotes": sum(x["six_month_source_class"] in (
                "PRE_DECISION_OFFICIAL_QUOTE_NO_CURRENT_POLICY_DELTA",
                "PRE_DECISION_ESTIMATED_QUOTE_NO_CURRENT_POLICY_DELTA") for x in country.values()),
            "historical_bond_yields": sum(x["bond_freshness"] != "OBSERVED_RECENT"
                                           for x in country.values()),
            "new_country_FX_scores": 0, "new_pair_theses": 0,
        },
        "safe_to_republish_D": False,
        "safe_to_recalculate_pair_rankings": False,
        "eligible_for_beta_model_validation": False,
        "eligible_for_forward_trade_attribution": False,
        "forecast_or_entry_generated": False,
        "no_cross_country_z_score_rank_generated": True,
        "writes_live_data": False
    }
    out["receipt_sha256"] = hashlib.sha256(json.dumps(
        {k:v for k,v in out.items() if k != "receipt_sha256"},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return out

def render(out):
    ensure(out["schema"] == SCHEMA and out["safe_to_republish_D"] is False
           and out["summary"]["new_country_FX_scores"] == 0,
           "only read-only evidence allowed in browser export")
    h = html.escape
    labels = {
        "OFFICIAL_POLICY_PRICING": "6M ufficiale certificato",
        "PRE_DECISION_OFFICIAL_QUOTE_NO_CURRENT_POLICY_DELTA": "6M ufficiale ma PRE decisione · no Δ tasso attuale",
        "PRE_DECISION_ESTIMATED_QUOTE_NO_CURRENT_POLICY_DELTA": "6M stimato PRE decisione · no Δ tasso attuale",
        "ESTIMATED_FUTURES_6M_CONTEXT_ONLY_NO_POLICY_DELTA": "6M futures indicativo · non è repricing di banca centrale",
        "CONFLICTED_FUTURES_6M_CONTEXT_ONLY_NO_POLICY_DELTA": "Futures 6M contestato · nessun pricing tasso",
        "SECONDARY_NON_OIS_6M_CONTEXT_ONLY": "6M secondario non OIS",
        "BANK_BILL_BASIS_DIRECTIONAL_CONTEXT_ONLY": "Bank bill: solo contesto direzionale",
        "NO_VERIFIED_6M_POLICY_PRICING": "6M non verificato"
    }
    cards = []
    for c, r in out["countries"].items():
        robust = r["domestic_class_robust_25to75pct"] or "NON ROBUSTA AI PESI"
        val = r["six_month_rate_pct_descriptive_only"]
        stamp = ("%.4f%%" % val) if val is not None else "n.d."
        is_indicator = r["six_month_source_class"] != "OFFICIAL_POLICY_PRICING"
        age = r["bond_age_days"]
        caveats = ", ".join(r["macro_source_caveats"]) or "Nessuna segnalazione aggiuntiva"
        cards.append(f"""<article class="country">
          <h3>{h(c)}</h3>
          <p><b>Macro domestica 50/50</b> {h(r["domestic_class_central_50pct"])}</p>
          <p><b>Robustezza 25–75%</b> <span class="{"warn" if r["domestic_ambiguity_if_not_robust"] else "good"}">{h(robust)}</span></p>
          <p><b>Inflazione (asse separato)</b> {h(r["domestic_inflation_context_own_history"])}</p>
          <p><b>CB — Want comunicato</b> {h(r["cb_communicated_bias_snapshot"])} <small>({h(r["cb_statement_date"])})</small></p>
          <p><b>CB — Can</b> da validare, non dedotto dai livelli macro</p>
          <p><b>Pricing 6M</b> {h(stamp)} <span class="{"warn" if is_indicator else "good"}">{h(labels[r["six_month_source_class"]])}</span>
          <small>({h(r["six_month_quote_date"])})</small></p>
          <p><b>2Y / 10Y</b> {r["two_year_yield_pct"]:.3f}% / {r["ten_year_yield_pct"]:.3f}%
          <small>({h(r["official_bond_date"])}, {age} gg)</small>
          <span class="{"warn" if r["bond_freshness"] != "OBSERVED_RECENT" else "good"}">{h(r["bond_freshness"])}</span></p>
          <p class="foot">Qualità: {h(caveats)}. Nessun punteggio FX derivato.</p>
        </article>""")
    ptable = "".join(
        "<tr><td><b>" + h(x["pair"]) + "</b></td><td>" +
        h(x["existing_legacy_setup_quality_NOT_recalculated"]) + "</td><td>" +
        h(x["existing_legacy_price_state"]) + "</td><td>Solo contesto · nessun nuovo segnale</td></tr>"
        for x in out["pairs"]
    )
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Macro V2 · Beta Evidence Desk (ricerca)</title>
<style>
:root{{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#07121f;color:#e3edf7}}
*{{box-sizing:border-box}}body{{margin:0;padding:1rem;line-height:1.5}}
main{{max-width:1320px;margin:auto}}header{{padding:1.5rem;border:1px solid #345170;
background:linear-gradient(125deg,#122f50,#0a182a);border-radius:18px}}
h1{{font-size:clamp(1.6rem,3vw,2.5rem);margin:.2rem 0}}
h2{{margin-top:2rem}}.sub{{color:#a9c3d8}}.warning{{color:#ffd69a;font-weight:700}}
.stats{{display:flex;gap:.6rem;flex-wrap:wrap;margin:1rem 0}}
.stat{{background:#102235;padding:.65rem .9rem;border:1px solid #284664;border-radius:10px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,285px),1fr));gap:.8rem}}
.country{{background:#0c1b2c;border:1px solid #24435d;border-radius:14px;padding:1rem;min-width:0;overflow-wrap:anywhere}}
.country h3{{margin:.1rem 0 .7rem;font-size:1.3rem}}p{{margin:.55rem 0}}b{{color:#dbeafe}}
small,.foot{{color:#9cb8ce}}.foot{{font-size:.85rem}}
.good{{color:#7adeaf;font-weight:600}}.warn{{color:#d8a4ff;font-weight:600}}
.scroll{{overflow-x:auto;border:1px solid #24435d;border-radius:14px}}
table{{border-collapse:collapse;width:100%;min-width:660px;font-size:.89rem}}
th,td{{text-align:left;padding:.72rem;border-bottom:1px solid #1e364b;vertical-align:top}}
th{{background:#132e48;position:sticky;top:0}}tbody tr:nth-child(even){{background:#0c1b2b}}
footer{{margin:2rem 0;color:#99b5c9}}
</style></head><body><main>
<header><div class="warning">RESEARCH BETA · NON È IL NUOVO CORE OPERATIVO</div>
<h1>Macro V2 — Evidence Desk G8 / 28 coppie</h1>
<p class="sub">Fotografia {h(out["as_of"])} · Core storico fermo al {h(out["legacy_model_baseline_as_of"])} · overlay prezzi {h(out["official_price_overlay_as_of"])}.
Macro normalizzata sulla storia di ciascun paese: <b>non confrontabile come forza FX fra valute</b>.</p>
<p>Want: orientamento della comunicazione CB nello snapshot. Can: non ancora determinato. OIS ufficiale distinto da futures indicativi e bank-bill proxy.</p>
</header>
<section class="stats">
<span class="stat">8 valute</span><span class="stat">28 coppie</span>
<span class="stat">{out["summary"]["domestic_classes_robust"]}/8 macro robuste ai pesi</span>
<span class="stat">{out["summary"]["official_policy_pricing"]} pricing 6M ufficiali</span>
<span class="stat">{out["summary"]["indicative_policy_pricing"]} pricing 6M indicativi</span>
<span class="stat">{out["summary"]["context_only_non_policy_6m"]} contesti 6M non OIS</span>
</section>
<h2>G8 — Macro, Want/Can, tassi e qualità</h2>
<div class="grid">{"".join(cards)}</div>
<h2>28 coppie — tesi legacy separate dalla beta</h2>
<p class="sub">Queste valutazioni provengono esclusivamente dal motore storico; non sono state ricalcolate con la formula V2. Nessun ranking, ingresso o probabilità di successo viene creato.</p>
<div class="scroll"><table><thead><tr><th>Coppia</th><th>Qualità esistente</th><th>Prezzo esistente</th><th>Beta V2</th></tr></thead>
<tbody>{ptable}</tbody></table></div>
<footer>Fonte: snapshot versionati del repository. Ricerca prospettica e valutazione quantitativa ancora non certificate; non attribuire causalità macro→FX. SHA-256 ricevuta: {h(out["receipt_sha256"])}.</footer>
</main></body></html>
"""

def run(*, as_of=RESEARCH_DAY):
    return build(domestic_run(as_of="2026-10-27"), read("D"),
                 read("PAIR_SETUP_OPERATIONAL_VIEW"), read("NATIVE_CB_DATA"),
                 read("OIS_OPERATIONAL_VIEW"), read("NATIVE_RATES_DATA"), as_of=as_of)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--as-of",default=RESEARCH_DAY)
    ap.add_argument("--receipt",type=Path)
    ap.add_argument("--html",type=Path)
    args=ap.parse_args()
    for p in (args.receipt,args.html):
        if p:
            ensure(p.resolve().is_relative_to(Path("/tmp")),
                   "research output must remain under /tmp")
    report=run(as_of=args.as_of)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                                encoding="utf-8")
    if args.html:
        args.html.parent.mkdir(parents=True,exist_ok=True)
        args.html.write_text(render(report),encoding="utf-8")
    print(json.dumps({"schema":SCHEMA,"status":report["status"],
                      "summary":report["summary"],
                      "safe_to_republish_D":False,
                      "receipt_sha256":report["receipt_sha256"]},
                     ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
