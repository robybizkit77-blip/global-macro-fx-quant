#!/usr/bin/env python3
"""Freeze non-official forecast BEFORE issuer's scheduled macro release.

First immutable observed provider forecast wins, keyed to issuer's exact
scheduled event. The provider-generated timestamp is NOT proof of upload
or real-time market availability; capture time is the actual runner instant.
Do not overwrite or re-date a frozen forecast on later feed updates.
Skip events with missing issuer clock, missing forecast, region/series mismatch
or source quote received after the scheduled release.

The output is a PRE-RELEASE PROVIDER FORECAST ledger, not observed actuals,
macro surprises, market causality or a trading signal. No model writes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.refresh_macro_consensus_secondary_v1 import series_compatible

ROOT=Path(__file__).resolve().parents[2]
SEED=ROOT/"live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json"
CONSENSUS=ROOT/"live_data/sections/MACRO_CONSENSUS_SECONDARY_V1.json"
LEDGER=ROOT/"validation/macro/MACRO_PRE_RELEASE_CONSENSUS_LEDGER_V1.jsonl"
SCHEMA="GMFQ_MACRO_FORECAST_FROZEN_BEFORE_SCHEDULED_RELEASE_V1"
G8={"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"}
FORECAST_RE=re.compile(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(%)\s*$")

def must(ok,why):
    if not ok:raise ValueError("MACRO_FROZEN_CONSENSUS_REJECTED: "+why)

def utc_iso(s):
    must(isinstance(s,str),"explicit UTC timestamp required")
    try:d=datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError:raise ValueError("MACRO_FROZEN_CONSENSUS_REJECTED: invalid ISO timestamp") from None
    must(d.tzinfo is not None and d.utcoffset() is not None,"offset-aware timestamp required")
    return d.astimezone(timezone.utc)

def utc_text(d):
    return d.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")

def scheduled(official):
    """Issuer calendar time is SCHEDULED, not actual first delivery."""
    wall=official.get("time_local")
    zone=official.get("timezone")
    if not wall or not zone:return None
    must(isinstance(wall,str) and re.fullmatch(r"\d\d:\d\d(?::\d\d)?",wall),
         "invalid issuer wall clock")
    must(isinstance(zone,str),"time zone required")
    try:
        local=datetime.fromisoformat(official["date"]+"T"+wall)
        tz=ZoneInfo(zone)
        aware=local.replace(tzinfo=tz)
    except (ValueError,KeyError):
        raise ValueError("MACRO_FROZEN_CONSENSUS_REJECTED: issuer time zone invalid") from None
    must(aware.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)==local,
         "nonexistent scheduled wall clock")
    # Wall-clock within an ambiguous DST hour cannot identify one UTC instant.
    must(aware.replace(fold=0).utcoffset()==aware.replace(fold=1).utcoffset(),
         "ambiguous issuer wall clock")
    return aware.astimezone(timezone.utc)

def parse_forecast(v):
    must(isinstance(v,str),"forecast must be explicit percent string")
    m=FORECAST_RE.fullmatch(v)
    must(m is not None,"percent format/unit cannot be inferred")
    n=float(m.group(1))
    must(math.isfinite(n),"nonfinite forecast")
    return n

def exact_event_key(e):
    return "|".join([e["ccy"],e["date"],e["event_type"],e["title"]])

def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,
            sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()

def validate_existing(rows):
    previous="GENESIS"
    seen=set()
    for row in rows:
        must(isinstance(row,dict) and row.get("schema")==SCHEMA,
             "unknown/modified ledger schema")
        expected=row.get("record_sha256")
        content={k:v for k,v in row.items() if k!="record_sha256"}
        must(isinstance(expected,str) and expected==digest(content),
             "historical forecast record has changed")
        must(row.get("previous_record_sha256")==previous,
             "historical ledger hash chain altered")
        key=row.get("event_key")
        must(isinstance(key,str) and key not in seen,
             "event cannot be captured twice or overwritten")
        seen.add(key)
        cap=utc_iso(row.get("captured_at_utc"))
        gen=utc_iso(row.get("source_generated_at_utc"))
        release=utc_iso(row.get("official_scheduled_release_utc"))
        must(gen<=cap<release,
             "historical forecast not actually captured before scheduled release")
        must(row.get("actual") is None and row.get("FX_signal") is None and
             row.get("surprise") is None and
             row.get("publisher_first_public_delivery_verified") is False and
             row.get("provider_is_official")==False,
             "ledger cannot present forecast as actual/official/causal signal")
        parse_forecast(row.get("consensus"))
        must(row.get("currency") in G8,
             "non-G8 historical currency")
        previous=expected
    return previous,seen

def freeze(official,consensus,existing,captured_at):
    now=utc_iso(captured_at) if isinstance(captured_at,str) else captured_at
    must(isinstance(now,datetime) and now.tzinfo is not None
         and now.utcoffset() is not None,"real offset-aware capture clock")
    now=now.astimezone(timezone.utc)
    must(isinstance(official,dict) and
         official.get("schema")=="GMFQ_MACRO_RELEASE_OFFICIAL_SEED_V1",
         "issuer calendar schema not accepted")
    must(isinstance(consensus,dict) and
         consensus.get("schema")=="GMFQ_MACRO_CONSENSUS_SECONDARY_V1" and
         consensus.get("provider")=="FOREX_FACTORY_FAIR_ECONOMY_WEEKLY" and
         consensus.get("provider_field")=="forecast" and
         consensus.get("rules",{}).get("never_promote_to_official") is True and
         consensus.get("rules",{}).get("actual_not_used_as_pre_release_consensus") is True and
         consensus.get("rules",{}).get("official_calendar_remains_primary") is True,
         "only explicitly non-official prior consensus feed accepted")
    previous,seen=validate_existing(existing)
    src_generated=utc_iso(consensus.get("generated_at_utc"))
    # Do not admit a timestamp fabricated in the future or one that has
    # not been observed by this runner. Future stale or delayed source
    # timestamps are never silently normalized.
    must(src_generated<=now,"source generation timestamp later than actual capture")
    official_by_key={exact_event_key(x):x for x in official.get("events",[])}
    must(len(official_by_key)==len(official.get("events",[])),
         "official schedule contains duplicate event keys")
    appended=[];skipped={}
    def skip(reason):skipped[reason]=skipped.get(reason,0)+1
    rows=consensus.get("events",[])
    must(isinstance(rows,list),"consensus events list required")
    keys=[r.get("event_key") for r in rows]
    must(len(keys)==len(set(keys)),"duplicate secondary consensus event identity")
    for r in rows:
        key=r.get("event_key")
        e=official_by_key.get(key)
        if not e:
            skip("NOT_EXACT_OFFICIAL_EVENT");continue
        if key in seen:
            skip("ALREADY_FROZEN_KEEP_FIRST_OBSERVATION");continue
        stamp=scheduled(e)
        if stamp is None:
            skip("OFFICIAL_SCHEDULE_HAS_NO_INTRADAY_CLOCK");continue
        if now>=stamp or src_generated>=stamp:
            skip("NOT_CAPTURED_BEFORE_ISSUER_SCHEDULE");continue
        if not (r.get("status")=="AVAILABLE" and
                r.get("ccy") in G8 and
                r.get("ccy")==e["ccy"] and
                r.get("official_date")==e["date"] and
                r.get("official_title")==e["title"] and
                r.get("event_type")==e["event_type"] and
                r.get("provider")=="FOREX_FACTORY_FAIR_ECONOMY_WEEKLY" and
                r.get("actual_ignored_for_pre_release_consensus") is True and
                r.get("official_date_overridden") is False and
                r.get("date_match_gap_days")==0 and
                r.get("confidence_grade")=="B" and
                series_compatible(e,{"event":r.get("provider_event")})):
            skip("SOURCE_IDENTITY_REGION_OR_SERIES_NOT_ATTESTED");continue
        try: value=parse_forecast(r.get("consensus"))
        except ValueError:
            skip("CONSENSUS_NOT_AN_EXPLICIT_PERCENT_NUMBER");continue
        # Forecast unit is percent, may measure q/q or m/m; do not convert,
        # annualize, compare disparate series, or assume revisions.
        record={
            "schema":SCHEMA,
            "event_key":key,
            "currency":r["ccy"],
            "event_type":e["event_type"],
            "official_event_date":e["date"],
            "official_event_title":e["title"],
            "official_time_local":e["time_local"],
            "official_timezone":e["timezone"],
            "official_scheduled_release_utc":utc_text(stamp),
            "official_scheduled_not_first_actual_delivery":True,
            "provider":"FOREX_FACTORY_FAIR_ECONOMY_WEEKLY",
            "provider_event":r["provider_event"],
            "consensus":r["consensus"],
            "consensus_unit":"PERCENT_UNCHANGED_ORIGINAL_PROVIDER_SCALE",
            "consensus_value_percent":value,
            "previous_provider_print":r.get("previous"),
            "quality":"SECONDARY_CONSENSUS_MATCH_B_NOT_OFFICIAL",
            "provider_is_official":False,
            "source_generated_at_utc":utc_text(src_generated),
            "captured_at_utc":utc_text(now),
            "capture_is_runner_observation_not_independent_redistribution_clock":True,
            "publisher_first_public_delivery_verified":False,
            "actual":None,"surprise":None,"FX_signal":None,
            "eligible_for_live_model":False,
            "eligible_for_beta_or_forward":False,
            "previous_record_sha256":previous,
        }
        record["record_sha256"]=digest(record)
        appended.append(record)
        seen.add(key);previous=record["record_sha256"]
    output=existing+appended
    validate_existing(output)
    return output,{
      "status":"PRE_RELEASE_CONSENSUS_FROZEN_OR_ALREADY_ARCHIVED",
      "records_before":len(existing),"new_forecasts_frozen":len(appended),
      "records_after":len(output),"skipped":skipped,
      "event_keys_frozen":[x["event_key"] for x in appended],
      "scope":"FORECAST_ONLY_NOT_ACTUAL_NOT_MACRO_SURPRISE_NOT_FX_SIGNAL",
      "safe_to_publish_core":False,"safe_to_update_28_pairs":False,
      "safe_for_beta":False,"safe_for_forward":False,
    }

def read_existing(path):
    if not path.exists():return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]

def run(official=SEED,consensus=CONSENSUS,ledger=LEDGER,captured_at=None):
    if captured_at is None:captured_at=datetime.now(timezone.utc)
    old=read_existing(ledger)
    new,receipt=freeze(json.loads(Path(official).read_text(encoding="utf-8")),
                       json.loads(Path(consensus).read_text(encoding="utf-8")),
                       old,captured_at)
    if len(new)>len(old):
        Path(ledger).parent.mkdir(parents=True,exist_ok=True)
        with Path(ledger).open("a",encoding="utf-8") as o:
            for item in new[len(old):]:
                o.write(json.dumps(item,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n")
    return receipt

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--official",type=Path,default=SEED)
    p.add_argument("--consensus",type=Path,default=CONSENSUS)
    p.add_argument("--ledger",type=Path,default=LEDGER)
    a=p.parse_args()
    print(json.dumps(run(a.official,a.consensus,a.ledger),
                     ensure_ascii=False,sort_keys=True))

if __name__=="__main__":main()
