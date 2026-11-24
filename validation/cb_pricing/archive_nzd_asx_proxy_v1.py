#!/usr/bin/env python3
"""Preserve original dated ASX bank-bill proxy captures, never official OIS."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from nzd_asx_scenario_sensitivity_v2 import check_asx

ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT/"validation/cb_pricing/history/NZD_ASX_PROXY_CAPTURES_V1.jsonl"
SOURCE=ROOT/"live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json"
SCHEMA="GMFQ_NZD_ASX_PROXY_CAPTURE_V1"

def validate(rec):
    if rec.get("schema")!=SCHEMA or not re.fullmatch(r"[0-9a-f]{40}|VALIDATED_COLLECTOR_RUNTIME",rec.get("source_commit","")):
        raise ValueError("Invalid capture provenance")
    feed=rec["feed"]
    captured=datetime.fromisoformat(feed["generated_at_utc"].replace("Z","+00:00"))
    if captured.utcoffset()!=timezone.utc.utcoffset(captured):
        raise ValueError("Capture timestamp must be UTC")
    check_asx(feed,captured.date())
    return rec

def identity(rec):
    f=rec["feed"]
    return (f["as_of"],tuple((h,p["expiry_label"],p["expiration"],p["settlement_price"])
                             for h,p in sorted(f["horizons"].items())))

def append(path,feed,write=False):
    rows=[validate(json.loads(line)) for line in path.read_text().splitlines() if line.strip()]
    seen={identity(row) for row in rows}
    if len(seen)!=len(rows):
        raise ValueError("Duplicate archive identity")
    rec=validate({"schema":SCHEMA,"source_commit":"VALIDATED_COLLECTOR_RUNTIME","feed":feed})
    new=identity(rec) not in seen
    if new and write:
        with path.open("a",encoding="utf-8") as out:
            out.write(json.dumps(rec,sort_keys=True,ensure_ascii=False)+"\n")
    dates={row["feed"]["as_of"] for row in rows}
    if new and write:dates.add(feed["as_of"])
    return {"status":"PASS_RESEARCH_ONLY","existing_captures":len(rows),
            "appended":int(new and write),"would_append":int(new),
            "observed_dates":len(dates),"latest_date":max(dates),
            "official_ois_created":False,"fx_engine_effect":"NONE"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--write",action="store_true")
    p.add_argument("--archive",type=Path,default=ARCHIVE)
    p.add_argument("--source",type=Path,default=SOURCE)
    a=p.parse_args()
    print(json.dumps(append(a.archive,json.loads(a.source.read_text()),a.write),sort_keys=True))

if __name__=="__main__":main()
