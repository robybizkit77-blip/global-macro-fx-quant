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
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "validation"))
from fetch_cboe_vix_candidate_v2 import previous_cboe_session  # noqa: E402
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


# Japanese Cabinet Office published national holidays for 2026 and 2027.
# Explicit coverage only; do not assume the calendar is complete for later years.
JP_HOLIDAY_SOURCE = "https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html"
JP_HOLIDAYS = {
    "2026-01-01","2026-01-12","2026-02-11","2026-02-23","2026-03-20",
    "2026-04-29","2026-05-03","2026-05-04","2026-05-05","2026-05-06",
    "2026-07-20","2026-08-11","2026-09-21","2026-09-22","2026-09-23",
    "2026-10-12","2026-11-03","2026-11-23",
    "2027-01-01","2027-01-11","2027-02-11","2027-02-23","2027-03-21",
    "2027-03-22","2027-04-29","2027-05-03","2027-05-04","2027-05-05",
    "2027-07-19","2027-08-11","2027-09-20","2027-09-23","2027-10-11",
    "2027-11-03","2027-11-23",
}
RBA_CADENCE_SOURCE = "https://www.rba.gov.au/schedules-events/frequency-statistical-releases.html"


def rate_cadence_context(currency: str, row: dict, now: dt.datetime, expected: str) -> dict | None:
    """Explain dated official observations; schedule consistency is not a live issuer check."""
    actual = valid_date(row.get("date"))
    if not actual or actual >= expected or row.get("quality") != "FULL_CURRENT_OFFICIAL":
        return None
    if not all(type(row.get(k)) in (int, float) and math.isfinite(row[k]) for k in ("2Y", "10Y")):
        return None
    tenors = row.get("tenors", [])
    if not all(any(t.get("tenor") == k and t.get("date") == actual and t.get("value") == row[k]
                   for t in tenors) for k in ("2Y", "10Y")):
        return None
    if currency == "JPY" and row.get("source", "").startswith("Japan Ministry of Finance · JGB Interest Rate"):
        target = dt.date.fromisoformat(expected)
        skipped = []
        while target.year in (2026, 2027) and (target.weekday() >= 5 or target.isoformat() in JP_HOLIDAYS):
            if target.isoformat() in JP_HOLIDAYS:
                skipped.append(target.isoformat())
            target -= dt.timedelta(days=1)
        if skipped and target.year in (2026, 2027) and actual == target.isoformat():
            return {"status": "HOLIDAY_CALENDAR_CONSISTENT", "expected_observation": target.isoformat(),
                    "holiday_dates": skipped, "calendar_source": JP_HOLIDAY_SOURCE,
                    "calendar_valid_through": "2027-12-31", "live_issuer_verified": False}
    if currency == "AUD" and row.get("source", "").startswith("Reserve Bank of Australia · F2 Capital Market Yields"):
        local = now.astimezone(ZoneInfo("Australia/Sydney"))
        friday = local.date() - dt.timedelta(days=(local.weekday()-4)%7)
        if local.date() == friday and local.time().replace(tzinfo=None) < dt.time(14):
            friday -= dt.timedelta(days=7)
        target = friday - dt.timedelta(days=2)
        # Normal weekly schedule, not a claim that a holiday-shifted edition
        # was published. Any non-matching period remains a source-review gap.
        if actual == target.isoformat():
            return {"status": "NORMAL_WEEKLY_CADENCE_CONSISTENT",
                    "expected_observation": target.isoformat(),
                    "scheduled_release_sydney": friday.isoformat()+"T14:00",
                    "next_regular_release_sydney": (friday+dt.timedelta(days=7)).isoformat()+"T14:00",
                    "calendar_source": RBA_CADENCE_SOURCE, "live_issuer_verified": False}
    return None


