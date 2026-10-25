#!/usr/bin/env python3
"""Read-only morning FX readiness gate: publication freshness != job SUCCESS.

The date check is for the most recent *prior* weekday session in Europe/Rome.
Official source holidays may legitimately trigger a review; no observations
are invented and structural/weekly data cannot masquerade as daily data.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
FEEDS = ROOT / "live_data" / "sections"
ROME = ZoneInfo("Europe/Rome")
G8 = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
REQUIRED = (
    "ECB_G8_PRICE_HISTORY.json", "PAIR_SETUP_OPERATIONAL_VIEW.json",
    "D.json", "NEWS_PULSE_OPERATIONAL.json", "CALENDAR_OPERATIONAL_VIEW.json",
    "NATIVE_RATES_DATA.json", "OIS_OPERATIONAL_VIEW.json",
    "V250_COT_CHART_DATA.json",
    "MACRO_THERMOMETER_DATA.json",
)


def prior_weekday(today: dt.date) -> dt.date:
    d = today - dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def valid_date(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        day = dt.date.fromisoformat(value)
    except ValueError:
        return None
    return day.isoformat() if value == day.isoformat() else None


def rome_build_day(stamp: object) -> str | None:
    """Interpret UTC publication timestamps in Europe/Rome, including midnight rollover."""
    if not isinstance(stamp, str):
        return None
    try:
        time = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if time.tzinfo is None or time.utcoffset() is None:
        return None
    return time.astimezone(ROME).date().isoformat()


def inspect(feeds: dict, now: dt.datetime, pipeline_outcome: str = "success") -> dict:
    now = now.astimezone(ROME)
    today = now.date()
    expected = prior_weekday(today).isoformat()
    problems: list[str] = []
    evidence = {}
    def session(name: str, date: object) -> None:
        actual = valid_date(date)
        # Before the morning briefing, an ECB fixing / VIX CLOSE dated today
        # has not been officially published yet. Require the previous weekday;
        # official market holidays remain an explicit source-review exception.
        status = "PREVIOUS_SESSION" if actual == expected else "NEEDS_SOURCE_REVIEW"
        evidence[name] = {"as_of": actual, "expected_not_before": expected, "status": status}
        if status != "PREVIOUS_SESSION":
            problems.append(name)

    fx = feeds["ECB_G8_PRICE_HISTORY.json"]
    pair = feeds["PAIR_SETUP_OPERATIONAL_VIEW.json"]
    model = feeds["D.json"]
    news = feeds["NEWS_PULSE_OPERATIONAL.json"]
    calendar = feeds["CALENDAR_OPERATIONAL_VIEW.json"]
    rates = feeds["NATIVE_RATES_DATA.json"]
    ois = feeds["OIS_OPERATIONAL_VIEW.json"]
    cot = feeds["V250_COT_CHART_DATA.json"]
    thermometer = feeds["MACRO_THERMOMETER_DATA.json"]

    if (fx.get("status") != "CURRENT_OFFICIAL_HISTORY" or
        not isinstance(fx.get("rows"), list) or len(fx["rows"]) < 21 or
        fx.get("row_count") != len(fx["rows"]) or
        fx["rows"][-1].get("Date") != fx.get("last_as_of") or
        any(not isinstance(fx["rows"][-1].get(c), (int, float)) or
                fx["rows"][-1][c] <= 0 for c in G8)):
        problems.append("FX_SOURCE_INTEGRITY")
    # A successful producer label is not proof that all 28 unordered G8
    # currency crosses are actually present, priced and anchored to the same
    # official fixing vintage. No fabricated or duplicate inverse crosses.
    pair_rows = pair.get("pairs")
    pair_keys = list(pair_rows) if isinstance(pair_rows, dict) else []
    expected_crosses = {frozenset((a, b)) for i, a in enumerate(G8)
                        for b in G8[i + 1:]}
    observed_crosses = {frozenset((key[:3], key[3:])) for key in pair_keys
                        if isinstance(key, str) and len(key) == 6 and
                        key[:3] in G8 and key[3:] in G8 and key[:3] != key[3:]}
    audit = pair.get("price_audit", {})
    if (pair.get("status") != "CURRENT_CANONICAL_ENGINE" or
        pair.get("pair_count") != 28 or len(pair_keys) != 28 or
        len(observed_crosses) != 28 or observed_crosses != expected_crosses or
        not isinstance(audit, dict) or audit.get("status") != "PASS" or
        audit.get("as_of") != pair.get("price_asof") or
        audit.get("history_asof") != fx.get("last_as_of") or
        audit.get("overlay_asof") != pair.get("price_asof") or
        audit.get("pair_count") != 28 or
        audit.get("complete_pair_count") != 28 or
        audit.get("no_lookahead") is not True or
        audit.get("returns_complete") is not True):
        problems.append("PAIR_SOURCE_INTEGRITY")
    session("FX_OFFICIAL_FIXING", fx.get("last_as_of"))
    session("PAIR_PRICE", pair.get("price_asof"))
    if pair.get("price_asof") != fx.get("last_as_of"):
        problems.append("PAIR_FX_SOURCE_DATE_DIVERGENCE")

    vix = model.get("risk", {}).get("VIX", {})
    if (not vix.get("dates") or vix["dates"][-1] != vix.get("last_date") or
        not isinstance(vix.get("last_value"), (int, float))):
        problems.append("VIX_SOURCE_INTEGRITY")
    session("VIX_OFFICIAL_CLOSE", vix.get("last_date"))
    for name, row in (("CALENDAR_REFRESH", calendar), ("NEWS_PULSE_REFRESH", news)):
        stamp = row.get("generated_at_utc")
        stamp_day = rome_build_day(stamp)
        try:
            build_instant = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")) if isinstance(stamp, str) else None
            if build_instant is None or build_instant.tzinfo is None or build_instant.utcoffset() is None:
                build_instant = None
        except ValueError:
            build_instant = None
        if build_instant is not None and build_instant > now:
            status = "FUTURE_DATED"
        elif stamp_day == today.isoformat() and build_instant is not None:
            status = "TODAY_BUILT"
        else:
            status = "NOT_BUILT_TODAY"
        evidence[name] = {"generated_at_utc": stamp, "generated_date_rome": stamp_day, "status": status}
        if status != "TODAY_BUILT":
            problems.append(name)

    # A freshly GENERATED News Pulse is not proof that its MARKET CONTENT
    # describes the latest session. Report the actual signal vintage
    # separately; do not fabricate news to fill a quiet-market gap.
    declared_news_vintage = valid_date(news.get("content_as_of"))
    news_items = news.get("items")
    item_vintages = ([valid_date(row.get("as_of"))
                      if isinstance(row, dict) else None for row in news_items]
                     if isinstance(news_items, list) else [])
    news_integrity_ok = bool(
        declared_news_vintage and isinstance(news_items, list)
        and news_items and all(item_vintages)
        and max(item_vintages) == declared_news_vintage
        and declared_news_vintage <= today.isoformat()
    )
    if not news_integrity_ok:
        problems.append("NEWS_CONTENT_VINTAGE_INTEGRITY")
    if not news_integrity_ok:
        content_status = "INVALID_OR_FUTURE_VINTAGE"
    elif declared_news_vintage < expected:
        content_status = "OLDER_THAN_PREVIOUS_TRADING_SESSION"
    else:
        content_status = "PREVIOUS_TRADING_SESSION_OR_NEWER"
    evidence["NEWS_CONTENT_VINTAGE"] = {
        "content_as_of": declared_news_vintage,
        "newest_item_as_of": max(item_vintages) if item_vintages and all(item_vintages) else None,
        "expected_previous_weekday": expected,
        "item_count": len(news_items) if isinstance(news_items, list) else None,
        "status": content_status,
        "generated_at_is_not_content_as_of": True,
    }
    # A previous-session mismatch is informative rather than a fabricated
    # official datum or a total Pages outage. It must nonetheless be visible
    # in the same morning receipt as the otherwise-green data checks.
    documented_gaps = (
        ["NEWS_CONTENT_OLDER_THAN_PREVIOUS_SESSION"]
        if content_status == "OLDER_THAN_PREVIOUS_TRADING_SESSION"
        else []
    )

    rate_rows = {}
    for c in G8:
        row = rates.get(c, {})
        as_of = valid_date(row.get("date"))
        status = ("RECENT_OFFICIAL" if as_of and expected <= as_of <= today.isoformat() and
                  "OFFICIAL" in str(row.get("quality") or "") else "PUBLISHED_LAG_OR_SOURCE_BLOCKED")
        rate_rows[c] = {"as_of": as_of, "status": status}
    evidence["RATES_2Y_10Y"] = rate_rows

    op = {c: ois.get("currencies", {}).get(c, {}).get("operational_status") for c in G8}
    evidence["OIS_G8"] = {
        "official": sorted(c for c in G8 if op[c] == "GREEN_OFFICIAL"),
        "estimated": sorted(c for c in G8 if op[c] == "GREEN_ESTIMATED"),
        "withheld": sorted(c for c in G8 if op[c] not in {"GREEN_OFFICIAL", "GREEN_ESTIMATED"}),
    }
    # Raw observation periods are not official release timestamps, PIT release
    # vintages, nor current structural model scores. Explicitly separate them.
    macro_rows = {}
    macro_invalid = []
    dimensions = thermometer.get("currencies")
    if (not isinstance(dimensions, dict) or set(dimensions) != set(G8)):
        macro_invalid.append("G8_COVERAGE")
        dimensions = dimensions if isinstance(dimensions, dict) else {}
    for c in G8:
        observations = dimensions.get(c, {})
        for pillar in ("inflation", "labour"):
            row = observations.get(pillar, {}) if isinstance(observations, dict) else {}
            if not isinstance(row, dict):
                row = {}
            period = row.get("as_of")
            source = row.get("source")
            value = row.get("latest_value")
            history = row.get("history")
            value_ok = (type(value) in (int, float) and math.isfinite(value)
                        and isinstance(history, list) and len(history) > 0
                        and type(history[-1]) in (int, float)
                        and math.isfinite(history[-1])
                        and abs(value - history[-1]) < 1e-8)
            period_ok = (isinstance(period, str) and
                         re.fullmatch(r"\d{4}-\d{2}(?:-01)?", period) is not None and
                         valid_date(period[:7] + "-01") is not None and
                         period[:7] <= today.strftime("%Y-%m"))
            source_ok = isinstance(source, str) and bool(source.strip())
            ok = bool(period_ok and source_ok and value_ok)
            key = f"{c}.{pillar}"
            macro_rows[key] = {
                "reference_period": period if period_ok else None,
                "value": value if value_ok else None,
                "source_label": source if source_ok else None,
                "state": "OBSERVED_PERIOD_ONLY_NOT_RELEASE_DATE" if ok
                         else "INVALID_OBSERVATION",
            }
            if not ok:
                macro_invalid.append(key)
    evidence["MACRO_OBSERVATIONS_G8"] = {
        "observed": sum(row["state"] == "OBSERVED_PERIOD_ONLY_NOT_RELEASE_DATE"
                        for row in macro_rows.values()),
        "expected": 16,
        "invalid": macro_invalid,
        "rows": macro_rows,
        "release_timestamps_verified": False,
        "full_first_release_pit_certified": False,
        "scores_recomputed": False,
    }
    if macro_invalid:
        problems.append("MACRO_OBSERVATION_SOURCE_INTEGRITY")

    # Macro cycle scores are a separate frozen baseline; weekly COT is not
    # expected to acquire today's date before the new official release.
    evidence["MACRO_BASELINE"] = {"as_of": valid_date(model.get("asOf")),
        "state": "HISTORICAL_NOT_AUTO_RECALCULATED"}
    evidence["COT_WEEKLY"] = {c: valid_date(cot.get(c, {}).get("dates", [None])[-1])
        if cot.get(c, {}).get("dates") else None for c in G8}
    if pair.get("macro_baseline_asof") != model.get("asOf"):
        problems.append("PAIR_MACRO_BASELINE_DIVERGENCE")
    if pipeline_outcome != "success":
        problems.append("REFRESH_PIPELINE_NOT_SUCCESS")
    return {
        "schema": "GMFQ_MORNING_READINESS_V1",
        "checked_at_rome": now.isoformat(timespec="seconds"),
        "refresh_pipeline_outcome": pipeline_outcome,
        "expected_previous_weekday": expected,
        "operational_state": "DAILY_READY_WITH_DOCUMENTED_GAPS" if not problems else "DAILY_INPUTS_INCOMPLETE",
        "critical_daily_problems": sorted(set(problems)),
        "documented_nonblocking_gaps": documented_gaps,
        "evidence": evidence,
        "caution": "Macro observations are raw dated reference periods, not release timestamps, full PIT vintages or current scores. This does not certify official release holidays, OIS proxies or COT weekly cadence.",
        "core_effect": "NONE",
    }


def read_feeds() -> dict:
    return {p: json.loads((FEEDS / p).read_text(encoding="utf-8")) for p in REQUIRED}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="Override current instant using ISO-8601 timezone-aware timestamp")
    ap.add_argument("--output")
    ap.add_argument("--strict-daily", action="store_true")
    ap.add_argument("--pipeline-outcome", default="success",
                    choices=("success", "failure", "cancelled", "skipped", "unknown"))
    args = ap.parse_args()
    now = dt.datetime.fromisoformat(args.as_of) if args.as_of else dt.datetime.now(ROME)
    if now.tzinfo is None or now.utcoffset() is None:
        ap.error("as-of must include a timezone offset")
    report = inspect(read_feeds(), now, pipeline_outcome=args.pipeline_outcome)
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return int(args.strict_daily and bool(report["critical_daily_problems"]))


if __name__ == "__main__":
    raise SystemExit(main())
