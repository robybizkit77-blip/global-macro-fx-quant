#!/usr/bin/env python3
"""Append mature outcome records without ever rewriting a decision snapshot."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ROOT / "validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl"
OUTCOMES = ROOT / "validation/forward/outcomes/CORE_DECISION_OUTCOMES_V1.jsonl"
HORIZONS = {"1D": 1, "3D": 3, "1W": 7, "2W": 14, "1M": 30, "3M": 90}

def canonical(x): return (json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
def sha(x): return hashlib.sha256(canonical(x)).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", required=True, help="ISO date at which maturity is judged")
    p.add_argument("--price-input", required=True, help="JSONL: snapshot_id, horizon, gross_return, cost_bps, source_id, available_at")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    as_of = dt.date.fromisoformat(a.as_of)
    if not DECISIONS.exists(): raise SystemExit("no decision snapshots to attach")
    decisions = {json.loads(x)["snapshot_id"]: json.loads(x) for x in DECISIONS.read_text(encoding="utf-8").splitlines() if x.strip()}
    supplied = [json.loads(x) for x in Path(a.price_input).read_text(encoding="utf-8").splitlines() if x.strip()]
    old = set()
    if OUTCOMES.exists(): old = {(json.loads(x)["snapshot_id"], json.loads(x)["horizon"]) for x in OUTCOMES.read_text(encoding="utf-8").splitlines() if x.strip()}
    additions=[]
    for x in supplied:
        snap = decisions.get(x.get("snapshot_id")); horizon=x.get("horizon")
        if not snap or horizon not in HORIZONS or (x.get("snapshot_id"), horizon) in old: continue
        cutoff = dt.datetime.fromisoformat(snap["decision_cutoff"].replace("Z", "+00:00")).date()
        if as_of < cutoff + dt.timedelta(days=HORIZONS[horizon]): continue
        if not x.get("available_at") or x["available_at"] <= snap["decision_cutoff"]: continue
        row={"schema_version":"GMFQ_CORE_FORWARD_OUTCOME_V1.0.0","snapshot_id":snap["snapshot_id"],"horizon":horizon,"gross_return":x.get("gross_return"),"cost_bps":x.get("cost_bps"),"net_return":None if x.get("gross_return") is None or x.get("cost_bps") is None else x["gross_return"]-x["cost_bps"]/10000,"source_id":x.get("source_id"),"available_at":x["available_at"]}
        row["outcome_sha256"]=sha(row); additions.append(row)
    if additions and not a.dry_run:
        OUTCOMES.parent.mkdir(parents=True,exist_ok=True)
        with OUTCOMES.open("ab") as f:
            for row in additions: f.write(canonical(row))
    print(json.dumps({"status":"PASS","appended":len(additions),"decision_rows_untouched":True,"join_key":"snapshot_id"},sort_keys=True))

if __name__ == "__main__": main()