def research_rates_evidence(feeds: dict, today: dt.date, expected: str) -> dict:
    """Informational only: never change canonical rate/monetary readiness."""
    research = feeds.get("_next_rates_research", {})
    snapshot = research.get("pricing", {})
    pricing = {}
    accepted = {"OIS", "FUTURES", "FUTURES SECONDARI", "PROXY FUTURES"}
    valid_snapshot = (snapshot.get("schema") == "GMFQ_FXV2_PRICING_SNAPSHOT_V1"
                      and snapshot.get("ui_only") is True
                      and snapshot.get("eligible_for_fx_engine") is False)
    for c in G8:
        row = snapshot.get("currencies", {}).get(c, {}) if valid_snapshot else {}
        h = row.get("horizons", {}).get("6m", {})
        period = valid_date(h.get("as_of"))
        value = h.get("rate")
        kind = row.get("kind")
        valid = (period and period <= today.isoformat() and type(value) in (int, float)
                 and math.isfinite(value) and kind in accepted
                 and isinstance(row.get("source"), str) and bool(row["source"].strip()))
        if valid and kind in {"FUTURES SECONDARI", "PROXY FUTURES"}:
            valid = isinstance(h.get("contract"), str) and bool(h["contract"].strip())
        pricing[c] = {"as_of": period if valid else None, "level": value if valid else None,
                      "instrument": kind if valid else None, "source": row.get("source") if valid else None,
                      "status": ("RECENT_DATED_REFERENCE" if period >= expected else "OLDER_DATED_REFERENCE")
                      if valid else "REFERENCE_UNVERIFIED"}
    nzd = research.get("nzd", {})
    government = {}
    rows = nzd.get("observations", [])
    last = rows[-1] if isinstance(rows, list) and rows else {}
    period = valid_date(last.get("date"))
    if (nzd.get("schema") == "GMFQ_NZD_RBNZ_B2_RECONCILED_RESEARCH_V1"
        and nzd.get("status") == "RBNZ_B2_HTML_XLSX_AGREE_POSTROLL_RESEARCH_ONLY"
        and nzd.get("research_only") is True and nzd.get("no_interpolation") is True
        and all(nzd.get(k) is False for k in ("eligible_for_core", "eligible_for_fx_pair_engine",
                                               "eligible_for_backtests", "eligible_for_automatic_promotion"))
        and nzd.get("source_url") == "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates"
        and nzd.get("xlsx_url") == "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close.xlsx"
        and all(re.fullmatch(r"[0-9a-f]{64}", str(nzd.get(k))) for k in ("html_sha256", "xlsx_sha256"))
        and period and period == nzd.get("last_observation_date")
        and period in nzd.get("html_xlsx_matched_dates", [])
        and valid_date(nzd.get("publication_date")) and period <= nzd["publication_date"] <= today.isoformat()
        and valid_date(nzd.get("benchmark_roll_date")) and nzd["benchmark_roll_date"] <= period
        and all(type(last.get(k)) in (int, float) and math.isfinite(last[k]) for k in ("2Y", "10Y"))):
        government["NZD"] = {"as_of": period, "2Y": last["2Y"], "10Y": last["10Y"],
                             "status": "RECONCILED_RESEARCH_ONLY", "source": nzd["source"]}
    chf = research.get("chf_spot", {})
    period = valid_date(chf.get("as_of"))
    if (chf.get("schema") == "GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1"
        and chf.get("status") == "OFFICIAL_PUBLISHED_10Y_INFORMATIONAL"
        and chf.get("source_url") == "https://www.snb.ch/en/the-snb/mandates-goals/statistics/statistics-pub/current_interest_exchange_rates"
        and chf.get("tenor") == "10Y" and chf.get("has_current_2y") is False
        and chf.get("eligible_for_curve_spreads") is False and chf.get("eligible_for_core_signals") is False
        and period and period <= today.isoformat()
        and type(chf.get("value_percent")) in (int, float) and math.isfinite(chf["value_percent"])):
        government["CHF"] = {"as_of": period, "10Y": chf["value_percent"],
                             "status": "OFFICIAL_10Y_ONLY_NOT_PAIRED", "source": chf["source"]}
    return {"pricing_6m_research": pricing,
            "dated_reference_count": sum(x["status"] != "REFERENCE_UNVERIFIED" for x in pricing.values()),
            "recent_reference_count": sum(x["status"] == "RECENT_DATED_REFERENCE" for x in pricing.values()),
            "government_research": government, "canonical_effect": "NONE",
            "scope": "Informational references, not official OIS coverage, current-session source verification or public HTTP proof"}


