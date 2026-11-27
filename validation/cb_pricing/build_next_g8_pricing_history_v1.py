#!/usr/bin/env python3
"""Derive a research-only G8 historical pricing chart feed from immutable sources.

No interpolated observations, no promotion to official OIS, no FX signal.
Official tenor snapshots are historical published 3M/6M/12M points, which can
still rotate futures contracts. Secondary quotes are single *listed contract*
bars, with unresolved historical conflicts removed. NZD uses archived ASX
bank-bill settlements and separately labeled derived prior references.
"""
from __future__ import annotations
import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from archive_nzd_asx_proxy_v1 import ARCHIVE as NZD_ARCHIVE, validate as validate_nzd_capture

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "site/fx-quant-v2/ois-pricing-snapshot.json"
OFFICIAL = ROOT / "validation/cb_pricing/history/OIS_G8_SNAPSHOTS_V1.jsonl"
QUOTES = ROOT / "validation/cb_pricing/history/OIS_SAME_CONTRACT_QUOTES_V1.jsonl"
CONFLICTS = ROOT / "validation/cb_pricing/history/OIS_SAME_CONTRACT_CONFLICTS_V1.jsonl"
NZD = ROOT / "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json"
DEST = ROOT / "site/fx-quant-v2/next/rates-pricing-history-v1.json"
CCYS = ("USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD")
TENORS = ("3m", "6m", "12m")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def good_day(v: object, cutoff: str) -> bool:
    if not isinstance(v, str) or len(v) != 10:
        return False
    try:
        return date.fromisoformat(v).isoformat() == v and v <= cutoff
    except ValueError:
        return False


def number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) < 1000


def prev_weekday(day: str) -> str:
    d = date.fromisoformat(day) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def nzd_monthly_reference(feed, observed, prices):
    """Separate fixed-contract evidence; never insert into rolling tenor history."""
    m=feed.get("monthly_reference")
    if not isinstance(m,dict) or m.get("schema")!="GMFQ_NZD_ASX_EXACT_20_WEEKDAY_REFERENCE_V1" or m.get("status")!="REFERENCE_PARSED" or m.get("official_ois_created") is not False or m.get("fx_engine_effect")!="NONE":
        return None
    d=feed.get("as_of")
    if not good_day(d,"2099-12-31") or m.get("as_of")!=d:
        return None
    ref=d
    for _ in range(20):
        ref=prev_weekday(ref)
    if m.get("reference_date")!=ref or m.get("current_source_url")!=feed.get("source_url") or m.get("reference_url")!="https://www.asx.com.au/data/futures/reports/EODWebMarketSummary"+date.fromisoformat(ref).strftime("%y%m%d")+"ZFT.htm":
        return None
    if not re.fullmatch(r"[a-f0-9]{64}",str(m.get("decoded_source_sha256",""))):
        return None
    h=m.get("horizons",{}).get("6m",{})
    current=feed.get("horizons",{}).get("6m",{})
    point=observed.get("6m",{}).get(d)
    if not point or not h or h.get("basis")!="EXACT_LISTED_ASX_BANK_BILL_CONTRACT_NOT_OIS":
        return None
    if not (h.get("contract")==current.get("expiry_label")==point["contract"] and h.get("expiration")==current.get("expiration")==point["expiration"]):
        return None
    vals=[h.get(k) for k in ("reference_price","reference_implied_pct","current_price","current_implied_pct","change_bp")]
    if not all(number(v) for v in vals):
        return None
    rp,rr,cp,cr,bp=vals
    if not (80<rp<105 and 80<cp<105 and abs(100-rp-rr)<.0002 and abs(100-cp-cr)<.0002 and cp==current.get("settlement_price") and cr==point["rate"] and abs(bp-(cr-rr)*100)<.011):
        return None
    existing=prices.get((ref,h["contract"],h["expiration"]),set())
    if existing and existing!={rp}:
        return None
    return {"from":ref,"to":d,"contract":h["contract"],"expiration":h["expiration"],
            "reference_rate":rr,"current_rate":cr,"change_bp":bp,
            "source_url":m["reference_url"],"source_sha256":m["decoded_source_sha256"],
            "basis":"EXACT_LISTED_ASX_BANK_BILL_CONTRACT_NOT_OIS"}


