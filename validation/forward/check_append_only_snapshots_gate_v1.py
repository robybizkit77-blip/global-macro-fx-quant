#!/usr/bin/env python3
"""Fail-closed growing Forward snapshot journal audit, independent of outcomes.

The final E2E gate previously required exactly one 28-pair smoke capture.
Legitimate later forward captures must NOT break site publishing. Validate
full append-only batches, identities, hashes, and no future input leakage.
Legacy V1.0 lacks the V1.1 PIT evidence fields: accept only as older
observational schema, NEVER certify historical PIT or forward performance.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from itertools import combinations

G8=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
PAIR_KEYS={tuple(sorted((a,b))) for a,b in combinations(sorted(G8),2)}
SCHEMAS={"GMFQ_CORE_FORWARD_DECISION_LOGGER_V1.0.0","GMFQ_CORE_FORWARD_DECISION_LOGGER_V1.1.0"}
FORWARD_RETURN_KEYS={"outcome","forward_return","future_return","future_pnl",
                     "realized_return","target_label","trade_pnl"}


def check(ok, reason):
    if not ok: raise ValueError("FORWARD_ARCHIVE_JOURNAL_REJECTED: "+reason)


def utc(stamp):
    check(isinstance(stamp,str), "missing source clock")
    try: x=dt.datetime.fromisoformat(stamp.replace("Z","+00:00"))
    except ValueError as exc: raise ValueError("invalid source clock") from exc
    check(x.tzinfo is not None and x.utcoffset()==dt.timedelta(0),"clock must be UTC-aware")
    return x


def canonical_hash(row):
    payload={k:v for k,v in row.items() if k!="snapshot_sha256"}
    return hashlib.sha256((json.dumps(payload,sort_keys=True,
        ensure_ascii=False,separators=(",",":"))+"\n").encode("utf-8")).hexdigest()


def inspect(rows):
    check(isinstance(rows,list) and len(rows)>=28 and len(rows)%28==0,
          "only complete 28-cross snapshot batches accepted")
    group_order=[]
    groups={}
    ids=set()
    for row in rows:
        check(isinstance(row,dict),"JSONL row must be an object")
        check(not (FORWARD_RETURN_KEYS & set(row)), "decision contains future outcomes")
        pair=row.get("pair")
        base, quote=row.get("base_currency"),row.get("quote_currency")
        check(isinstance(pair,str) and base in G8 and quote in G8 and base != quote
              and pair==base+"/"+quote and tuple(sorted((base,quote))) in PAIR_KEYS,
              "non-G8 or inconsistent cross identity")
        cutoff=row.get("decision_cutoff")
        now=utc(cutoff)
        runid=row.get("run_id")
        check(isinstance(runid,str) and bool(runid.strip()),"no unique batch run ID")
        key=(runid,cutoff)
        if key not in groups:
            group_order.append(key)
            groups[key]=[]
        check(group_order[-1]==key,"interleaved / rewritten snapshot batch")
        check(row.get("schema_version") in SCHEMAS,"unknown Forward schema version")
        check(re.fullmatch("[0-9a-f]{40}",str(row.get("source_commit"))) is not None,
              "invalid source commit reference")
        sid=row.get("snapshot_id")
        check(re.fullmatch("[0-9a-f]{64}",str(sid)) is not None and sid not in ids,
              "invalid or repeated snapshot identity")
        ids.add(sid)
        check(row.get("snapshot_sha256")==canonical_hash(row),
              "body tampered / SHA256 mismatch")
        check(row.get("rules_fingerprint") is not None,
              "missing original decision rules reference")
        if row["schema_version"].endswith("V1.1.0"):
            check(row.get("core_recomputed_at_capture") is False and
                  row.get("current_macro_score_certified") is False and
                  row.get("source_panel_is_true_historical_pit") is False and
                  row.get("price_anchor_is_executable") is False,
                  "v1.1 historical score, market price, or PIT certification forgery")
            check(isinstance(row.get("inputs"),dict) and row["inputs"],
                  "v1.1 dated source provenance missing")
            for inp in row["inputs"].values():
                if not isinstance(inp,dict):continue
                avail=inp.get("available_at")
                if avail is not None:
                    check(utc(avail)<=now,"future source used in prior capture")
        groups[key].append(row)
    expected=PAIR_KEYS
    canonical_pair_spelling={x["pair"] for x in groups[group_order[0]]}
    previous=None
    v1_0=0
    for key in group_order:
        lines=groups[key]
        check(len(lines)==28 and
              {tuple(sorted((x["base_currency"],x["quote_currency"]))) for x in lines}==expected
              and {x["pair"] for x in lines}==canonical_pair_spelling,
              "missing / duplicate / extra G8 pair or orientation drift in capture")
        check(len({x["schema_version"] for x in lines})==1,
              "mixed schema inside same cutoff")
        check(len({x["source_commit"] for x in lines})==1,
              "multiple source commits in same cutoff")
        check(len({x["rules_fingerprint"] for x in lines})==1,
              "multiple rule fingerprints in same cutoff")
        clock=utc(key[1])
        check(previous is None or clock>previous,"replayed / reversed cutoff chronology")
        previous=clock
        if lines[0]["schema_version"].endswith("V1.0.0"):
            v1_0+=1
    return {
        "schema":"GMFQ_FORWARD_GROWING_28_PAIR_JOURNAL_GATE_V1",
        "status":"PASS_RESEARCH_OBSERVATIONAL_ARCHIVE_NOT_FORWARD_VALIDATION",
        "snapshot_rows":len(rows),"complete_28_pair_batches":len(group_order),
        "unique_pairs_per_batch":28,"legacy_v1_0_batches":v1_0,
        "cutoffs":[key[1] for key in group_order],
        "run_ids":[key[0] for key in group_order],
        "snapshot_hash_identity_integrity":True,
        "batch_chronology_and_pair_set_integrity":True,
        "source_available_at_not_future_for_v1_1":True,
        "legacy_v1_0_missing_some_provenance_not_PIT":True,
        "no_forward_returns_embedded":True,
        "backtest_PIT_certified":False,
        "forward_outcomes_validated":False,
        "Beta_PDF_A_to_Z_certified":False,
        "safe_to_modify_core_or_pairs":False,
    }
