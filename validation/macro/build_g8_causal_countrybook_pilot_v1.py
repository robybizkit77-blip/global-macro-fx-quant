#!/usr/bin/env python3
"""Research-only G8 causal Country Book: grounded conditional narratives, NEVER FX signals.

Snapshot joins current *revised* descriptive features, archived sector context,
certified policy actions and source-quality-labelled rates. It is not a historic
PIT replay, a central-bank decision forecast, or a substitute for human review.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "GMFQ_G8_CAUSAL_COUNTRY_BOOK_PILOT_RESEARCH_V1"
FX = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
PATHS = {
    "method": "validation/macro/G8_CAUSAL_REACTION_COUNTRY_BOOK_V1.json",
    "macro": "site/fx-quant-v2/macro-baseline-candidate-v1.json",
    "sector_archive": "site/fx-quant-v2/design-studio-macro-g8-v1-data.json",
    "cb": "live_data/sections/NATIVE_CB_DATA.json",
    "ois": "live_data/sections/OIS_OPERATIONAL_VIEW.json",
    "rates": "live_data/sections/NATIVE_RATES_DATA.json",
}
COUNTRY = {
    "USD": {
        "name": "Stati Uniti", "bank": "Fed",
        "firm": "US_NEWORDER_history_NEWORDER", "consumer": "US_PCEC96_history_value",
        "chain": "Se gli ordini delle imprese e le assunzioni rallentano, il potere contrattuale dei lavoratori e la spesa reale delle famiglie potrebbero attenuarsi solo con ritardo.",
        "counter": "Se invece salari reali, domanda interna e ordini rimangono forti, le pressioni sui servizi possono persistere.",
        "next": "JOLTS per assunzioni e licenziamenti, payrolls per settori, reddito reale e PCE core",
    },
    "EUR": {
        "name": "Area euro", "bank": "BCE",
        "firm": "EA_IP_history_value", "consumer": "EA_RETAIL_VOL_history_value",
        "chain": "Se nuovi ordinativi e domanda di credito delle aziende indeboliscono investimenti e occupazione, la minore crescita del reddito può frenare i consumi; la trasmissione bancaria conta molto.",
        "counter": "Se i servizi e i salari rimangono persistenti, l'inflazione domestica può non seguire il rallentamento dell'industria.",
        "next": "PMI e nuovi ordini, prestiti bancari, salari negoziati, servizi HICP e volumi retail",
    },
    "GBP": {
        "name": "Regno Unito", "bank": "BoE",
        "firm": "UK_PRODUCTION_history_value", "consumer": "UK_RETAIL_VOL_history_value",
        "chain": "Se mutui più onerosi e minori assunzioni riducono il reddito spendibile, la domanda per servizi e beni discrezionali potrebbe raffreddarsi.",
        "counter": "Se i salari e i prezzi dei servizi restano vischiosi, un calo dei consumi potrebbe non tradursi subito in disinflazione.",
        "next": "retribuzioni del settore privato, CPI servizi, approvazioni mutui e retail reale",
    },
    "JPY": {
        "name": "Giappone", "bank": "BoJ",
        "firm": "JP_IIP_history_value", "consumer": "JP_RETAIL_history_value",
        "chain": "Se i rialzi salariali diventano reddito reale e sostengono la domanda domestica, la dinamica salari-prezzi potrebbe rendere più sostenibile la normalizzazione monetaria.",
        "counter": "Se la crescita dei prezzi riflette soprattutto energia e importazioni senza aumento della spesa reale, la trasmissione domestica resta fragile.",
        "next": "Shunto, salari reali, consumi delle famiglie, Tankan, prezzi domestici dei servizi",
    },
    "CHF": {
        "name": "Svizzera", "bank": "SNB",
        "firm": "CH_PRODUCTION_history_value", "consumer": "CH_RETAIL_REAL_history_value",
        "chain": "Se domanda europea ed esportazioni rallentano, possono moderarsi assunzioni e consumi; un CHF più forte può inoltre comprimere l'inflazione importata.",
        "counter": "Se la domanda interna regge e la pressione sui prezzi riemerge, il margine della SNB per allentare si riduce.",
        "next": "ordini export e PMI, salari e occupazione, CPI domestico, cambio effettivo CHF",
    },
    "CAD": {
        "name": "Canada", "bank": "BoC",
        "firm": "CA_BUSINESS_LOANS_OUTSTANDING_history_value", "consumer": "CA_RETAIL_VOLUME_history_value",
        "chain": "Se il rinnovo dei mutui aumenta l'onere sul reddito e le imprese rallentano le assunzioni, la spesa delle famiglie può indebolirsi anche con PIL ancora positivo.",
        "counter": "Se l'inflazione di fondo e i servizi restano persistenti, il calo della domanda può non essere sufficiente a consentire un allentamento rapido.",
        "next": "spesa reale, rinnovi dei mutui, disoccupazione per settori, CPI trim/median e petrolio",
    },
    "AUD": {
        "name": "Australia", "bank": "RBA",
        "firm": "AU_CREDIT_BUSINESS_CURRENT_SA_history_value", "consumer": "AU_HOUSEHOLD_SPENDING_history_value",
        "chain": "Se mutui e costo del credito comprimono le famiglie e i piani di investimento, il lavoro potrebbe perdere forza; Cina e commodity possono amplificare il ciclo esterno.",
        "counter": "Se domanda di servizi e inflazione trimmed-mean restano alte, la RBA può dover dare priorità alla persistenza dei prezzi.",
        "next": "spesa reale delle famiglie, ore lavorate, Wage Price Index, trimmed-mean CPI, Cina e ferro",
    },
    "NZD": {
        "name": "Nuova Zelanda", "bank": "RBNZ",
        "firm": "NZ_REAL_GDP_Q_history_value", "consumer": "NZ_RETAIL_VOLUME_Q_history_value",
        "chain": "Se debito delle famiglie, mutui e debolezza immobiliare comprimono la spesa, le imprese possono reagire riducendo assunzioni e investimenti.",
        "counter": "Se l'inflazione non-tradable rimane elevata, la RBNZ potrebbe non avere lo spazio di manovra suggerito dalla sola debolezza della domanda.",
        "next": "volumi retail aggiornati, mercato immobiliare, disoccupazione, aspettative salari, CPI non-tradable",
    },
}

def require(ok, msg):
    if not ok:
        raise ValueError("G8_CAUSAL_PILOT_REJECTED: " + msg)

def finite(v):
    return type(v) in (int, float) and math.isfinite(v)

def pct(v):
    return f"{v:.2f}".replace(".", ",") + "%"

def pp(v):
    sign = "+" if v > 0 else ""
    return (sign + f"{v:.2f}").replace(".", ",") + " pp"

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def sources(root=ROOT):
    data, fingerprints = {}, {}
    for name, rel in PATHS.items():
        b = (root/rel).read_bytes()
        data[name] = json.loads(b)
        fingerprints[name] = sha(b)
    return data, fingerprints

def direction(v, threshold=.05, subject=""):
    if v > threshold:
        return "in aumento"
    if v < -threshold:
        return "in diminuzione"
    return "pressoché stabile"

def study_country(ccy, data, date_today):
    macro = data["macro"]["features"][ccy]
    spec = data["method"]["countries"][ccy]
    config = COUNTRY[ccy]
    old = data["sector_archive"]["currencies"][ccy]
    cb = data["cb"][ccy]
    curve = data["ois"]["currencies"][ccy]
    rate = data["rates"][ccy]
    g, i, j = (macro[key] for key in
               ("growth_qoq_pct", "inflation_change_pp", "unemployment_change_pp"))
    require(all(finite(g.get(x)) for x in ("value",)) and
            all(finite(z.get(x)) for z in (i, j) for x in ("value", "level")),
            ccy+" non-finite macro axes")
    require(all(isinstance(z.get("period"), str) and z["period"]
                for z in (g, i, j)), ccy+" missing economic periods")
    require(g.get("unit") == "PERCENT_QOQ_NONANNUALIZED_WITHIN_COUNTRY",
            ccy+" GDP transform drift")
    require(g.get("level_does_not_measure_relative_fx_strength") is True,
            ccy+" GDP illicit FX strength")
    require(i.get("unit") == "YOY_CHANGE_OVER_THREE_OBSERVATION_INTERVALS_PP" and
            j.get("unit") == "UNEMP_RATE_CHANGE_OVER_THREE_OBSERVATION_INTERVALS_PP",
            ccy+" macro transformation drift")
    require(isinstance(spec.get("bank"), str) and len(spec["bank"])>2,
            ccy+" missing institutional mandate")
    require(cb.get("bank") and cb.get("last_date") and finite(cb.get("rate")),
            ccy+" invalid latest central bank")
    require(date.fromisoformat(cb["last_date"])<=date_today,
            ccy+" policy date in future")
    require(curve.get("operational_status") in
            ("GREEN_OFFICIAL","GREEN_ESTIMATED","WITHHELD"),
            ccy+" unsupported OIS tier")
    require(curve.get("quality") in ("OFFICIAL_CERTIFIED","ESTIMATED_INFORMATIONAL"),
            ccy+" unsupported OIS quality")
    require(date.fromisoformat(curve["as_of"]) <= date_today,
            ccy+" pricing date in future")
    require(date.fromisoformat(rate["date"]) <= date_today,
            ccy+" two-year quote in future")
    require(finite(rate.get("2Y")) and finite(rate.get("10Y")),
            ccy+" absent sovereign 2Y or 10Y")
    firm = [o for o in old["indicators"] if o["id"]==config["firm"]]
    consumer = [o for o in old["indicators"] if o["id"]==config["consumer"]]
    require(len(firm)==len(consumer)==1,ccy+" missing archived sector source")
    require(all(isinstance(x["date"],str) and finite(x.get("value"))
                for x in (firm[0], consumer[0])),ccy+" malformed sector evidence")
    # The sector design-studio is a separate older archive. NEVER describe it
    # as present-day activity even if its numeric history appears complete.
    archived = [
        {"role":role,"label":x["label"],"value":x["value"],
         "unit":x.get("unit",""),"observation_period":x["date"],
         "id":x["id"],"source":x.get("source_file"),
         "quality":"HISTORICAL_CONTEXT_NOT_CERTIFIED_CURRENT_RELEASE_OR_PIT"}
        for role,x in (("imprese",firm[0]),("consumatori",consumer[0]))
    ]
    accel = g.get("gdp_acceleration_pp")
    require(accel is None or finite(accel),ccy+" GDP acceleration malformed")
    if accel is not None:
        require(g.get("acceleration_quality")=="TWO_CONTIGUOUS_QUARTERS",
                ccy+" GDP comparison not supported")
    activity = (
        f"Il PIL è cresciuto del {pct(g['value'])} nell'ultimo trimestre disponibile "
        f"({g['period']})" if g["value"]>=0
        else f"Il PIL si è contratto del {pct(abs(g['value']))} "
             f"nell'ultimo trimestre disponibile ({g['period']})"
    )
    activity += (
        f", con variazione del ritmo di {pp(accel)} rispetto al trimestre precedente."
        if accel is not None
        else ". Non disponiamo di un'accelerazione trimestrale omogenea certificata."
    )
    job_text = (f"La disoccupazione è al {pct(j['level'])} ({j['period']}) ed è "
                f"{direction(j['value'])} ({pp(j['value'])} sulle tre osservazioni).")
    inflation_text = (
        f"L'inflazione headline annua è al {pct(i['level'])} ({i['period']}), "
        f"{direction(i['value'])} ({pp(i['value'])} sulle ultime tre osservazioni "
        f"{'trimestrali' if i['period_frequency']=='Q' else 'mensili'} disponibili)."
    )
    opposing = (i["value"]>.05 and j["value"]>.05)
    if opposing:
        synthesis = ("La pressione sui prezzi aumenta mentre il lavoro perde slancio: "
                     "il potenziale conflitto tra inflazione e attività va distinto "
                     "dall'effettiva persistenza dei prezzi di fondo.")
    elif i["value"]>.05 and j["value"]<=.05:
        synthesis = ("L'inflazione headline si rafforza senza una chiara crescita "
                     "della disoccupazione: questo può ridurre lo spazio per "
                     "allentamenti, ma non prova una nuova inflazione da domanda.")
    elif i["value"]<=.05 and j["value"]>.05:
        synthesis = ("L'indebolimento del lavoro potrebbe amplificare la "
                     "disinflazione, ma servono dati su domanda e salari reali.")
    else:
        synthesis = ("Il quadro è misto: il solo PIL o la sola headline non "
                     "identificano il cambiamento del ciclo domestico.")
    bank_text = (
        f"Per {config['bank']} la questione non è prevedere automaticamente la prossima "
        "decisione, ma capire se lavoro, prezzi e domanda cambiano il "
        "bilanciamento dei rischi secondo il mandato specifico. "
        "Se i prezzi di fondo persistono, la banca potrebbe restare restrittiva; "
        "se la debolezza di domanda e occupazione si diffonde e l'inflazione "
        "si modera, potrebbe aumentare lo spazio per allentare."
    )
    six = curve.get("horizons",{}).get("6m",{})
    quality = curve["operational_status"]
    if quality=="GREEN_OFFICIAL":
        require(curve["quality"]=="OFFICIAL_CERTIFIED" and finite(six.get("rate")),
                ccy+" false official six-month rate")
        pricing = (f"Contratto a 6 mesi da fonte di mercato certificata: "
                   f"{pct(six['rate'])} (riferimento {curve['as_of']}); "
                   f"tasso ufficiale corrente {pct(cb['rate'])}. "
                   "Il livello di un futures non è una probabilità di decisione "
                   "né una misura diretta del repricing senza confronto sullo stesso contratto.")
        pricing_type = "OFFICIAL_FUTURES_CONTEXT_NOT_OIS_LEVEL"
    elif quality=="GREEN_ESTIMATED":
        pricing = (f"Contesto futures secondario indicativo ({curve['as_of']}): "
                   "non può essere convertito in rialzi/tagli impliciti "
                   "né essere trattato come OIS certificato.")
        pricing_type = "SECONDARY_ESTIMATE_NOT_POLICY_PRICING"
    else:
        pricing = ("Nessuna curva OIS 6M ufficiale sufficientemente validata "
                   "per dedurre oggi il percorso della banca centrale.")
        pricing_type = "WITHHELD_NO_6M_POLICY_PRICING"
    age_2y = (date_today-date.fromisoformat(rate["date"])).days
    price_quality = ("2Y_STALE_NOT_SAME_DAY"
                     if age_2y>7 else "2Y_DATED_OFFICIAL_CONTEXT")
    rates_text = (f"Rendimento governativo 2Y {pct(rate['2Y'])} e 10Y "
                  f"{pct(rate['10Y'])} ({rate['date']}); "
                  + ("la serie è datata e non si può usarla per confermare un repricing recente."
                     if age_2y>7
                     else "sono livelli, non dimostrazioni del repricing di un singolo dato."))
    quality_note = (
        "Per le aziende e i consumatori disponiamo di osservazioni archiviate "
        "non verificate come pubblicazioni correnti: la catena economica resta "
        "un'ipotesi condizionata, NON un fatto già osservato. "
        "Mancano consenso congelato prima dei dati, revisione verificata "
        "e confronto OIS pre/post-evento."
    )
    narrative = [
        f"{config['name']}. {activity}",
        job_text+" "+inflation_text,
        synthesis,
        config["chain"],
        bank_text,
        f"{pricing} {rates_text}",
        "Alternativa: "+config["counter"]+" Da verificare: "+config["next"]+".",
    ]
    return {
        "currency":ccy, "country":config["name"],"bank":config["bank"],
        "mandate_scope":spec["mandate_focus"],
        "judgement":"SCENARIO_DA_VERIFICARE_NON_TRADE",
        "observed_axes":{
            "GDP_quarterly_pct":g,
            "inflation_headline_three_observations_pp":i,
            "unemployment_three_observations_pp":j,
        },
        "archived_transmission_context":archived,
        "macro_evidence_status":"REVISED_DESCRIPTIVE_NOT_FIRST_RELEASE_PIT",
        "causal_hypothesis":config["chain"],
        "alternative_hypothesis":config["counter"],
        "central_bank_conditional_reaction":bank_text,
        "central_bank_last_observed":{"rate_pct":cb["rate"],"decision_date":cb["last_date"]},
        "rates_and_pricing":{
            "ois_status":quality,"ois_quality":curve["quality"],"ois_as_of":curve["as_of"],
            "six_month_quality":pricing_type,
            "six_month_rate_pct":six.get("rate") if quality=="GREEN_OFFICIAL" else None,
            "government_yield_2y_pct":rate["2Y"],"government_yield_10y_pct":rate["10Y"],
            "yield_as_of":rate["date"],"yield_freshness":price_quality,
            "official_pre_release_consensus":None,
            "same_contract_event_repricing_bp":None,
        },
        "what_to_monitor":config["next"],
        "counter_evidence":config["counter"],
        "coverage_limit":quality_note,
        "narrative_it":narrative,
        "thesis_strength":None,"trade_attractiveness":None,
        "automatic_fx_signal":None,"expected_return":None
    }

def build(*,today:date,root=ROOT):
    d,fingerprints=sources(root)
    require(d["method"]["schema"]=="GMFQ_G8_CAUSAL_CB_REACTION_COUNTRY_BOOK_V1",
            "unknown causal method")
    require(d["macro"]["schema"]=="GMFQ_FXV2_MACRO_CANDIDATE_8X3_DESCRIPTIVE_V1"
            and d["macro"]["published_source_lineage"]=="MACRO_V3_OBSERVED_REVISED_NOT_PIT"
            and d["macro"]["eligible_for_live_fx_signals"] is False
            and d["macro"]["eligible_for_backtests"] is False,
            "no current revised 24-axis research contract")
    require(date.fromisoformat(d["macro"]["as_of_research"])<=today,
            "future macro snapshot")
    require(set(d["method"]["countries"])==set(FX)
            and set(d["macro"]["features"])==set(FX)
            and set(d["sector_archive"]["currencies"])==set(FX)
            and set(d["cb"])==set(FX)
            and set(d["ois"]["currencies"])==set(FX)
            and set(d["rates"])==set(FX),
            "G8 source coverage incomplete")
    countries={c:study_country(c,d,today) for c in FX}
    require(len(countries)==8 and all(len(v["narrative_it"])>=6 for v in countries.values()),
            "incomplete country book")
    return {
        "schema":SCHEMA,
        "research_run_date_rome":today.isoformat(),
        "macro_observation_snapshot_as_of":d["macro"]["as_of_research"],
        "sector_archive_snapshot_created":d["sector_archive"]["snapshot_created"],
        "source_files":PATHS,
        "source_sha256":fingerprints,
        "scope":{"currencies":8,"macro_axes":24,"fx_pair_universe":28,
                 "fx_pairs_scored":0,"fx_signals_created":0,
                 "site_modified":False,"official_historic_PIT":False,
                 "central_bank_decision_forecast":False,
                 "safe_to_update_D":False,"safe_to_update_28_pair_ranking":False},
        "limitations":[
          "Descriptive revised country macro; not historical as-released PIT.",
          "Consumer and firm detail is archived, not confirmed contemporaneous.",
          "OIS/futures vary by source status and may not directly infer future policy actions.",
          "No frozen pre-release consensus or event-study repricing.",
          "No mechanically inferred direction, probability, or profitability of FX trades."
        ],
        "countries":countries,
    }

def markdown(book):
    lines=[
        "# Country Book G8 · Pilot di ricerca — NON segnali",
        f"**Revisione dati macro:** {book['macro_observation_snapshot_as_of']} · "
        f"**Esecuzione:** {book['research_run_date_rome']} · "
        f"**Archivio settoriale:** {book['sector_archive_snapshot_created']}",
        "",
        "Gli otto testi seguenti distinguono dati osservati, meccanismi ipotetici, "
        "funzione di reazione condizionata e qualità del pricing. "
        "Non sono consigli di trading né una fotografia point-in-time del passato.",
        ""
    ]
    for c in FX:
        row=book["countries"][c]
        lines += [f"## {c} · {row['country']} / {row['bank']}",""]
        lines += [s+"\n" for s in row["narrative_it"]]
        lines += [f"**Limite:** {row['coverage_limit']}",""]
        lines += ["**Archivi imprese/famiglie (NON conferme recenti):** "+
            "; ".join(f"{x['label']}: {x['value']} ({x['observation_period']})"
                      for x in row["archived_transmission_context"]),"","---",""]
    return "\n".join(lines)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--json-out",type=Path)
    parser.add_argument("--md-out",type=Path)
    args=parser.parse_args()
    book=build(today=datetime.now(ZoneInfo("Europe/Rome")).date())
    for path,body in ((args.json_out,json.dumps(book,indent=2,ensure_ascii=False)+"\n"),
                      (args.md_out,markdown(book))):
        if path:
            require(path.resolve().is_relative_to(Path("/tmp")),
                    "research previews must remain in /tmp; never site/ or live_data/")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(body,encoding="utf-8")
    print(json.dumps({
        "status":"G8_CAUSAL_PILOT_RESEARCH_ONLY",
        "macro_as_of":book["macro_observation_snapshot_as_of"],
        "currencies":list(book["countries"]),
        "signal_count":0,
        "pricing_quality_by_currency":{
            c:book["countries"][c]["rates_and_pricing"]["six_month_quality"] for c in FX},
        "stale_2y_currencies":[c for c in FX if
            book["countries"][c]["rates_and_pricing"]["yield_freshness"]=="2Y_STALE_NOT_SAME_DAY"]
    },ensure_ascii=False,sort_keys=True))
    for c in FX:
        r=book["countries"][c]
        print(f"{c} | "+r["narrative_it"][0]+" "+r["narrative_it"][1])
    return 0

if __name__=="__main__":
    raise SystemExit(main())
