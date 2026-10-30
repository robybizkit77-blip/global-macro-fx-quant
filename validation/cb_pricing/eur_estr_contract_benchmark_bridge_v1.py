#!/usr/bin/env python3
"""Research-only exact-window validation of independent EUR OIS references.

The Eurex FST3 is a forward 3-month compounded €STR contract. Its expiry
must not be confused with an 'as-of 3M/6M/12M' spot-start Term €STR.
FST3 months name START of accrual, and end is 3rd Wednesday +3 months.
The existing daily futures archive is checked; no independent OIS par
rates have been imported or invented.

Optional third-party reference records are accepted only with verified
same observation DAY, start/end dates, independently sourced €STR 3M
forward OIS quote and release timestamp. Cross-instrument spreads are
DESCRIPTIVE, not predictive OIS forecast MAE (convexity/basis not fit).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
import argparse
import calendar
import hashlib
import json
import math

from validation.cb_pricing.audit_estimated_ois_reliability_v1 import (
    SOURCE, check_archive, require
)

SCHEMA = "GMFQ_EUR_FST3_INDEPENDENT_BENCHMARK_BRIDGE_V1"
MONTHS = {key: i for i, key in enumerate("FGHJKMNQUVXZ", 1)}
OFFICIAL_SPEC = "https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/Three-Month-Euro-STR-Futures-3402480"
CME_SOURCE = "https://www.cmegroup.com/market-data/cme-group-benchmark-administration/term-estr-rate.html"
CME_HISTORY = "https://www.cmegroup.com/reports/cme-term-estr-historical-data.csv"
MATCH_CLASS = "INDEPENDENT_FORWARD_START_ESTR_OIS_SAME_ACCRUAL_WINDOW"
INCOMPARABLE = {
    "CME_TERM_ESTR_SPOT",
    "LSEG_TERM_ESTR_SPOT",
    "ECB_ESTR_COMPOUNDED_IN_ARREARS",
    "FUTURES_ESTR_SAME_SOURCE",
    "EURIBOR_INTERBANK_RATE"
}


def day(value):
    require(isinstance(value, str), "date required")
    d = date.fromisoformat(value)
    require(d.isoformat() == value, "strict ISO date required")
    return d


def utc(value):
    require(isinstance(value, str), "timestamp must be ISO UTC")
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(t.tzinfo is not None and t.utcoffset().total_seconds() == 0, "UTC timestamp required")
    return t


def third_wednesday(y, m):
    first = date(y, m, 1).weekday()  # Monday=0, Wednesday=2
    dom = 1 + (2 - first) % 7 + 14
    return date(y, m, dom)


def contract_period(code):
    require(isinstance(code, str) and len(code) == 9 and code.startswith("FST3")
            and code[4] in MONTHS and code[5:].isdigit(), "unknown FST3 ticker")
    y, m = int(code[5:]), MONTHS[code[4]]
    require(2020 <= y <= 2100, "unexpected listed contract year")
    start = third_wednesday(y, m)
    ey, em = divmod((m - 1) + 3, 12)
    end = third_wednesday(y + ey, em + 1)
    require(85 <= (end - start).days <= 100, "bad FST3 3M window")
    return start.isoformat(), end.isoformat()


def eur_archive(text):
    all_rows = check_archive([json.loads(x) for x in text.splitlines() if x.strip()])
    selected = [r for r in all_rows if r["currency"] == "EUR"]
    require(selected, "EUR quote archive empty")
    contracts = {}
    by_trade_date = defaultdict(list)
    out = []
    for r in selected:
        start, end = contract_period(r["contract"])
        require(end == r["expiration"], "futures expiry != third Wednesday: " + r["contract"])
        require(day(r["observation_date"]) < day(end), "futures observed after expiry")
        require(r["official_ois_quote"] is False, "futures not OIS")
        contracts[r["contract"]] = {"contract": r["contract"],
            "accrual_start": start, "accrual_end": end,
            "underlying": "3M_COMPOUNDED_ESTR",
            "source": OFFICIAL_SPEC}
        by_trade_date[r["observation_date"]].append(r["contract"])
        out.append({"contract":r["contract"],"horizon_label":r["observed_under_horizon"],
            "quote_date":r["observation_date"],"first_seen_at_utc":r["first_seen_at_utc"],
            "rate_pct":r["implied_rate"],"accrual_start":start,"accrual_end":end,
            "source_method":r["source_method"],"official_ois":False})
    return {"contracts": sorted(contracts.values(), key=lambda x:x["accrual_start"]),
        "observations": out, "currency": "EUR"}


def admitted_reference(raw):
    require(isinstance(raw, dict), "independent reference must be an object")
    cls = raw.get("source_class")
    require(cls == MATCH_CLASS, "spot/start/underlying not eligible as same-period OIS")
    require(raw.get("currency") == "EUR" and raw.get("floating_index") == "ESTR"
            and raw.get("compounding") == "DAILY_COMPOUNDED" and
            raw.get("accrual_convention") == "ACT_360", "underlying/convention mismatch")
    require(raw.get("source_independent_of_fst3") is True and
            raw.get("source_instrument") == "FORWARD_START_3M_OIS_SWAP" and
            raw.get("official_data_licence_authorized") is True,
            "independence/instrument/usage approval not attested")
    require(isinstance(raw.get("source_url"), str) and
            raw["source_url"].startswith("https://") and
            isinstance(raw.get("source_content_sha256"), str) and
            len(raw["source_content_sha256"]) == 64 and
            all(c in "0123456789abcdef" for c in raw["source_content_sha256"]),
            "no independently verifiable immutable source")
    obs, start, end = map(day,(raw.get("quote_date"),
                               raw.get("accrual_start"),
                               raw.get("accrual_end")))
    require(obs <= start < end and 85 <= (end-start).days <= 100,
            "reference observation/period mismatch")
    first_seen = utc(raw.get("source_first_seen_at_utc"))
    require(first_seen.date() >= obs, "reference seen before quote date")
    r = raw.get("rate_pct")
    require(type(r) in (float, int) and math.isfinite(r) and -5 <= r <= 25,
            "bad independent OIS reference rate")
    require(raw.get("time_alignment") == "END_OF_DAY_BOTH_SOURCES",
            "market timestamps not aligned")
    return {**raw,"_first_seen":first_seen}


def compare(text, references):
    research = eur_archive(text)
    require(isinstance(references, list), "reference rows must be list")
    rows = [admitted_reference(r) for r in references]
    by_period = {}
    for r in rows:
        k = (r["quote_date"],r["accrual_start"],r["accrual_end"])
        require(k not in by_period,"duplicated independent same-date reference")
        by_period[k] = r
    compared = []
    unmatched = []
    for f in research["observations"]:
        k = (f["quote_date"],f["accrual_start"],f["accrual_end"])
        o = by_period.get(k)
        if o is None:
            unmatched.append({"contract":f["contract"],"date":f["quote_date"],
                "reason":"NO_INDEPENDENT_FORWARD_START_OIS_SAME_DATE_AND_WINDOW"})
            continue
        spread = round((f["rate_pct"] - o["rate_pct"])*100,5)
        compared.append({"contract":f["contract"],"date":f["quote_date"],
            "accrual_start":f["accrual_start"],"accrual_end":f["accrual_end"],
            "futures_rate_pct":f["rate_pct"],
            "independent_forward_ois_quote_pct":o["rate_pct"],
            "descriptive_futures_minus_ois_spread_bp":spread,
            "not_OIS_prediction_error":True,
            "original_futures_first_seen_at_utc":f["first_seen_at_utc"],
            "independent_source_first_seen_at_utc":o["source_first_seen_at_utc"],
            "historical_trade_PIT_certified":False})
    return {"schema":SCHEMA,
        "status":"DESCRIPTIVE_MATCHED_FORWARD_OIS_ONLY" if compared else
                  "NO_ADMISSIBLE_INDEPENDENT_SAME_WINDOW_OIS_REFERENCE",
        "eur_archived_futures_observations":len(research["observations"]),
        "distinct_eurex_futures_periods":len(research["contracts"]),
        "contract_windows":research["contracts"],
        "reference_rows_submitted":len(references),
        "admissible_same_window_pairs":len(compared),
        "matched":compared, "unmatched":unmatched,
        "CME_Term_ESTR_spot_reference_is_not_a_same_future_period":True,
        "CME_history_public_download":CME_HISTORY,
        "CME_reference_methodology":CME_SOURCE,
        "incomparable_spot_and_in_arrears_source_classes":sorted(INCOMPARABLE),
        "calendar_and_source_identity_checked":True,
        "futures_vs_OIS_spread_includes_unknown_convexity_and_basis":True,
        "actual_model_OIS_level_MAE_bp":None,
        "predicted_OIS_direction_hit_rate":None,
        "historical_PIT_and_walk_forward_validated":False,
        "eligible_to_change_OIS_operational_feed":False,
        "eligible_to_change_FX_or_forward_models":False,
        "writes_live_data":False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--benchmarks-json",type=Path,help="Authorized research file; never auto-ingested")
    p.add_argument("--out",type=Path,default=Path("/tmp/eur-estr-benchmark-readiness.json"))
    args = p.parse_args()
    require(args.out.resolve().is_relative_to(Path("/tmp")),
            "audit receipt must be under /tmp")
    if args.benchmarks_json:
        require(args.benchmarks_json.resolve().is_relative_to(Path("/tmp")),
                "external independent benchmark inputs must remain research-only")
        refs = json.loads(args.benchmarks_json.read_text(encoding="utf-8"))
    else: refs = []
    raw=SOURCE.read_text(encoding="utf-8")
    result=compare(raw,refs)
    result["futures_archive_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],
      "FST3_observations":result["eur_archived_futures_observations"],
      "contract_windows":result["distinct_eurex_futures_periods"],
      "independent_comparable_pairs":result["admissible_same_window_pairs"],
      "OIS_MAE":result["actual_model_OIS_level_MAE_bp"],
      "research_receipt":str(args.out)},sort_keys=True))


if __name__=="__main__":
    main()
