#!/usr/bin/env python3
"""Single-date official-actual GitHub writer with bounded non-force CAS retries.

Runs only after the separate issuer UTC/2026 gate. Source capture remains
issuer-only and uses the real, post-network observation clock. If a concurrent
GitHub workflow commits to main, discard the candidate, re-read main,
reacquire the official source and recompute News Pulse, at most 3 attempts.
Do not rewrite another writer's actual or merge ledger SHA chains by guess.

NO intraday OIS/FX causal claims; no D/Core, 28 pairs, Beta or Forward writes.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime,timezone
from pathlib import Path

from validation.macro.freeze_pre_release_consensus_v1 import ROOT
from validation.macro.capture_official_postrelease_actuals_v1 import (
    run as capture_actuals, OUT, LEDGER,
)
from validation.macro.one_date_oct30_official_actual_fast_poll_gate_v1 import gate
from validation.macro.freeze_pre_release_consensus_v1 import read_existing

NEWS=ROOT/"live_data/sections/NEWS_PULSE_OPERATIONAL.json"
ALLOWED={
    "validation/macro/MACRO_OFFICIAL_ACTUAL_FIRST_SEEN_V1.jsonl",
    "live_data/sections/NEWS_PULSE_OPERATIONAL.json",
}
MAX_ATTEMPTS=3
SCHEMA="GMFQ_20261030_ACTUAL_SAFE_RECHECK_MAIN_CAS_RETRIES_V1"

def git(*args,check=True):
    process=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,
                           text=True,check=False)
    if check and process.returncode:
        raise RuntimeError("GIT_SAFE_PUBLICATION_FAILED ["+" ".join(args[:3])+"]: "
                           +process.stderr[-600:])
    return process

def check_files():
    # No other source, score, policy, model, calendar, or repository change
    # is permitted during this targeted official actual writer.
    changed=set(git("diff","--name-only").stdout.splitlines())
    staged=set(git("diff","--cached","--name-only").stdout.splitlines())
    untracked=set(git("ls-files","--others","--exclude-standard").stdout.splitlines())
    if (changed|staged|untracked)-ALLOWED:
        raise ValueError("OCT30_FAST_POLL_UNEXPECTED_LOCAL_FILES: "+
                         repr(sorted((changed|staged|untracked)-ALLOWED)))
    git("diff","--check")
    return changed|staged|untracked

def validate_news():
    n=json.loads(NEWS.read_text(encoding="utf-8"))
    ctx=n["macro_event_market_context"]
    if (ctx["schema"]!="GMFQ_MACRO_EVENT_CONTEXT_DAILY_MATCH_V1"
        or ctx["summary"]["events"]!=2
        or ctx["summary"]["FX_signals"]!=0
        or ctx["summary"]["issuer_event_intraday_reactions_certified"]!=0
        or any(row["event_causality_verified"] is not False
               or row["FX_trade_signal"] is not None
               or row["eligible_for_Core_Beta_Forward"] is not False
               for row in ctx["events"])):
        raise ValueError("EVENT_MARKET_CONTEXT_FAILED_NONCAUSAL_GATE")

def observe():
    # Observed result is recomputed on each checkout. If another writer
    # already recorded these event actuals, capture_actuals() is idempotent.
    official=capture_actuals()
    if (official["status"]!="OFFICIAL_ACTUAL_POST_RELEASE_FIRST_CAPTURE_MONITOR"
        or official["fx_or_rates_causality_verified"] is not False
        or official["actual_first_release_PIT_verified"] is not False
        or official["Core_changed"] is not False
        or official["Beta_or_Forward_changed"] is not False):
        raise ValueError("ACTUAL_ISSUER_SOURCE_RECEIPT_INVARIANTS_FAILED")
    if official["new_actuals"]:
        subprocess.run(["python","validation/build_news_pulse_operational_v1.py"],
                       cwd=ROOT,check=True)
        validate_news()
    return official

def attempt_commit():
    changes=check_files()
    if not changes:return True
    local=git("rev-parse","HEAD").stdout.strip()
    remote=git("ls-remote","origin","refs/heads/main").stdout.split()[0]
    if local!=remote:
        # Another writer may have already recorded the same issuer actual;
        # do not publish stale ledger or overwrite a newer News Pulse.
        return False
    git("config","user.name","github-actions[bot]")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    git("add",*sorted(ALLOWED))
    git("commit","-m","Capture issuer actual and noncausal macro context")
    attempted=git("push","origin","HEAD:main",check=False)
    if attempted.returncode==0:return True
    after=git("ls-remote","origin","refs/heads/main").stdout.split()[0]
    local_head=git("rev-parse","HEAD").stdout.strip()
    base=git("rev-parse","HEAD^").stdout.strip()
    if after==local_head:return True
    if after==base:
        raise RuntimeError("GIT_PUSH_REJECTED_WITHOUT_REMOTE_MOVEMENT: "+
                           attempted.stderr[-600:])
    return False

def refresh_main():
    # Only callable after the allowlist has been checked: nothing outside
    # the two generated files can be reset. The first observed runner
    # attempt is not retained after a conflict because on a new main
    # snapshot source/ledger reconciliation must be re-verified.
    check_files()
    git("fetch","origin","main")
    git("reset","--hard","origin/main")
    check_files()

def retry_transaction(observe_fn,commit_fn,reset_fn,attempts=MAX_ATTEMPTS):
    if type(attempts) is not int or not 1<=attempts<=MAX_ATTEMPTS:
        raise ValueError("ONLY_ONE_TO_THREE_BOUNDED_GITHUB_WRITE_ATTEMPTS")
    history=[]
    for attempt in range(1,attempts+1):
        receipt=observe_fn()
        if receipt["new_actuals"]==0:
            return {"status":"NO_NEW_OFFICIAL_ACTUAL_SOURCE", "attempts":attempt,
                    "history":history,"official_capture":receipt,"published":False}
        if commit_fn():
            return {"status":"OFFICIAL_ACTUAL_RECORDED_ON_MAIN",
                    "attempts":attempt,"history":history,
                    "official_capture":receipt,"published":True}
        history.append("MAIN_MOVED_RECONCILE_OFFICIAL_SOURCE_WITH_CURRENT_MAIN")
        if attempt < attempts:reset_fn()
    raise RuntimeError("OFFICIAL_ACTUAL_MAIN_CONFLICT_UNRESOLVED_AFTER_3_ATTEMPTS")

def run():
    # Defend direct invocation: no issuer HTTP before the precise event and
    # none on later years even if a GitHub Actions cron retries.
    now=datetime.now(timezone.utc)
    g=gate(read_existing(LEDGER),read_existing(OUT),now)
    if not g["should_poll"]:
        return {"schema":SCHEMA,"status":g["status"],"published":False,
                "attempts":0,"gate":g,"writes_Core_Beta_Forward":False}
    r=retry_transaction(observe,attempt_commit,refresh_main)
    r["schema"]=SCHEMA
    r["gate"]=g
    r["writes_Core_Beta_Forward"]=False
    r["first_observation_is_after_successful_issuer_parse"]=True
    r["never_force_push"]=True
    return r

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--receipt",type=Path,required=True)
    args=ap.parse_args()
    if not args.receipt.resolve().is_relative_to(Path("/tmp")):
        raise ValueError("GITHUB_RELEASE_RECEIPT_ONLY_UNDER_TMP")
    receipt=run()
    args.receipt.write_text(json.dumps(receipt,indent=2,sort_keys=True,
                                       ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":receipt["status"],
                      "attempts":receipt["attempts"],
                      "published":receipt["published"]},sort_keys=True))
if __name__=="__main__":main()
