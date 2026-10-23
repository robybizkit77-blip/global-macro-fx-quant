#!/usr/bin/env python3
"""Offline, opt-in EUR/USD historical bid/ask event-window importer.

Does not download, scrape, or redistribute provider data. Caller supplies a
lawfully acquired CSV and verifies provenance. Numeric values without original
timestamps are rejected. Outputs only an unapproved /tmp research receipt.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from datetime import datetime,timedelta,timezone
from pathlib import Path
from validation.macro.v2_shadow_features_v1 import require,timestamp
from validation.macro.v2_bls_us_u3_2026_shadow_replay_v1 import evidence,validate
from validation.macro.v2_bls_us_unrate_25_release_pilot_v1 import read_fixture
from validation.macro.v2_bls_shutdown_sparse_reentry_v1 import load_evidence

SCHEMA="GMFQ_MACRO_V2_EURUSD_INTRADAY_CSV_RESEARCH_V1"
WINDOW=timedelta(minutes=5)
MAX_STALENESS=timedelta(minutes=2)
COLUMNS={"timestamp","bidPrice","askPrice"}
KNOWN_PROVIDER="Dukascopy historical EUR/USD tick export"
def parse_utc(raw):
    require(isinstance(raw,str) and raw.strip(),"quote timestamp required")
    if raw.isdigit():
        # Dukascopy examples provide epoch milliseconds; seconds not accepted.
        require(len(raw)==13,"epoch timestamp must be in milliseconds")
        t=datetime.fromtimestamp(int(raw)/1000,tz=timezone.utc)
    else:
        t=timestamp(raw)
    require(t.tzinfo is not None,"timestamp must include timezone")
    return t.astimezone(timezone.utc)

def import_csv(path:Path,*,source_url:str,usage_authorized:bool,verified_original:bool):
    require(path.is_file(),"caller must supply existing local historical tick CSV")
    require(usage_authorized is True and verified_original is True,
            "source license and original timestamp review must be confirmed")
    require(source_url.startswith("https://") and
            ("dukascopy.com/" in source_url or "dukascopy-node.app/" in source_url),
            "source must identify declared provider")
    raw=path.read_bytes()
    require(0<len(raw)<=12_000_000,"one event-day CSV must be size bounded")
    fingerprint=hashlib.sha256(raw).hexdigest()
    text=raw.decode("utf-8-sig")
    records=list(csv.DictReader(text.splitlines()))
    require(records and COLUMNS.issubset(records[0].keys()),
            "required columns: timestamp,bidPrice,askPrice")
    require(len(records)<=200_000,"large tick files not supported in pilot")
    ticks=[]
    for row in records:
        clock=parse_utc(row["timestamp"].strip())
        bid=float(row["bidPrice"])
        ask=float(row["askPrice"])
        require(math.isfinite(bid) and math.isfinite(ask) and
                .5<bid<2.5 and bid<=ask and (ask-bid)<.05,
                "bad FX bid/ask or inverted spread")
        ticks.append((clock,bid,ask))
    require(all(ticks[i][0]<=ticks[i+1][0] for i in range(len(ticks)-1)),
            "tick timestamps unsorted; reject arbitrary reordering")
    b=evidence();validate(b,read_fixture(),load_evidence())
    results=[]
    for release in b["first_release_values"]:
        t=timestamp(release["released_at"])
        before=t-WINDOW; after=t+WINDOW
        # Last quote in 2min preceding each 5min checkpoint, no future leakage.
        pre=[x for x in ticks if before-MAX_STALENESS<=x[0]<=before]
        post=[x for x in ticks if after-MAX_STALENESS<=x[0]<=after]
        def select(items):
            if not items:return None
            q=items[-1]
            return {"observed_at":q[0].isoformat(),"bid":q[1],
                    "ask":q[2],"mid":round((q[1]+q[2])/2,7),
                    "spread_pips":round((q[2]-q[1])*10000,3)}
        p,q=select(pre),select(post)
        results.append({"period":release["observation_period"],
           "release_at":t.isoformat(),"pre":p,"post":q,
           "complete_bid_ask_window":p is not None and q is not None,
           "raw_bps_fx_mid_move":None if p is None or q is None else
              round((q["mid"]/p["mid"]-1)*10000,3),
           "interpretation":"UNVERIFIED_INTRADAY_DESCRIPTIVE_NOT_CAUSAL"})
    complete=sum(x["complete_bid_ask_window"] for x in results)
    return {"schema":SCHEMA,"status":"OFFLINE_SOURCE_SUBMITTED_RESEARCH_NOT_INDEPENDENTLY_CERTIFIED",
       "source_declared":KNOWN_PROVIDER,"source_url":source_url,
       "source_file_sha256":fingerprint,"source_bytes_n":len(raw),
       "usage_authorized_asserted":True,"original_timestamps_reviewed_asserted":True,
       "independent_license_or_source_attestation":False,
       "FX_windows_complete":complete,"events":results,
       "Treasury2Y_window_available":False,"USD_OIS_window_available":False,
       "pre_release_consensus_available":False,"cross_asset_event_window_complete":False,
       "causal_conclusion":None,"ready_for_backtest":False,
       "ready_for_FX_score":False,"safe_to_publish_new_D":False,
       "safe_to_update_pair_theses":False,"writes_live_data":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv",type=Path,required=True)
    p.add_argument("--source-url",required=True)
    p.add_argument("--usage-authorized",action="store_true")
    p.add_argument("--original-timestamps-reviewed",action="store_true")
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    require(a.out.resolve().is_relative_to(Path("/tmp")),
            "only write to /tmp; no production data mutations")
    r=import_csv(a.csv,source_url=a.source_url,usage_authorized=a.usage_authorized,
                 verified_original=a.original_timestamps_reviewed)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":r["status"],"fx_windows_complete":r["FX_windows_complete"],
      "cross_asset_event_window_complete":r["cross_asset_event_window_complete"]}))
if __name__=="__main__":main()
