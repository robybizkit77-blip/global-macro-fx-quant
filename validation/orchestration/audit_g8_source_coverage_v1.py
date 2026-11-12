#!/usr/bin/env python3
"""Read-only G8 source coverage and before/after change receipt.
No missing data are filled, no stale observation is promoted, and a successful
workflow is never reported as proof of new market data. No network access.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
FX = ("USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD")
FILES = {
    "macro_series": "live_data/sections/MACRO_SERIES.json",
    "macro": "live_data/sections/MACRO_THERMOMETER_DATA.json",
    "rates": "live_data/sections/NATIVE_RATES_DATA.json",
    "ois": "site/fx-quant-v2/ois-pricing-snapshot.json",
    "cb_estimated": "live_data/sections/CB_PRICING_ESTIMATED.json",
    "price": "live_data/sections/ECB_G8_PRICE_HISTORY.json",
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])(?:-\d{2})?$")


def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and abs(x) < float("inf")


def age_days(s, asof):
    if not isinstance(s, str) or not DATE_RE.fullmatch(s):
        return None
    try:
        return (date.fromisoformat(asof) - date.fromisoformat(s)).days
    except ValueError:
        return None


def age_months(s, asof):
    if not isinstance(s, str) or not PERIOD_RE.fullmatch(s):
        return None
    y, m = map(int, s[:7].split("-"))
    ay, am = map(int, asof[:7].split("-"))
    return (ay - y) * 12 + am


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()[:16]


def latest_periods(series, asof):
    out = []
    for s in series if isinstance(series, list) else []:
        dates, vals = s.get("dates"), s.get("values")
        if not isinstance(dates, list) or not isinstance(vals, list) or len(dates) != len(vals):
            continue
        eligible = [(p, vals[i]) for i, p in enumerate(dates)
                    if age_months(p, asof) is not None and age_months(p, asof) >= 0 and number(vals[i])]
        if eligible:
            p, v = max(eligible, key=lambda item: item[0])
            out.append({"id": s.get("id"), "category": s.get("category"),
                        "period": p, "value": v})
    return out


def coverage(root=ROOT, asof=None):
    asof = asof or datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    date.fromisoformat(asof)
    data = {k: json.loads((Path(root) / p).read_text(encoding="utf-8")) for k, p in FILES.items()}
    rows, signatures = {}, {k: {} for k in ("macro_series", "rates", "pricing_official", "pricing_proxy", "price")}
    for c in FX:
        all_macro = data["macro_series"].get(c, [])
        observations = latest_periods(all_macro, asof)
        recent = [x for x in observations if 0 <= age_months(x["period"], asof) <= 5]
        r = data["rates"].get(c) or {}
        r_age = age_days(r.get("date"), asof)
        w = r.get("weekly2_validation") or {}
        rates_ok = (r_age is not None and 0 <= r_age <= 7 and number(r.get("2Y")) and
                    number(w.get("change_bp")) and w.get("end_date") == r.get("date") and
                    isinstance(w.get("source"), str) and len(w["source"]) > 8)
        o = (data["ois"].get("currencies") or {}).get(c) or {}
        h = (o.get("horizons") or {}).get("6m") or {}
        o_age = age_days(h.get("as_of"), asof)
        official = (o.get("quality") == "FONTE UFFICIALE" and o.get("kind") in ("OIS", "FUTURES") and
                    o_age is not None and 0 <= o_age <= 7 and o.get("as_of") == h.get("as_of") and
                    number(h.get("rate")) and number(h.get("change_1w_bp")))
        e = (data["cb_estimated"].get("currencies") or {}).get(c) or {}
        eh = (e.get("horizons") or {}).get("6m") or {}
        e_age = age_days(e.get("as_of"), asof)
        gov = e.get("governance") or {}
        proxy = (not official and e.get("status") == "ESTIMATED_ACTIVE" and
                 e.get("input_mode") == "LIVE_SECONDARY_OVERLAY" and
                 e.get("source_quality") == "SECONDARY_PUBLIC_LIVE_PROXY" and
                 e.get("policy_repricing_inference_allowed") is False and
                 gov.get("informational_only") is True and
                 eh.get("quote_timestamp_verified") is True and
                 eh.get("quote_as_of") == e.get("as_of") and
                 eh.get("raw_level_gap_not_policy_repricing") is True and
                 e_age is not None and 0 <= e_age <= 7 and number(eh.get("rate")) and
                 isinstance(eh.get("contract"), str) and "!" not in eh["contract"])
        rows[c] = {
            "macro_series": {"catalogue": len(all_macro), "observed_with_value": len(observations),
                             "within_5_months": len(recent),
                             "latest_observation_period": max((x["period"] for x in observations), default=None),
                             "not_new_release_claim": True},
            "rates_2y": {"status": "RECENT_OFFICIAL" if rates_ok else "STALE_OR_UNALIGNED",
                         "observation_date": r.get("date"), "weekly_change_bp": w.get("change_bp") if rates_ok else None},
            "pricing_6m": {"status": "OFFICIAL_1W" if official else "INDICATIVE_PROXY" if proxy else "WITHHELD",
                           "observation_date": h.get("as_of") if official else e.get("as_of") if proxy else None,
                           "weekly_change_bp": h.get("change_1w_bp") if official else None,
                           "secondary_contract": eh.get("contract") if proxy else None},
        }
        signatures["macro_series"][c] = digest(observations)
        signatures["rates"][c] = digest({"2Y": r.get("2Y"), "date": r.get("date"), "weekly": w.get("change_bp")})
        signatures["pricing_official"][c] = digest({"asof": o.get("as_of"), "h6": h})
        signatures["pricing_proxy"][c] = digest({"asof": e.get("as_of"), "h6": eh})
    price = data["price"]
    price_date = price.get("last_as_of")
    latest = [x for x in price.get("rows", []) if isinstance(x, dict) and x.get("Date") == price_date]
    signatures["price"]["G8"] = digest({"date": price_date, "rows": latest})
    status = "OBSERVED_WITH_GAPS" if any(r["rates_2y"]["status"] != "RECENT_OFFICIAL" or
                     r["pricing_6m"]["status"] == "WITHHELD" for r in rows.values()) else "OBSERVED"
    return {
        "schema": "GMFQ_G8_SOURCE_COVERAGE_RECEIPT_V1",
        "as_of": asof, "state": status, "fx_fixing_date": price_date,
        "rows": rows, "fingerprints": signatures,
        "policy": "Read-only observed source dates and payload fingerprints; never an assertion of full freshness or inferred policy repricing.",
    }


def compare(before, after):
    groups = set((before or {}).get("fingerprints") or {}) | set(after.get("fingerprints") or {})
    changes = {}
    for group in sorted(groups):
        prior = (before or {}).get("fingerprints", {}).get(group, {})
        current = after.get("fingerprints", {}).get(group, {})
        changes[group] = {
            k: "CHANGED" if prior.get(k) != v else "UNCHANGED"
            for k, v in current.items()
        }
    return changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--before", default="")
    ap.add_argument("--as-of", default="")
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()
    after = coverage(asof=args.as_of or None)
    if args.before:
        old = json.loads(Path(args.before).read_text(encoding="utf-8"))
        after["since_before_phase"] = compare(old, after)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(after, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["## G8 source outcomes · observed / secondary / withheld",
             "- As-of Rome: " + after["as_of"],
             "- FX fixing observation date: " + str(after["fx_fixing_date"]),
             "- These are source observation periods, NOT guaranteed release or successful refresh dates."]
    for c, row in after["rows"].items():
        group = after.get("since_before_phase", {})
        changed = {k: v[c] for k, v in group.items() if c in v and v[c] == "CHANGED"}
        lines.append("- " + c + ": macro " + str(row["macro_series"]["within_5_months"]) +
                     "/" + str(row["macro_series"]["catalogue"]) + " observed ≤5mo;" +
                     " 2Y " + row["rates_2y"]["status"] + ";" +
                     " pricing " + row["pricing_6m"]["status"] + ";" +
                     " changed inputs " + (", ".join(changed) or "none"))
    if args.summary and os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("G8_SOURCE_COVERAGE_RECEIPT " + after["state"] + " — NOT a full-freshness certification")


if __name__ == "__main__":
    main()