def usd_roll_momentum(points, daily_quotes):
    """Estimate a single observed rollover; no synthetic daily price series."""
    if not points:
        return {}
    last=points[-1]
    end=last["date"]
    result={}
    for days in (5,20):
        start=end
        for _ in range(days):
            start=prev_weekday(start)
        first=next((p for p in points if p["date"]==start),None)
        if not first or first["contract"]==last["contract"]:
            continue
        old,new=first["contract"],last["contract"]
        selected=[p for p in points if start<=p["date"]<=end]
        if {p["contract"] for p in selected}!={old,new}:
            continue
        old_last=max(p["date"] for p in selected if p["contract"]==old)
        new_first=min(p["date"] for p in selected if p["contract"]==new)
        if old_last>=new_first:
            continue
        # The tenor archive omits ambiguous mapping days from its chart.
        # Recover only a unique overlapping source day between the segments.
        overlap=[]
        for d,rows in daily_quotes.items():
            if not old_last<=d<=new_first or not start<d<end:
                continue
            if {q["contract"] for q in rows}!={old,new}:
                continue
            a=[q for q in rows if q["contract"]==old]
            b=[q for q in rows if q["contract"]==new]
            if len(a)!=1 or len(b)!=1:
                continue
            a,b=a[0],b[0]
            try:
                ta,tb=(datetime.fromisoformat(q["first_seen_at_utc"].replace("Z","+00:00")) for q in (a,b))
                gap=abs((tb-ta).total_seconds())/3600
            except (ValueError,TypeError):
                continue
            if gap>24 or a["expiration"]>=b["expiration"]:
                continue
            overlap.append((d,a,b,gap))
        if len(overlap)!=1:
            continue
        roll,a,b,gap=overlap[0]
        # No third contract or reversal hidden by an omitted tenor date.
        if any(q["contract"] not in (old,new) or
               (d<roll and q["contract"]==new) or (d>roll and q["contract"]==old)
               for d,rows in daily_quotes.items() if start<=d<=end for q in rows):
            continue
        old_move=round((a["implied_rate"]-first["rate"])*100,4)
        new_move=round((last["rate"]-b["implied_rate"])*100,4)
        result[str(days)]={"from":start,"to":end,"roll_date":roll,
            "old_contract":old,"new_contract":new,
            "start_rate":first["rate"],"old_roll_rate":a["implied_rate"],
            "new_roll_rate":b["implied_rate"],"end_rate":last["rate"],
            "old_move_bp":old_move,"new_move_bp":new_move,
            "change_bp":round(old_move+new_move,4),
            "capture_gap_hours":round(gap,3),
            "old_capture_utc":a["first_seen_at_utc"],"new_capture_utc":b["first_seen_at_utc"],
            "basis":"ESTIMATED_SINGLE_ROLL_SAME_SOURCE_NOT_SYNCHRONIZED",
            "official_ois_created":False,"fx_engine_effect":"NONE"}
    return result


