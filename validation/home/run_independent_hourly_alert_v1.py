#!/usr/bin/env python3
"""Independent GitHub hourly editorial engine. No ChatGPT automation access."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "validation/home/CHATGPT_ALERT_EDITORIAL_V3_CANONICAL.md"
SCHEMA = "GMFQ_NEXT_INDEPENDENT_HOURLY_AI_DESK_V1"
API = "https://api.openai.com/v1/responses"
MODEL = "gpt-6.1-terra"  # editable via MARKET_DESK_MODEL; never hardcode credentials
CATEGORIES = {"FUTURES_IMPLIED_REPRICING","OIS_REPRICING","MARKET_GOVERNMENT_RATES",
              "MARKET_FX_ECB_FIXING","MARKET_VOLATILITY_CLOSE",
              "MARKET_EQUITY_CLOSE","MARKET_CREDIT_OAS","MACRO_OFFICIAL_ACTUAL"}
REPORT_FIELDS = ("headline","lead","news","desk_judgment","fx_implications",
                 "what_changed","contrary_evidence","watch")
NEWS_FIELDS = ("headline","analysis","kind","published_date","event_date",
               "market_area","sources")
BLOCKED = re.compile(r"\bnon (?:abbiamo|possiamo)\b|verifica incompleta|nessuna notizia",re.I)

def utcnow():
    return datetime.now(timezone.utc)

def parse_day(value: str):
    try:
        dt=datetime.strptime(value,"%Y-%m-%d")
        return dt.date() if value == dt.strftime("%Y-%m-%d") else None
    except (TypeError,ValueError):
        return None

def parse_time(value: str):
    if not isinstance(value,str): return None
    try: return datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError: return None

def safe_url(url):
    if not isinstance(url,str) or len(url)>2048: return False
    try:
        u=urlparse(url)
        return u.scheme=="https" and bool(u.hostname) and "." in u.hostname and not u.username and not u.password
    except ValueError: return False

def read(path, default=None):
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError: return default

def strval(v):
    return str(v).strip() if isinstance(v,str) else ""

def fingerprint(data):
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def source_bundle(root:Path, now:datetime, prior=None):
    sections=root/"live_data/sections"
    pulse=read(sections/"NEWS_PULSE_OPERATIONAL.json")
    calendar=read(sections/"CALENDAR_OPERATIONAL_VIEW.json",{})
    commodity=read(sections/"ESTIMATED_RESIDUAL_GAPS.json",{})
    if not isinstance(pulse,dict) or not isinstance(pulse.get("items"),list):
        raise ValueError("Operational news pulse missing: no silent synthetic fallback.")
    today=now.astimezone(ZoneInfo("Europe/Rome")).date()
    if parse_day(pulse.get("content_as_of")) is None or parse_day(pulse["content_as_of"])>today:
        raise ValueError("News-pulse observation date is missing or in the future.")
    events=[]
    for x in pulse["items"]:
        if not isinstance(x,dict) or x.get("category") not in CATEGORIES: continue
        d=parse_day(x.get("as_of"))
        if d is None or not(0<=(today-d).days<=7): continue
        if not isinstance(x.get("title"),str) or not x.get("title").strip():continue
        e={k:x.get(k) for k in ("title","detail","category","importance","as_of","ccy","pair","source","source_url","quality")}
        events.append(e)
    events.sort(key=lambda x:(x.get("as_of") or "",x.get("importance")=="HIGH"),reverse=True)
    if len(events)<4: raise ValueError("Less than four dated market observations; skip edition.")
    releases=[]
    if isinstance(calendar,dict) and isinstance(calendar.get("events"),list):
        for e in calendar["events"]:
            if not isinstance(e,dict) or e.get("importance")!="HIGH": continue
            d=parse_day(e.get("date"))
            if d and 0<=(d-today).days<=5:
                releases.append({k:e.get(k) for k in ("date","title","ccy","status","quality",
                    "source_url","event_type","timezone","time_local")})
    releases.sort(key=lambda x:x["date"])
    commodities=[]
    for key in ("GOLD.market_proxy","WTI.market_proxy","BRENT.market_proxy"):
        x=(commodity.get("lanes") or {}).get(key) if isinstance(commodity,dict) else None
        if not isinstance(x,dict) or x.get("status")!="MARKET_PROXY_ACTIVE_SECONDARY":continue
        d=parse_day(x.get("proxy_as_of"))
        if d and 0<=(today-d).days<=4:
            commodities.append({k:x.get(k) for k in ("proxy_as_of","change_1d_pct","change_1w_pct","value","source","source_endpoint")}|{"asset":key.split(".")[0],"kind":"SECONDARY_MARKET_PROXY"})
    previous=[]
    if isinstance(prior,dict) and prior.get("schema")==SCHEMA:
        for e in prior.get("news",[])[:6]:
            if isinstance(e,dict):
                previous.append({"headline":e.get("headline"),"kind":e.get("kind"),"published_date":e.get("published_date")})
    return {"observation_created_utc":strval(pulse.get("generated_at_utc")),
       "news_content_as_of":pulse["content_as_of"],
       "observed_market_events":events[:24],
       "official_calendar_upcoming":releases[:10],
       "commodity_futures_proxies":commodities,
       "last_edition":previous,
       "last_editorial_headline":prior.get("headline") if isinstance(prior,dict) else None,
       "NOTE":"Every observation has its own vintage. ECB FX fixings and dated market prices are NOT intraday event reactions. Headlines from the web require separate source URLs."}

def editorial_schema():
    # Required fields and additionalProperties:false for strict Structured Outputs.
    text={"type":"string"}
    news={"type":"object","additionalProperties":False,
          "properties":{"headline":text,"analysis":text,
              "kind":{"type":"string","enum":["NEWS","FOLLOW_UP","PREVIEW"]},
              "published_date":text,"event_date":text,"market_area":text,
              "sources":{"type":"array","items":text}},
          "required":list(NEWS_FIELDS)}
    return {"type":"object","additionalProperties":False,"properties":{
        "headline":text,"lead":text,
        "news":{"type":"array","items":news},
        "desk_judgment":text,"fx_implications":text,
        "what_changed":text,"contrary_evidence":text,"watch":text},
        "required":list(REPORT_FIELDS)}

def request_payload(canonical:str, bundle:dict, now:datetime, model:str):
    rome=now.astimezone(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d %H:%M %Z")
    adapter=("ADATTAMENTO TECNICO DI CONSEGNA: il testo sopra è lo standard V3 INTEGRALE; "
       "questo output è un notiziario per il sito, non un messaggio ChatGPT. "
       "Esegui ricerca web attiva ogni ora attraverso lo strumento web_search; "
       "copri notizie macro/FX/banche centrali, azioni/credito, materie prime e geopolitica. "
       "Non limitarti al solo contesto GitHub; il feed interno è supporto, NON tutte le notizie del mondo. "
       "Produci solo un oggetto JSON secondo lo schema, con 3-6 notizie realmente documentate "
       "(anche 1-2 solo se davvero giustificato), fonte HTTPS cliccabile per ciascuna, data dell'articolo "
       "e data del fatto. Per ogni fonte usa esclusivamente URL effettivamente emersi dalla ricerca web "
       "oppure URL presenti nelle fonti interne. Se un fatto è anteprima, usa PREVIEW; "
       "per approfondimenti datati usa FOLLOW_UP. Niente affermazioni su flussi non osservati. "
       "La prima lettura dev'essere un QUADRO GENERALE e non una lista di indicatori. "
       "Spiega le implicazioni FX sempre in modo relativo. Inserisci almeno una contraddizione "
       "alla spiegazione dominante. Non usare frasi difensive «non abbiamo/non possiamo»; "
       "usa eventuali stime/proxy dichiarati con as-of. Non fingere che fonti degli ultimi giorni siano dati intraday.")
    return {"model":model,"instructions":canonical+"\n\n"+adapter,
       "input":rome+"\nCONTESTO DI MERCATO DATATO E CRONOLOGIA DEL DESK:\n"+
           json.dumps(bundle,ensure_ascii=False,separators=(",",":")),
       "tools":[{"type":"web_search"}],
       "tool_choice":"required",
       "include":["web_search_call.action.sources"],
       "text":{"format":{"type":"json_schema","name":"hourly_market_desk",
                         "strict":True,"schema":editorial_schema()}},
       "max_output_tokens":4300,"store":False}

def call_ai(request,api_key,endpoint=API,timeout=150):
    if not api_key:raise ValueError("MARKET_DESK_API_KEY not configured")
    if endpoint != API:raise ValueError("Unapproved API endpoint; use the official OpenAI Responses API")
    payload=json.dumps(request,ensure_ascii=False).encode()
    req=Request(endpoint,data=payload,method="POST",
                headers={"Authorization":"Bearer "+api_key,"Content-Type":"application/json"})
    with urlopen(req,timeout=timeout) as resp:
        return json.load(resp)

def parse_output(raw):
    if not isinstance(raw,dict) or raw.get("status")!="completed":
        raise ValueError("AI response not completed; do not publish")
    output=raw.get("output")
    if not isinstance(output,list):raise ValueError("Missing output")
    sources=set()
    used_web=False
    for o in output:
        if not isinstance(o,dict):continue
        if o.get("type")=="web_search_call":
            used_web=True
            action=o.get("action") or {}
            for s in action.get("sources",[]) or []:
                url=s.get("url") if isinstance(s,dict) else None
                if safe_url(url): sources.add(url)
        if o.get("type")=="message":
            for c in o.get("content",[]) or []:
                for a in c.get("annotations",[]) or []:
                    if isinstance(a,dict) and safe_url(a.get("url")):
                        sources.add(a["url"])
    content=next((c.get("text") for o in output if o.get("type")=="message" for c in o.get("content",[])
                  if isinstance(c,dict) and c.get("type")=="output_text" and isinstance(c.get("text"),str)),None)
    if not used_web or not sources:raise ValueError("A real web search with sourced results is mandatory")
    if not content:raise ValueError("No editorial text in AI response")
    return json.loads(content),sources

def validate_editorial(doc,allowed_sources,now):
    if not isinstance(doc,dict) or set(doc)!=set(REPORT_FIELDS):
        raise ValueError("Editorial output schema mismatch")
    if not isinstance(doc["news"],list) or not 1<=len(doc["news"])<=6:
        raise ValueError("Expected 1-6 sourced news articles")
    for k in REPORT_FIELDS:
        if k=="news":continue
        v=doc[k]
        if not isinstance(v,str) or len(v.strip())< (35 if k in ("headline","lead","desk_judgment","fx_implications") else 20):
            raise ValueError("Editorial narrative too thin: "+k)
        if BLOCKED.search(v):raise ValueError("Defensive/empty editorial: "+k)
    today=now.astimezone(ZoneInfo("Europe/Rome")).date()
    distinct=set()
    for e in doc["news"]:
        if not isinstance(e,dict) or set(e)!=set(NEWS_FIELDS):
            raise ValueError("Incomplete news article")
        for k,minimum in (("headline",15),("analysis",25),("market_area",2)):
            if not isinstance(e[k],str) or len(e[k].strip())<minimum:
                raise ValueError("Empty/weak news: "+k)
        if e["kind"] not in {"NEWS","FOLLOW_UP","PREVIEW"} or BLOCKED.search(e["analysis"]):
            raise ValueError("Invalid news category or defensive narrative")
        pub=parse_day(e["published_date"]); event=parse_day(e["event_date"])
        if not pub or not event or pub>today or pub<today-timedelta(days=7):
            raise ValueError("Unverified or stale publication")
        if event>today and e["kind"]!="PREVIEW":
            raise ValueError("Future event falsely described as actual")
        if not isinstance(e["sources"],list) or not e["sources"]:
            raise ValueError("Missing article citations")
        for url in e["sources"]:
            if not safe_url(url) or url not in allowed_sources:
                raise ValueError("Source URL not supported by web search or canonical feed")
            distinct.add(urlparse(url).hostname)
    if not distinct: raise ValueError("No verified source domains")
    return doc

def generate(root,now,prior=None,ai_response=None,api_key=None,model=MODEL):
    canonical=(root/"validation/home/CHATGPT_ALERT_EDITORIAL_V3_CANONICAL.md").read_text(encoding="utf-8")
    if not canonical.startswith("# GLOBAL MACRO & CROSS-ASSET RESEARCH DESK — STANDARD EDITORIALE CANONICO V3"):
        raise ValueError("Canonical ChatGPT V3 instruction file changed unexpectedly")
    bundle=source_bundle(root,now,prior)
    payload=request_payload(canonical,bundle,now,model)
    raw=ai_response if ai_response is not None else call_ai(payload,api_key)
    article,web_sources=parse_output(raw)
    internal={x.get("source_url") for x in bundle["observed_market_events"] if safe_url(x.get("source_url"))}
    internal|={x.get("source_url") for x in bundle["official_calendar_upcoming"] if safe_url(x.get("source_url"))}
    internal|={x.get("source_endpoint") for x in bundle["commodity_futures_proxies"] if safe_url(x.get("source_endpoint"))}
    validate_editorial(article,web_sources|internal,now)
    history=(prior.get("history",[]) if isinstance(prior,dict) and prior.get("schema")==SCHEMA else [])
    if isinstance(prior,dict) and prior.get("status")=="ACTIVE":
        previous={k:prior.get(k) for k in REPORT_FIELDS}
        previous.update({"generated_at_utc":prior.get("generated_at_utc")})
        history=[previous]+history
    return {"schema":SCHEMA,"status":"ACTIVE",
       "generated_at_utc":now.isoformat().replace("+00:00","Z"),
       "edition_time_rome":now.astimezone(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d %H:%M"),
       "model":model,"editorial_contract":"CHATGPT_ALERT_V3_EXACT_COPY",
       "input_vintages":{"news":bundle["news_content_as_of"],
                         "input_build":bundle["observation_created_utc"]},
       **article,
       "history":history[:24],
       "provenance":{"web_source_urls":sorted(web_sources)[:40],
          "method":"LLM_WITH_WEB_SEARCH_AND_DATED_MARKET_CONTEXT",
          "intraday_reaction_not_inferred_from_older_closes":True,
          "chatgpt_automation_unchanged":True}}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=str(ROOT));p.add_argument("--output",required=True)
    p.add_argument("--previous");p.add_argument("--mock-response")
    p.add_argument("--now")
    args=p.parse_args()
    now=parse_time(args.now) if args.now else utcnow()
    if not now or not now.tzinfo:raise ValueError("UTC offset-aware --now required")
    root=Path(args.root).resolve()
    prior=read(args.previous,{}) if args.previous else {}
    mock=read(args.mock_response) if args.mock_response else None
    result=generate(root,now,prior,ai_response=mock,api_key=os.environ.get("MARKET_DESK_API_KEY"),
                    model=os.environ.get("MARKET_DESK_MODEL",MODEL))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("HOURLY_GITHUB_DESK_ACTIVE "+json.dumps({"edition":result["edition_time_rome"],
       "articles":len(result["news"]),"web_sources":len(result["provenance"]["web_source_urls"]),
       "chatgpt_modified":False}))
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("HOURLY_GITHUB_DESK_BLOCKED "+str(exc),file=sys.stderr);sys.exit(1)
