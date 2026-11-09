#!/usr/bin/env python3
"""Inflation transmission research V3 for all G8 FX currencies.

Separate WHAT CHANGED (headline/core/services), WHY IT COULD CHANGE
(wages/demand/supply hypotheses), CENTRAL BANK REACTION, and WHAT IS PRICED.
Read-only preview. Revised monthly/quarterly histories, NOT first release/PIT.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro import build_g8_causal_evidence_bridge_v2 as v2

SCHEMA = "GMFQ_G8_INFLATION_TRANSMISSION_RESEARCH_V3"
ROOT = v2.v1.ROOT
SOURCE = v2.MACRO_SERIES
# The label "core" is not a universal statistical definition:
# US CPI ex-food/energy, JP core ex fresh food (includes energy),
# BoC trimmed/median, AU trimmed mean, NZ sectoral factor.
INFLATION = {
    "USD": {
        "headline": "US_CPIAUCSL_history_value",
        "core": ["US_CPILFESL_history_value","US_PCEPILFE_history_value"],
        "services": [], "wages": ["US_AHE_TOTAL_PRIVATE_history_value"],
        "expectations": [],
        "core_definition": "CPI ex cibo ed energia; core PCE è una MISURA DIVERSA con ritardo distinto.",
        "wages_definition": "Salario orario nominale osservato: non indica di per sé potere d'acquisto reale.",
        "reaction": "La Fed deve distinguere shock energia/beni da persistenza nei servizi e considerare l'occupazione: un CPI headline alto non rende automatico un rialzo.",
        "check": "Core PCE e servizi, salari rispetto alla produttività, PCE reale, prezzi energia e repricing Fed Funds/2Y.",
    },
    "EUR": {
        "headline": "EA_HICP_HEADLINE_YOY_history_value",
        "core": ["EA_HICP_CORE_YOY_history_value"],
        "services": ["EA_HICP_SERVICES_YOY_history_value"],
        "wages": ["EA_NEGOTIATED_WAGES_YOY_history_value"],
        "expectations": [],
        "core_definition": "HICP core pubblicato (composizione specifica area euro), distinto da servizi e headline.",
        "wages_definition": "Salari negoziati YoY trimestrali; non necessariamente coprono tutti i contratti e i redditi.",
        "reaction": "La BCE deve pesare salari e servizi rispetto a credito, debolezza industriale e domanda; i prezzi energetici importati non equivalgono a pressione salariale.",
        "check": "HICP servizi/core aggiornati, salari negoziati, aspettative dei consumatori, credito e €STR/2Y.",
    },
    "GBP": {
        "headline": "UK_CPI_HEADLINE_YOY_history_value",
        "core": ["UK_CPI_CORE_YOY_history_value"],
        "services": [], "wages": [], "expectations": [],
        "core_definition": "CPI core UK; manca una serie CPI servizi selezionata nel source runtime.",
        "wages_definition": "Salari non disponibili come serie diretta selezionata in questo runtime.",
        "reaction": "La BoE non deve confondere domanda debole/mutui costosi con disinflazione dei servizi: senza dati sui salari e CPI servizi il quadro è incompleto.",
        "check": "CPI servizi UK, private regular pay, reddito e retail reali, mutui, SONIA OIS.",
    },
    "JPY": {
        "headline": "JP_CPI_HEADLINE_YOY_history_value",
        "core": ["JP_CPI_CORE_YOY_history_value"],
        "services": [], "wages": [], "expectations": [],
        "core_definition": "Core CPI GIAPPONESE esclude gli alimentari freschi ma può includere energia: NON è equivalente al core CPI USA.",
        "wages_definition": "Nessun indicatore diretto recente di salari nominali/reali selezionato.",
        "reaction": "Per la BoJ la normalizzazione richiede prezzi domestici e salari sostenibili; core nazionale in rialzo per energia non prova un ciclo domanda-salari.",
        "check": "Core-core giapponese ex energia, salari reali, spesa delle famiglie, servizi domestici, TONA/JGB.",
    },
    "CHF": {
        "headline": "CH_CPI_HEADLINE_YOY_history_value",
        "core": ["CH_CPI_CORE1_YOY_history_value"],
        "services": [], "wages": [], "expectations": [],
        "core_definition": "Inflazione core svizzera, da separare dal cambio e dai prezzi importati.",
        "wages_definition": "Nessun indicatore diretto di salari selezionato.",
        "reaction": "Per SNB contano inflazione domestica e previsione condizionata, ma anche il CHF come fonte di restrizione e disinflazione importata.",
        "check": "CPI importato/domestico, dinamica dei salari, tasso di cambio effettivo, previsione SNB, SARON.",
    },
    "CAD": {
        "headline": "CA_CPI_HEADLINE_YOY_history_value",
        "core": ["CA_CPI_TRIM_YOY_history_value","CA_CPI_MEDIAN_YOY_history_value"],
        "services": [], "wages": [],
        "expectations": ["CA_BOC_BOS_LEAD_INDICATORS_history_BOS_Price_Indicator"],
        "core_definition": "CPI-trim e CPI-median BoC sono due MISURE ROBUSTE differenti; non una media improvvisata.",
        "wages_definition": "Nessuna serie salariale diretta selezionata qui; domanda di lavoro non sostituisce i salari.",
        "reaction": "La BoC deve verificare la persistenza con trim/median e servizi, distinguendo prezzi energia e shelter dalla domanda che risente dei rinnovi mutui.",
        "check": "CPI-trim/median recenti, componenti shelter, salari, consumi reali, prezzi energia, CORRA/2Y.",
    },
    "AUD": {
        "headline": "AU_CPI_HEADLINE_Q_YOY_history_value",
        "core": ["AU_CPI_TRIMMED_MEAN_Q_YOY_history_value"],
        "services": [], "wages": ["AU_WPI_YOY_history_value"],
        "expectations": [],
        "other_frequencies": ["AU_CPI_HEADLINE_M_YOY_context_value","AU_CPI_TRIMMED_MEAN_M_YOY_context_value"],
        "core_definition": "Trimmed mean CPI trimestrale confrontata SOLO con headline trimestrale; proxy mensili non sono lo stesso contratto.",
        "wages_definition": "Wage Price Index YoY trimestrale, non direttamente salario reale né reddito disponibile.",
        "reaction": "La RBA ha un doppio mandato: deve confrontare trimmed mean persistente con fragilità dei mutui, spesa delle famiglie e lavoro.",
        "check": "Trimmed mean CPI, spesa delle famiglie reale, WPI, servizi/affitti, Cina, OIS/IB futures.",
    },
    "NZD": {
        "headline": "NZ_CPI_HEADLINE_YOY_history_value",
        "core": ["NZ_CORE_INFLATION_SFM_Q_history_value"],
        "services": [], "wages": [],
        "expectations": [
            "NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_CPI_1Y",
            "NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_CPI_2Y",
        ],
        "wage_expectations": ["NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_Wage_1Y"],
        "core_definition": "Sectoral factor model inflation trimestrale RBNZ; non ha identica struttura del CPI headline.",
        "wages_definition": "Disponibile SOLO un sondaggio di salari attesi, non salari realmente pagati.",
        "reaction": "La RBNZ deve verificare inflazione non-tradable e aspettative mentre il credito e i consumi si contraggono o recuperano; i sondaggi non sono prezzi effettivi.",
        "check": "Non-tradables CPI, salari osservati, aspettative 1Y/2Y, retail trimestrale aggiornato, OCR pricing.",
    },
}
# Evidence tags: DO NOT label indirect wage/cost/inflation surveys as direct values.
PROXY_KIND = {
    "CA_BOC_BOS_LEAD_INDICATORS_history_BOS_Price_Indicator": "BUSINESS_PRICE_SURVEY_INDICATOR_NOT_CPI",
    "NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_Wage_1Y": "SURVEY_WAGE_EXPECTATION_NOT_PAID_WAGES",
}
RISK_CHANNELS = {
    "USD": "Energia e prezzi importati potrebbero produrre shock headline; serve verifica delle componenti.",
    "EUR": "Energia importata e cambio possono alimentare headline prima dei servizi domestici.",
    "GBP": "Energia, cambio e servizi possono reagire con ritardi differenti.",
    "JPY": "JPY debole e importazioni energetiche possono far salire il core nazionale anche senza domanda più forte.",
    "CHF": "CHF e importazioni possono spingere la headline in direzioni differenti dalla domanda interna.",
    "CAD": "Petrolio e housing possono influenzare i prezzi senza raccontare tutto sulla domanda interna.",
    "AUD": "Importazioni, affitti ed energia si sommano alla pressione domestica, senza identità automatica.",
    "NZD": "Tradables/imports e non-tradables possono divergere; serve componente osservata.",
}

def require(ok,msg):
    if not ok:
        raise ValueError("G8_INFLATION_V3_REJECTED: "+msg)

def is_index(row):
    return row.get("unit","").lower().startswith("index ")

def is_yoy_rate(row):
    return ("yoy" in str(row.get("unit","")).lower()
            or "% yoy" in str(row.get("unit","")).lower()
            or str(row.get("unit","")).lower().strip() in
                {"percent","percent y/y","percent yoy sa"})

def pct(x):
    return f"{x:.2f}".replace(".",",")+"%"

def point_delta(v):
    return (("+" if v>0 else "")+f"{v:.2f}").replace(".",",")+" pp"

def yoy_index_values(row, current_index):
    # Look up the exact same observation month one calendar year earlier.
    dates=row["dates"]
    vals=row["values"]
    raw=dates[current_index]
    end,freq=v2.observation_end(raw,"M")
    target=(end.year-1,end.month)
    matches=[]
    for i in range(current_index):
        d,_=v2.observation_end(dates[i],"M")
        if (d.year,d.month)==target:
            matches.append(i)
    require(len(matches)==1,row["id"]+" missing/duplicate 12m index comparator")
    old=vals[matches[0]]
    new=vals[current_index]
    require(v2.v1.finite(old) and v2.v1.finite(new) and old>0,
            row["id"]+" invalid CPI index")
    return 100*(new/old-1)

def inflation_row(row, *, today, meaning):
    # RBNZ expectations are quarterly surveys even when tokens are YYYY-MM.
    # Without this override, a 3-month survey gap is falsely flagged as missing month.
    prepared=dict(row)
    if prepared["id"].startswith("NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_"):
        prepared["frequency"]="Q"
    base=v2.evidence_row(prepared,today=today)
    ident=base["id"]
    if is_index(row):
        require(base["frequency"]=="M",ident+" only monthly index YoY supported")
        rate=yoy_index_values(row,len(row["values"])-1)
        earlier=yoy_index_values(row,len(row["values"])-2)
        transform="DERIVED_YOY_FROM_MATCHED_12M_SEASONALLY_ADJUSTED_INDEX"
    elif meaning=="wages" and ident=="US_AHE_TOTAL_PRIVATE_history_value":
        rate=yoy_index_values(row,len(row["values"])-1)
        earlier=yoy_index_values(row,len(row["values"])-2)
        transform="NOMINAL_WAGE_YOY_DERIVED_FROM_HOURLY_PAY_LEVEL"
    elif is_yoy_rate(row):
        rate=row["last_value"]
        earlier=row["values"][-2]
        transform="DIRECT_YOY_RATE_PUBLISHED_IN_SOURCE"
    elif ident in PROXY_KIND or ident in INFLATION["NZD"].get("expectations",[]):
        rate=row["last_value"]
        earlier=row["values"][-2]
        transform=PROXY_KIND.get(ident,"SURVEY_EXPECTED_INFLATION_NOT_OBSERVED_CPI")
    else:
        raise ValueError("G8_INFLATION_V3_REJECTED: cannot classify scale for "+ident)
    require(v2.v1.finite(rate) and v2.v1.finite(earlier),ident+" non-finite derived inflation")
    delta=round(rate-earlier,4) if base["contiguous_latest_observations"] else None
    return {
        **base,
        "component":meaning,
        "transformation":transform,
        "latest_rate_pct_or_proxy_value":round(rate,4),
        "previous_rate_pct_or_proxy_value":round(earlier,4),
        "rate_change_pp_or_proxy_units":delta,
        "raw_unit":row.get("unit"),
        "is_observed_inflation":meaning in ("headline","core","services","monthly_context"),
        "is_actual_wage":meaning=="wages",
        "is_survey_not_price_or_paid_wage":meaning in ("expectations","wage_expectations"),
        "direction_tells_causality":False,
    }

def inflation_sentence(rec, *,kind):
    if not rec:
        return f"{kind}: componente non disponibile nel dataset G8 selezionato."
    v=rec[0]
    is_survey_index=(v["transformation"]=="BUSINESS_PRICE_SURVEY_INDICATOR_NOT_CPI")
    p=(f"{v['latest_rate_pct_or_proxy_value']:.2f}".replace(".",",")
       if is_survey_index else pct(v["latest_rate_pct_or_proxy_value"]))
    d=v["rate_change_pp_or_proxy_units"]
    if d is None:
        m="non è possibile confrontare due osservazioni contigue"
    else:
        m=("in aumento" if d>.05 else "in diminuzione" if d<-.05 else "sostanzialmente invariata")
        suffix=(" punti indice" if is_survey_index else " pp")
        formatted=(("+" if d>0 else "")+f"{d:.2f}").replace(".",",")
        m+=f" ({formatted}{suffix} rispetto alla rilevazione precedente)"
    status=v["status"]
    quality=(
        "Osservazione non recente"
        if status!="RECENT_PERIOD_NOT_RELEASE_VERIFIED"
        else "Periodo recente, ma data effettiva della pubblicazione non verificata"
    )
    return f"{kind}: {v['label']} {p} ({v['observation_period']}), {m}. {quality}."


def compare_recent_vs_three_observations(headline, macro_axis):
    """Compare direction of latest YoY change with the previous 3-observation window.

    Only if same country, period, frequency, meaning, and explicitly linked series.
    A three-observation change is NOT an acceleration and cannot imply causality.
    """
    c_id=macro_axis.get("series_id")
    same_alias=(isinstance(c_id,str) and c_id in headline["id"])
    same_frequency=(macro_axis.get("period_frequency")==headline["frequency"])
    try:
        e,_=v2.observation_end(macro_axis["period"],headline["frequency"])
        same_period=e.isoformat()==headline["observation_end_assumed"]
    except (ValueError,KeyError):
        same_period=False
    same_level=(v2.v1.finite(macro_axis.get("level")) and
                abs(macro_axis["level"]-headline["latest_rate_pct_or_proxy_value"])<=.06)
    recent=headline["rate_change_pp_or_proxy_units"]
    three=macro_axis.get("value")
    good=(same_alias and same_frequency and same_period and same_level
          and v2.v1.finite(recent) and v2.v1.finite(three))
    if not good:
        return {"status":"NOT_COMPARABLE_UNVERIFIED_ID_PERIOD_LEVEL_OR_CLOCK",
                "latest_change_pp":recent,
                "three_observations_change_pp":three,
                "matching_period":same_period,
                "matching_level":same_level,
                "matching_series_id":same_alias,
                "narrative_it":"Ultima variazione e finestra sulle tre osservazioni non confrontabili con sufficiente certezza: nessun punto di svolta dedotto."}
    def sign(v):
        return "UP" if v>.05 else "DOWN" if v<-.05 else "FLAT"
    a,b=sign(recent),sign(three)
    if a=="DOWN" and b=="UP":
        status="RECENT_DOWN_WHILE_THREE_OBSERVATIONS_UP"
        msg=("L'inflazione annua scende nell'ultima osservazione, ma resta "
             "in aumento rispetto alla finestra di tre osservazioni: "
             "possibile perdita di slancio, NON svolta già confermata.")
    elif a=="FLAT" and b=="UP":
        status="RECENT_FLAT_WHILE_THREE_OBSERVATIONS_UP"
        msg=("L'ultimo tasso annuo è stabile, mentre sulle tre osservazioni "
             "precedenti risulta ancora una crescita: "
             "possibile decelerazione da verificare nei dati successivi.")
    elif a=="UP" and b=="DOWN":
        status="RECENT_UP_WHILE_THREE_OBSERVATIONS_DOWN"
        msg=("Ultimo tasso annuo in rialzo nonostante un confronto più lungo "
             "ancora negativo: segnale di possibile cambiamento da confermare.")
    elif a==b:
        status="SAME_DIRECTION_ACROSS_WINDOWS"
        msg=("La direzione dell'ultima osservazione coincide con quella "
             "delle tre osservazioni; non prova da sola persistenza né "
             "una pressione da domanda.")
    else:
        status="MIXED_WINDOWS_NO_CONFIRMED_TURN"
        msg=("Le due finestre danno segnali diversi; è necessario verificare "
             "componenti, effetti base e pubblicazioni successive.")
    msg+=(" Ultima variazione "+point_delta(recent)+
          "; tre osservazioni "+point_delta(three)+".")
    return {"status":status,"latest_change_pp":round(recent,4),
            "three_observations_change_pp":round(three,4),
            "matching_period":True,"matching_level":True,"matching_series_id":True,
            "narrative_it":msg}


def build(*,today,root=ROOT):
    base=v2.build(today=today,root=root)
    raw=(root/SOURCE).read_bytes()
    series=json.loads(raw)
    require(tuple(base["countries"])==v2.v1.FX and set(series)==set(v2.v1.FX)
            and set(INFLATION)==set(v2.v1.FX),"G8 sources/selector mismatch")
    out={}
    missing=[]
    unverified_services=[]
    for c in v2.v1.FX:
        profile=INFLATION[c]
        index={x["id"]:x for x in series[c]}
        recs={}
        for component in ("headline","core","services","wages","expectations",
                          "other_frequencies","wage_expectations"):
            ids=([profile["headline"]] if component=="headline"
                 else profile.get(component,[]))
            require(len(ids)==len(set(ids)),c+" duplicate selector "+component)
            use_name="monthly_context" if component=="other_frequencies" else component
            recs[component]=[]
            for ident in ids:
                require(ident in index,c+" missing selected source "+ident)
                recs[component].append(inflation_row(index[ident],today=today,meaning=use_name))
            if not ids and component in ("services","wages","expectations"):
                missing.append(c+"."+component)
        require(len(recs["headline"])==1 and len(recs["core"])>=1,
                c+" missing headline or underlying inflation")
        headline=recs["headline"][0]
        core=recs["core"][0]
        window_compare=compare_recent_vs_three_observations(
            headline,
            base["countries"][c]["observed_axes"]["inflation_headline_three_observations_pp"])
        aligned=(headline["observation_end_assumed"]==core["observation_end_assumed"])
        core_is_recent=(core["status"]=="RECENT_PERIOD_NOT_RELEASE_VERIFIED")
        head_is_recent=(headline["status"]=="RECENT_PERIOD_NOT_RELEASE_VERIFIED")
        # A same-period headline/core spread can be reported as descriptive,
        # but it is not causal attribution nor proof of underlying demand.
        gap=round(headline["latest_rate_pct_or_proxy_value"]-
                  core["latest_rate_pct_or_proxy_value"],4) if aligned else None
        if not aligned:
            interpretation=(
                "Le osservazioni headline e core non appartengono allo stesso "
                "periodo: non posso attribuire la variazione headline alle "
                "componenti sottostanti né confrontarne lo spread."
            )
        elif not (core_is_recent and head_is_recent):
            interpretation=(
                "Headline e core sono confrontabili per periodo, ma almeno "
                "una non è recente: servono dati freschi prima di trarne "
                "conclusioni per la prossima riunione."
            )
        else:
            interpretation=(
                "Headline e core sono disponibili nello stesso periodo; la "
                "differenza è descrittiva, non prova una causa da domanda o offerta."
            )
        if not recs["services"]:
            unverified_services.append(c)
        survey_count=sum(len(recs[k]) for k in ("expectations","wage_expectations"))
        source_fact=(
            "Il driver domanda/salari NON è dimostrato: "
            "mancano prezzo dei servizi, salari osservati o domanda contemporanea, "
            "oppure le date non coincidono."
        )
        if not recs["services"]:
            source_fact=(
                "Non ho una componente prezzi dei servizi diretta in questa fonte. "
                "Non etichetto automaticamente l'inflazione come persistente o "
                "domestica."
            )
        supply=(
            f"Offerta/importazioni — {RISK_CHANNELS[c]} "
            "Non c'è qui una serie contemporanea certificata che ne "
            "attribuisca la quota all'inflazione osservata."
        )
        sentences=[
            base["countries"][c]["economic_transmission_narrative_it"][0],
            inflation_sentence(recs["headline"],kind="Headline"),
            inflation_sentence(recs["core"],kind="Inflazione sottostante"),
            inflation_sentence(recs["services"],kind="Servizi"),
            inflation_sentence(recs["wages"],kind="Salari"),
            inflation_sentence(recs["expectations"],kind="Aspettative"),
            interpretation,
            window_compare["narrative_it"],
            supply,
            "Imprese → lavoro → famiglie (periodi osservati, non causalità provata): "
            + " ".join(base["countries"][c]["economic_transmission_narrative_it"][2:5]),
            f"Meccanismo da testare: {source_fact} {profile['reaction']}",
            f"Conferme/invalidazioni da cercare: {profile['check']} "
            "Solo dopo confrontare la sorpresa con OIS, futures e 2Y, "
            "senza dedurre un segnale valutario automatico.",
        ]
        if c=="NZD":
            sentences[5]+=(" La previsione salariale disponibile è un sondaggio, "
                           "non il salario effettivamente realizzato.")
        if c=="AUD":
            sentences[2]+=(" Il dato mensile trimmed mean rimane un riferimento "
                           "separato e non viene sommato al trimestrale.")
        out[c]={
            **base["countries"][c],
            "inflation_layer":{
                "headline":recs["headline"],
                "core":recs["core"],
                "services":recs["services"],
                "wages":recs["wages"],
                "expectations":recs["expectations"],
                "monthly_context":recs["other_frequencies"],
                "wage_expectations":recs["wage_expectations"],
                "headline_core_same_economic_period":aligned,
                "latest_vs_three_observations":window_compare,
                "headline_core_yoy_gap_pp_same_period_only":gap,
                "core_definition":profile["core_definition"],
                "wage_evidence_definition":profile["wages_definition"],
                "demand_driven_inflation_verified":False,
                "supply_driven_inflation_verified":False,
                "persistent_services_inflation_verified":False,
                "central_bank_next_move_forecast":None,
                "supply_causality_proof":None,
                "series_available_are_revised_not_first_release":True,
                "public_release_dates_certified":False,
                "human_economic_review_required":True,
                "survey_count":survey_count,
            },
            "inflation_narrative_it":sentences,
            "inflation_research_status":"UNCERTIFIED_CAUSAL_INTERPRETATION",
            "ready_for_site":False,
            "ready_for_reports":False,
            "safe_for_fx_ranking":False,
            "automatic_fx_signal":None,
        }
    return {
        "schema":SCHEMA,
        "research_run_date_rome":today.isoformat(),
        "macro_as_of":base["macro_as_of"],
        "source_paths":{**base["source_paths"],"inflation_series":SOURCE},
        "source_sha256":{**base["source_shas"],"inflation_series":hashlib.sha256(raw).hexdigest()},
        "coverage":{
            "currencies":8,"core_available_all":8,
            "services_direct_missing":unverified_services,
            "selected_components_missing":sorted(missing),
            "driver_attributions_proven":0,"fx_signal_count":0,
        },
        "limitations":[
            "Observed inflation is not inflation caused by demand.",
            "Year-over-year levels, monthly index-derived YoY and quarterly rates are NOT interchangeable clocks.",
            "CPI core definitions differ by country; Japan excludes fresh food but includes energy.",
            "Unaligned core and headline observation periods cannot be spread or attributed.",
            "Household and labor releases may be stale; wage EXPECTATIONS are not actual wages.",
            "No official per-release consensus, component decomposition, or time-stamped OIS surprise attribution.",
            "Never infer 28 FX-pair trades or numerical bank decision probabilities."
        ],
        "safe_for_site":False,"safe_for_reports":False,
        "safe_for_28pair_signals":False,
        "countries":out,
    }

def markdown(book):
    lines=[
        "# Macro G8 · Inflazione, persistenza e funzione di reazione — V3",
        f"**As-of ricerca:** {book['research_run_date_rome']} · **Baseline macro:** "
        f"{book['macro_as_of']} · **SOLO RICERCA, NO SITO/REPORT AUTOMATICI**",
        "",
        "La stessa variazione headline può essere domanda, offerta o un mix. "
        "Senza dati componenti puntuali e rilascio/prezzi prima/dopo non è "
        "certificabile la spiegazione causale né il repricing. "
        "I dati disponibili sono revisionati, non prime pubblicazioni point-in-time.",
        "",
    ]
    for c in v2.v1.FX:
        row=book["countries"][c]
        lines += [f"## {c} · {row['country']} / {row['bank']}",""]
        lines += [s+"\n" for s in row["inflation_narrative_it"]]
        lines += ["**Definizione:** "+row["inflation_layer"]["core_definition"],"","---",""]
    return "\n".join(lines)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--json-out",type=Path)
    ap.add_argument("--md-out",type=Path)
    args=ap.parse_args()
    book=build(today=datetime.now(ZoneInfo("Europe/Rome")).date())
    for path,raw in ((args.json_out,json.dumps(book,indent=2,ensure_ascii=False)+"\n"),
                     (args.md_out,markdown(book))):
        if path:
            require(path.resolve().is_relative_to(Path("/tmp")),
                    "only /tmp research previews allowed")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(raw,encoding="utf-8")
    print(json.dumps({
        "schema":SCHEMA,"G8":list(book["countries"]),
        "core_currencies":book["coverage"]["core_available_all"],
        "services_missing":book["coverage"]["services_direct_missing"],
        "driver_attributions_proven":0,"signal_count":0
    },ensure_ascii=False))
    for c in v2.v1.FX:
        p=book["countries"][c]
        print(c+" | "+p["inflation_narrative_it"][0]+" "+p["inflation_narrative_it"][1])
    return 0

if __name__=="__main__":
    raise SystemExit(main())