def inspect(feeds: dict, now: dt.datetime, pipeline_outcome: str = "success", *, current_source_audit: bool = False) -> dict:
    now = now.astimezone(ROME)
    today = now.date()
    expected = prior_weekday(today).isoformat()
    problems: list[str] = []
    evidence = {}
    def session(name: str, date: object) -> None:
        actual = valid_date(date)
        # ECB and Cboe have different calendars. VIX must match the last
        # regular Cboe close, not the last European weekday. Never accept
        # a holiday/future observation or relax the ECB fixing requirement.
        required_date = (previous_cboe_session(today).isoformat()
                         if name == "VIX_OFFICIAL_CLOSE" else expected)
        current_ecb = (current_source_audit and name in ("FX_OFFICIAL_FIXING", "PAIR_PRICE")
                       and today.weekday() < 5 and now.hour >= 17
                       and actual == today.isoformat())
        status = ("CURRENT_SESSION_OFFICIAL" if current_ecb else
                  "PREVIOUS_SESSION" if actual == required_date else "NEEDS_SOURCE_REVIEW")
        evidence[name] = {"as_of": actual, "expected_not_before": required_date, "status": status}
        if status not in ("PREVIOUS_SESSION", "CURRENT_SESSION_OFFICIAL"):
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
    # The runtime explicitly selects the freshest official ECB row. A
    # lagging overlay does not invalidate a newer official history snapshot.
    overlay_day = valid_date(audit.get("overlay_asof")) if isinstance(audit, dict) else None
    history_day = valid_date(audit.get("history_asof")) if isinstance(audit, dict) else None
    overlay_matches = (overlay_day is not None and history_day is not None and
                       (overlay_day == pair.get("price_asof") or
                        (overlay_day < history_day == pair.get("price_asof") and
                         audit.get("current_row_source") == "official history snapshot" and
                         audit.get("history_status") == "CURRENT_OFFICIAL_HISTORY" and
                         audit.get("source") == fx.get("source") == "ECB euro foreign exchange reference rates")))
    if (pair.get("status") != "CURRENT_CANONICAL_ENGINE" or
        pair.get("pair_count") != 28 or len(pair_keys) != 28 or
        len(observed_crosses) != 28 or observed_crosses != expected_crosses or
        not isinstance(audit, dict) or audit.get("status") != "PASS" or
        audit.get("as_of") != pair.get("price_asof") or
        audit.get("history_asof") != fx.get("last_as_of") or
        not overlay_matches or
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
        # generated_at_utc dates the last CONTENT change. A successful
        # daily rebuild can validate identical sources without changing the
        # underlying economic news or forward calendar. Use a separate
        # last_checked_at_utc for refresh admission, never fake signal dates.
        generated = row.get("generated_at_utc")
        checked = row.get("last_checked_at_utc") or generated
        generated_day = rome_build_day(generated)
        checked_day = rome_build_day(checked)

        def aware_instant(value: object) -> dt.datetime | None:
            try:
                parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else None
                if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
                    return None
                return parsed
            except ValueError:
                return None

        generated_instant = aware_instant(generated)
        checked_instant = aware_instant(checked)
        if (generated_instant is None or checked_instant is None
            or generated_instant > now or checked_instant > now
            or checked_instant < generated_instant):
            status = "FUTURE_OR_INVALID_SOURCE_CLOCK"
        elif checked_day == today.isoformat():
            status = "TODAY_RECHECKED"
        else:
            status = "NOT_RECHECKED_TODAY"
        evidence[name] = {
            "generated_at_utc": generated,
            "generated_date_rome": generated_day,
            "last_checked_at_utc": checked,
            "checked_date_rome": checked_day,
            "freshness_basis": "LAST_CHECKED_AT" if row.get("last_checked_at_utc") else "LEGACY_GENERATED_AT",
            "status": status,
            "content_modification_is_not_source_recheck": True,
        }
        if status != "TODAY_RECHECKED":
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
        cadence = rate_cadence_context(c, row, now, expected)
        if cadence:
            rate_rows[c]["cadence_context"] = cadence
    evidence["RATES_2Y_10Y"] = rate_rows

    op = {c: ois.get("currencies", {}).get(c, {}).get("operational_status") for c in G8}
    evidence["OIS_G8"] = {
        "official": sorted(c for c in G8 if op[c] == "GREEN_OFFICIAL"),
        "estimated": sorted(c for c in G8 if op[c] == "GREEN_ESTIMATED"),
        "withheld": sorted(c for c in G8 if op[c] not in {"GREEN_OFFICIAL", "GREEN_ESTIMATED"}),
    }
    try:
        evidence["NEXT_RATES_RESEARCH"] = research_rates_evidence(feeds, today, expected)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        evidence["NEXT_RATES_RESEARCH"] = {"status": "RESEARCH_EVIDENCE_INVALID", "canonical_effect": "NONE", "error": type(exc).__name__}
    # A delivery can meet the 08:00 SLA while some research sources remain
    # lagging or unavailable. Surface those gaps in the same compact receipt
    # used by Pages and the orchestrator, without inventing estimates or
    # changing the daily blocking rules for differently scheduled releases.
    lagging_rates = sorted(c for c in G8 if rate_rows[c]["status"] != "RECENT_OFFICIAL"
                           and not rate_rows[c].get("cadence_context"))
    cadence_rates = sorted(c for c in G8 if rate_rows[c].get("cadence_context"))
    missing_ois = evidence["OIS_G8"]["withheld"]
    if lagging_rates:
        documented_gaps.append("RATES_2Y_10Y_LAG_OR_BLOCKED:" + ",".join(lagging_rates))
    if cadence_rates:
        documented_gaps.append("RATES_2Y_10Y_CALENDAR_CONSISTENT_NOT_LIVE_VERIFIED:" + ",".join(cadence_rates))
    if missing_ois:
        documented_gaps.append("OIS_G8_UNAVAILABLE:" + ",".join(missing_ois))
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


def critical_source_blockers(report: dict) -> list[str]:
    """For publication only: distinguish data integrity from pipeline failure.

    A failed collector must remain in the audit and cannot certify the 08:00
    delivery. Existing independently checked daily sources may nevertheless
    be safely published if they pass *all* current-source integrity checks.
    """
    if not isinstance(report, dict) or report.get("schema") != "GMFQ_MORNING_READINESS_V1":
        return ["MISSING_OR_INVALID_MORNING_RECEIPT"]
    problems = report.get("critical_daily_problems")
    if not isinstance(problems, list) or not all(isinstance(x, str) for x in problems):
        return ["MISSING_SOURCE_PROBLEMS"]
    return sorted(x for x in problems if x != "REFRESH_PIPELINE_NOT_SUCCESS")


def read_feeds() -> dict:
    feeds = {p: json.loads((FEEDS / p).read_text(encoding="utf-8")) for p in REQUIRED}
    optional = {"pricing": ROOT / "site/fx-quant-v2/ois-pricing-snapshot.json",
                "nzd": ROOT / "site/fx-quant-v2/nzd-rbnz-b2-reconciled-research.json",
                "chf_spot": FEEDS / "CHF_SNB_10Y_SPOT_CONTEXT.json"}
    research = {}
    for name, path in optional.items():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                research[name] = value
        except (OSError, ValueError):
            pass
    feeds["_next_rates_research"] = research
    return feeds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="Override current instant using ISO-8601 timezone-aware timestamp")
    ap.add_argument("--output")
    ap.add_argument("--strict-daily", action="store_true")
    ap.add_argument("--strict-sources", action="store_true",
                    help="Block only current-source integrity errors; never certify pipeline success")
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
    return int((args.strict_daily and bool(report["critical_daily_problems"]))
               or (args.strict_sources and bool(critical_source_blockers(report))))


if __name__ == "__main__":
    raise SystemExit(main())
