#!/usr/bin/env python3
"""Preregistered future-only 6M futures / FX reference direction experiment.

This is NOT a trading signal or a certified predictive model. Runs only
after the real evening ECB fixing, never backfills old decisions, freezes
all 28 pair statuses, and observes five future ECB fixing sessions.
"""
from __future__ import annotations

from datetime import datetime, date, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import argparse
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.quant.fxv2_rates_fx_temporal_readiness_v1 import (
    FX_PATH, QUOTES_PATH, MACRO_PATH, validate_fx, validate_quotes, validate_macro,
    utc_first_seen, decimal_rate,
)

ROOT=Path(__file__).resolve().parents[2]
POLICY_PATH=ROOT/"validation/quant/FXV2_6M_PREREGISTERED_PROTOCOL_V1.json"
JOURNAL=ROOT/"validation/quant/prospective/FXV2_6M_FROZEN_EXPERIMENT_V1.jsonl"
OUTCOMES=ROOT/"validation/quant/prospective/FXV2_6M_FUTURE_ECB_REFERENCE_V1.jsonl"
ROME=ZoneInfo("Europe/Rome")
SCHEMA="GMFQ_FXV2_FROZEN_6M_FX_EXPERIMENT_V1"
OUT_SCHEMA="GMFQ_FXV2_6M_OBSERVED_FUTURE_REFERENCE_V1"
CANDIDATES={"EUR/USD","EUR/CHF","USD/CHF"}


def require(v,why):
    if not v: raise ValueError("FXV2_6M_PROSPECTIVE_REJECTED: "+why)


def canonical(row):
    return (json.dumps(row,ensure_ascii=False,sort_keys=True,
                       separators=(",",":"))+"\n").encode("utf-8")


def seal(row):
    return sha256(canonical(row)).hexdigest()


def sign(x):
    return 1 if x>0 else -1 if x<0 else 0


def price(row,base,quote):
    # ECB rates: units of currency per EUR => quote/base cross.
    a,b=row[base],row[quote]
    require(a>0 and b>0,"nonpositive ECB FX")
    return b/a


def policy_ok(p):
    require(p.get("schema")=="GMFQ_FXV2_PREREGISTERED_6M_FX_FUTURES_TRIAL_V1" and
            p.get("earliest_eligible_capture_rome")=="2026-11-06" and
            p.get("rate_data_eligible_pairs")==["EUR/USD","EUR/CHF","USD/CHF"] and
            p.get("source_rate_classification")=="SECONDARY_LISTED_FUTURES_NOT_OIS_AND_NOT_POLICY_REPRICING" and
            p.get("signal_definition",{}).get("magnitude_threshold_abs_bp")==2.0 and
            p.get("baseline",{}).get("name")=="FIVE_ECB_FIXING_SESSIONS_FX_MOMENTUM" and
            p.get("target",{}).get("horizon")=="FIVE_FUTURE_ECB_REFERENCE_FIXING_SESSIONS" and
            p.get("pre_capture_rules",{}).get("max_lag_ECB_sessions_between_feature_last_market_day_and_T0")==2 and
            p.get("eligible_for_live_fx_engine") is False and
            p.get("eligible_for_trading") is False and
            p.get("original_28_pair_signals_untouched") is True,
            "preregistration contract changed: new experiment version required")


def check_clock(now,policy):
    require(isinstance(now,datetime) and now.tzinfo is not None and
            now.utcoffset() is not None,"real timezone-aware observation required")
    local=now.astimezone(ROME)
    require(local.weekday()<5 and local.hour>=19 and
            local.date()>=date.fromisoformat(policy["earliest_eligible_capture_rome"]),
            "not an eligible prospective Rome cutoff")
    return now.astimezone(timezone.utc), local.date().isoformat()


def verified_journal(rows,policy_hash):
    seen=set()
    for r in rows:
        require(r.get("schema")==SCHEMA and r.get("frozen_sha256")==seal({
            k:v for k,v in r.items() if k!="frozen_sha256"
        }),"tampered prospective freeze")
        require(r.get("policy_sha256")==policy_hash and
                r.get("eligible_for_fx_engine") is False and
                r.get("experimental_not_trading") is True and
                r.get("future_price_observed_at_capture") is False and
                len(r.get("pairs",{}))==28,
                "old journal unregistered or promoted")
        d=r.get("rome_day")
        require(d not in seen and
                r["captured_at_utc"].startswith(d) and
                d>="2026-11-06", "duplicate or backfilled research date")
        seen.add(d)
    return seen


