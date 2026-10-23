#!/usr/bin/env python3
"""USD labour -> UST 2Y -> ECB EUR/USD research association, no causal attribution.

This module observes the next available DAILY sources after original BLS dates,
never an intraday event window. ECB reference fixings are normally determined at
14:10 Europe/Rome, 20 minutes BEFORE the 08:30 NY BLS U-3 release.
Unverified pre-release consensus, matched OIS or release-timed market ticks are
absent. No surprise, repricing, predictive validity, backtest or FX trade signal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp
from validation.macro.v2_bls_us_u3_2026_shadow_replay_v1 import evidence, validate
from validation.macro.v2_bls_us_unrate_25_release_pilot_v1 import read_fixture
from validation.macro.v2_bls_shutdown_sparse_reentry_v1 import load_evidence

RECEIPT = "GMFQ_MACRO_V2_BLS_DAILY_MARKET_ASSOCIATION_AUDIT_V1"
SOURCE_FX = "live_data/sections/ECB_G8_PRICE_HISTORY.json"
SOURCE_RATES = "live_data/sections/NATIVE_RATES_DATA.json"
SOURCE_OIS = "validation/cb_pricing/history/OIS_G8_SNAPSHOTS_V1.jsonl"
SOURCE_QUOTES = "validation/cb_pricing/history/OIS_SAME_CONTRACT_QUOTES_V1.jsonl"
ECBFIX = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"
UST = "https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics"
SIFMA = "https://www.sifma.org/resources/general/holiday-schedule"
WINDOW_END = date(2026, 10, 23)
BAD_MARKET_SESSION = {
    "2026-04-03": "GOOD_FRIDAY_US_BOND_EARLY_CLOSE",
    "2026-07-02": "INDEPENDENCE_DAY_US_BOND_EARLY_CLOSE",
}
MIN_SOURCE_RATES = date(2026, 1, 1)


def read_json(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def read_lines(root: Path, path: str) -> list[dict]:
    return [json.loads(x) for x in (root / path).read_text(encoding="utf-8").splitlines()
            if x.strip()]


def safe_number(v: object) -> bool:
    return type(v) in (int, float) and math.isfinite(v)


def parse_day(s: str) -> date:
    require(isinstance(s,str) and len(s)==10, "invalid ISO observation date")
    try:
        d=date.fromisoformat(s)
    except ValueError as ex:
        raise ValueError("invalid source day") from ex
    require(d.isoformat()==s, "noncanonical calendar date")
    return d


def dated_series(days: list, vals: list, *, limit: date, kind: str) -> list[tuple[date,float]]:
    require(isinstance(days,list) and isinstance(vals,list) and
            len(days)==len(vals) and len(days)>100,
            kind+": insufficient aligned official daily observations")
    seen=set();out=[];previous=None
    for ds,v in zip(days,vals):
        d=parse_day(ds)
        require(safe_number(v) and 0.01< v < (20 if kind=="UST2Y" else 3),
                kind+": invalid rate/fixing")
        require(d<=limit and d not in seen and (previous is None or d>previous),
                kind+": future, duplicate or reversed source date")
        out.append((d,float(v)));seen.add(d);previous=d
    return out


def inventory(*, rates: dict, fx: dict, ois: list[dict],
              contracts: list[dict], bls: dict, as_of: date) -> dict:
    require(as_of==WINDOW_END, "audit fixed at 2026-10-23; no later data inferred")
    validate(bls,read_fixture(),load_evidence())
    require(isinstance(rates,dict) and set(rates)==
            {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"},
            "G8 sovereign source keys drifted")
    usd=rates["USD"]
    require(usd.get("quality")=="FULL_CURRENT_OFFICIAL" and
            isinstance(usd.get("source"),str) and
            usd["source"].startswith("U.S. Department of the Treasury") and
            parse_day(usd["date"])<=as_of and
            usd["history2"].get("last_date")==usd["date"] and
            usd["history2"].get("last_value")==usd["2Y"],
            "USD Treasury 2Y current source integrity failed")
    y=dated_series(usd["history2"]["dates"],usd["history2"]["values"],
                   limit=as_of,kind="UST2Y")
    require(y[-1][0].isoformat()==usd["date"],
            "latest UST Treasury observation is not the dated canonical value")
    require(fx.get("schema")=="GMFQ_ECB_G8_PRICE_HISTORY_V1" and
            fx.get("status")=="CURRENT_OFFICIAL_HISTORY" and fx.get("base")=="EUR" and
            fx.get("source")=="ECB euro foreign exchange reference rates" and
            fx.get("source_url")=="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml" and
            "USD" in fx.get("currencies",[]) and fx.get("row_count")==len(fx.get("rows",[])),
            "ECB daily EUR/USD source contract failed")
    raw_fx=fx["rows"]
    f=dated_series([x.get("Date") for x in raw_fx],
                   [x.get("USD") for x in raw_fx],
                   limit=as_of,kind="EURUSD")
    require(f[-1][0].isoformat()==fx["last_as_of"],
            "last ECB fixing does not match official FX ledger date")
    require(f[0][0].isoformat()==fx["first_as_of"] and
            usd["history2"]["dates"][0]>="2025-01-01",
            "historical dataset coverage changed unexpectedly")
    # Recent same-contract research snapshots begin only in October 2026.
    # These are futures proxies; even a dated quote is not an OIS surprise.
    for row in contracts:
        require(row.get("schema")=="GMFQ_OIS_SAME_CONTRACT_QUOTE_V1" and
                row.get("official_ois_quote") is False and
                row.get("policy_delta_eligible") is False and
                row.get("backtest_eligible_as_official") is False,
                "estimated futures contract must not be promoted as official OIS")
        require(parse_day(row["observation_date"])<=as_of,
                "future-dated contract in history")
    for row in ois:
        require(row.get("schema")=="GMFQ_OIS_G8_SNAPSHOT_V1" and
                row.get("backtest_eligible_as_official") is False and
                (row.get("source_as_of") is None or
                 parse_day(row["source_as_of"])<=as_of),
                "OIS operational snapshot cannot be used as certified backtest")
    first_contract=min((parse_day(x["observation_date"]) for x in contracts),
                       default=None)
    first_ois=min((parse_day(x["source_as_of"]) for x in ois
                   if x.get("currency")=="USD" and x.get("source_as_of")),default=None)
    require(first_contract is not None and first_contract>=date(2026,10,16)
            and first_ois is not None and first_ois>=date(2026,10,16),
            "earlier market-pricing history may need a new event-window audit")
    release_rows=bls["first_release_values"]
    out=[]
    for row in release_rows:
        instant=timestamp(row["released_at"])
        release=instant.astimezone(ZoneInfo("America/New_York")).date()
        require(instant.date()<=as_of and row["observation_period"].startswith("2026-"),
                "BLS 2026 release outside audit")
        # Always classify the event-day ECB fixing BEFORE BLS, regardless of
        # its delayed 16:00 publication; never mistake publication for collection.
        local_fix=datetime.combine(release,time(14,10),ZoneInfo("Europe/Rome"))
        require(local_fix.astimezone(timezone.utc)<instant,
                "ECB 14:10 reference time is not before this BLS announcement")
        before_fix=[(d,v) for d,v in f if d<=release]
        after_fix=[(d,v) for d,v in f if d>release]
        require(before_fix and after_fix, "ECB observation missing around event")
        bday,bval=before_fix[-1];aday,aval=after_fix[0]
        # ECB on release day is a pre-BLS reference (if recorded), never the
        # post-release market response.
        require((release-bday).days<=5 and 1<=(aday-release).days<=6,
                "ECB nearest references span too many calendar days")
        fx_change=(aval/bval-1)*100
        previous=[(d,v) for d,v in y if d<release]
        same=[(d,v) for d,v in y if d==release]
        require(previous, "no UST2Y prior reference")
        pd,pv=previous[-1]
        lag=(release-pd).days
        treasury={
            "pre_reference_day":pd.isoformat(),
            "pre_2y_percent":pv,
            "pre_gap_calendar_days":lag,
            "event_day":release.isoformat() if same else None,
            "event_day_2y_percent":same[0][1] if same else None,
            "daily_observed_move_bp":round((same[0][1]-pv)*100,2) if same else None,
            "end_of_day_ust_3_30pm_et_not_intraday_tick":True,
            "multi_session_pre_gap":lag>3,
            "session_warning":BAD_MARKET_SESSION.get(release.isoformat()),
            "interpretation":("NO_SAME_DAY_RECORD" if not same else
                "HOLIDAY_REDUCED_MARKET_ACTIVITY" if release.isoformat() in BAD_MARKET_SESSION else
                "MULTI_SESSION_PRE_REFERENCE" if lag>3 else
                "DAILY_SESSION_ASSOCIATION_ONLY"),
        }
        fxr={
            "pair":"EURUSD","unit":"USD per EUR",
            "pre_fixing_day":bday.isoformat(),"pre_fixing_eurusd":bval,
            "event_date_fixing_if_available":(bval if bday==release else None),
            "event_date_fixing_role":"PRE_RELEASE_NOT_RESPONSE" if bday==release else "NONE_MARKET_HOLIDAY",
            "first_later_fixing_day":aday.isoformat(),
            "first_later_fixing_eurusd":aval,
            "calendar_days_from_pre_to_later":(aday-bday).days,
            "next_fixing_eurusd_change_pct":round(fx_change,5),
            "direction_usd_vs_eur":("USD_STRONGER" if fx_change<0 else
                                     "USD_WEAKER" if fx_change>0 else "FLAT"),
            "interpretation":"NEXT_REFERENCE_COMPARISON_NOT_INTRADAY_OR_CAUSAL",
            "extended_interval":(aday-bday).days>4,
        }
        out.append({
            "observation_period":row["observation_period"],
            "BLS_first_released_at_utc":instant.isoformat(),
            "BLS_U3_first_release_value_pct":row["value"],
            "release_day":release.isoformat(),
            "consensus_status":"NOT_AVAILABLE_PRE_RELEASE_NO_SURPRISE_CALCULATED",
            "OIS_event_window_status":"NO_TIMESTAMPED_HISTORICAL_OIS_QUOTES",
            "ust_2y":treasury,"eurusd_ecb_reference":fxr,
            "event_causal_conclusion":None,
            "usd_directional_prediction":None,
            "tradable_reaction_event":False,
        })
    require(len(out)==9, "BLS event count changed")
    return {
        "schema":RECEIPT, "status":"DESCRIPTIVE_DAILY_ASSOCIATION_ONLY",
        "as_of":as_of.isoformat(),
        "coverage":{
            "BLS_releases":len(out),
            "UST2Y_daily_pairs_with_event_observation":
                sum(x["ust_2y"]["event_day"] is not None for x in out),
            "UST2Y_clean_uninterrupted_normal_sessions":
                sum(x["ust_2y"]["interpretation"]=="DAILY_SESSION_ASSOCIATION_ONLY" for x in out),
            "UST2Y_problematic_or_multisession":
                sum(x["ust_2y"]["interpretation"]!="DAILY_SESSION_ASSOCIATION_ONLY" for x in out),
            "ECB_pre_and_first_later_fixings":len(out),
            "ECB_missing_event_day_fixings":
                sum(x["eurusd_ecb_reference"]["event_date_fixing_if_available"] is None for x in out),
            "OIS_true_release_aligned_windows":0,
            "BLS_pre_release_consensus_synchronized":0,
            "intraday_millisecond_aligned_FX_or_rates":0,
        },
        "sources":{
            "BLS":"https://www.bls.gov/bls/news-release/empsit.htm",
            "US_Treasury":UST,"ECB_FX":ECBFIX,
            "US_good_friday_exception":SIFMA,
            "source_dataset_US_Treasury":SOURCE_RATES,
            "source_dataset_ECB":SOURCE_FX,
            "source_dataset_OIS":SOURCE_OIS,
            "source_dataset_same_contract_futures":SOURCE_QUOTES,
            "FX_fixing_method_reference_local":"14:10 Europe/Rome approximate",
            "BLS_original_publish_local":"08:30 America/New_York",
            "UST_end_of_day_method_reference_local":"15:30 America/New_York approximate",
            "history_fx_last_date":fx["last_as_of"],
            "history_rates_last_date":usd["date"],
            "ois_usd_earliest_observed_date":first_ois.isoformat(),
        },
        "events":out,
        "source_market_fixes_independently_verified_at_event":False,
        "claim_actual_surprise_against_consensus":False,
        "claim_intraday_repricing_or_OIS":False,
        "claim_causal_response":False,
        "claim_out_of_sample_predictive_effect":False,
        "ready_for_economic_fx_strength_model":False,
        "eligible_for_backtest":False,
        "safe_to_publish_new_D":False,
        "safe_to_update_pair_theses":False,
        "writes_live_data":False,
    }


def run(root: Path = ROOT, *, as_of: date = WINDOW_END) -> dict:
    receipt=inventory(
        rates=read_json(root,SOURCE_RATES),
        fx=read_json(root,SOURCE_FX),
        ois=read_lines(root,SOURCE_OIS),
        contracts=read_lines(root,SOURCE_QUOTES),
        bls=evidence(),as_of=as_of)
    summary={k:v for k,v in receipt.items() if k!="events"}
    receipt["method_fingerprint_sha256"]=hashlib.sha256(json.dumps({
        "summary":summary,"events":receipt["events"]
    },sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return receipt


def markdown(report: dict) -> str:
    cov=report["coverage"]
    lines=[
        "# Macro V2 — BLS → Treasury 2Y → ECB fixing (research, not causality)",
        "As of 23 October 2026 · No pre-release consensus, no aligned OIS history.",
        "",
        f"Events: {cov['BLS_releases']}; daily UST same-day matches: "
        f"{cov['UST2Y_daily_pairs_with_event_observation']}; clean-rate "
        f"calendar sessions: {cov['UST2Y_clean_uninterrupted_normal_sessions']}; "
        f"daily ECB next-fixing comparisons: {cov['ECB_pre_and_first_later_fixings']}.",
        "ECB event-day fixing is BEFORE BLS 08:30 NY, not a post-release price. "
        "USD stronger if USD-per-EUR declines, not vice versa.",
        "",
        "| Release | U-3 | 2Y daily bp | 2Y date quality | Next ECB fix vs pre (%) | First later ECB date |",
        "| --- | ---: | ---: | --- | ---: | --- |",
    ]
    for r in report["events"]:
        y=r["ust_2y"];fx=r["eurusd_ecb_reference"]
        lines.append("| {date} | {bls:.1f}% | {bp} | {q} | {change:+.3f}% | {after} |".format(
            date=r["release_day"],bls=r["BLS_U3_first_release_value_pct"],
            bp="n.a." if y["daily_observed_move_bp"] is None else
               f"{y['daily_observed_move_bp']:+.1f}",
            q=y["interpretation"],change=fx["next_fixing_eurusd_change_pct"],
            after=fx["first_later_fixing_day"],
        ))
    lines+=["",
        "**Do not read these differences as a Labour surprise response.** "
        "The daily Treasury curve is collected around 15:30 NY and can absorb "
        "other news; ECB reference is at about 14:10 Rome, earlier than BLS "
        "at 14:30. Longer weekends and Good Friday invalidate clean isolation.",
        "**No OIS event-window data:** existing futures-based proxy snapshots "
        "begin only 16 October 2026, after all nine BLS releases.",
        "**No pre-release consensus:** actual-minus-consensus surprises, "
        "conditional price responses and causal strength cannot be assessed.",
        "**No model promotion:** Macro scores, ranking, trading decisions "
        "and backtests remain blocked.",""]
    return "\n".join(lines)


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--json-out",type=Path)
    parser.add_argument("--markdown-out",type=Path)
    args=parser.parse_args()
    result=run()
    for path,content in (
        (args.json_out,json.dumps(result,indent=2,ensure_ascii=False)+"\n"),
        (args.markdown_out,markdown(result)+"\n"),
    ):
        if path:
            require(path.resolve().is_relative_to(Path("/tmp")),
                    "audit may write only to temporary research files")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content,encoding="utf-8")
    print(json.dumps({"status":result["status"],"coverage":result["coverage"],
                      "safe_to_publish_new_D":result["safe_to_publish_new_D"]}))


if __name__=="__main__":
    main()
