#!/usr/bin/env python3
"""Read-only morning HTTP proof for the published FX Quant V2 website.

This verifies public GitHub Pages bytes against approved main, and never
certifies economic release freshness, OIS market accuracy, or trading signals.
The check cannot retroactively prove publication before 08:00 if run late.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site/fx-quant-v2"
URL = "https://robybizkit77-blip.github.io/global-macro-fx-quant/site/fx-quant-v2/"
FILES = (
    "index.html", "valute.html", "coppie.html", "tassi.html", "ois.html",
    "macro.html", "banche.html", "cot.html", "cross-asset.html",
    "liquidita-credito.html", "calendario-news.html", "research.html",
    "assets/site-nav.js", "assets/site-nav.css",
    "ois-pricing-snapshot.json", "cross-asset-live-data.json",
    "chf-nzd-benchmark-research.json", "nzd-asx-government-anchor-v1.json",
    "pricing-relative-28pairs-research.json", "quant-temporal-readiness-v1.json",
    "macro-baseline-candidate-v1.json",
)
CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}
TENORS = ("3m", "6m", "12m")


def evaluate(now: dt.datetime, rows: list[dict], *, expected=FILES) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware evaluation time required")
    local = now.astimezone(ROME)
    deadline = dt.datetime.combine(local.date(), dt.time(8), tzinfo=ROME)
    paths = [r.get("path") for r in rows]
    delivered = bool(
        len(rows) == len(expected) and len(set(paths)) == len(expected)
        and set(paths) == set(expected)
        and all(r.get("status") == "MATCH" and r.get("http") == 200
                and isinstance(r.get("expected_sha256"), str)
                and len(r["expected_sha256"]) == 64
                and r.get("public_sha256") == r["expected_sha256"]
                for r in rows)
    )
    if local.weekday() > 4:
        status = "NOT_WEEKDAY"
    elif not delivered:
        status = "FAIL_PUBLIC_FILES_NOT_MATCHED"
    elif local > deadline:
        status = "VERIFIED_AFTER_0800_ON_TIME_UNPROVEN"
    else:
        status = "PASS_12_PAGES_PUBLIC_BY_0800"
    return {
        "schema": "GMFQ_FXV2_MORNING_PUBLIC_PROOF_V1",
        "date_rome": local.date().isoformat(),
        "verified_at_rome": local.isoformat(timespec="seconds"),
        "deadline_rome": deadline.isoformat(timespec="seconds"),
        "status": status,
        "on_time_proven": status == "PASS_12_PAGES_PUBLIC_BY_0800",
        "public_files_verified": sum(r.get("status") == "MATCH" for r in rows),
        "expected_file_count": len(expected),
        "all_exact_public_bytes_match": delivered,
        "critical_coverage": {"pages": 12, "files": len(expected)},
        "source_scope": "FXV2_PUBLIC_HTML_AND_STATIC_ASSETS_ONLY",
        "economic_data_freshness_certified": False,
        "ois_market_accuracy_certified": False,
        "legacy_v10_untouched": True,
        "note": "Late verification does not prove when files first became available. Source-level as-of dates and instrument quality require separate review.",
        "files": rows,
    }



# Research-grade delivery is a different product from certified trading Core:
# official CHF/NZD gaps and unavailable policy OIS are still reported, but
# cannot by themselves invalidate a dated, complete, source-labeled V2 website.
# However, a single missing/stale critical *research* feed fails this gate.
RESEARCH_REQUIRED = {
    "prices": {"ECB G8 matched-date fixing", "DXY synthetic (not ICE)"},
    "pairs": {"28-cross market price"},
    "macro_observed_research": {"G8 / 24 osservazioni / 28 confronti V3"},
    "rates_research": {
        "CHF SNB same-date spot pair (not Core)",
        "NZD RBNZ B2 post-roll web research",
    },
    "calendar": {"refresh operativo"},
    "news": {"last check"},
    "cross_asset_live": {
        "S&P 500", "Nasdaq Composite", "IG OAS", "HY OAS", "VIX Cboe",
    },
    "liquidity_credit_live": {
        "IG_OAS FRED published source", "HY_OAS FRED published source",
    },
}
G8 = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")


def research_sources_usable(checks: list[dict], freshness: dict, research: dict) -> bool:
    """Only dated, on-cadence and independently sourced V2 research is usable.

    This explicitly does NOT certify lagging sovereign *Core* yields,
    unlicensed OIS, backtested signals or static secondary equity snapshots.
    """
    if (freshness.get("status") == "AUDIT_FAILED" or
        freshness.get("hard_errors") or
        research.get("state") != "AVAILABLE_WITH_SOURCE_QUALITY_LIMITS" or
        research.get("website_pages") != 12 or
        research.get("rate_pricing_horizons") != 24):
        return False
    observed = {}
    for row in checks:
        if row.get("state") == "ON_CADENCE":
            observed.setdefault(row.get("area"), set()).add(row.get("item"))
    if any(not items.issubset(observed.get(area, set()))
           for area, items in RESEARCH_REQUIRED.items()):
        return False
    if any(c+" CFTC weekly" not in observed.get("positioning", set())
           for c in G8):
        return False
    if any(c+" "+ten not in observed.get("ois_v2_research_tenor", set())
           for c in G8 for ten in ("3m", "6m", "12m")):
        return False
    return True


def attach_source_evidence(report: dict, freshness: dict | None, decision: dict | None) -> dict:
    """Attach existing source-date and Research/Core audits; never infer updates.

    Public-byte equality and source freshness are independent facts. Missing,
    stale or contradictory receipts cannot be represented as a green morning.
    """
    result = dict(report)
    result["source_evidence"] = {
        "status": "SOURCE_AUDIT_MISSING_OR_INCOMPLETE",
        "freshness_as_of": None,
        "source_checks": 0,
        "date_delays_or_invalid": None,
        "unresolved_gaps": None,
        "hard_errors": None,
        "research_readiness": "UNVERIFIED",
        "trading_core_readiness": "UNVERIFIED",
        "canonical_gov_as_of": {},
        "pricing_tenor_as_of": {},
        "macro_v3_as_of": None,
        "macro_legacy_baseline_as_of": None,
        "data_currentness_proven": False,
        "signal_model_revalidated": False,
        "research_sources_on_cadence": False,
    }
    if isinstance(freshness, dict) and isinstance(decision, dict):
        summary = freshness.get("summary") or {}
        research = decision.get("research") or {}
        core = decision.get("trading_core") or {}
        checks = freshness.get("checks") or []
        valid = (
            freshness.get("schema") == "GMFQ_FXV2_FRESHNESS_AUDIT_V1"
            and decision.get("schema") == "GMFQ_FXV2_READINESS_DUAL_TRACK_V1"
            and freshness.get("as_of_rome") == result["date_rome"]
            and decision.get("as_of_rome") == result["date_rome"]
            and isinstance(checks, list) and len(checks) >= 40
            and summary.get("checks") == len(checks)
            and summary.get("v2_pages") == 12
            and summary.get("fx_pairs") == 28
            and research.get("website_pages") == 12
            and research.get("rate_pricing_horizons") == 24
            and core.get("pair_count") == 28
            and isinstance(freshness.get("hard_errors"), list)
            and isinstance(summary.get("gaps"), int)
            and isinstance(summary.get("late_or_invalid"), int)
            and freshness.get("status") in
                ("DATE_CHECKS_PASS", "DATA_GAPS_PRESENT", "AUDIT_FAILED")
        )
        if valid:
            by_area = lambda area: {r["item"]: r["as_of"] for r in checks
                                    if r.get("area") == area and
                                    isinstance(r.get("as_of"), str)}
            g = by_area("governments")
            tenors = {}
            for row in checks:
                if row.get("area") != "ois_v2_research_tenor":
                    continue
                bits = str(row.get("item", "")).split()
                if len(bits) != 2 or bits[1] not in TENORS:
                    continue
                tenors.setdefault(bits[0], {})[bits[1]] = row.get("as_of")
            # An old or incomplete audit must never be called complete.
            if set(g) != CURRENCIES or set(tenors) != CURRENCIES or any(
                    set(tenors.get(c, {})) != set(TENORS) for c in CURRENCIES):
                return result | {
                    "joint_status": (
                        "PUBLIC_BY_0800_SOURCE_AUDIT_MISSING"
                        if result["on_time_proven"] else "PUBLIC_NOT_VERIFIED_BY_0800"),
                    "all_sections_ready_with_current_data": False,
                    "official_ois_8_of_8_certified": False,
                    "signal_model_revalidated": False,
                    "research_usable_by_0800": False,
                }
            research_usable = research_sources_usable(checks, freshness, research)
            result["source_evidence"] = {
                "status": freshness["status"],
                "freshness_as_of": freshness["as_of_rome"],
                "source_checks": len(checks),
                "date_delays_or_invalid": summary["late_or_invalid"],
                "unresolved_gaps": summary["gaps"],
                "hard_errors": len(freshness["hard_errors"]),
                "research_readiness": research.get("state", "UNVERIFIED"),
                "trading_core_readiness": core.get("state", "UNVERIFIED"),
                "canonical_gov_as_of": g,
                "pricing_tenor_as_of": tenors,
                "macro_v3_as_of": next((c.get("as_of") for c in checks
                                      if c.get("area") == "macro_observed_research"), None),
                "macro_legacy_baseline_as_of": core.get("baseline_macro_as_of"),
                "data_currentness_proven": freshness["status"] == "DATE_CHECKS_PASS"
                  and summary["gaps"] == 0 and summary["late_or_invalid"] == 0
                  and not freshness["hard_errors"],
                "signal_model_revalidated": False,
                "research_sources_on_cadence": research_usable,
            }
    source = result["source_evidence"]
    result["joint_status"] = (
        "PUBLIC_NOT_VERIFIED_BY_0800"
        if not result["on_time_proven"] else
        "PUBLIC_BY_0800_SOURCE_AUDIT_MISSING"
        if source["status"] == "SOURCE_AUDIT_MISSING_OR_INCOMPLETE" else
        "PUBLIC_BY_0800_RESEARCH_AVAILABLE_CORE_SOURCE_GAPS_VISIBLE"
        if source["research_sources_on_cadence"] and not source["data_currentness_proven"] else
        "PUBLIC_BY_0800_SOURCE_GAPS_VISIBLE"
        if not source["data_currentness_proven"] else
        "PUBLIC_BY_0800_DATA_CADENCE_CHECKS_PASS"
    )
    result["all_sections_ready_with_current_data"] = (
        result["on_time_proven"] and source["data_currentness_proven"])
    result["research_usable_by_0800"] = (
        result["on_time_proven"] and source["research_sources_on_cadence"])
    result["official_ois_8_of_8_certified"] = False
    result["signal_model_revalidated"] = False
    result["note"] += (
        " Joint status distinguishes website publication from source-data"
        " cadence and Research/Core validation; futures proxies are never OIS."
    )
    return result


def check_snapshot() -> None:
    data = json.loads((SITE / "ois-pricing-snapshot.json").read_text(encoding="utf-8"))
    if data.get("schema") != "GMFQ_FXV2_PRICING_SNAPSHOT_V1":
        raise ValueError("OIS snapshot schema drift")
    currencies = data.get("currencies", {})
    if set(currencies) != CURRENCIES:
        raise ValueError("G8 pricing coverage missing currencies")
    for c, row in currencies.items():
        horizons = row.get("horizons", {})
        if any(not isinstance(horizons.get(t, {}).get("rate"), (float, int))
               or not -5 <= horizons[t]["rate"] <= 30 for t in TENORS):
            raise ValueError(f"Invalid indicative pricing horizon for {c}")
        if c == "GBP" and row.get("kind") != "OIS":
            raise ValueError("OIS GBP provenance lost")
        if c != "GBP" and row.get("kind") == "OIS":
            raise ValueError(f"Futures/estimate {c} incorrectly labelled OIS")


def fetch_one(path: str, *, attempts: int = 3) -> dict:
    data = (SITE / path).read_bytes()
    expected = hashlib.sha256(data).hexdigest()
    last_error = ""
    public_hash = None
    http = None
    for retry in range(attempts):
        try:
            req = Request(URL + path + "?fxv2_proof=" + str(int(time.time())),
                          headers={"Cache-Control": "no-cache", "User-Agent": "FXV2-Morning-Public-Proof/1"})
            with urlopen(req, timeout=9) as response:
                http = response.status
                public_hash = hashlib.sha256(response.read()).hexdigest()
            if http == 200 and public_hash == expected:
                return {"path": path, "http": http, "status": "MATCH",
                        "expected_sha256": expected, "public_sha256": public_hash}
            last_error = "bytes differ from approved main"
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
            http = getattr(exc, "code", None)
        if retry < attempts - 1:
            time.sleep(3)
    return {"path": path, "http": http, "status": "MISMATCH_OR_UNAVAILABLE",
            "expected_sha256": expected, "public_sha256": public_hash,
            "error": last_error[:250]}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--freshness", help="Existing read-only freshness.json receipt")
    p.add_argument("--readiness", help="Existing read-only decision-readiness.json receipt")
    args = p.parse_args()
    check_snapshot()
    rows = [fetch_one(name) for name in FILES]
    report = evaluate(dt.datetime.now(dt.timezone.utc), rows)
    def receipt(file):
        if not file:
            return None
        try:
            return json.loads(Path(file).read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            return None
    report = attach_source_evidence(report, receipt(args.freshness), receipt(args.readiness))
    report["run_trigger"] = os.environ.get("GITHUB_EVENT_NAME", "manual")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("FXV2_MORNING_PUBLIC_PROOF", json.dumps({k: v for k, v in report.items() if k != "files"}))
    for row in rows:
        if row["status"] != "MATCH":
            print("PUBLIC_MISMATCH", row["path"], row.get("error", ""))
    # An on-time, independently usable research website can pass despite
    # explicitly reported non-certified trading Core or static snapshot gaps.
    # Missing page / missing receipt / stale critical research / late run FAIL.
    return 0 if report.get("research_usable_by_0800") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
