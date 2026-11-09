#!/usr/bin/env python3
"""G8 research V6: frozen surprise -> dated market context -> 28 relative FX pairs.

Only the two 30-Oct-2026 events have both frozen pre-release consensus and
post-release primary-source actual observations in the canonical repository.
An ECB fixing or official government yield with a calendar date CANNOT prove
an intraday response to the release, even if daily values straddle that date.
All pair price/yield moves herein are MULTIDAY DESCRIPTIVE CONTEXT ONLY.
No OIS, CB policy repricing, FX alpha or causality is estimated.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date,datetime,timedelta
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro import build_g8_relative_pair_countrybook_v5 as v5
from validation.macro.freeze_pre_release_consensus_v1 import (
    LEDGER,read_existing,validate_existing
)
from validation.macro.capture_official_postrelease_actuals_v1 import (
    OUT as ACTUAL_LEDGER,validate_actual_log
)
from validation.macro.build_macro_event_market_context_v1 import (
    ANCHORS,validate_anchors,MAX_POST_DAYS
)

ROOT=v5.ROOT
SCHEMA="GMFQ_G8_MACRO_SURPRISE_RELATIVE_28PAIRS_RESEARCH_V6"
FX=v5.FX
MARKET_MAX_PRE_DAYS=9
# The release-day ECB fixing is forbidden as a post-event print because
# source does not certify fixing intraday sequence vs economic publication.
FIRST_POST_MAX_CALENDAR_DAYS=14

def require(ok,msg):
    if not ok:
        raise ValueError("G8_EVENT_SURPRISE_V6_REJECTED: "+msg)

def finite(n):
    return type(n) in (int,float) and math.isfinite(n)

def round_or_null(v,places=4):
    return round(v,places) if v is not None else None

def iso(t):
    require(isinstance(t,str), "timestamp must be string")
    return datetime.fromisoformat(t.replace("Z","+00:00"))

def dates(x):
    return date.fromisoformat(x)

def digest(b):
    return hashlib.sha256(b).hexdigest()

def validate_event_ledgers(forecasts,actuals,anchors,today):
    validate_existing(forecasts)
    validate_actual_log(actuals,forecasts)
    validate_anchors(anchors,forecasts)
    require(len(forecasts)==len(actuals)==len(anchors)==2,
            "two verified 30-Oct events are the ONLY supported V6 universe")
    fm={x["event_key"]:x for x in forecasts}
    am={x["event_key"]:x for x in actuals}
    xm={x["event_key"]:x for x in anchors}
    require(set(fm)==set(am)==set(xm),"missing or duplicate official actual/forecast/anchor")
    for key in fm:
        f,a,b=fm[key],am[key],xm[key]
        scheduled=iso(f["official_scheduled_release_utc"])
        require(scheduled.tzinfo is not None and scheduled.date()<=today,
                key+" missing/premature release")
        require(f["currency"]==a["currency"]==b["currency"],key+" currency changed")
        require(iso(f["captured_at_utc"])<scheduled,key+" late consensus")
        require(iso(b["captured_at_utc"])<scheduled,key+" late pre-market snapshot")
        require(iso(a["captured_at_utc"])>=scheduled,key+" actual captured pre-release")
        require(a["forecast_receipt_sha256"]==f["record_sha256"]==
                b["forecast_sha256"],key+" hash-linked consensus not identical")
        require(a["reference_period"] and a["unit"] and
                a["source_url"].startswith("https://"),key+" missing issuer receipt")
        require(a["publisher_first_release_PIT_verified"] is False,
                key+" cannot promote issuer page first-seen to certified PIT")
        require(f["quality"]=="SECONDARY_CONSENSUS_MATCH_B_NOT_OFFICIAL",
                key+" unsupported consensus quality")
        require(finite(f["consensus_value_percent"]) and
                finite(a["actual_percent"]) and
                finite(a["actual_minus_frozen_consensus_pp"]),
                key+" nonfinite surprise input")
        calc=a["actual_percent"]-f["consensus_value_percent"]
        require(math.isclose(calc,a["actual_minus_frozen_consensus_pp"],abs_tol=1e-9),
                key+" official actual minus immutable forecast mismatch")
        require(a["actual_percent"]==0.0 or a["actual_percent"]!=None,
                key+" zero actual cannot be replaced by null")
    return fm,am,xm

def first_daily_post_fx(rows,release,today):
    end=min(today,release+timedelta(days=FIRST_POST_MAX_CALENDAR_DAYS))
    valid=[r for r in rows if release<dates(r["Date"])<=end]
    return min(valid,key=lambda r:r["Date"]) if valid else None

def fx_multiday(pair,fx,anchor,release,today):
    base,quote=pair.split("/")
    before_day=anchor["fx"]["date"]
    require(dates(before_day)<release,
            "frozen ECB fixing after release date forbidden")
    require((release-dates(before_day)).days<=MARKET_MAX_PRE_DAYS,
            "frozen FX baseline too old")
    rows=fx["rows"]
    candidates=[r for r in rows if r["Date"]==before_day]
    require(len(candidates)==1,"frozen ECB quote date not uniquely available")
    before=candidates[0]
    ev=anchor["currency"]
    require(math.isclose(before[ev],anchor["fx"]["quote_per_euro"],
                         rel_tol=0,abs_tol=1e-9),
            "archived and live ECB pre-reference conflict")
    post=first_daily_post_fx(rows,release,today)
    if post is None:
        return {"status":"NO_FIRST_POST_RELEASE_DAILY_ECB_FIXING",
                "base_date":before_day,"post_date":None,
                "return_pct":None,"intraday_event_response_verified":False}
    old=v5.fx_ratio(before,base,quote)
    new=v5.fx_ratio(post,base,quote)
    return {
        "status":"MULTIDAY_DESCRIPTIVE_ECB_FIXING_NOT_EVENT_EFFECT",
        "base_date":before_day,"post_date":post["Date"],
        "observations_calendar_gap_days":(dates(post["Date"])-dates(before_day)).days,
        "base_price_quote_per_base":round(old,8),
        "post_price_quote_per_base":round(new,8),
        "return_pct":round(100*(new/old-1),5),
        "intraday_event_response_verified":False,
        "synchronous_2y_fx_post_fix_verified":False,
        "not_trade_execution_price":True,
    }

def yield_series(r,tenor):
    h=r["history2" if tenor=="2Y" else "history10"]
    ds,vs=h["dates"],h["values"]
    require(isinstance(ds,list) and isinstance(vs,list) and len(ds)==len(vs),
            "dated yield history unavailable")
    result={}
    for d,v in zip(ds,vs):
        if isinstance(d,str) and len(d)==10:
            require(finite(v),"non-finite dated yield")
            require(d not in result,"duplicate dated yield quote")
            require(d<=r["date"],"future relative to official source snapshot")
            result[d]=v
    return result

def relative_2y_multiday(pair,rates,anchor,release,today):
    b,q=pair.split("/")
    require(b in rates and q in rates, "missing currency government yields")
    sources={c:yield_series(rates[c],"2Y") for c in (b,q)}
    both=set(sources[b])&set(sources[q])
    reference_day=min(dates(anchor["2Y"]["date"]),iso(anchor["captured_at_utc"]).date())
    earliest=release-timedelta(days=MARKET_MAX_PRE_DAYS)
    before=sorted(d for d in both if earliest<=dates(d)<=reference_day and dates(d)<release)
    deadline=min(today,release+timedelta(days=FIRST_POST_MAX_CALENDAR_DAYS))
    after=sorted(d for d in both if release<dates(d)<=deadline)
    if not before or not after:
        return {"status":"NO_PAIRED_PRE_POST_SAME_DATES",
                "start":before[-1] if before else None,
                "end":after[0] if after else None,
                "relative_spread_change_bp":None,
                "intraday_event_repricing_verified":False}
    start,end=before[-1],after[0]
    require(start<end,"wrong chronological yield comparison")
    event_leg=anchor["currency"]
    frozen=anchor["2Y"]
    if start==frozen["date"]:
        require(math.isclose(sources[event_leg][start],frozen["yield_pct"],
                             rel_tol=0,abs_tol=1e-6),
                "frozen event leg 2Y reference mismatch")
    pre=(sources[b][start]-sources[q][start])*100
    post=(sources[b][end]-sources[q][end])*100
    return {
        "status":"MULTIDAY_SOVEREIGN_SPREAD_CONTEXT_NOT_EVENT_REPRICING",
        "start":start,"end":end,
        "start_spread_bp":round(pre,4),
        "end_spread_bp":round(post,4),
        "relative_spread_change_bp":round(post-pre,4),
        "days_between":(dates(end)-dates(start)).days,
        "same_start_day_for_both_legs":True,
        "same_end_day_for_both_legs":True,
        "treasury_gilt_jgb_benchmarks_not_pure_policy":True,
        "first_release_market_timestamp_not_certified":True,
        "intraday_event_repricing_verified":False,
    }

def event_scenario(event):
    c=event["currency"]
    surprise=event["actual_minus_frozen_consensus_pp"]
    if c=="CAD":
        return (
            "Il PIL mensile canadese è sotto il consenso congelato: "
            "potrebbe aumentare l'attenzione della BoC ai rischi sulla crescita, "
            "ma serve verificare revisioni, composizione, inflazione sottostante "
            "e quanto fosse già prezzato prima del comunicato."
        ) if surprise<0 else (
            "Il PIL canadese non è sotto il consenso: occorre verificare "
            "composizione della crescita e repricing."
        )
    if c=="USD":
        return (
            "L'Employment Cost Index ha rispettato il consenso archiviato: "
            "la sorpresa aggregata è nulla. Non significa che i salari e "
            "l'inflazione dei servizi siano irrilevanti; servono composizione, "
            "revisioni e aspettative Fed pre-evento."
        ) if abs(surprise)<1e-9 else (
            "Il costo del lavoro si discosta dal consenso: verificare "
            "composizione e implicazioni per Fed senza dedurre un trade."
        )
    return "Nessuna funzione di reazione automatico da sorpresa isolata."

def build(*,today,root=ROOT,forecast_records=None,actual_records=None,anchor_records=None,
          rates_override=None,fx_override=None):
    v5book=v5.build(today=today,root=root)
    paths={
        "pre_forecast":"validation/macro/MACRO_PRE_RELEASE_CONSENSUS_LEDGER_V1.jsonl",
        "first_seen_actual":"validation/macro/MACRO_OFFICIAL_ACTUAL_FIRST_SEEN_V1.jsonl",
        "pre_market_anchor":"validation/macro/MACRO_EVENT_PRE_RELEASE_MARKET_ANCHORS_V1.jsonl",
        "native_yields":v5.RATE_FILE,"ecb_fx":v5.PRICE_FILE,
        "canonical_pairs":v5.PAIR_REGISTRY_FILE,
    }
    forecast_records=read_existing(root/paths["pre_forecast"]) if forecast_records is None else forecast_records
    actual_records=read_existing(root/paths["first_seen_actual"]) if actual_records is None else actual_records
    anchor_records=read_existing(root/paths["pre_market_anchor"]) if anchor_records is None else anchor_records
    fm,am,xm=validate_event_ledgers(forecast_records,actual_records,anchor_records,today)
    rates=json.loads((root/paths["native_yields"]).read_text()) if rates_override is None else rates_override
    fx=json.loads((root/paths["ecb_fx"]).read_text()) if fx_override is None else fx_override
    require(fx.get("base")=="EUR" and fx.get("status")=="CURRENT_OFFICIAL_HISTORY",
            "canonical ECB cross reference missing")
    events=[]
    for key,f in fm.items():
        a=am[key]
        release=iso(f["official_scheduled_release_utc"]).date()
        event={
          "event_key":key,"currency":f["currency"],
          "reference_period":a["reference_period"],"metric_unit":a["unit"],
          "release_scheduled_utc":f["official_scheduled_release_utc"],
          "consensus_captured_at_utc":f["captured_at_utc"],
          "anchor_captured_at_utc":xm[key]["captured_at_utc"],
          "issuer_actual_first_observed_at_utc":a["captured_at_utc"],
          "secondary_consensus_pct":f["consensus_value_percent"],
          "actual_pct":a["actual_percent"],
          "surprise_pp":round(a["actual_minus_frozen_consensus_pp"],5),
          "forecast_source_quality":f["quality"],
          "issuer_receipt_quality":a["quality"],
          "issuer_url":a["source_url"],
          "issuer_first_publication_PIT_verified":False,
          "actual_is_first_runner_observation":True,
          "market_baseline_early_not_last_tick":True,
          "market_event_causality_verified":False,
          "no_intraday_reaction_verified":True,
          "central_bank_policy_surprise_bp":None,
          "hypothesis_it":None,
          "other_same_instant_events":[],
        }
        event["hypothesis_it"]=event_scenario(event)
        events.append(event)
    for ev in events:
        ev["other_same_instant_events"]=[
            e["event_key"] for e in events
            if e["event_key"]!=ev["event_key"]
            and e["release_scheduled_utc"]==ev["release_scheduled_utc"]]
    require(len(events)==2 and {x["currency"] for x in events}=={"USD","CAD"},
            "V6 only admits two archived USD/CAD actuals")
    pairs={}
    for key,prior in v5book["pairs"].items():
        base,quote=key.split("/")
        exposures=[]
        for event in events:
            if event["currency"] not in (base,quote):
                continue
            evkey=event["event_key"]
            release=iso(event["release_scheduled_utc"]).date()
            anchor=xm[evkey]
            price=fx_multiday(key,fx,anchor,release,today)
            yields=relative_2y_multiday(key,rates,anchor,release,today)
            exp={
                "event_key":evkey,
                "event_currency":event["currency"],
                "event_leg":"BASE" if event["currency"]==base else "QUOTE",
                "actual_minus_frozen_consensus_pp":event["surprise_pp"],
                "event_scenario_it":event["hypothesis_it"],
                "ecb_fx_daily_context":price,
                "government_2y_relative_daily_context":yields,
                "relative_6m_policy_path_change_bp":None,
                "relative_6m_comparison_status":
                    "NO_SYNCHRONIZED_IDENTICAL_POLICY_CONTRACTS_ACROSS_BOTH_LEGS",
                "verified_cb_want_can_from_release":None,
                "event_causal_fx_repricing_bp":None,
                "no_intraday_causal_inference":True,
                "confounding_same_instant_events":event["other_same_instant_events"],
                "analyst_reading_it":(
                    f"{key}: sorpresa macro su {event['currency']} "
                    f"{event['surprise_pp']:+.2f} pp. "
                    "Le variazioni giornaliere successive di ECB e 2Y sono "
                    "solo CONTESTO MULTIGIORNO, non prova della reazione al dato. "
                    "Confermare il cambiamento nelle curve datate prima di formulare "
                    "una tesi valutaria operativa."
                )
            }
            exposures.append(exp)
        pairs[key]={
            "pair":key,"base":base,"quote":quote,
            "countrybook_v5_gate":prior["research_gate"],
            "scenario_legs":[prior["base_causal_hypothesis"],
                             prior["quote_causal_hypothesis"]],
            "events":exposures,
            "event_covered":bool(exposures),
            "both_legs_same_release_time_confounder":len(exposures)>1,
            "unpriced_policy_surprise_verified":False,
            "trade_attractiveness":None,"thesis_strength":None,
            "fx_signal":None,"validated_impact":None,
        }
    related=sum(bool(x["events"]) for x in pairs.values())
    observed=sum(len(x["events"]) for x in pairs.values())
    rel2=sum(z["government_2y_relative_daily_context"]["relative_spread_change_bp"] is not None
             for x in pairs.values() for z in x["events"])
    fxcount=sum(z["ecb_fx_daily_context"]["return_pct"] is not None
                for x in pairs.values() for z in x["events"])
    result={
        "schema":SCHEMA,"research_run_date_rome":today.isoformat(),
        "market_fx_reference_asof":v5book["fx_price_last_asof"],
        "source_paths":paths,
        "source_sha256":{k:digest((root/path).read_bytes()) for k,path in paths.items()},
        "events":events,
        "coverage":{
            "g8_currencies":8,"canonical_fx_pairs":28,
            "frozen_consensus_actual_events":2,
            "pairs_exposed_to_frozen_events":related,
            "pair_event_exposures":observed,
            "historical_paired_2y_multiday_contexts":rel2,
            "historical_ecb_fx_multiday_contexts":fxcount,
            "proven_intraday_market_responses":0,
            "proven_macro_causality":0,
            "policy_repricing_confirmed":0,
            "fx_signals":0,
        },
        "limitations":[
            "Only two USD/CAD 30-Oct events have fully archived frozen forecast and first-seen official actual.",
            "First-runner-seen official page is not independently certified first-issuer-release PIT.",
            "Both events share scheduled release time. Even their pair legs cannot be attributed independently.",
            "ECB daily reference fixes are not timestamped pre/post macro announcement execution prices.",
            "Two-year yields are mixed government benchmarks, not homogeneous CB OIS curves.",
            "Dated pre/post references span intervening trading sessions and shocks. No causal attribution.",
            "A 6M rate level or secondary quote is not proof of policy repricing or current FX carry.",
            "No historical OOS predictive claims or numerical meeting probabilities."
        ],
        "ready_for_site":False,"ready_for_reports":False,
        "eligible_for_fx_core":False,"eligible_for_forecasting_backtest":False,
        "pairs":pairs,
    }
    require(len(pairs)==28 and observed==14 and related==13,
            "unexpected two-event exposures across G8 canonical pair universe")
    return result

def markdown(book):
    s=book["coverage"]
    out=[
        "# FX Quant Country Book V6 — Surprise macro e contesto multiday",
        f"**Ricerca:** {book['research_run_date_rome']} · **28 coppie canoniche**",
        "",
        f"Due eventi con consenso congelato ed actual ufficiale osservato. "
        f"{s['pairs_exposed_to_frozen_events']} coppie esposte, "
        f"{s['pair_event_exposures']} esposizioni evento-coppia. "
        "**ZERO attribuzioni causali intraday**.",
        ""
    ]
    for e in book["events"]:
        out+= [
            f"## {e['currency']} — {e['reference_period']}",
            f"Consenso congelato {e['secondary_consensus_pct']:.2f}% → "
            f"actual {e['actual_pct']:.2f}%, sorpresa {e['surprise_pp']:+.2f} pp.",
            e["hypothesis_it"],
            "Il consenso è secondario ma congelato prima dell'evento; "
            "l'actual è prima osservazione del runner dalla pagina ufficiale, "
            "non prima pubblicazione editoriale certificata.",
            ""
        ]
    out+=["## Coppie con esposizione a quei due eventi", ""]
    for pair,x in book["pairs"].items():
        if not x["events"]:continue
        out+=[f"### {pair}"+(" · EVENTI CONCORRENTI" if x["both_legs_same_release_time_confounder"] else "")]
        for e in x["events"]:
            f=e["ecb_fx_daily_context"]
            r=e["government_2y_relative_daily_context"]
            out+=[
                f"- {e['event_currency']} ({e['event_leg']}), sorpresa "
                f"{e['actual_minus_frozen_consensus_pp']:+.2f} pp. "
                f"FX ECB: "+(
                    f"{f['return_pct']:+.2f}% da {f['base_date']} a {f['post_date']}"
                    if f["return_pct"] is not None else f["status"]) +
                ". Spread 2Y relativo: "+(
                    f"{r['relative_spread_change_bp']:+.2f} pb "
                    f"dal {r['start']} al {r['end']}"
                    if r["relative_spread_change_bp"] is not None else r["status"]) +
                ". **Solo cambiamenti multiday non attribuibili al dato**."
            ]
        out+=[""]
    out+=["---","",
          "I 15 cross non esposti ad eventi certificati non vengono artificialmente "
          "associati a questi comunicati. Nessun cambiamento al ranking delle 28 coppie, "
          "a D.json, sito o report automatici."]
    return "\n".join(out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--json-out",type=Path)
    ap.add_argument("--md-out",type=Path)
    args=ap.parse_args()
    b=build(today=datetime.now(ZoneInfo("Europe/Rome")).date())
    for p,body in (
      (args.json_out,json.dumps(b,ensure_ascii=False,indent=2)+"\n"),
      (args.md_out,markdown(b))):
        if p is not None:
            require(p.resolve().is_relative_to(Path("/tmp")),
                    "only /tmp for non-production evidence artifacts")
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(body,encoding="utf-8")
    print(json.dumps({
        "status":b["schema"],
        "coverage":b["coverage"],
        "events":[{"ccy":e["currency"],"surprise_pp":e["surprise_pp"]}
                  for e in b["events"]],
        "usd_cad_pair":len(b["pairs"]["USD/CAD"]["events"]),
    },ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    raise SystemExit(main())
