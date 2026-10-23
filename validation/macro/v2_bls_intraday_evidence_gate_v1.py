#!/usr/bin/env python3
"""Fail-closed acquisition gate for timestamped BLS market-event evidence.

Zero-filled template by design: no fabricated event prices, consensus or OIS.
Source permissions and independently timestamped data must precede event tests.
"""
from __future__ import annotations
import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp
from validation.macro.v2_bls_us_u3_2026_shadow_replay_v1 import evidence, validate
from validation.macro.v2_bls_us_unrate_25_release_pilot_v1 import read_fixture
from validation.macro.v2_bls_shutdown_sparse_reentry_v1 import load_evidence

SCHEMA="GMFQ_MACRO_V2_EVENT_MARKET_EVIDENCE_GATE_V1"
FIELDS=("consensus_pre_release","ust2y_before","ust2y_after",
        "usd_ois_before","usd_ois_after","eurusd_before","eurusd_after")
PROVIDERS={
 "consensus_pre_release":"TIME_STAMPED_ECONOMIST_SURVEY_LICENSED",
 "ust2y_before":"TREASURY_INTRADAY_SAME_INSTRUMENT",
 "ust2y_after":"TREASURY_INTRADAY_SAME_INSTRUMENT",
 "usd_ois_before":"USD_SOFR_OIS_SAME_CONTRACT_INTRADAY",
 "usd_ois_after":"USD_SOFR_OIS_SAME_CONTRACT_INTRADAY",
 "eurusd_before":"SPOT_EURUSD_INTRADAY_SAME_VENUE",
 "eurusd_after":"SPOT_EURUSD_INTRADAY_SAME_VENUE",
}
SOURCE_CATALOG={
 "consensus_pre_release":{
   "category":"HISTORICAL_ECONOMIST_SURVEY",
   "access":"LICENSE_OR_PROVIDER_VERIFICATION_REQUIRED",
   "cannot_substitute":"BLS previous value or current weekly calendar forecast",
 },
 "ust2y_before":{
   "category":"HISTORICAL_INTRADAY_TREASURY",
   "candidate":"CME DataMine BrokerTec or GovPX Treasury market data",
   "access":"DATASET_COVERAGE_AND_LICENSE_VERIFICATION_REQUIRED",
 },
 "usd_ois_before":{
   "category":"USD_OIS_SAME_CONTRACT_BID_ASK",
   "candidate":"Licensed OTC vendor quotes or dated same-contract SOFR derivatives",
   "access":"INSTRUMENT_TENOR_AND_LICENSE_VERIFICATION_REQUIRED",
   "cannot_substitute":"daily SOFR fixing, Term SOFR or another futures expiry",
 },
 "eurusd_before":{
   "category":"HISTORICAL_SPOT_FX",
   "candidate":"CME DataMine EBS Spot FX",
   "access":"DATASET_COVERAGE_AND_LICENSE_VERIFICATION_REQUIRED",
   "cannot_substitute":"ECB 14:10 reference fixing or daily close",
 }
}
EXPECTED_BEFORE=timedelta(minutes=5)
EXPECTED_AFTER=timedelta(minutes=5)
MAX_QUOTE_AGE=timedelta(minutes=2)


def template() -> dict:
    bls=evidence()
    validate(bls,read_fixture(),load_evidence())
    return {
      "schema":SCHEMA,
      "as_of":"2026-10-23",
      "status":"DATA_ACCESS_GAP__NO_EVENT_CAUSAL_OR_PREDICTIVE_TEST",
      "source_catalog":SOURCE_CATALOG,
      "quote_rule":"08:25 and 08:35 America/New_York, no quote older than 2 minutes",
      "events":[{
        "period":v["observation_period"],"release_at":timestamp(v["released_at"]).isoformat(),
        "actual_first_release":v["value"],
        "inputs":{k:None for k in FIELDS},
        "event_window_complete":False,
        "causal_claim_allowed":False,
      } for v in bls["first_release_values"]],
      "safe_to_publish_new_D":False,
      "safe_to_update_pair_theses":False,
      "eligible_for_backtest":False,
      "writes_live_data":False,
    }