def actual_quote_feature(by_quote,days,t0_index,now):
    """Only choose a single same listed contract for consecutive ECB days."""
    end=t0_index
    for lag in range(3):
        ix=end-lag
        if ix<1: break
        prev,day=days[ix-1],days[ix]
        matched={}
        for c in ("USD","EUR","CHF"):
            older={x["contract"]:x for x in by_quote.get((c,"6m",prev),())}
            newer={x["contract"]:x for x in by_quote.get((c,"6m",day),())}
            common=older.keys() & newer.keys()
            if len(common)!=1: continue
            instrument=next(iter(common))
            a,b=older[instrument],newer[instrument]
            if max(utc_first_seen(a["first_seen_at_utc"],"older"),
                   utc_first_seen(b["first_seen_at_utc"],"newer"))>now:
                continue
            matched[c]={
                "contract":instrument, "previous_date":prev.isoformat(),
                "last_market_date":day.isoformat(),
                "previous_seen_at_utc":a["first_seen_at_utc"],
                "last_seen_at_utc":b["first_seen_at_utc"],
                "change_bp":float((Decimal("100")*(
                    decimal_rate(b["implied_rate"],"new")-
                    decimal_rate(a["implied_rate"],"old")
                )).quantize(Decimal("0.001"),rounding=ROUND_HALF_UP))
            }
        # Caller only accepts matched legs that both refer to this SAME
        # last market day; don't use a USD update and stale EUR update.
        yield lag,matched


def freeze(now,policy,fx,quotes,macro,prior=(),policy_hash=None,fx_hash=None,quotes_hash=None):
    policy_ok(policy)
    when,local_day=check_clock(now,policy)
    days=validate_fx(fx)
    names=validate_macro(macro)
    by_quote=validate_quotes(quotes)
    digest=policy_hash or seal(policy)
    existing=verified_journal(prior,digest)
    if local_day in existing:
        return None,"ALREADY_FROZEN_NO_OVERWRITE"
    if fx["last_as_of"]!=local_day:
        return None,"NO_SAME_DAY_OFFICIAL_ECB_FIXING"
    idx=len(days)-1
    require(days[idx].isoformat()==local_day and idx>=5,"missing five-session pre-capture price history")
    pair_data={}
    present={name:set() for name in CANDIDATES}
    for old in prior:
        for name in CANDIDATES:
            e=old["pairs"].get(name) or {}
            if e.get("last_rate_market_date"):
                present[name].add(e["last_rate_market_date"])
    all_matched=list(actual_quote_feature(by_quote,days,idx,when))
    for pair in names:
        a,b=pair.split("/")
        px=price(fx["rows"][idx],a,b)
        oldpx=price(fx["rows"][idx-5],a,b)
        mom=math.log(px/oldpx)
        row={
            "status":"ABSTAIN_NO_SUPPORTED_6M_SOURCE",
            "observed_fx_price_t0":px,
            "observed_fx_baseline_5fixing_log_return":round(mom,12),
            "momentum_sign":sign(mom),
            "experimental_rate_hypothesis_sign":None,
            "rate_change_bp":None,
            "last_rate_market_date":None,
            "base_contract":None,"quote_contract":None,
            "feature_first_usable_at_utc":None,
            "expected_fx_return":None,"trade_signal":None
        }
        if pair in CANDIDATES:
            for lag,matched in all_matched:
                if a not in matched or b not in matched:continue
                x,y=matched[a],matched[b]
                row["last_rate_market_date"]=x["last_market_date"]
                row["base_contract"]=x["contract"];row["quote_contract"]=y["contract"]
                row["source_lag_ecb_sessions"]=lag
                row["rate_change_bp"]=round(x["change_bp"]-y["change_bp"],3)
                row["base_rate_change_bp"]=x["change_bp"]
                row["quote_rate_change_bp"]=y["change_bp"]
                row["feature_first_usable_at_utc"]=max(
                    x["previous_seen_at_utc"],x["last_seen_at_utc"],
                    y["previous_seen_at_utc"],y["last_seen_at_utc"])
                require(utc_first_seen(row["feature_first_usable_at_utc"],"paired")<=when,
                        "rate quotes were not available at capture")
                if row["last_rate_market_date"] in present[pair]:
                    row["status"]="ABSTAIN_REPEATED_SAME_SOURCE_FEATURE"
                elif abs(row["rate_change_bp"])<2:
                    row["status"]="ABSTAIN_SMALL_RELATIVE_MOVE"
                else:
                    row["status"]="FROZEN_EXPERIMENTAL_DIRECTION"
                    row["experimental_rate_hypothesis_sign"]=sign(row["rate_change_bp"])
                break
            if row["rate_change_bp"] is None:
                row["status"]="ABSTAIN_NO_RECENT_SAME_CONTRACT_6M_PAIR"
        pair_data[pair]=row
    count=sum(r["experimental_rate_hypothesis_sign"] in (-1,1)
              for r in pair_data.values())
    doc={
        "schema":SCHEMA,"policy_sha256":digest,
        "rome_day":local_day,
        "captured_at_utc":when.isoformat().replace("+00:00","Z"),
        "official_ecb_t0_day":local_day,
        "official_ecb_t0_source":"ECB_REFERENCE_NON_EXECUTABLE",
        "fx_history_sha256":fx_hash,
        "futures_archive_sha256":quotes_hash,
        "all_28_pairs_frozen":True,
        "new_experimental_directions":count,
        "future_price_observed_at_capture":False,
        "eligible_for_fx_engine":False,
        "experimental_not_trading":True,
        "historical_macro_PIT_validated":False,
        "no_backfill":True,
        "pairs":pair_data
    }
    doc["frozen_sha256"]=seal(doc)
    return doc,"FROZEN_PROSPECTIVE_COHORT"


