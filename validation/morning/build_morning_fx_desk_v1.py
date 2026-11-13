#!/usr/bin/env python3
"""Morning Macro/FX Desk V1: dated pre-session narrative and two relevant charts.

Uses only observations strictly preceding the edition date, separates
conditional hypotheses from evidence and never modifies the trading engine.
This deterministic desk narrative is not human/LLM editorial research.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
ROME = ZoneInfo("Europe/Rome")
SCHEMA = "GMFQ_MORNING_MACRO_FX_V1"
FILES = {
    "fx": "live_data/sections/ECB_G8_PRICE_HISTORY.json",
    "rates": "live_data/sections/NATIVE_RATES_DATA.json",
    "cb": "live_data/sections/NATIVE_CB_DATA.json",
    "events": "live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json",
    "pairs": "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
    "forecast": "validation/macro/MACRO_EXACT_METRIC_FORECAST_FIRST_SEEN_V9.jsonl",
    "actual": "validation/macro/MACRO_BLS_CPI_EXACT_ACTUAL_FIRST_SEEN_V10.jsonl",
}
COUNTRIES = {"USD": "Stati Uniti", "EUR": "Eurozona", "GBP": "Regno Unito",
             "JPY": "Giappone", "CHF": "Svizzera", "CAD": "Canada",
             "AUD": "Australia", "NZD": "Nuova Zelanda"}
FX_PAIRS = {"USD": "EURUSD", "EUR": "EURUSD", "GBP": "GBPUSD",
            "JPY": "USDJPY", "CHF": "EURCHF", "CAD": "USDCAD",
            "AUD": "AUDUSD", "NZD": "NZDUSD"}
YIELD_PAIRS = {"USD": ("USD","EUR"), "EUR": ("USD","EUR"), "GBP": ("GBP","USD"),
               "JPY": ("USD","JPY"), "CHF": ("EUR","CHF"), "CAD": ("USD","CAD"),
               "AUD": ("AUD","USD"), "NZD": ("NZD","USD")}
EVENT_SCORE = {"CENTRAL_BANK_DECISION": 6, "INFLATION": 5, "LABOUR": 4,
               "GROWTH": 3, "LABOUR_COST": 2}

def isnum(x):
    return type(x) in (int,float) and math.isfinite(x)

def to_date(s):
    try: return date.fromisoformat(s)
    except (TypeError, ValueError): return None

def pretty(s):
    d = s if isinstance(s,date) else to_date(s)
    return d.strftime("%d/%m/%Y") if d else "data non verificata"

def fmt(x,n=2):
    return f"{x:,.{n}f}".replace(",", "_").replace(".", ",").replace("_", ".") if isnum(x) else "n.d."

def signed(x,n=1,unit=""):
    if not isnum(x):
        return "n.d."
    precision=1 if n==0 and 0<abs(x)<0.5 else n
    rounded=round(x,precision)
    return ("+" if rounded>0 else "−" if rounded<0 else "")+fmt(abs(rounded),precision)+unit

def load(root,name):
    p=root/FILES[name]
    if name in ("forecast","actual"):
        return [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()] if p.exists() else []
    return json.loads(p.read_text(encoding="utf-8"))

def event_clock(evt):
    try:
        h,m=map(int,evt["time_local"].split(":"))
        local=datetime.combine(date.fromisoformat(evt["date"]),datetime.min.time()).replace(
            hour=h,minute=m,tzinfo=ZoneInfo(evt["timezone"]))
        return local.astimezone(ROME).strftime("%H:%M")
    except (KeyError,TypeError,ValueError):
        return "orario non verificato"

def choose_event(seed,day):
    events=[x for x in seed.get("events",[]) if x.get("ccy") in COUNTRIES
            and x.get("importance")=="HIGH" and to_date(x.get("date"))]
    today=[x for x in events if x["date"]==day.isoformat()]
    if today:
        return max(today,key=lambda x:(EVENT_SCORE.get(x.get("event_type"),0),x.get("ccy")=="USD")),"TODAY"
    recent=[x for x in events if day-timedelta(days=2)<=to_date(x["date"])<day
            and x.get("ccy")=="USD" and x.get("event_type")=="INFLATION"]
    if recent:
        return max(recent,key=lambda x:x["date"]),"PREVIOUS_CPI"
    # Upcoming is a *candidate* catalyst, not an automatic daily headline.
    # Provisional/medium-relevance events are not promoted above today's
    # observable FX/rates question just because the calendar has a slot.
    future=[x for x in events if day<to_date(x["date"])<=day+timedelta(days=2)
            and x.get("quality")=="OFFICIAL_CONFIRMED"
            and EVENT_SCORE.get(x.get("event_type"),0)>=3]
    if future:
        return min(future,key=lambda x:(x["date"],-EVENT_SCORE.get(x.get("event_type"),0))),"UPCOMING"
    return None,"RELATIVE_PRICING"

def get_pair_price(row,pair):
    base,quote=pair[:3],pair[3:]
    a=1 if base=="EUR" else row.get(base)
    b=1 if quote=="EUR" else row.get(quote)
    return b/a if isnum(a) and isnum(b) and a>0 else None

def skipped_market_sessions(last_seen,edition):
    """Missing completed weekdays between the last fixing and edition date."""
    last=to_date(last_seen)
    if not last or last>=edition:
        return 0
    return sum((last+timedelta(days=i)).weekday()<5
               for i in range(1,(edition-last).days))

def source_snapshots(d,day):
    fx=load(d,"fx")
    rows=sorted([x for x in fx.get("rows",[]) if to_date(x.get("Date"))
                 and to_date(x["Date"])<day
                 and all(isnum(x.get(k)) and x[k]>0 for k in COUNTRIES if k!="EUR")],
                key=lambda x:x["Date"])
    if len(rows)<8 or to_date(rows[-1]["Date"])<day-timedelta(days=6):
        raise ValueError("G8 fixing incomplete or too old for an opening edition")
    if skipped_market_sessions(rows[-1]["Date"],day)>1:
        raise ValueError("G8 missing more than one completed weekday: no current Morning story")
    rates=load(d,"rates")
    return rows,rates

def forecast_reference(rows,event,day):
    if not event:return ""
    found=[x for x in rows if x.get("currency")==event["ccy"]
           and event["date"] in x.get("event_key","")
           and (x.get("captured_at_utc") or "")[:10]<day.isoformat()
           and isnum(x.get("forecast_value_percent"))]
    if event["ccy"]=="USD" and event.get("event_type")=="INFLATION":
        h=next((x for x in found if x.get("metric_id")=="US_CPI_U_HEADLINE_MOM_SA"),None)
        c=next((x for x in found if x.get("metric_id")=="US_CPI_U_CORE_MOM_SA"),None)
        if h and c:
            return (f"Le stime secondarie rilevate prima del comunicato erano "
                    f"{signed(h['forecast_value_percent'],1,'%')} headline mensile e "
                    f"{signed(c['forecast_value_percent'],1,'%')} core mensile: "
                    "non sono un consenso da survey certificato. ")
    return "Non è disponibile un confronto completo con un consenso da survey certificato. "

def validate(report):
    if report.get("schema")!=SCHEMA or report.get("eligible_for_fx_signal") is not False:
        raise ValueError("Invalid desk editorial contract")
    day=report["edition_date"]
    if report["observation_cutoff_exclusive"]!=day:
        raise ValueError("Observation cutoff mismatch")
    if len(report.get("paragraphs",[]))!=4 or len(report.get("charts",[]))!=2:
        raise ValueError("Incomplete narrative or chart set")
    for p in report["paragraphs"]:
        if not isinstance(p,str) or len(p)<110:
            raise ValueError("Insufficient reasoning in a narrative paragraph")
    for ch in report["charts"]:
        if len(ch["points"])<8 or ch["as_of"]>=day:
            raise ValueError("Invalid dated chart history")
        if any(pt["date"]>=day or not isnum(pt["value"]) for pt in ch["points"]):
            raise ValueError("Future or non-finite chart values")
    if report["sources"]["fx_fixing"]>=day or report["sources"]["rates"]>=day:
        raise ValueError("Future information leaked into the morning")
    return report

def build(root,day,now,*,event_seed=None):
    if day.weekday()>4 or now.tzinfo is None:
        raise ValueError("Requires weekday and timezone-aware clock")
    if day>now.astimezone(ROME).date():
        raise ValueError("Cannot generate tomorrow's briefing as if already available")
    rows,rates=source_snapshots(root,day)
    seed=load(root,"events") if event_seed is None else event_seed
    cb=load(root,"cb");pairs=load(root,"pairs")
    event,stage=choose_event(seed,day)
    ccy=event["ccy"] if event else "USD"
    pair=FX_PAIRS[ccy]
    u,v=YIELD_PAIRS[ccy]
    series={}
    for currency in {u,v}:
        hist=(rates.get(currency) or {}).get("history2") or {}
        series[currency]={dt:value for dt,value in zip(hist.get("dates",[]),hist.get("values",[]))
                          if to_date(dt) and to_date(dt)<day and isnum(value)}
    common=sorted(set(series[u]) & set(series[v]))
    if len(common)<8 or to_date(common[-1])<day-timedelta(days=7):
        raise ValueError("Insufficient same-date 2Y observations")
    if skipped_market_sessions(common[-1],day)>2:
        raise ValueError("2Y differential too stale: cannot publish a current Morning story")
    cutoff=common[-1]
    first=next((x for x in common if to_date(x)>=to_date(cutoff)-timedelta(days=8)),common[0])
    spread=(series[u][cutoff]-series[v][cutoff])*100
    previous_spread=(series[u][first]-series[v][first])*100
    fxlast,fxprev=rows[-1],rows[-2]
    spot=get_pair_price(fxlast,pair);before=get_pair_price(fxprev,pair)
    if not isnum(spot) or not isnum(before):
        raise ValueError("FX pair missing from historical ECB fixing")
    spot_change=(spot/before-1)*100

    # Compare rate differentials and FX only at identical ECB fixing/rate dates.
    # The most recent FX fixing can be later than the last comparable 2Y quote:
    # state that gap rather than calling the movement confirmation.
    fx_by_date={r["Date"]:r for r in rows}
    aligned=[d for d in common if d in fx_by_date and isnum(get_pair_price(fx_by_date[d],pair))]
    if len(aligned)<4:
        raise ValueError("Insufficient same-day paired FX / 2Y evidence")
    aligned_last=aligned[-1]
    aligned_first=next((d for d in aligned if to_date(d)>=to_date(aligned_last)-timedelta(days=8)),aligned[0])
    if aligned_last==aligned_first:
        raise ValueError("Single aligned FX/rates date cannot establish a change")
    observed_diff=(series[u][aligned_last]-series[v][aligned_last]
                   -series[u][aligned_first]+series[v][aligned_first])*100
    aligned_fx_start=get_pair_price(fx_by_date[aligned_first],pair)
    aligned_fx_end=get_pair_price(fx_by_date[aligned_last],pair)
    observed_fx=(aligned_fx_end/aligned_fx_start-1)*100
    orient=-1 if pair=="EURUSD" else 1
    if abs(observed_diff)<1 or abs(observed_fx)<0.05:
        cross_reading=("La variazione comparabile è troppo piccola o poco direzionale "
                       "per certificare una conferma del differenziale nel cambio.")
        cross_state="NON_CONCLUSIVO"
    elif observed_diff*observed_fx*orient>0:
        cross_reading=("Nell'intervallo sulle stesse date, spread e prezzo si muovono "
                       "nella direzione economicamente coerente; non dimostrano causalità.")
        cross_state="COERENTE"
    else:
        cross_reading=("Nell'intervallo sulle stesse date, il prezzo non segue "
                       "la direzione suggerita dal differenziale: divergenza da indagare, "
                       "non automaticamente un'opportunità.")
        cross_state="DIVERGENTE"

    central=cb.get(ccy) or {}
    if to_date(central.get("last_date")) and to_date(central["last_date"])>=day:
        central={}
    meeting=central.get("last_date")
    cb_name=central.get("bank") or ccy
    cb_context=(f"La {cb_name} arriva alla seduta dopo la decisione del {pretty(meeting)}, "
                f"con tasso di riferimento {central.get('rate_text') or 'da verificare'}. "
                "Il punto economico è se crescita e inflazione consentano a quella banca "
                "di mantenere il percorso atteso, non il semplice livello del tasso.")
    if ccy=="USD" and meeting=="2026-10-28":
        cb_context=("Il contesto viene dalla Fed del 28 ottobre: tassi invariati al "
                    "3,75–4,00%, con due membri favorevoli a un rialzo. "
                    "La crescita continua a essere descritta come resistente, ma "
                    "l'inflazione rimane il vincolo per un eventuale allentamento. "
                    "Per il dollaro la domanda è quanto di questa prudenza sia già "
                    "incorporato nei tassi e quanto possa ancora sorprendere il mercato.")
    elif ccy=="GBP" and meeting=="2026-11-05":
        cb_context=("Arriviamo dalla decisione della BoE del 5 novembre: Bank Rate "
                    "portato al 4,00% con un rialzo di 25 punti base. "
                    "Questo rende la crescita britannica un test particolarmente "
                    "delicato: una banca centrale più restrittiva deve capire se "
                    "la domanda interna può reggere condizioni finanziarie più rigide. "
                    "Per la sterlina conta la differenza fra le nuove aspettative BoE "
                    "e quelle Fed, non il solo livello del Bank Rate.")
    rates_context=(f"Il differenziale governativo a due anni {u}–{v} è "
                   f"{signed(spread,0,' punti base')} al {pretty(cutoff)}; "
                   f"rispetto al {pretty(first)} è cambiato di "
                   f"{signed(spread-previous_spread,1,' pb')}. "
                   f"Il fixing BCE di {pair[:3]}/{pair[3:]} è {fmt(spot,4)} "
                   f"al {pretty(fxlast['Date'])}, {signed(spot_change,2,'%')} "
                   "sul fixing precedente. "
                   f"Confrontando invece rigorosamente le stesse date "
                   f"({pretty(aligned_first)}–{pretty(aligned_last)}), "
                   f"lo spread si è mosso di {signed(observed_diff,1,' pb')} "
                   f"e il cambio di {signed(observed_fx,2,'%')}. "
                   f"{cross_reading} Il livello del governativo 2Y non "
                   "sostituisce un confronto delle variazioni OIS/futures.")
    reference=forecast_reference(load(root,"forecast"),event,day)
    clock=event_clock(event) if event else None
    actual=load(root,"actual")
    # Explicitly validate signed, atomic issuer snapshots before narrative use.
    from validation.macro.capture_us_cpi_exact_actuals_v10 import validate_actual_log
    validate_actual_log(actual, load(root,"forecast"))
    # Even a future research replay cannot show an actual that was first
    # observed after this edition's opening; checked archive ≠ publisher PIT.
    observed_metrics=set()
    observed_values={}
    for entry in actual:
        if entry.get("event_key")!="USD|2026-11-10|INFLATION|Consumer Price Index":
            continue
        try:
            observed=datetime.fromisoformat(entry["observed_at_utc"].replace("Z","+00:00"))
            if observed.tzinfo and observed<=now and observed.astimezone(ROME).date()<day:
                observed_metrics.add(entry.get("metric_id"))
                observed_values[entry.get("metric_id")] = entry.get("actual_percent")
        except (ValueError,KeyError,TypeError):
            continue
    certified_actuals=len(observed_metrics)==4
    official_monthly=(observed_metrics >= {
        "US_CPI_U_HEADLINE_MOM_SA","US_CPI_U_CORE_MOM_SA"})
    pair_label=f"{pair[:3]}/{pair[3:]}"
    if stage=="TODAY":
        if ccy=="USD" and event.get("title")=="Consumer Price Index":
            headline=("Il CPI mette alla prova la prudenza della Fed: "
                      "il dollaro ha bisogno di una conferma dai differenziali.")
            lead=(f"Dopo la Fed del 28 ottobre arriviamo al CPI con un differenziale "
                  f"nominale a due anni USD–EUR di {signed(spread,0,' pb')}, "
                  f"ma il cambio {pair_label} non replica necessariamente quel vantaggio. "
                  "La domanda di oggi è se l'inflazione cambierà il percorso dei tassi "
                  "già incorporato nei prezzi, non se il numero sarà soltanto alto o basso.")
            catalyst=(f"Alle {clock} italiane è previsto il CPI USA "
                      f"({event.get('reference_period','periodo da verificare')}). {reference}"
                      "Conta la componente core e la sua persistenza: una sorpresa più forte "
                      "potrebbe rafforzare il rischio di Fed restrittiva più a lungo; una "
                      "decelerazione diffusa potrebbe fare il contrario. Prima servono "
                      "la pubblicazione e le revisioni ufficiali; poi variazioni confrontabili "
                      "Fed funds/€STR e la risposta di EUR/USD e USD/JPY.")
            scenario_main={"title":"CPI più persistente del previsto",
              "text":"La tesi USD si rafforza soltanto se il front-end USA sale rispetto all'Eurozona e il dollaro è confermato da più cambi, non da EUR/USD isolato."}
            scenario_alt={"title":"CPI più debole e disinflazione convincente",
              "text":"Il mercato potrebbe ridurre il rischio Fed restrittivo; cerchiamo calo relativo del front-end USD e prezzo FX coerente, separando effetto tassi e risk-off."}
        elif ccy=="USD" and event.get("title")=="Producer Price Index":
            headline=("PPI USA: il test per il dollaro è il repricing Fed, "
                      "non il solo dato sui prezzi alla produzione.")
            lead=("Il PPI di ottobre misura i prezzi alla produzione, "
                  "non l'inflazione al consumo. Per il dollaro conta se "
                  "la pubblicazione modifica le aspettative sul percorso "
                  "della Fed rispetto alle altre banche centrali. "
                  "Non possiamo conoscere in anticipo sorpresa, composizione "
                  "o reazione del Forex.")
            catalyst=(f"Alle {clock} italiane è previsto il Producer Price Index "
                      f"USA ({event.get('reference_period','periodo da verificare')}). "
                      f"{reference}"
                      "Prezzi alla produzione più persistenti possono alimentare "
                      "l'attenzione sui costi, ma il passaggio al CPI non è "
                      "automatico. Per interpretare il dato servono "
                      "consenso pre-pubblicazione, composizione e revisioni; "
                      "poi variazioni OIS/futures e risposte osservate "
                      "su EUR/USD e USD/JPY.")
            scenario_main={"title":"PPI sopra attese con pricing Fed più restrittivo",
              "text":"Una reazione USD più convincente richiede il rialzo relativo del front-end USA e conferma dei cambi. Il PPI non prova da solo inflazione persistente al consumo."}
            scenario_alt={"title":"PPI debole oppure risposta dei tassi assente",
              "text":"Una lettura più morbida può pesare sul dollaro soltanto se modifica il pricing monetario relativo. Prezzo e tassi in divergenza riducono la tesi."}
        elif ccy=="GBP" and event["event_type"]=="GROWTH":
            headline=("Dopo il rialzo della BoE, il PIL britannico mette alla prova "
                      "la tenuta della sterlina.")
            lead=("La BoE ha appena alzato il Bank Rate al 4,00%. Ora il mercato "
                  "deve capire se l'attività britannica possa reggere tassi più alti: "
                  "il PIL del terzo trimestre è un test sulla sostenibilità del percorso "
                  "monetario, non un numero da tradurre direttamente in acquisti di GBP.")
            catalyst=(f"Alle {clock} italiane arriva la prima stima del PIL UK "
                      f"({event.get('reference_period','periodo non verificato')}). {reference}"
                      "Una crescita migliore delle attese potrebbe limitare il rischio "
                      "di una BoE più accomodante, ma potrebbe anche essere già prezzata. "
                      "Una crescita più debole aumenterebbe il conflitto fra domanda e "
                      "stretta monetaria. Confronteremo BoE SONIA, front-end USA e "
                      "GBP/USD prima di attribuire un significato operativo.")
            scenario_main={"title":"PIL UK più resistente",
              "text":"Una crescita che regge la restrizione potrebbe sostenere GBP solo se il pricing BoE si irrigidisce rispetto alla Fed e il cambio conferma."}
            scenario_alt={"title":"PIL UK deludente",
              "text":"Il mercato potrebbe ridurre le attese di ulteriori rialzi BoE. Una sterlina debole senza conferma dei tassi richiederebbe prudenza sulla causalità."}
        else:
            headline=(f"{COUNTRIES[ccy]}: {event['title']} misura se la "
                      f"lettura macro per {ccy} regge alla prossima prova.")
            lead=(f"Arriviamo a {event['title']} con un differenziale di tasso "
                  f"{u}–{v} di {signed(spread,0,' pb')} e un prezzo {pair_label} "
                  "da confrontare con il percorso della banca centrale. "
                  "Non basta sapere che l'evento è importante: il punto è quale "
                  "parte delle aspettative possa ancora essere sorpresa.")
            catalyst=(f"Alle {clock} italiane è previsto {event['title']} "
                      f"({event.get('reference_period','periodo da verificare')}). {reference}"
                      "Una sorpresa va giudicata per composizione, revisioni, "
                      "aspettative pre-evento e confronto dei tassi relativi. "
                      "Se pricing e prezzo non concordano, la tesi resta aperta "
                      "anche in presenza di un dato economico chiaro.")
            scenario_main={"title":"Sorpresa restrittiva per la banca centrale",
              "text":f"Il segnale su {ccy} sarebbe più solido con aumento del differenziale relativo e conferma su {pair_label}."}
            scenario_alt={"title":"Sorpresa più accomodante",
              "text":f"Attese monetarie meno rigide potrebbero pesare su {ccy}; il cambio deve confermarlo senza che il rischio globale domini il movimento."}
        status="EVENT_TODAY"
        title=f"Oggi · {event['title']} · {clock}"
    elif stage=="PREVIOUS_CPI":
        headline=("Il CPI è passato, ma la direzione del dollaro dipende "
                  "da ciò che è verificabile nel repricing.")
        lead=("La giornata riparte dopo l'inflazione USA. La domanda ora non è "
              "ripetere la narrativa pre-CPI: dobbiamo distinguere ciò che sappiamo "
              "dal comunicato, ciò che è cambiato nelle attese Fed e la risposta "
              "effettiva del dollaro nelle varie coppie.")
        if official_monthly and not certified_actuals:
            actual_context=(
                "Il BLS ha pubblicato headline mensile "+
                signed(observed_values["US_CPI_U_HEADLINE_MOM_SA"],1,"%")+
                " e core mensile "+
                signed(observed_values["US_CPI_U_CORE_MOM_SA"],1,"%")+
                ". I tassi annuali ottobre 2026 non sono pubblicabili: "
                "manca la base di ottobre 2025. Il registro conserva "
                "il primo rilevamento del runner, non l'orario di prima pubblicazione. ")
        elif certified_actuals:
            actual_context=(
                "Il registro conserva quattro misure ufficiali, distinte "
                "per componente e base temporale. ")
        else:
            actual_context=(
                "Nel registro del progetto non sono ancora presenti misure "
                "BLS validate e datate. Non attribuiamo una sorpresa o un "
                "nuovo percorso Fed a dati che il motore non ha acquisito. ")
        catalyst=("Il CPI era atteso ieri alle 14:30 italiane. "+
                  actual_context+
                  "Un'interpretazione post-evento richiede attese disponibili "
                  "con qualità dichiarata, composizione, OIS/futures e risposta "
                  "relativa delle valute nelle medesime finestre temporali.")
        status=("AFTERMATH_TO_VERIFY" if certified_actuals else
                "AFTERMATH_MONTHLY_ONLY_YOY_UNAVAILABLE" if official_monthly else
                "AFTERMATH_UNVERIFIED")
        title="Dopo il CPI · cosa sappiamo e cosa manca"
        scenario_main={"title":"Repricing monetario USA verificato",
          "text":"Se le misure ufficiali confermano pressione core e il front-end USA si rafforza relativamente, rivalutare la tesi USD con EUR/USD e USD/JPY."}
        scenario_alt={"title":"Dollaro e rendimenti non confermano",
          "text":"Se il pricing relativo o le coppie non seguono, non attribuire un regime hawkish all'evento: distinguere liquidazioni, rischio e debolezza della controparte."}
    elif stage=="UPCOMING":
        headline=(f"Verso {event['title']}: {ccy} aspetta un test "
                  "che il prezzo potrebbe aver già anticipato.")
        lead=(f"Oggi il calendario non presenta un dato dominante. Il prossimo "
              f"catalizzatore è {event['title']} il {pretty(event['date'])}, "
              "ma prima del rilascio conta capire se tassi e cambio abbiano "
              "già incorporato un esito e con quale convinzione.")
        catalyst=(f"L'appuntamento è {event['title']}, il {pretty(event['date'])} "
                  f"alle {clock} italiane. Prepariamo l'evento confrontando il "
                  f"differenziale {u}–{v} con {pair_label}: una lettura plausibile "
                  "non è ancora una sorpresa, e il mercato potrebbe aver già "
                  "anticipato il dato.")
        title=f"Prossimo · {event['title']} · {pretty(event['date'])}"
        status="NEXT_CATALYST"
        scenario_main={"title":"Prezzo e differenziale anticipano il dato",
          "text":f"Un movimento concorde {ccy} richiede ancora verifica della sorpresa, altrimenti può essere già nel prezzo."}
        scenario_alt={"title":"La relazione si interrompe prima dell'evento",
          "text":"Una divergenza fra cambio e tassi riduce l'attrattiva di anticipare il rilascio, anche con una tesi macro plausibile."}
    else:
        headline=(f"{pair_label}: " +
                  ("tassi e cambio divergono; il problema macro è capire perché." if cross_state=="DIVERGENTE" else
                   "il movimento relativo richiede conferme, non una nuova storia." if cross_state=="NON_CONCLUSIVO" else
                   "tassi e prezzo convergono, ma serve capire cosa è già prezzato."))
        lead=(f"Nessun dato domina oggi il calendario ufficiale. "
              f"Fra {pretty(aligned_first)} e {pretty(aligned_last)} lo spread "
              f"{u}–{v} si è mosso di {signed(observed_diff,1,' pb')}, mentre "
              f"{pair_label} ha registrato {signed(observed_fx,2,'%')} "
              "nelle stesse date. Il catalizzatore della mattina è dunque "
              "verificare se questa relazione prosegua e quale aspettativa "
              "monetaria, se presente, l'abbia determinata.")
        catalyst=(f"Non forziamo un evento inesistente. Il punto da osservare oggi è "
                  f"se il differenziale {u}–{v} e {pair_label} confermino o "
                  "smentiscano la relazione recente. Senza variazioni comparabili "
                  "OIS/futures non attribuiamo automaticamente uno shock di banca "
                  "centrale al movimento governativo.")
        title="Oggi · tassi relativi e conferma valutaria"
        status="RELATIVE_PRICING"
        scenario_main={"title":"La relazione prezzi–tassi si consolida",
          "text":f"Un movimento coerente e persistente del differenziale {u}–{v} e di {pair_label} rafforzerebbe la lettura relativa, ma non crea da solo un ingresso."}
        scenario_alt={"title":"La divergenza persiste o il differenziale si arresta",
          "text":f"Se il prezzo di {pair_label} non conferma la direzione del tasso relativo, cercare altri driver prima di assegnare un bias FX."}
    pair_setup=pairs.get("pairs",{}).get(pair,{}) if to_date(pairs.get("price_asof")) and to_date(pairs["price_asof"])<day else {}
    fav=(pair_setup.get("setup") or {}).get("structuralFav")
    price_state=((pair_setup.get("setup") or {}).get("price") or {}).get("state")
    pair_quality=((pair_setup.get("setup") or {}).get("quality") or "NON VALUTABILE")
    if fav:
        pair_clause=(f"Nel modello delle coppie del {pretty(pairs.get('price_asof'))}, "
                     f"{fav} ha il vantaggio relativo; il quadro resta "
                     f"{pair_quality.lower()}. ")
    else:
        pair_clause=("Il dossier della coppia non fornisce un vantaggio "
                     "strutturale verificabile prima dell'apertura. ")
    if price_state=="BAD":
        pair_clause+="Nel modello il prezzo diverge dalla struttura, non è una conferma operativa. "
    elif price_state=="GOOD":
        pair_clause+="Il prezzo è coerente nell'orizzonte del modello, non necessariamente nell'ultimo fixing. "
    else:
        pair_clause+="La conferma del prezzo resta insufficiente. "
    companions={"USD":"USDJPY","EUR":"EURGBP","GBP":"EURGBP","JPY":"EURJPY",
                "CHF":"USDCHF","CAD":"CADJPY","AUD":"AUDJPY","NZD":"NZDJPY"}
    secondary=companions[ccy]
    sec_now=get_pair_price(fxlast,secondary)
    sec_before=get_pair_price(fxprev,secondary)
    if isnum(sec_now) and isnum(sec_before) and sec_before>0:
        secondary_story=(f"Nel medesimo fixing {secondary[:3]}/{secondary[3:]} "
                         f"si muove di {signed((sec_now/sec_before-1)*100,2,'%')} "
                         "dal giorno precedente. Una sola controparte non dimostra "
                         "forza generalizzata della valuta.")
    else:
        secondary_story=("Non abbiamo una seconda coppia comparabile per "
                         "distinguere forza valutaria da debolezza della controparte.")
    forex_context=(f"Il banco di prova FX è {pair_label}. "+pair_clause+secondary_story+
                   " La tesi economica non è un segnale d'ingresso finché "
                   "pricing relativo e prezzo non convergono.")
    verdict=(f"Al {pretty(cutoff)} lo spread 2Y {u}–{v} è "
             f"{signed(spread,0,' pb')}; il confronto allineato col cambio è "
             +("divergente" if cross_state=="DIVERGENTE" else
               "concorde, senza prova causale" if cross_state=="COERENTE" else
               "non conclusivo")+". "
             +("Il dato di oggi può modificare le attese monetarie, "
               if stage=="TODAY" else
               "L'effetto del dato precedente resta da certificare, "
               if stage=="PREVIOUS_CPI" else
               "Il prossimo evento va preparato, non anticipato, "
               if stage=="UPCOMING" else
               "Un movimento relativo non è automaticamente un nuovo regime, ")
             +f"ma {pair_label} richiede una conferma specifica. "
             "Questa lettura non produce un segnale di ingresso.")
    watch=(f"Seguire {pair_label} e {secondary[:3]}/{secondary[3:]}, "
           f"aggiornamenti dello spread {u}–{v} su date omogenee, "
           "eventuali OIS/futures comparabili e pubblicazioni ufficiali "
           "rispetto ad attese documentate. Il COT è settimanale, "
           "non misura flussi intraday.")
    now_rome=now.astimezone(ROME)
    edition_status=("MORNING_SNAPSHOT" if now_rome.date()==day and now_rome.hour<9 else
                    "LATE_MORNING_SNAPSHOT" if now_rome.date()==day and now_rome.hour<11 else
                    "RECONSTRUCTION_NOT_POINT_IN_TIME")
    report={
        "schema":SCHEMA,"edition_date":day.isoformat(),
        "created_at_utc":now.astimezone(timezone.utc).isoformat().replace("+00:00","Z"),
        "edition_status":edition_status,"event_status":status,
        "editorial_quality":"DATED_RULED_NARRATIVE_NOT_HUMAN_REVIEWED",
        "observation_cutoff_exclusive":day.isoformat(),
        "sources":{"fx_fixing":fxlast["Date"],"rates":cutoff,
                   "pair_setup":pairs.get("price_asof") if to_date(pairs.get("price_asof")) and to_date(pairs["price_asof"])<day else None,
                   "calendar":"OFFICIAL_SEED"},
        "headline":headline,"lead":lead,
        "paragraphs":[cb_context,rates_context,catalyst,forex_context],
        "catalyst":{"title":title,"text":catalyst,"date":event["date"] if event else None,
                    "currency":ccy,"time_rome":clock},
        "scenarios":[scenario_main,scenario_alt],
        "verdict":verdict,
        "watch":watch,
        "relative_evidence":{
            "aligned_from":aligned_first,"aligned_to":aligned_last,
            "two_year_spread_bp":round(spread,3),
            "spread_change_aligned_bp":round(observed_diff,3),
            "pair_change_aligned_pct":round(observed_fx,4),
            "alignment":cross_state,
            "companion_pair":secondary,
            "pair_model_quality":pair_quality},
        "pair":pair,
        "charts":[
            {"label":f"Differenziale 2Y {u}–{v}", "unit":"pb","precision":1 if 0<abs(spread)<0.5 else 0,"as_of":cutoff,
             "last_value":round(spread,3),
             "points":[{"date":x,"value":round((series[u][x]-series[v][x])*100,4)}
                       for x in common[-28:]]},
            {"label":f"{pair[:3]}/{pair[3:]} · fixing BCE","unit":"","precision":4,
             "as_of":fxlast["Date"],"last_value":round(spot,6),
             "points":[{"date":x["Date"],"value":round(get_pair_price(x,pair),6)}
                       for x in rows[-28:]]}],
        "eligible_for_fx_signal":False,"modifies_28_pair_engine":False,
        "limitations":["Ricostruzione per date di osservazione, non un archivio publisher point-in-time.",
                       "Nessuna causalità intraday dedotta dai fixing o dai rendimenti daily.",
                       "Forecast secondari non equivalgono a survey consensus certificato."]
    }
    return validate(report)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--edition-date",required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--reconstruct",action="store_true")
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    day=date.fromisoformat(args.edition_date)
    local=now.astimezone(ROME)
    if not args.reconstruct and (day!=local.date() or local.hour>=11):
        raise SystemExit("Cannot publish future, historical or late edition as current")
    report=build(args.root,day,now)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"MORNING_MACRO_FX_V1_VALIDATED",
         "edition":report["edition_date"],"mode":report["edition_status"],
         "catalyst":report["catalyst"]["title"],"source_dates":report["sources"]},
         ensure_ascii=False))

if __name__=="__main__":
    main()