def _valid_quote(field: str, quote: dict, release: datetime) -> bool:
    if not isinstance(quote,dict) or quote.get("kind")!=PROVIDERS[field]:
        return False
    if not isinstance(quote.get("source_url"),str) or not quote["source_url"].startswith("https://"):
        return False
    if quote.get("license_authorized") is not True or quote.get("original_timestamp_verified") is not True:
        return False
    if quote.get("source_bytes_sha256") is None or not isinstance(quote["source_bytes_sha256"],str) or len(quote["source_bytes_sha256"])!=64:
        return False
    if not isinstance(quote.get("value"),(int,float)) or isinstance(quote["value"],bool) or not math.isfinite(quote["value"]):
        return False
    try:
        ts=timestamp(quote.get("observed_at"))
    except (TypeError,ValueError,KeyError):
        return False
    if field=="consensus_pre_release":
        return ts<release and quote.get("survey_closed_at")==quote.get("observed_at") and quote["value"]>=0
    target=release+(-EXPECTED_BEFORE if field.endswith("before") else EXPECTED_AFTER)
    if not (target-MAX_QUOTE_AGE<=ts<=target):
        return False
    if field.endswith("before") and ts>=release:
        return False
    if field.endswith("after") and ts<=release:
        return False
    if field.startswith("eurusd"):
        return 0.1<quote["value"]<3
    return -5<quote["value"]<30


def audit(payload: dict) -> dict:
    canonical=template()
    require(isinstance(payload,dict) and payload.get("schema")==SCHEMA and
            payload.get("as_of")==canonical["as_of"] and
            isinstance(payload.get("events"),list) and len(payload["events"])==9,
            "exact nine-event BLS evidence contract required")
    out=[]
    for ref,record in zip(canonical["events"],payload["events"]):
        require((record.get("period"),record.get("release_at"),record.get("actual_first_release"))==
                (ref["period"],ref["release_at"],ref["actual_first_release"]),
                "BLS first release identity cannot be changed")
        inputs=record.get("inputs")
        require(isinstance(inputs,dict) and set(inputs)==set(FIELDS),
                "complete evidence slots required; no silent assumptions")
        release=timestamp(ref["release_at"])
        flags={key:_valid_quote(key,inputs[key],release) for key in FIELDS}
        # Before and after observations must be from identical instruments.
        comparable=all(flags.values())
        if comparable:
            for a,b in (("ust2y_before","ust2y_after"),("usd_ois_before","usd_ois_after"),
                        ("eurusd_before","eurusd_after")):
                comparable=comparable and inputs[a].get("instrument_id")==inputs[b].get("instrument_id") and (
                    inputs[a].get("venue")==inputs[b].get("venue"))
        # A daily settlement or quote from another tenor is not a 10-minute event window.
        complete=bool(comparable)
        require(record.get("event_window_complete") is complete,
                "event-window state must reflect proven inputs")
        require(record.get("causal_claim_allowed") is False,
                "even a complete price window alone does not establish causality")
        out.append({"period":ref["period"],"available_fields":sum(flags.values()),
                    "valid_fields":flags,"complete_event_window":complete,
                    "missing_fields":[k for k in FIELDS if not flags[k]],
                    "causal_claim_allowed":False})
    complete=sum(x["complete_event_window"] for x in out)
    return {
        "schema":SCHEMA,"events":9,"complete_event_windows":complete,
        "observations_without_complete_windows":9-complete,
        "research_readiness":"DATA_GAP" if complete==0 else "PARTIAL_REQUIRES_INDEPENDENT_QA",
        "events_detail":out,
        "source_permissions_checked":False,
        "causal_conclusion":None,
        "predictive_edge_validated":False,
        "safe_to_publish_new_D":False,
        "safe_to_update_pair_theses":False,
        "eligible_for_backtest":False,
        "writes_live_data":False,
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--json-out",type=Path)
    args=p.parse_args()
    payload=template()
    result=audit(payload)
    if args.json_out:
        require(args.json_out.resolve().is_relative_to(Path("/tmp")),
                "research receipt may only be written to /tmp")
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(json.dumps({"template":payload,"audit":result},indent=2)+"\n")
    print(json.dumps({"events":result["events"],"complete_event_windows":result["complete_event_windows"],
                      "ready":result["research_readiness"]}))

if __name__=="__main__":
    main()
