#!/usr/bin/env python3
"""Non-mutating G8 OIS source/access audit. Never upgrades an OIS observation."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACCESS = ROOT / "validation/cb_pricing/OIS_SOURCE_ACCESS_PLAN_V1_2026-10-19.json"
VIEW = ROOT / "live_data/sections/OIS_OPERATIONAL_VIEW.json"
OFFICIAL = ROOT / "live_data/sections/OIS_DATA.json"
REQUIRED = ("USD", "EUR", "CHF", "NZD")
ALL_G8 = frozenset(("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"))
H = ("3m", "6m", "12m")


def audit(plan: dict, view: dict, official: dict) -> dict:
    if plan.get("schema") != "GMFQ_OIS_SOURCE_ACCESS_PLAN_V1":
        raise ValueError("invalid OIS source registry schema")
    gov = plan.get("governance") or {}
    for key in ("no_automatic_promotions", "no_core_score_effect", "no_bias_effect",
                "no_sizing_effect", "no_backtest_effect", "report_only"):
        if gov.get(key) is not True:
            raise ValueError("access audit may not change runtime or trading signals")
    sources = plan.get("blocked_sources") or {}
    if set(sources) != set(REQUIRED):
        raise ValueError("missing specific currency source/access plan")
    curves = view.get("currencies") or {}
    cert = official.get("currencies") or {}
    if set(curves) != ALL_G8 or set(cert) != ALL_G8:
        raise ValueError("OIS input requires complete G8 universe")
    summary = view.get("summary") or {}
    counted_green = sum(str(r.get("operational_status", "")).startswith("GREEN_") for r in curves.values())
    counted_official = sum(r.get("operational_status") == "GREEN_OFFICIAL" for r in curves.values())
    counted_withheld = sum(r.get("operational_status") == "WITHHELD" for r in curves.values())
    if (summary.get("g8_total") != 8 or
        summary.get("operational_green") != counted_green or
        summary.get("operational_withheld") != counted_withheld or
        summary.get("green_official") != counted_official or
        counted_green + counted_withheld != 8):
        raise ValueError("OIS runtime summary is inconsistent")

    rows = {}
    for c in REQUIRED:
        src = sources[c]
        if not str(src.get("source_url", "")).startswith("https://"):
            raise ValueError(f"{c}: no trusted source URL")
        if not src.get("access_status") or not src.get("required_for_activation"):
            raise ValueError(f"{c}: absent source access decision")
        row = curves[c]
        official_row = cert[c]
        status = row.get("operational_status")
        if status not in ("GREEN_OFFICIAL", "GREEN_ESTIMATED", "WITHHELD"):
            raise ValueError(f"{c}: unknown operational status")
        horizons = row.get("horizons") or {}
        if status == "WITHHELD":
            if row.get("backtest_eligible_as_official") is not False:
                raise ValueError(f"{c}: withheld but official backtest eligible")
            for h in H:
                q = horizons.get(h) or {}
                if q.get("rate") is not None or q.get("policy_delta_bp") is not None:
                    raise ValueError(f"{c}: withheld OIS level leak")
            if row.get("change_1d_available") is not False or row.get("change_1w_available") is not False:
                raise ValueError(f"{c}: withheld OIS repricing leak")
        if status == "GREEN_OFFICIAL":
            if official_row.get("status") != "ACTIVE":
                raise ValueError(f"{c}: official promotion bypassed official runtime")
            if row.get("backtest_eligible_as_official") is not True:
                raise ValueError(f"{c}: official backtest flag inconsistent")
        if status == "GREEN_ESTIMATED":
            if official_row.get("status") == "ACTIVE":
                raise ValueError(f"{c}: estimated source shadowing active official")
            if row.get("backtest_eligible_as_official") is not False:
                raise ValueError(f"{c}: estimated source must not be official backtest")
        # All four currently blocked source lanes must be examined. No source
        # name or access plan upgrades a WITHHELD operational row to GREEN.
        if c == "EUR" and status == "WITHHELD":
            if row.get("quality") != "ESTIMATED_INFORMATIONAL":
                raise ValueError("EUR withheld source quality changed unexpectedly")
        quote_dates = {}
        ctx = row.get("secondary_quote_context")
        if ctx is not None:
            if c == "NZD" or status != "WITHHELD":
                raise ValueError(f"{c}: secondary quote context not allowed")
            for flag in ("full_curve_usable", "cross_date_join_allowed",
                         "policy_delta_allowed", "repricing_signal_allowed",
                         "backtest_eligible_as_official"):
                if ctx.get(flag) is not False:
                    raise ValueError(f"{c}: secondary context has unsafe promotion flag {flag}")
            for h, q in (ctx.get("horizons") or {}).items():
                if h not in H or q.get("rate_indicative") is None:
                    raise ValueError(f"{c}: invalid individual contract quote")
                day = str(q.get("quote_as_of") or "")
                date.fromisoformat(day)
                if not q.get("contract") or q.get("source_quality") != "SECONDARY_VERIFIED_DAILY_BAR":
                    raise ValueError(f"{c}: unverified contract context")
                quote_dates[h] = day
            if ctx.get("date_mismatch") != (len(set(quote_dates.values())) > 1):
                raise ValueError(f"{c}: quote date mismatch incorrectly reported")
        proxy = row.get("market_direction_proxy")
        if c == "NZD" and proxy:
            if proxy.get("substitutes_for_ois_level") is not False or proxy.get("policy_delta_from_proxy_allowed") is not False:
                raise ValueError("NZD bank bill directional proxy may never substitute OIS")
        elif c != "NZD" and proxy:
            raise ValueError(f"{c}: invalid NZD bank bill proxy")

        rows[c] = {
            "official_status": official_row.get("status"),
            "operational_status": status,
            "source_access_status": src["access_status"],
            "candidate": src["preferred_source"],
            "source_url": src["source_url"],
            "activation_condition": src["required_for_activation"],
            "individual_verified_quote_dates": quote_dates,
            "non_ois_proxy_present": proxy is not None,
            "provenance": ("OFFICIAL_CERTIFIED" if status == "GREEN_OFFICIAL"
                           else "INFORMATIONAL_ESTIMATED" if status == "GREEN_ESTIMATED"
                           else "WITHHELD_WITH_OPTIONAL_RESEARCH_CONTEXT"),
        }
    return {
        "schema": "GMFQ_OIS_SOURCE_ACCESS_AUDIT_V1",
        "status": "PASS_NON_MUTATING",
        "source_reviewed_as_of": plan["reviewed_as_of"],
        "operational_coverage": summary,
        "official_coverage": sum(x.get("status") == "ACTIVE" for x in cert.values()),
        "blocked_source_decisions": rows,
        "scope": "READ_ONLY_DIAGNOSTIC_NO_LIVE_PRICE_APPROVAL",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=str(ACCESS))
    ap.add_argument("--view", default=str(VIEW))
    ap.add_argument("--official", default=str(OFFICIAL))
    ap.add_argument("--output", default="/tmp/ois-source-access-audit-v1.json")
    ap.add_argument("--summary")
    args = ap.parse_args()
    obj = audit(
        json.loads(Path(args.plan).read_text(encoding="utf-8")),
        json.loads(Path(args.view).read_text(encoding="utf-8")),
        json.loads(Path(args.official).read_text(encoding="utf-8")),
    )
    Path(args.output).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": obj["status"],
                      "operational": obj["operational_coverage"],
                      "official": obj["official_coverage"],
                      "missing_sources": {c: r["source_access_status"]
                                          for c, r in obj["blocked_source_decisions"].items()}},
                     sort_keys=True))
    if args.summary:
        lines = ["### OIS G8 access readiness (informational only)", "",
                 "No source access or quotation was promoted to official OIS.", "",
                 "| Currency | Official | Operational | Current blocker |",
                 "|---|---|---|---|"]
        for c, r in obj["blocked_source_decisions"].items():
            lines.append(f"| {c} | {r['official_status']} | {r['operational_status']} | {r['source_access_status']} |")
        lines.append("")
        with Path(args.summary).open("a", encoding="utf-8") as fp:
            fp.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