def build(snapshot: dict, archive: list[dict], quotes: list[dict],
          conflicts: list[dict], nzd: dict, nzd_archive: list[dict] | None = None) -> dict:
    today = snapshot["snapshot_built_from_repo_date"]
    if not good_day(today, today):
        raise ValueError("invalid source snapshot date")
    source_currencies = snapshot["currencies"]
    if set(source_currencies) != set(CCYS):
        raise ValueError("all G8 sources required")

    # Quarantine the original AND conflicting prints, never silently choose one.
    disputed = {
        tuple(x["key"]) for x in conflicts
        if x.get("status") == "UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT"
    }
    official_points = defaultdict(dict)
    for rec in archive:
        c = rec.get("currency")
        if c not in ("GBP", "JPY", "CAD", "AUD"):
            continue
        if (rec.get("schema") != "GMFQ_OIS_G8_SNAPSHOT_V1" or
                rec.get("operational_status") != "GREEN_OFFICIAL" or
                rec.get("official_status") != "ACTIVE" or
                rec.get("method_id") != "OFFICIAL_CERTIFIED_V1" or
                rec.get("backtest_eligible_as_official") is not True):
            continue
        # An invalid rate invalidates the entire CAD curve, not just one tenor.
        if c == "CAD" and any(not number((rec.get("horizons", {}).get(t) or {}).get("rate"))
                or not -5 <= rec["horizons"][t]["rate"] <= 25 for t in TENORS):
            continue
        day = rec.get("source_as_of")
        if not good_day(day, today) or rec.get("source") != source_currencies[c]["source"]:
            continue
        if str(rec.get("captured_at_utc", ""))[:10] < day:
            continue
        for t in TENORS:
            h = (rec.get("horizons") or {}).get(t) or {}
            v = h.get("rate")
            if not number(v):
                continue
            key = (day, t)
            existing = official_points[c].get(key)
            if not existing or rec["captured_at_utc"] > existing["captured_at_utc"]:
                official_points[c][key] = {
                    "date": day, "rate": round(float(v), 6),
                    "contract": None, "source_class": "OFFICIAL_TENOR",
                    "derived": False, "captured_at_utc": rec["captured_at_utc"]
                }

    secondary = defaultdict(lambda: defaultdict(list))
    for row in quotes:
        c, t, day = row.get("currency"), row.get("observed_under_horizon"), row.get("observation_date")
        if c not in ("USD", "EUR", "CHF") or t not in TENORS or not good_day(day, today):
            continue
        if (row.get("schema") != "GMFQ_OIS_SAME_CONTRACT_QUOTE_V1" or
            row.get("source_method") != "TRADINGVIEW_DATED_FUTURES_SSR_V2" or
            row.get("source_timestamp_evidence") != "SSR_DAILY_BAR_DATA_UPDATE_TIME" or
            row.get("official_ois_quote") is not False or
            row.get("policy_delta_eligible") is not False or
            row.get("backtest_eligible_as_official") is not False):
            continue
        if (c, row.get("contract"), day) in disputed:
            continue
        if not good_day(row.get("expiration"), "2099-12-31"):
            continue
        rate, price = row.get("implied_rate"), row.get("futures_price")
        if not number(rate) or not number(price) or abs((100.0 - price) - rate) > .011:
            continue
        if not str(row.get("first_seen_at_utc", ""))[:10] >= day:
            continue
        secondary[(c, t)][day].append(row)

    # Archived and current NZD source captures are independent observed levels.
    # Conflicts are quarantined across all horizons by listed contract identity.
    nzd_candidates = defaultdict(list)
    nzd_contract_prices = defaultdict(set)
    for record in (nzd_archive or []) + [{"schema": "GMFQ_NZD_ASX_PROXY_CAPTURE_V1",
                                           "source_commit": "VALIDATED_COLLECTOR_RUNTIME", "feed": nzd}]:
        try:
            feed = validate_nzd_capture(record)["feed"]
        except (ValueError, TypeError, KeyError):
            continue
        d = feed["as_of"]
        if not good_day(d, today):
            continue
        for t, h in feed["horizons"].items():
            identity = (d, h["expiry_label"], h["expiration"])
            nzd_contract_prices[identity].add(h["settlement_price"])
            nzd_candidates[(t, d)].append((identity, h["implied_bank_bill_rate"]))
    nzd_conflicts = {key for key, prices in nzd_contract_prices.items() if len(prices) > 1}
    nzd_observed = defaultdict(dict)
    for (t, d), candidates in nzd_candidates.items():
        identities = {x[0] for x in candidates}
        if len(identities) != 1 or identities & nzd_conflicts:
            continue
        identity, value = candidates[0]
        nzd_observed[t][d] = {"date": d, "rate": round(float(value), 6),
                              "contract": identity[1], "expiration": identity[2],
                              "source_class": "BANK_BILL_PROXY", "derived": False}
    # Current contract identities are NOT applied retrospectively to previous
    # instruments. Store contract in every point, break the graph at each roll.
    lines = {}
    for c in CCYS:
        row = source_currencies[c]
        tenors = {}
        for t in TENORS:
            if c in ("GBP", "JPY", "CAD", "AUD"):
                points = [dict(p) for (d, x), p in official_points[c].items() if x == t]
                for p in points:
                    p.pop("captured_at_utc", None)
            elif c in ("USD", "EUR", "CHF"):
                points = []
                for d, candidates in secondary[(c, t)].items():
                    # Different contracts on the same day under one horizon
                    # cannot be assigned an unambiguous point.
                    identities = {(x["contract"], x["expiration"]) for x in candidates}
                    if len(identities) != 1:
                        continue
                    item = min(candidates, key=lambda x: x["first_seen_at_utc"])
                    rates = [x["implied_rate"] for x in candidates]
                    if max(rates) - min(rates) > .00001:
                        continue
                    points.append({
                        "date": d, "rate": round(float(item["implied_rate"]), 6),
                        "contract": item["contract"], "source_class": "SECONDARY_SAME_CONTRACT",
                        "derived": False, "captured_at_utc": item["first_seen_at_utc"]
                    })
            else:  # NZD: archive plus explicitly reconstructed reference levels.
                points = []
                source_h = (nzd.get("horizons") or {}).get(t) or {}
                current = (row.get("horizons") or {}).get(t) or {}
                d, rate = row.get("as_of"), current.get("rate")
                if (nzd.get("schema") == "GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1" and
                        nzd.get("currency") == "NZD" and nzd.get("as_of") == d and
                        good_day(d, today) and number(rate) and
                        source_h.get("expiry_label") == current.get("contract") and
                        number(source_h.get("implied_bank_bill_rate")) and
                        abs(source_h["implied_bank_bill_rate"] - rate) < .00001):
                    # The current observed level is already in the validated capture set.
                    # Do not reconstruct a reference over a conflicting or actual archived date.
                    day1 = prev_weekday(d)
                    if (d in nzd_observed[t] and (t, day1) not in nzd_candidates
                            and number(source_h.get("change_1d_bp"))):
                        points.append({"date": day1,
                                       "rate": round(float(rate - source_h["change_1d_bp"]/100), 6),
                                       "contract": current.get("contract"),
                                       "source_class": "BANK_BILL_PROXY_DELTA_REFERENCE",
                                       "derived": True})
                    week = source_h.get("weekly_reference_trade_date")
                    if (d in nzd_observed[t] and (t, week) not in nzd_candidates
                            and good_day(week, d) and week < d and
                            5 <= (date.fromisoformat(d) - date.fromisoformat(week)).days <= 10
                            and number(source_h.get("change_1w_bp"))):
                        points.append({"date": week,
                                       "rate": round(float(rate - source_h["change_1w_bp"]/100), 6),
                                       "contract": current.get("contract"),
                                       "source_class": "BANK_BILL_PROXY_DELTA_REFERENCE",
                                       "derived": True})
                points.extend(nzd_observed[t].values())
            points.sort(key=lambda x: x["date"])
            tenors[t] = points
        lines[c] = {
            "kind": row["kind"], "quality": row["quality"], "source": row["source"],
            "tenors": tenors, "latest_date": max(
                (p["date"] for t in TENORS for p in tenors[t]), default=None),
            "observed_dates": len({p["date"] for t in TENORS for p in tenors[t] if not p["derived"]}),
            "derived_reference_points": sum(p["derived"] for t in TENORS for p in tenors[t]),
        }
    roll=usd_roll_momentum(lines["USD"]["tenors"]["6m"],secondary[("USD","6m")])
    if roll:
        lines["USD"]["estimated_roll_momentum"]=roll
    monthly=nzd_monthly_reference(nzd,nzd_observed,nzd_contract_prices)
    if monthly:
        lines["NZD"]["fixed_contract_20d"]=monthly
    # Build date is the upper bound for accepting observations, not a market date.
    latest_observation = max(
        (row["latest_date"] for row in lines.values() if row["latest_date"]),
        default=None,
    )
    return {
        "schema": "GMFQ_NEXT_G8_PRICING_HISTORY_V1",
        "as_of": latest_observation, "eligible_for_fx_engine": False,
        "eligible_for_backtests_as_official_ois": False,
        "official_ois_created": False,
        "date_gaps_interpolated": False, "excluded_conflicted_contract_days": len(disputed),
        "excluded_nzd_conflicted_contract_days": len(nzd_conflicts),
        "note": ("Archive quotes have source dates but may be collected later. Official "
                 "published 3M/6M/12M futures tenor series can rotate contracts. "
                 "Secondary rates always retain their listed contract identity; "
                 "NZD archived ASX bank-bill settlements are observed proxy levels; "
                 "only explicitly marked delta references are reconstructed. No meeting probabilities or signals."),
        "currencies": lines
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEST)
    args = parser.parse_args()
    actual = build(
        json.loads(SNAP.read_text(encoding="utf-8")),
        read_jsonl(OFFICIAL), read_jsonl(QUOTES), read_jsonl(CONFLICTS),
        json.loads(NZD.read_text(encoding="utf-8")), read_jsonl(NZD_ARCHIVE))
    if args.check:
        expected = json.loads(args.output.read_text(encoding="utf-8"))
        if expected != actual:
            raise SystemExit("G8 pricing history output differs from immutable archive sources")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    print(json.dumps({"status": "PASS", "check": args.check,
                      "as_of": actual["as_of"], "coverage": {
                          c: actual["currencies"][c]["observed_dates"] for c in CCYS}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
