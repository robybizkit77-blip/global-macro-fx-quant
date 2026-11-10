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
    return ("+" if x>0 else "−" if x<0 else "")+fmt(abs(x),n)+unit if isnum(x) else "n.d."

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
    future=[x for x in events if day<to_date(x["date"])<=day+timedelta(days=3)]
    if future:
        return min(future,key=lambda x:(x["date"],-EVENT_SCORE.get(x.get("event_type"),0))),"UPCOMING"
    return None,"RELATIVE_PRICING"

def get_pair_price(row,pair):
    base,quote=pair[:3],pair[3:]
    a=1 if base=="EUR" else row.get(base)
    b=1 if quote=="EUR" else row.get(quote)
    return b/a if isnum(a) and isnum(b) and a>0 else None

def source_snapshots(d,day):
    fx=load(d,"fx")
    rows=sorted([x for x in fx.get("rows",[]) if to_date(x.get("Date"))
                 and to_date(x["Date"])<day
                 and all(isnum(x.get(k)) and x[k]>0 for k in COUNTRIES if k!="EUR")],
                key=lambda x:x["Date"])
    if len(rows)<8 or to_date(rows[-1]["Date"])<day-timedelta(days=6):
        raise ValueError("G8 fixing incomplete or too old for an opening edition")
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

