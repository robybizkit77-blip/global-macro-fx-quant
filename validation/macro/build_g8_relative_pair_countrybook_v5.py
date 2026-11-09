#!/usr/bin/env python3
"""Relative macro/rates/FX research for the complete G8 28-pair universe.

Pairs are observations and competing conditional hypotheses, NOT FX signals.
OIS, different futures families and sovereign 2Y have independent dates,
definitions and benchmarks. Price observations are ECB reference FX fixes,
NOT live tradable FX and not evidence of causal positioning/flows.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro import build_g8_credit_liquidity_v4 as v4

SCHEMA="GMFQ_G8_RELATIVE_MACRO_PRICING_28PAIRS_RESEARCH_V5"
ROOT=v4.ROOT
FX=v4.FX
RATE_FILE="live_data/sections/NATIVE_RATES_DATA.json"
OIS_FILE="live_data/sections/OIS_OPERATIONAL_VIEW.json"
PRICE_FILE="live_data/sections/ECB_G8_PRICE_HISTORY.json"
PAIR_REGISTRY_FILE="live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json"
# Other benchmark definitions must remain visible, not silently normalized.
FRONT_END_DEF={
    "USD":"US Treasury daily par curve",
    "EUR":"ECB AAA zero/spot Svensson curve",
    "GBP":"BoE nominal government zero-coupon spot",
    "JPY":"Japan MoF JGB government yield",
    "CHF":"SNB Confederation spot government curve",
    "CAD":"BoC benchmark government bond yield",
    "AUD":"RBA government bond yield",
    "NZD":"RBNZ B2 government closing yield",
}
RISK_CHANNELS={
    "USD":"USD può beneficiare di domanda di liquidità anche se il differenziale di tassi diminuisce.",
    "EUR":"EUR risente anche di frammentazione creditizia, crescita estera ed energia.",
    "GBP":"GBP è sensibile a rendimenti reali, servizi domestici e premio di rischio UK.",
    "JPY":"JPY può salire per riduzione forzata del carry anche senza una sorpresa BoJ.",
    "CHF":"CHF può rafforzarsi in risk-off indipendentemente dalla differenza di policy.",
    "CAD":"CAD reagisce anche a petrolio, domanda USA e rischio globale.",
    "AUD":"AUD reagisce anche a domanda cinese, commodity e risk sentiment.",
    "NZD":"NZD risente di Cina, export agricolo, immobiliare e propensione al rischio.",
}

def require(condition,msg):
    if not condition:
        raise ValueError("G8_RELATIVE_V5_REJECTED: "+msg)

def isnum(x):
    return type(x) in (int,float) and math.isfinite(x)

def pct(x):
    return f"{x:+.2f}%".replace(".",",")

def num(x, unit=""):
    return f"{x:+.1f}{unit}".replace(".",",")

def time_age(date_raw,today):
    ref=date.fromisoformat(date_raw)
    require(ref<=today,"future market reference "+str(date_raw))
    return (today-ref).days

def fx_ratio(row,base,quote):
    """ECB quote is units of C per EUR. Cross A/B = EUR/B divided by EUR/A."""
    x,y=row[base],row[quote]
    require(isnum(x) and isnum(y) and x>0 and y>0,
            f"invalid ECB reference rate for {base}/{quote}")
    return y/x

def price_history(rows,base,quote,today):
    require(isinstance(rows,list) and len(rows)>=26,"insufficient ECB observations")
    dates=[r["Date"] for r in rows]
    require(len(set(dates))==len(dates),"duplicated ECB fixing date")
    require(dates==sorted(dates),"ECB history not ordered")
    for r in (rows[-1],rows[-6],rows[-21]):
        require(date.fromisoformat(r["Date"])<=today,"future ECB reference")
    p0,p5,p20=(fx_ratio(r,base,quote) for r in (rows[-1],rows[-6],rows[-21]))
    v5=100*(p0/p5-1)
    v20=100*(p0/p20-1)
    age=time_age(rows[-1]["Date"],today)
    return {
        "as_of":rows[-1]["Date"],
        "reference_price_quote_per_base":round(p0,8),
        "five_observation_change_pct":round(v5,4),
        "twenty_observation_change_pct":round(v20,4),
        "five_observation_start":rows[-6]["Date"],
        "twenty_observation_start":rows[-21]["Date"],
        "observation_age_calendar_days":age,
        "price_status":"DATED_ECB_REFERENCE_NOT_LIVE" if age>4
                       else "OFFICIAL_ECB_FIXING_REFERENCE_NOT_LIVE",
        "interpretation_status":"DESCRIPTIVE_DIRECTION_NOT_TRADE_CONFIRMATION",
        "flow_inference":None,
    }

def treasury(a,b,rd,today):
    x,y=rd[a],rd[b]
    for c,r in ((a,x),(b,y)):
        require(isnum(r.get("2Y")) and isnum(r.get("10Y")) and r.get("date"),
                c+" invalid 2Y/10Y reference")
        time_age(r["date"],today)
        require(r.get("quality","").startswith("FULL_CURRENT_OFFICIAL"),
                c+" government curve not official")
    da,db=x["date"],y["date"]
    age_a,age_b=time_age(da,today),time_age(db,today)
    same=da==db
    current_both=age_a<=7 and age_b<=7
    # In contrast to an unsynchronized yield level comparison, the published
    # exact-day spread is allowed ONLY if as-of dates match and both not old.
    spread=round((x["2Y"]-y["2Y"])*100,2) if same and current_both else None
    # We cannot diff changes across source series if the "chg" observation
    # prior dates/definitions are not independently verified.
    return {
        "base":{ "currency":a,"yield_2y_pct":x["2Y"],"yield_10y_pct":x["10Y"],
                 "as_of":da,"source":x["source"],
                 "benchmark_definition":FRONT_END_DEF[a],
                 "age_calendar_days":age_a},
        "quote":{ "currency":b,"yield_2y_pct":y["2Y"],"yield_10y_pct":y["10Y"],
                  "as_of":db,"source":y["source"],
                  "benchmark_definition":FRONT_END_DEF[b],
                  "age_calendar_days":age_b},
        "exact_same_date":same,
        "date_gap_days":abs((date.fromisoformat(da)-date.fromisoformat(db)).days),
        "spread_2y_bp":spread,
        "observed_change_1d_relative_bp":None,
        "rate_gap_status":("ILLUSTRATIVE_SAME_DAY_DIFFERENT_GOVERNMENT_BENCHMARKS"
                           if spread is not None
                           else "NO_SYNCHRONIZED_RECENT_2Y_COMPARISON"),
        "not_policy_pricing":True,
        "long_end_has_other_drivers":True,
    }

def forward_market(a,b,curves,today):
    p,q=curves[a],curves[b]
    for c,d in ((a,p),(b,q)):
        require(d.get("operational_status") in
                {"GREEN_OFFICIAL","GREEN_ESTIMATED","WITHHELD"},
                c+" unsupported forward quality")
        require(d.get("as_of"),c+" no dated curve")
        time_age(d["as_of"],today)
    def certified(o):
        six=o.get("horizons",{}).get("6m",{})
        return (o["operational_status"]=="GREEN_OFFICIAL" and
                o.get("quality")=="OFFICIAL_CERTIFIED" and
                isnum(six.get("rate")))
    pa,pb=certified(p),certified(q)
    same=p["as_of"]==q["as_of"]
    near=time_age(p["as_of"],today)<=7 and time_age(q["as_of"],today)<=7
    informative=pa and pb and same and near
    # Even these are NOT equivalent OIS curves. Official GBP is OIS,
    # CAD CRA is a CORRA futures product, JPY 3m TONA, AUD 30-day cash.
    raw_spread=round((p["horizons"]["6m"]["rate"]-
                       q["horizons"]["6m"]["rate"])*100,2) if informative else None
    return {
        "base":{"currency":a,"as_of":p["as_of"],"status":p["operational_status"],
                "source":p["source"],"6m_reference_rate_pct":
                p["horizons"]["6m"].get("rate") if pa else None},
        "quote":{"currency":b,"as_of":q["as_of"],"status":q["operational_status"],
                 "source":q["source"],"6m_reference_rate_pct":
                 q["horizons"]["6m"].get("rate") if pb else None},
        "same_as_of":same,
        "both_official_6m_reference":pa and pb,
        "six_month_arithmetic_reference_spread_bp":raw_spread,
        "comparable_equivalent_policy_6m":False,
        "implied_policy_move_difference_bp":None,
        "event_repricing_bp":None,
        "cross_country_overnight_basis_verified":False,
        "status":("OFFICIAL_SAME_DAY_HETEROGENEOUS_REFERENCE_NOT_POLICY_SPREAD"
                  if informative else "PARTIAL_OR_ASYNCHRONOUS_REFERENCE"),
        "fx_trade_signal":None,
    }

def compare(a,b,book,rd,ois,rows,today):
    one,two=book["countries"][a],book["countries"][b]
    require(one["bank"] and two["bank"],"missing country bank")
    rates=treasury(a,b,rd,today)
    fwd=forward_market(a,b,ois,today)
    price=price_history(rows,a,b,today)
    ga,gb=(one["observed_axes"]["GDP_quarterly_pct"],
           two["observed_axes"]["GDP_quarterly_pct"])
    # Different GDP quarter dates / publication vintages are not comparable
    # as same-time macro momentum. No arithmetic GDP "currency advantage".
    gp_ok=(ga.get("period")==gb.get("period") and
           ga.get("unit")==gb.get("unit"))
    observed_macro={
        "base_growth_period":ga["period"],
        "quote_growth_period":gb["period"],
        "growth_same_period_and_unit":gp_ok,
        "relative_growth_slope":None, # only after official vintage, forecast surprise
        "country_signals_reused":False,
    }
    r5=price["five_observation_change_pct"]
    r20=price["twenty_observation_change_pct"]
    if abs(r5)<.05:
        move="quasi invariato nelle ultime cinque osservazioni ECB"
    elif r5>0:
        move="salito nelle ultime cinque osservazioni ECB"
    else:
        move="sceso nelle ultime cinque osservazioni ECB"
    p1=f"{a}/{b}: cambio {move} ({pct(r5)}); "
    p1+="la variazione non dimostra che il mercato stia prezzando la nostra ipotesi."
    # Distinct and explicit two-leg mechanisms, not two country "scores".
    p2=(f"{a} — {one['bank']}: "+one["monetary_transmission_hypothesis"]+
        f" {b} — {two['bank']}: "+two["monetary_transmission_hypothesis"])
    want_a,can_a=v4.v3.v2.v1.CB_REACTION[a]
    want_b,can_b=v4.v3.v2.v1.CB_REACTION[b]
    p2b=(f"Funzione di reazione relativa: {one['bank']} persegue {want_a}; "
         f"{can_a} {two['bank']} persegue {want_b}; {can_b} "
         "Le differenze di mandato non implicano direzioni FX senza surprise e pricing.")
    if rates["spread_2y_bp"] is not None:
        p3=(f"Due anni governativi sullo stesso giorno ({rates['base']['as_of']}): "
            f"differenza {a} meno {b} {num(rates['spread_2y_bp'],' pb')}. "
            "Benchmark non omogenei; non è una misura di sorpresa monetaria.")
    else:
        p3=("2Y non confrontabili con un riferimento recente alla stessa data "
            f"({a} {rates['base']['as_of']}, {b} {rates['quote']['as_of']}); "
            "nessun differenziale sincronizzato dedotto.")
    if fwd["six_month_arithmetic_reference_spread_bp"] is not None:
        p4=(f"Riferimenti ufficiali 6M dello stesso giorno "
            f"({fwd['base']['as_of']}): scarto aritmetico "
            f"{num(fwd['six_month_arithmetic_reference_spread_bp'],' pb')}. "
            "Sono strumenti con scadenze, basi e contratti diversi: "
            "NON è lo spread OIS omogeneo né il repricing di due banche centrali.")
    else:
        p4=(f"Percorsi monetari 6M non confrontabili in modo omogeneo: "
            f"{a} {fwd['base']['status']}, {b} {fwd['quote']['status']}. "
            "Nessuna deduzione di rialzi/tagli relativi.")
    p5=(f"Perché conta: una divergenza potrebbe emergere SOLO se "
        f"il meccanismo su {a} o {b} venisse confermato da nuove pubblicazioni "
        "e sorprendesse rispetto al pricing pre-evento. "
        f"Rischi alternativi: {RISK_CHANNELS[a]} {RISK_CHANNELS[b]}")
    p6=(f"Conferma: verificare {a} — {one['what_to_monitor']}; "
        f"{b} — {two['what_to_monitor']}. "
        "Poi confronto su stessa data/tenore delle curve e reazione del cambio; "
        "senza tali prove non abbiamo un vantaggio operativo validato.")
    return {
        "pair":f"{a}/{b}","base":a,"quote":b,
        "base_bank":one["bank"],"quote_bank":two["bank"],
        "relative_economy":observed_macro,
        "base_macro_status":one["inflation_research_status"],
        "quote_macro_status":two["inflation_research_status"],
        "base_causal_hypothesis":one["monetary_transmission_hypothesis"],
        "quote_causal_hypothesis":two["monetary_transmission_hypothesis"],
        "rates_2y":rates,
        "money_market_6m":fwd,
        "price_ecb_reference":price,
        "current_relative_monetary_repricing_bp":None,
        "unexpected_policy_divergence_verified":False,
        "macro_surprise_consensus_dated":None,
        "relative_repricing_pre_post_event_bp":None,
        "relative_economic_thesis_strength":None,
        "trade_attractiveness":None,
        "positioning_flow_inference":None,
        "fx_signal":None,"position_size":None,"probability_of_fx_move":None,
        "base_bank_want_can":one["central_bank_conditional_reaction"],
        "quote_bank_want_can":two["central_bank_conditional_reaction"],
        "pair_narrative_it":[p1,p2,p2b,p3,p4,p5,p6],
        "research_gate":"DESCRIPTIVE_HYPOTHESES_NOT_TRADABLE",
    }

def build(*,today,root=ROOT):
    book=v4.build(today=today,root=root)
    inputs={}
    shas={}
    for k,path in {"rates":RATE_FILE,"ois":OIS_FILE,"price":PRICE_FILE,
                   "canonical_pair_registry":PAIR_REGISTRY_FILE}.items():
        raw=(root/path).read_bytes()
        inputs[k]=json.loads(raw)
        shas[k]=hashlib.sha256(raw).hexdigest()
    rd,ois,fx=inputs["rates"],inputs["ois"]["currencies"],inputs["price"]
    require(tuple(book["countries"])==FX and set(rd)==set(FX) and
            set(ois)==set(FX) and set(fx["currencies"])==set(FX),
            "G8 currencies not complete")
    require(fx.get("schema")=="GMFQ_ECB_G8_PRICE_HISTORY_V1"
            and fx.get("base")=="EUR" and
            fx.get("status")=="CURRENT_OFFICIAL_HISTORY" and
            fx.get("pair_count")==28,
            "unexpected ECB FX reference provenance")
    require(fx["rows"][-1]["Date"]==fx.get("last_as_of"),
            "ECB latest quote metadata mismatch")
    registry=inputs["canonical_pair_registry"]
    require(registry.get("schema")=="GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1"
            and registry.get("pair_count")==28
            and len(registry.get("pairs",{}))==28,
            "unexpected canonical pair registry")
    keys=[]
    combinations=set()
    for code,rec in registry["pairs"].items():
        pair=rec["canonical_pair"]
        vals=pair.split("/")
        require(len(vals)==2 and all(v in FX for v in vals)
                and vals[0]!=vals[1] and code=="".join(vals),
                "invalid canonical pair naming "+pair)
        combo=frozenset(vals)
        require(combo not in combinations,"canonical duplicate of "+pair)
        keys.append((pair,vals[0],vals[1]))
        combinations.add(combo)
    expect={frozenset([a,b]) for a,b in itertools.combinations(FX,2)}
    require(combinations==expect,"canonical 28-pair G8 universe incomplete")
    rows=fx["rows"]
    pairs={pair:compare(a,b,book,rd,ois,rows,today)
           for pair,a,b in keys}
    require(len(pairs)==28 and tuple(pairs)==tuple(p for p,_,_ in keys),
            "not exactly 28 canonical G8 pairs")
    official6=sum(p["money_market_6m"]["six_month_arithmetic_reference_spread_bp"]
                  is not None for p in pairs.values())
    current2=sum(p["rates_2y"]["spread_2y_bp"] is not None for p in pairs.values())
    return {
        "schema":SCHEMA,"research_as_of_rome":today.isoformat(),
        "macro_as_of":book["countries"]["USD"]["observed_axes"]["GDP_quarterly_pct"]["period"],
        "source_sha256":{**book["source_sha256"],**shas},
        "source_paths":{**book["source_paths"],
                        "rates":RATE_FILE,"ois":OIS_FILE,"price":PRICE_FILE,
                        "canonical_pair_registry":PAIR_REGISTRY_FILE},
        "fx_price_last_asof":fx["last_as_of"],
        "scope":{
            "currencies":8,"pairs":28,"price_series":28,
            "synchronized_2y_references":current2,
            "official_same_day_heterogeneous_6m_pairs":official6,
            "validated_policy_repricing":0,"fx_signals":0,
            "automatic_monetary_policy_divergences":0,
            "site_published":False,"reports_published":False,
            "28pair_canonical_core_modified":False,
        },
        "prohibitions":[
            "No mechanical relative FX score from GDP growth, core CPI or rate LEVEL.",
            "No claim that official futures cash rate, CORRA, TONA and BoE OIS have identical contract/basis/maturity.",
            "No OIS/policy path when WITHHELD or ESTIMATED_INFORMATIONAL.",
            "No same-day 2Y spread for different dates, and no event repricing without matching timestamps.",
            "No carry returns from cross-benchmark yield spreads.",
            "No trade confirmation from ECB fixings alone; no inferred flows or options positions.",
            "Archived economic series are not verified as first-release point-in-time.",
        ],
        "pairs":pairs,
    }

def markdown(book):
    n=book["scope"]
    lines=[
      "# G8 · Dalla tesi economica al confronto relativo nelle 28 coppie — V5",
      f"**Ricerca:** {book['research_as_of_rome']} · **Prezzo ECB:** "
      f"{book['fx_price_last_asof']} · **28 coppie, nessun segnale FX**",
      "",
      f"Riferimenti sincronizzati 2Y: {n['synchronized_2y_references']}/28. "
      f"Riferimenti monetari ufficiali 6M alla stessa data, ma NON equivalenti: "
      f"{n['official_same_day_heterogeneous_6m_pairs']}/28.",
      "",
      "Ricerca prospettica, con nessi causali da verificare: "
      "scenari macro a due economie → reazione della banca centrale → "
      "pricing datato → prezzo osservato → conferme e smentite. "
      "Non ha validazione per investimento o pubblicazione automatica.","",
    ]
    for key,row in book["pairs"].items():
        lines.extend([f"## {key}",""])
        lines.extend([s+"\n" for s in row["pair_narrative_it"]])
        lines.extend(["","---",""])
    return "\n".join(lines)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--json-out",type=Path)
    ap.add_argument("--md-out",type=Path)
    a=ap.parse_args()
    book=build(today=datetime.now(ZoneInfo("Europe/Rome")).date())
    for path,data in (
        (a.json_out,json.dumps(book,indent=2,ensure_ascii=False)+"\n"),
        (a.md_out,markdown(book))):
        if path:
            require(path.resolve().is_relative_to(Path("/tmp")),
                    "research artifact only in /tmp")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(data,encoding="utf-8")
    print(json.dumps({
        "status":SCHEMA,
        "fx_price_asof":book["fx_price_last_asof"],
        "scope":book["scope"],
        "sample_pairs":{
            p:book["pairs"][p]["pair_narrative_it"][0]
            for p in ("EUR/USD","GBP/JPY","AUD/NZD","NZD/CAD")
        }
    },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