def verified_outcomes(prior_outcomes,valid_snaps):
    known=set()
    for r in prior_outcomes:
        require(r.get("schema")==OUT_SCHEMA and
                r.get("observation_sha256")==seal({
                    k:v for k,v in r.items() if k!="observation_sha256"
                }) and
                r.get("trade_PNL") is None and r.get("alpha") is None,
                "tampered or falsely promoted outcomes")
        key=(r.get("snapshot_id"),r.get("pair"))
        require(key not in known and r.get("snapshot_id") in valid_snaps,
                "unknown or duplicated outcome")
        known.add(key)
    return known


def observe(now,policy,fx,snapshots,prior_outcomes=()):
    policy_ok(policy)
    when,local_day=check_clock(now,policy)
    days=validate_fx(fx)
    require(days[-1].isoformat()<=local_day,"future ECB price history")
    digest=seal(policy)
    verified_journal(snapshots,digest)
    valid_snaps={s["rome_day"]:s for s in snapshots}
    known=verified_outcomes(prior_outcomes,valid_snaps)
    date_to_index={r["Date"]:i for i,r in enumerate(fx["rows"])}
    observed=[]
    for snap in snapshots:
        t0=snap["rome_day"];i=date_to_index.get(t0)
        if i is None: continue
        if len(days)<=i+5: continue
        future=fx["rows"][i+5];maturity=days[i+5].isoformat()
        if maturity>local_day:continue
        for pair,entry in snap["pairs"].items():
            if entry["status"]!="FROZEN_EXPERIMENTAL_DIRECTION":continue
            key=(t0,pair)
            if key in known:continue
            a,b=pair.split("/")
            p0=price(fx["rows"][i],a,b)
            require(abs(p0-entry["observed_fx_price_t0"])<1e-12,
                    "frozen ECB t0 revised or changed, quarantine outcome")
            p1=price(future,a,b)
            ret=math.log(p1/p0)
            row={
                "schema":OUT_SCHEMA,"snapshot_id":t0,"pair":pair,
                "original_freeze_sha256":snap["frozen_sha256"],
                "t0_fixing_date":t0,"t5_fixing_date":maturity,
                "observed_at_utc":when.isoformat().replace("+00:00","Z"),
                "ecb_log_reference_return":round(ret,12),
                "experimental_rate_direction":entry["experimental_rate_hypothesis_sign"],
                "five_session_momentum_direction":entry["momentum_sign"],
                "rate_direction_correct_observed":(sign(ret)==entry["experimental_rate_hypothesis_sign"]) if ret!=0 else False,
                "baseline_direction_correct_observed":(sign(ret)==entry["momentum_sign"]) if ret!=0 else False,
                "not_independent_across_pairs_or_overlapping_dates":True,
                "statistically_validated":False,
                "no_inferred_policy_repricing":True,
                "trade_PNL":None,"alpha":None
            }
            row["observation_sha256"]=seal(row)
            observed.append(row)
    return observed


def read_jsonl(path):
    if not path.exists():return []
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def append(path,rows):
    if not rows:return
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as out:
        for row in rows:out.write(canonical(row).decode("utf-8"))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--verify-only",action="store_true")
    args=parser.parse_args()
    policy_bytes=POLICY_PATH.read_bytes()
    policy=json.loads(policy_bytes)
    fx_bytes=FX_PATH.read_bytes()
    quote_bytes=QUOTES_PATH.read_bytes()
    fx=json.loads(fx_bytes)
    macro=json.loads(MACRO_PATH.read_bytes())
    quotes=[json.loads(s) for s in quote_bytes.splitlines() if s.strip()]
    snapshots=read_jsonl(JOURNAL)
    existing_outcomes=read_jsonl(OUTCOMES)
    if args.verify_only:
        policy_ok(policy)
        verified_journal(snapshots,seal(policy))
        verified_outcomes(existing_outcomes,{r["rome_day"]:r for r in snapshots})
        print(json.dumps({"status":"PREREGISTERED_CONTRACT_AND_JOURNAL_VALID",
                          "capture_rows":len(snapshots),
                          "matured_reference_rows":len(existing_outcomes)}))
        return
    now=datetime.now(timezone.utc)
    freeze_row,status=freeze(now,policy,fx,quotes,macro,snapshots,
                             fx_hash=sha256(fx_bytes).hexdigest(),
                             quotes_hash=sha256(quote_bytes).hexdigest())
    if freeze_row:
        append(JOURNAL,[freeze_row])
        snapshots.append(freeze_row)
    # Outcome observer may run even when no fresh feature appears today.
    new_outcomes=observe(now,policy,fx,snapshots,existing_outcomes)
    append(OUTCOMES,new_outcomes)
    print(json.dumps({"status":status,"new_freezes":int(freeze_row is not None),
                      "new_experimental_directions":freeze_row["new_experimental_directions"] if freeze_row else 0,
                      "new_observed_reference_outcomes":len(new_outcomes),
                      "total_freezes":len(snapshots),
                      "no_trading_signal":True,"no_alpha_claim":True}))
if __name__=="__main__":
    main()
