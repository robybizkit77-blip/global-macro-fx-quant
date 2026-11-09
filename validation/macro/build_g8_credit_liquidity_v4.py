#!/usr/bin/env python3
"""G8 credit, liquidity and financial-condition bridge — research only, V4.

Never treat bank lending stocks as originations or easier standards; never
translate CB assets/reserves into current liquidity for asset prices. The
period is an economic observation, NOT a verified release timestamp.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import calendar
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro import build_g8_inflation_transmission_v3 as v3

SCHEMA="GMFQ_G8_CREDIT_LIQUIDITY_TRANSMISSION_RESEARCH_V4"
FX=v3.v2.v1.FX
ROOT=v3.ROOT
SERIES_FILE=v3.SOURCE
ROLES=("credit_supply","borrowing_cost","credit_quantity","liquidity","conditions")
# semantic_kind, field IDs. Some countries intentionally have no direct
# bank standards, lending rates, or stress index: do not guess substitutes.
SELECTORS={
    "USD":{
      "credit_supply":[("survey_tightening","US_SLOOS_CI_LARGE_MIDDLE_history_value")],
      "borrowing_cost":[("borrower_rate","US_MORTGAGE30US_history_MORTGAGE30US")],
      "credit_quantity":[("loan_stock","US_TOTBKCR_history_value")],
      "liquidity":[("bank_reserves_stock","US_WRESBAL_history_value")],
      "conditions":[("financial_stress_index","US_NFCI_history_value")]},
    "EUR":{
      "credit_supply":[("survey_tightening","EA_BLS_CREDIT_STANDARDS_ENTERPRISES_history_value"),
                       ("survey_demand","EA_BLS_LOAN_DEMAND_ENTERPRISES_history_value")],
      "borrowing_cost":[],
      "credit_quantity":[("loan_stock","EA_HH_LOANS_history_value")],
      "liquidity":[("cb_balance_sheet_stock","EA_EUROSYSTEM_TOTAL_ASSETS_history_value")],
      "conditions":[("financial_stress_index","EA_CISS_history_value")]},
    "GBP":{
      "credit_supply":[("survey_unverified_sign","UK_CCS_CORPORATE_CREDIT_AVAILABILITY_history_value")],
      "borrowing_cost":[("borrower_rate","UK_MORTGAGE_RATE_2Y_75LTV_history_value")],
      "credit_quantity":[("mortgage_approvals","UK_MORTGAGE_APPROVALS_HOUSE_PURCHASE_SA_history_value")],
      "liquidity":[("bank_reserves_stock","UK_BOE_RESERVE_BALANCES_history_value")],
      "conditions":[]},
    "JPY":{
      "credit_supply":[("survey_unverified_sign","JP_TANKAN_LENDING_ATTITUDE_history_value")],
      "borrowing_cost":[("borrower_rate","JP_NEW_LOANS_RATE_history_value")],
      "credit_quantity":[("loan_stock","JP_BANK_CREDIT_DOMESTIC_BANKS_history_value")],
      "liquidity":[("bank_reserves_stock","JP_BOJ_RESERVE_BALANCES_history_value")],
      "conditions":[("exchange_rate_index","JP_YEN_BROAD_NEER_history_value")]},
    "CHF":{
      "credit_supply":[],
      "borrowing_cost":[("borrower_rate","CH_MORTGAGE_RATE_FIXED_3_5Y_history_value")],
      "credit_quantity":[("loan_stock","CH_BANK_CREDIT_CUSTOMERS_history_value"),
                         ("loan_stock","CH_MORTGAGE_CREDIT_DOMESTIC_history_value")],
      "liquidity":[("bank_reserves_stock","CH_SNB_SIGHT_DEPOSITS_DOMESTIC_BANKS_history_value")],
      "conditions":[("exchange_rate_index","CH_NEER_NOMINAL_OVERALL_history_value")]},
    "CAD":{
      "credit_supply":[("survey_unverified_sign","CA_SLOS_BUSINESS_LENDING_history_value")],
      "borrowing_cost":[("borrower_rate","CA_BUSINESS_LOAN_RATE_NEW_history_value")],
      "credit_quantity":[("loan_stock","CA_BUSINESS_LOANS_OUTSTANDING_history_value"),
                         ("loan_stock","CA_MORTGAGE_OUTSTANDING_UNINSURED_history_value")],
      "liquidity":[("cb_balance_sheet_stock","CA_BOC_TOTAL_ASSETS_history_value")],
      "conditions":[]},
    "AUD":{
      "credit_supply":[],
      "borrowing_cost":[("borrower_rate","AU_MORTGAGE_RATE_OWNER_OCC_OUTSTANDING_history_value")],
      "credit_quantity":[("loan_stock","AU_CREDIT_BUSINESS_CURRENT_SA_history_value"),
                         ("loan_stock","AU_CREDIT_OWNER_OCC_HOUSING_SA_history_value")],
      "liquidity":[("bank_reserves_stock","AU_EXCHANGE_SETTLEMENT_BALANCES_history_value")],
      "conditions":[("exchange_rate_index","AU_AUD_TWI_history_value")]},
    "NZD":{
      "credit_supply":[],"borrowing_cost":[],"credit_quantity":[],
      "liquidity":[],"conditions":[]},
}
# Exactly five country-specific transmission stories. No claims of proven causation.
MECHANISMS={
    "USD":{
      "main":"Se le banche irrigidiscono davvero gli standard, alcune aziende possono frenare investimenti e assunzioni; il reddito da lavoro condizionerebbe successivamente i consumi.",
      "counter":"Se credito e domanda restano accessibili, un SLOOS restrittivo potrebbe non tradursi subito in attività debole.",
      "monitor":"SLOOS, prestiti originati e insolvenze, tassi sui mutui, payrolls settoriali e PCE reale"},
    "EUR":{
      "main":"Se gli standard bancari rimangono restrittivi nonostante una minore intensità di irrigidimento, il credito può trasmettere la debolezza industriale a investimenti e lavoro.",
      "counter":"Il recupero della domanda di prestiti e dei servizi potrebbe limitare la decelerazione, mentre salari e HICP restano da verificare.",
      "monitor":"BLS domanda/offerta, tassi sui nuovi prestiti, prestiti netti alle PMI e HICP servizi"},
    "GBP":{
      "main":"Mutui onerosi e minori approvazioni potrebbero comprimere gli acquisti immobiliari e il reddito spendibile, con effetti ritardati sulla domanda interna.",
      "counter":"Un mercato del lavoro più resistente e salari elevati potrebbero attenuare il freno sui consumi.",
      "monitor":"rifinanziamenti mutui, tassi effettivi delle famiglie, approvazioni, salari e CPI servizi"},
    "JPY":{
      "main":"Il costo effettivo dei nuovi prestiti e il credito bancario aiutano a verificare se la normalizzazione BoJ limita gli investimenti o resta assorbibile dalle imprese.",
      "counter":"Se salari reali e investimenti tengono, una crescita del credito può convivere con rialzi graduali dei tassi.",
      "monitor":"Tankan lending, nuovi prestiti, retribuzioni reali, investimenti e consumi domestici"},
    "CHF":{
      "main":"Tassi ipotecari e consistenze di credito possono indicare la trasmissione interna, mentre il CHF influenza direttamente i prezzi importati e la competitività delle imprese.",
      "counter":"Un cambio meno forte o domanda estera migliore potrebbero attenuare la pressione disinflazionistica anche con crescita moderata.",
      "monitor":"condizioni sui nuovi prestiti, CHF effettivo, CPI domestico/importato e export"},
    "CAD":{
      "main":"Il costo dei nuovi prestiti e i rinnovi ipotecari potrebbero modificare i margini delle imprese e la spesa delle famiglie con ritardo rispetto ai cambiamenti di policy BoC.",
      "counter":"Se redditi reali e domanda USA resistono, la trasmissione dei mutui potrebbe pesare meno sulla crescita aggregata.",
      "monitor":"mutui in rinnovo, dati di origination, standard credito, salari, retail reale e trim/median"},
    "AUD":{
      "main":"Il costo dei mutui e il credito alle imprese possono trasmettere le scelte RBA a famiglie e investimento, mentre Cina e commodity influenzano la domanda estera.",
      "counter":"Lavoro resistente e prezzi dei servizi persistenti potrebbero impedire allentamenti anche con famiglie indebitate.",
      "monitor":"rate sui nuovi mutui, credito e insolvenze, spesa reale, ore lavorate, CPI trimmed mean"},
    "NZD":{
      "main":"La sensibilità di famiglie e imprese ai mutui resta un'importante ipotesi, ma qui non ci sono serie dirette recenti di credito e liquidità per valutarla.",
      "counter":"Prezzi non-tradable o una ripresa della domanda possono cambiare la risposta RBNZ nonostante un PIL debole.",
      "monitor":"RBNZ credito per settore, tassi effettivi mutui, flussi nuovi prestiti, debito famiglie e condizioni bancarie"},
}

KINDS={
    "survey_tightening":("Sondaggio standard credito, saldo netto positivo = irrigidimento", "survey_points"),
    "survey_demand":("Sondaggio domanda di prestiti, saldo non equivale a erogazioni", "survey_points"),
    "survey_unverified_sign":("Sondaggio credito, convenzione di segno da verificare", "survey_unverified"),
    "borrower_rate":("Tasso effettivo applicato a prestiti/mutui, non rendimento governativo", "rate"),
    "loan_stock":("Consistenza del credito in essere, NON flusso di nuove erogazioni", "stock"),
    "mortgage_approvals":("Numero approvazioni di mutui, NON flusso monetario erogato", "approvals"),
    "bank_reserves_stock":("Saldo di riserve/depositi bancari, NON liquidità investibile netta", "balance"),
    "cb_balance_sheet_stock":("Totale bilancio banca centrale, NON shock causale di liquidità", "balance"),
    "financial_stress_index":("Indice di stress/condizioni finanziarie, più alto = condizioni più tese", "index"),
    "exchange_rate_index":("Cambio effettivo nominale, NON indice di stress del credito", "fx_index"),
}

def require(ok,msg):
    if not ok:
        raise ValueError("G8_CREDIT_V4_REJECTED: "+msg)

def parse_period(raw,freq):
    txt=str(raw).strip()
    week=re.fullmatch(r"(\d{4})-W(\d{2})",txt)
    if week:
        y,w=map(int,week.groups())
        return date.fromisocalendar(y,w,7),"W"
    if re.fullmatch(r"\d{4}-?Q[1-4]",txt):
        return v3.v2.observation_end(txt,"Q")
    if re.fullmatch(r"\d{4}/\d{2}",txt):
        return v3.v2.observation_end(txt,freq)
    if re.fullmatch(r"\d{4}-\d{2}",txt):
        return v3.v2.observation_end(txt,freq)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*",txt):
        day=date.fromisoformat(txt[:10])
    else:
        day=None
        for pattern in ("%d %b %Y","%d/%m/%Y","%d-%b-%Y","%b-%y"):
            try:
                day=datetime.strptime(txt,pattern).date()
                break
            except ValueError:
                continue
        require(day is not None,"unsupported observation date token "+txt)
    return (date(day.year,day.month,calendar.monthrange(day.year,day.month)[1])
            if freq in ("M","Q") else day),freq

def observation(row,kind,*,today):
    require(kind in KINDS,row["id"]+" unsupported credit semantic kind")
    dates,vals=row.get("dates"),row.get("values")
    require(isinstance(dates,list) and isinstance(vals,list)
            and len(dates)==len(vals) and len(vals)>=2,row["id"]+" malformed history")
    require(row.get("last_date")==dates[-1],row["id"]+" last_date mismatch")
    require(v3.v2.v1.finite(row.get("last_value"))
            and all(v3.v2.v1.finite(x) for x in vals[-2:]),
            row["id"]+" non-finite credit observations")
    require(math.isclose(row["last_value"],vals[-1],rel_tol=1e-10,abs_tol=1e-8),
            row["id"]+" last_value mismatch")
    freq=str(row.get("frequency") or "").upper()
    if freq not in ("M","Q","W","D"):
        sample=str(dates[-1])
        freq="Q" if re.fullmatch(r"\d{4}-?Q[1-4]",sample) else (
            "W" if re.fullmatch(r"\d{4}-W\d{2}",sample) else "M")
    curr,_=parse_period(dates[-1],freq)
    prev,_=parse_period(dates[-2],freq)
    require(prev<curr<=today,row["id"]+" non-ordered or future period")
    gap=(curr-prev).days
    maxgap={"D":5,"W":12,"M":45,"Q":106}[freq]
    comparable=gap<=maxgap
    diff=round(vals[-1]-vals[-2],6) if comparable else None
    age=(today-curr).days
    rec={"D":7,"W":21,"M":75,"Q":135}[freq]
    dated={"D":21,"W":56,"M":150,"Q":210}[freq]
    status=("RECENT_PERIOD_RELEASE_NOT_VERIFIED" if age<=rec else
            "OLDER_PERIOD_NOT_CURRENT" if age<=dated else
            "STALE_HISTORICAL_PERIOD")
    group=KINDS[kind][1]
    delta_pct=(round(100*diff/vals[-2],4) if
               comparable and group in ("stock","balance") and vals[-2]>0 else None)
    change_bp=(round(100*diff,2) if comparable and group=="rate" else None)
    # Positive standards balance = NET tightening even when decelerating.
    tightening=("NET_TIGHTENING" if vals[-1]>0.01 else
                "NET_EASING" if vals[-1]<-.01 else "NEUTRAL_BALANCE") if kind=="survey_tightening" else None
    return {
        "id":row["id"],"label":row["label"],"kind":kind,"semantic_guardrail":KINDS[kind][0],
        "observation_period":dates[-1],"prior_observation_period":dates[-2],
        "period_end":curr.isoformat(),"period_age_days":age,"frequency":freq,
        "current":vals[-1],"previous":vals[-2],"unit":row.get("unit") or "UNIT_UNSPECIFIED",
        "change_raw_units":diff,"change_bp_if_borrower_rate":change_bp,
        "within_series_stock_change_pct_not_credit_growth_rate":delta_pct,
        "net_tightening_status_if_verified":tightening,
        "source_file":row.get("source_file"),"status":status,
        "comparable_adjacent_periods":comparable,
        "effective_release_at":None,"data_vintage":"REVISED_NOT_FIRST_RELEASE_PIT",
        "source_label_is_not_proven_causal_effect":True,
    }

def fmtval(x):
    return f"{x:.2f}".replace(".",",")

def describe(role,rows):
    names={"credit_supply":"Accesso al credito",
           "borrowing_cost":"Costo effettivo del finanziamento",
           "credit_quantity":"Quantità e richieste di credito",
           "liquidity":"Bilanci e riserve",
           "conditions":"Condizioni finanziarie e cambio"}
    if not rows:
        return names[role]+": non abbiamo una serie diretta utilizzabile; nessuna inferenza."
    sentences=[]
    for d in rows[:2]:
        val=fmtval(d["current"])
        period=d["observation_period"]
        move=d["change_raw_units"]
        if move is None:
            shift="confronto con il dato precedente non verificabile"
        elif d["kind"]=="borrower_rate":
            shift=f"{d['change_bp_if_borrower_rate']:+.1f} pb sul tasso applicato"
        elif d["kind"]=="survey_tightening":
            is_tight=d["net_tightening_status_if_verified"]=="NET_TIGHTENING"
            shift=("saldo ancora positivo di irrigidimento; " if is_tight
                   else "saldo non positivo di irrigidimento; ")+
                ("intensità in aumento" if move>0 else
                 "intensità in diminuzione" if move<0 else
                 "intensità stabile")
        elif d["kind"] in ("loan_stock","bank_reserves_stock","cb_balance_sheet_stock"):
            shift=(f"{d['within_series_stock_change_pct_not_credit_growth_rate']:+.2f}% "
                   "rispetto al periodo prima (stock, non erogazioni)"
                   if d["within_series_stock_change_pct_not_credit_growth_rate"] is not None
                   else "variazione stock non verificabile")
        else:
            shift=("in aumento" if move>0 else "in calo" if move<0 else "invariato")
        sentences.append(
            f"{d['label']}: {val} ({period}); {shift}. "+
            ("Periodo datato; non descrive necessariamente le condizioni di oggi."
             if d["status"]!="RECENT_PERIOD_RELEASE_NOT_VERIFIED"
             else "Periodo relativamente recente, ma non sappiamo quando il dato fosse pubblicato.")
        )
    return names[role]+": "+" ".join(sentences)

def build(*,today,root=ROOT):
    base=v3.build(today=today,root=root)
    raw=(root/SERIES_FILE).read_bytes()
    series=json.loads(raw)
    require(tuple(base["countries"])==FX and set(SELECTORS)==set(FX)
            and set(series)==set(FX),"G8 coverage mismatch")
    countries={}
    missing=[]
    old=[]
    for c in FX:
        prior=base["countries"][c]
        ix={x["id"]:x for x in series[c]}
        require(len(ix)==len(series[c]),c+" duplicate series")
        roles={}
        for role in ROLES:
            selected=SELECTORS[c][role]
            require(len(set(x[1] for x in selected))==len(selected),
                    c+" duplicate selected series")
            records=[]
            for kind,ident in selected:
                require(ident in ix,c+" missing "+ident)
                records.append(observation(ix[ident],kind,today=today))
            roles[role]=records
            if not records:
                missing.append(c+"."+role)
            elif not all(x["status"]=="RECENT_PERIOD_RELEASE_NOT_VERIFIED" for x in records):
                old.append(c+"."+role)
        rate=prior["rates_and_pricing"]
        require(rate["yield_as_of"] and rate["yield_freshness"],c+" missing front-end rate reference")
        # 'FULL_CURRENT_OFFICIAL' can mean the source was official, NOT that the
        # observation is recent. Reuse V1 date-based age, not an optimistic label.
        rates_text=(
            f"2Y {fmtval(rate['government_yield_2y_pct'])}% e "
            f"10Y {fmtval(rate['government_yield_10y_pct'])}% "
            f"(osservazione {rate['yield_as_of']}; {rate['yield_freshness']}). "
            "Sono rendimenti governativi: non equivalgono a tassi dei nuovi prestiti, "
            "né la loro variazione può essere attribuita automaticamente alla banca centrale."
        )
        hypothesis=MECHANISMS[c]
        lines=[
            prior["inflation_narrative_it"][0],
            describe("credit_supply",roles["credit_supply"]),
            describe("borrowing_cost",roles["borrowing_cost"]),
            describe("credit_quantity",roles["credit_quantity"]),
            describe("liquidity",roles["liquidity"]),
            describe("conditions",roles["conditions"]),
            "Trasmissione economica, IPOTESI: "+hypothesis["main"],
            "Risposta banca centrale condizionata: "+prior["central_bank_conditional_reaction"],
            "Mercato dei tassi: "+rates_text,
            "Scenario contrario: "+hypothesis["counter"],
            "Conferme e invalidazioni da cercare: "+hypothesis["monitor"]+".",
            "Limite: stock bancari, saldi di riserve, survey e rendimenti sono "
            "oggetti differenti. Senza dati rilasciati point-in-time, domanda/offerta "
            "di prestiti separate e reazione dei prezzi pre/post-evento non si può "
            "dimostrare il nesso causale né produrre un trade FX.",
        ]
        countries[c]={
            **prior,
            "credit_liquidity_channels":roles,
            "credit_liquidity_narrative_it":lines,
            "monetary_transmission_hypothesis":hypothesis["main"],
            "counter_scenario":hypothesis["counter"],
            "what_to_monitor":hypothesis["monitor"],
            "coverage_missing_roles":[r for r in ROLES if not roles[r]],
            "coverage_older_roles":[r for r in ROLES if roles[r] and
                not all(v["status"]=="RECENT_PERIOD_RELEASE_NOT_VERIFIED" for v in roles[r])],
            "source_releases_verified":False,
            "credit_transmission_causally_verified":False,
            "actual_borrower_rate_is_government_yield":False,
            "liquidity_stock_is_automatic_risk_flow":False,
            "ready_for_site":False,"ready_for_reports":False,
            "automatic_fx_signal":None,
        }
    return {
        "schema":SCHEMA,"research_run_date_rome":today.isoformat(),
        "base_country_book_schema":base["schema"],
        "source_paths":{**base["source_paths"],"credit_series":SERIES_FILE},
        "source_sha256":{**base["source_sha256"],"credit_series":hashlib.sha256(raw).hexdigest()},
        "coverage":{"countries":8,"channels_possible":8*len(ROLES),
                    "channels_missing":sorted(missing),
                    "channels_with_old_observations":sorted(old),
                    "verified_causal_credit_chains":0,"fx_signals":0},
        "limits":[
            "A lending stock is not loan supply, new origination, or loan demand.",
            "Central-bank assets and reserves alone do not prove tradeable liquidity or net easing.",
            "An increase in a NET TIGHTENING index is not the same as merely slower tightening.",
            "Actual borrower rates differ from government 2Y/10Y yield levels.",
            "FX effective index is not a credit-spread or financial stress measure.",
            "Observation period is not publication date; no first-release PIT provenance.",
            "No credit IG/HY spreads available from this source; no fake credit-risk conclusion.",
        ],
        "safe_for_site":False,"safe_for_reports":False,
        "safe_for_fx_ranking":False,"countries":countries,
    }

def markdown(book):
    lines=["# Macro G8 · Credito, liquidità e trasmissione monetaria V4",
           f"**Ricerca:** {book['research_run_date_rome']} · **NO SITO / REPORT / SEGNALI**",
           "",
           "Dati di credito e riserve sono stock, sondaggi, prezzi di finanziamento "
           "o indicatori: non sono convertibili direttamente fra loro né provano "
           "chi sta comprando/vendendo rischio. Periodi economici, non release time.",""]
    for c in FX:
        p=book["countries"][c]
        lines.extend([f"## {c} — {p['country']} · {p['bank']}",""])
        lines.extend([line+"\n" for line in p["credit_liquidity_narrative_it"]])
        lines.extend(["","**Buchi di copertura:** "+(", ".join(p["coverage_missing_roles"]) or
                                            "Nessun ruolo assente; verificare comunque freschezza e pubblicazione."),"","---",""])
    return "\n".join(lines)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--json-out",type=Path)
    parser.add_argument("--md-out",type=Path)
    args=parser.parse_args()
    book=build(today=datetime.now(ZoneInfo("Europe/Rome")).date())
    for path,content in ((args.json_out,json.dumps(book,ensure_ascii=False,indent=2)+"\n"),
                         (args.md_out,markdown(book))):
        if path:
            require(path.resolve().is_relative_to(Path("/tmp")),
                    "research previews only in /tmp")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content,encoding="utf-8")
    print(json.dumps({
        "status":SCHEMA,"currencies":list(book["countries"]),
        "missing":book["coverage"]["channels_missing"],
        "older":book["coverage"]["channels_with_old_observations"],
        "causal_chains_verified":0,"signals":0
    },ensure_ascii=False))
    for c in FX:
        p=book["countries"][c]
        print(c+" | "+p["credit_liquidity_narrative_it"][0]+" "+p["credit_liquidity_narrative_it"][6])
    return 0

if __name__=="__main__":
    raise SystemExit(main())