def build(root,day,now):
    if day.weekday()>4 or now.tzinfo is None:
        raise ValueError("Requires weekday and timezone-aware clock")
    if day>now.astimezone(ROME).date():
        raise ValueError("Cannot generate tomorrow's briefing as if already available")
    rows,rates=source_snapshots(root,day)
    seed=load(root,"events");cb=load(root,"cb");pairs=load(root,"pairs")
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
    cutoff=common[-1]
    first=next((x for x in common if to_date(x)>=to_date(cutoff)-timedelta(days=8)),common[0])
    spread=(series[u][cutoff]-series[v][cutoff])*100
    previous_spread=(series[u][first]-series[v][first])*100
    fxlast,fxprev=rows[-1],rows[-2]
    spot=get_pair_price(fxlast,pair);before=get_pair_price(fxprev,pair)
    if not isnum(spot) or not isnum(before):
        raise ValueError("FX pair missing from historical ECB fixing")
    spot_change=(spot/before-1)*100
    central=cb.get(ccy) or {}
    if to_date(central.get("last_date")) and to_date(central["last_date"])>=day:
        central={}
    meeting=central.get("last_date")
    cb_name=central.get("bank") or ccy
    cb_context=(f"La {cb_name} arriva alla seduta dopo la decisione del {pretty(meeting)}, "
                f"con tasso di riferimento {central.get('rate_text') or 'da verificare'}. "
                "La questione non è ripetere il livello dei tassi, ma stabilire quali "
                "condizioni economiche possano modificare il percorso atteso.")
    if ccy=="USD" and meeting=="2026-10-28":
        cb_context=("Partiamo dalla Federal Reserve del 28 ottobre: tassi invariati al "
                    "3,75–4,00% e due membri favorevoli a un rialzo. "
                    "La crescita è ancora descritta come resistente, mentre l'inflazione "
                    "rimane un vincolo. Per il dollaro questa postura conta soltanto "
                    "nella misura in cui il mercato la modifica rispetto alle attese già incorporate.")
    rates_context=(f"Il differenziale governativo a due anni {u}–{v} è {signed(spread,0,' punti base')} "
                   f"al {pretty(cutoff)}, cambiato di {signed(spread-previous_spread,1,' pb')} "
                   f"rispetto al {pretty(first)}. Nello stesso arco, il fixing BCE di "
                   f"{pair[:3]}/{pair[3:]} è {fmt(spot,4)} al {pretty(fxlast['Date'])}, "
                   f"contro {fmt(before,4)} alla rilevazione precedente ({signed(spot_change,2,'%')}). "
                   "I due mercati non vanno trattati come una reazione causale già dimostrata. "
                   "Per misurare un repricing monetario servono variazioni omogenee OIS/futures, "
                   "che il semplice livello governativo non sostituisce.")
    reference=forecast_reference(load(root,"forecast"),event,day)
    clock=event_clock(event) if event else None
    actual=load(root,"actual")
    certified_actuals=len({x.get("metric_id") for x in actual
                           if x.get("event_key")=="USD|2026-11-10|INFLATION|Consumer Price Index"})==4
    if stage=="TODAY":
        if ccy=="USD" and event["event_type"]=="INFLATION":
            headline="Il CPI mette alla prova una Fed ancora restrittiva. Per il dollaro conta ciò che è già prezzato."
            lead=("Arriviamo alla giornata con un vantaggio di rendimento USA, ma senza una prova "
                  "che questo produca automaticamente nuova forza del dollaro. "
                  "L'inflazione di oggi può modificare il quadro: sarà decisiva la conferma dei mercati.")
            catalyst=(f"Alle {clock} italiane è previsto il CPI USA di ottobre. {reference}"
                      "Una lettura superiore alle attese, soprattutto nel core persistente, "
                      "potrebbe sostenere aspettative Fed più restrittive; una disinflazione credibile "
                      "potrebbe ridurre quella pressione. Ma il numero isolato non dimostra il repricing: "
                      "cercheremo la risposta del front-end relativo e poi del Forex.")
        else:
            headline=f"{COUNTRIES[ccy]}: {event['title']} è il test macro della giornata."
            lead=(f"Il mercato arriva all'appuntamento con una struttura di tassi già prezzata "
                  f"e una valuta da verificare. Oggi il dato {event['title']} potrebbe "
                  "cambiare le aspettative, ma soltanto una sorpresa misurata e confermata "
                  "dagli strumenti monetari può diventare una tesi direzionale convincente.")
            catalyst=(f"Oggi alle {clock} italiane è previsto {event['title']} "
                      f"({event.get('reference_period','periodo da verificare')}). {reference}"
                      "Guarderemo la composizione e le eventuali revisioni prima di interpretare "
                      "la risposta della banca centrale. Il differenziale di rendimento e il cambio "
                      "sono le conferme successive, non prove automatiche del significato economico.")
        status="EVENT_TODAY"
        title=f"Oggi · {event['title']} · {clock}"
    elif stage=="PREVIOUS_CPI":
        headline="Dopo il CPI, il mercato deve dimostrare se il percorso Fed è davvero cambiato."
        lead=("Il catalizzatore di ieri è passato, ma la lettura economica richiede ancora "
              "un controllo delle fonti ufficiali, del pricing e delle valute. "
              "Non confondiamo la volatilità successiva al dato con un nuovo regime già consolidato.")
        catalyst=("Il CPI USA era previsto ieri alle 14:30 italiane. "+
                  ("Il registro contiene quattro misure ufficiali, da leggere separatamente. " if certified_actuals else
                   "Il registro del progetto non ha ancora quattro misure ufficiali complete e validate: "
                   "non attribuiamo una sorpresa, un movimento Fed o un segnale FX non verificati. ")+
                   "Per cambiare view occorrono confronto esatto con le aspettative pre-evento, "
                   "componenti persistenti, repricing monetario omogeneo e risposta EUR/USD e USD/JPY.")
        status="AFTERMATH_UNVERIFIED" if not certified_actuals else "AFTERMATH_TO_VERIFY"
        title="Dopo il CPI · verifica della reazione e del pricing"
    elif stage=="UPCOMING":
        headline=f"Verso {event['title']}: il mercato prepara il prossimo test per {ccy}."
        lead=("Oggi non emerge un evento dominante dal calendario ufficiale, ma il confronto "
              "fra le economie si muove già in vista del prossimo dato. "
              "L'obiettivo della mattina è capire quali aspettative siano incorporate "
              "nei tassi e dove il prezzo valutario le confermi o le contraddica.")
        catalyst=(f"Il prossimo appuntamento di rilievo è {event['title']}, "
                  f"il {pretty(event['date'])} alle {clock} italiane. "
                  "Non anticipiamo una sorpresa: la preparazione corretta è osservare "
                  "se il differenziale monetario si muove prima del dato, come reagisce il cambio "
                  "e cosa potrebbe falsificare l'ipotesi sulla banca centrale.")
        title=f"Prossimo · {event['title']} · {pretty(event['date'])}"
        status="NEXT_CATALYST"
    else:
        headline="È il repricing relativo il tema del giorno: il Forex deve confermare la macro."
        lead=("Nessuna pubblicazione domina il calendario ufficiale di oggi. "
              "Per questo non creiamo un catalizzatore artificiale: seguiamo la traiettoria "
              "delle aspettative monetarie e il modo in cui le valute stanno realmente reagendo.")
        catalyst=("Il test della giornata è la convergenza tra differenziale di rendimento, "
                  "aspettative monetarie e prezzo. Se i dati non sono sincronizzati, "
                  "la tesi può essere ragionevole ma non abbastanza verificata per un'operazione.")
        title="Oggi · conferme o divergenze nel pricing relativo"
        status="RELATIVE_PRICING"
    pair_setup=pairs.get("pairs",{}).get(pair,{}) if to_date(pairs.get("price_asof")) and to_date(pairs["price_asof"])<day else {}
    fav=(pair_setup.get("setup") or {}).get("structuralFav")
    price_state=((pair_setup.get("setup") or {}).get("price") or {}).get("state")
    pair_clause=("Il modello datato delle coppie " + (
        f"indica un vantaggio strutturale parziale per {fav}" if fav else
        "non certifica un vantaggio strutturale completo") +
        (", ma il prezzo diverge." if price_state=="BAD" else
         ", con prezzo coerente." if price_state=="GOOD" else
         "; resta da controllare il prezzo."))
    forex_context=(f"Il passaggio al Forex è su {pair[:3]}/{pair[3:]}. {pair_clause} "
                   "Osserviamo poi una seconda coppia della valuta coinvolta, per distinguere "
                   "forza della valuta da debolezza della controparte. "
                   "La conclusione non è un segnale d'ingresso: serve capire "
                   "che cosa il mercato abbia già incorporato e quale conferma manchi.")
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
        "scenarios":[
            {"title":"Se la lettura diventa più restrittiva","text":
             "La sorpresa e le componenti del dato dovrebbero trovare conferma nei differenziali monetari e nel prezzo FX; senza questo, la tesi perde attrattività."},
            {"title":"Se la lettura diventa più accomodante","text":
             "Una sorpresa più debole può attenuare la pressione monetaria, ma serve una risposta relativa dei tassi e delle valute; crescita e rischio possono cambiare la conclusione."}],
        "verdict":("La tesi macro rimane condizionata al catalizzatore e alle verifiche del mercato. "
                   f"Su {pair[:3]}/{pair[3:]} il livello dei tassi da solo non costituisce un'opportunità. "
                   "Thesis Strength e Trade Attractiveness restano valutazioni distinte."),
        "watch":("Monitorare la pubblicazione ufficiale, il confronto con le attese certificate, "
                 "il repricing OIS/futures omogeneo e la risposta del prezzo valutario. "
                 "Se una di queste prove manca, esplicitarlo."),
        "pair":pair,
        "charts":[
            {"label":f"Differenziale 2Y {u}–{v}", "unit":"pb","precision":0,"as_of":cutoff,
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
