#!/usr/bin/env python3
"""Access/readiness decisions never imply missing OIS prices or policy repricing."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from audit_ois_source_access_v1 import ACCESS, OFFICIAL, VIEW, audit


def rejects(plan: dict, view: dict, official: dict, contains: str) -> None:
    try:
        audit(plan, view, official)
    except (ValueError, TypeError) as exc:
        if contains not in str(exc):
            raise AssertionError(f"unexpected error {exc!s}, expected {contains!r}") from exc
    else:
        raise AssertionError(f"source audit unexpectedly accepted {contains}")


def main() -> None:
    plan = json.loads(ACCESS.read_text(encoding="utf-8"))
    view = json.loads(VIEW.read_text(encoding="utf-8"))
    official = json.loads(OFFICIAL.read_text(encoding="utf-8"))
    report = audit(plan, view, official)
    assert report["status"] == "PASS_NON_MUTATING"
    assert report["scope"] == "READ_ONLY_DIAGNOSTIC_NO_LIVE_PRICE_APPROVAL"
    assert report["operational_coverage"] == view["summary"]
    assert report["official_coverage"] == 4
    rows = report["blocked_source_decisions"]
    assert set(rows) == {"USD", "EUR", "CHF", "NZD"}
    assert rows["NZD"]["source_access_status"] == "BENCHMARK_EXISTS_BUT_PAID_SUBSCRIPTION_NOT_CONFIGURED_IN_REPO"
    assert rows["USD"]["source_url"].startswith("https://")
    assert rows["EUR"]["source_url"].startswith("https://www.eurex.com/")
    assert rows["EUR"]["candidate"].startswith("Eurex Three-Month Euro STR Futures")
    assert rows["EUR"]["operational_status"] == view["currencies"]["EUR"]["operational_status"]
    assert rows["CHF"]["source_url"].startswith("https://")
    # These three may change with later official certification; the test
    # enforces truth of live states rather than hardcoding 5/8 forever.
    assert all(r["official_status"] == official["currencies"][c]["status"] for c, r in rows.items())

    mutated_plan = deepcopy(plan)
    del mutated_plan["blocked_sources"]["EUR"]
    rejects(mutated_plan, view, official, "missing specific currency source/access plan")

    mutated = deepcopy(view)
    mutated["currencies"]["EUR"]["horizons"]["3m"]["policy_delta_bp"] = 22.5
    rejects(plan, mutated, official, "withheld OIS level leak")

    mutated = deepcopy(view)
    mutated["currencies"]["EUR"]["secondary_quote_context"]["cross_date_join_allowed"] = True
    rejects(plan, mutated, official, "unsafe promotion flag")

    # USD/CHF have estimated futures levels today; a changed estimated rate
    # is NOT a WITHHELD level leak. Assert the actual governance boundary:
    # never official backtest-eligible and never shadow an active official feed.
    for ccy in ("USD", "CHF"):
        state = view["currencies"][ccy]["operational_status"]
        if state == "WITHHELD":
            altered = deepcopy(view)
            altered["currencies"][ccy]["horizons"]["3m"]["rate"] = 4.25
            rejects(plan, altered, official, "withheld OIS level leak")
        elif state == "GREEN_ESTIMATED":
            altered = deepcopy(view)
            altered["currencies"][ccy]["backtest_eligible_as_official"] = True
            rejects(plan, altered, official, "estimated source must not be official backtest")
            altered_official = deepcopy(official)
            altered_official["currencies"][ccy]["status"] = "ACTIVE"
            rejects(plan, view, altered_official, "estimated source shadowing active official")
        else:
            assert state == "GREEN_OFFICIAL"
            altered_official = deepcopy(official)
            altered_official["currencies"][ccy]["status"] = "WITHHELD"
            rejects(plan, view, altered_official, "official promotion bypassed official runtime")

    if view["currencies"]["CHF"].get("secondary_quote_context"):
        altered = deepcopy(view)
        altered["currencies"]["CHF"]["secondary_quote_context"]["cross_date_join_allowed"] = True
        rejects(plan, altered, official, "unsafe promotion flag")
        altered = deepcopy(view)
        altered["currencies"]["CHF"]["secondary_quote_context"]["date_mismatch"] = False
        rejects(plan, altered, official, "date mismatch incorrectly reported")
    else:
        altered = deepcopy(view)
        altered["currencies"]["CHF"]["secondary_quote_context"] = {
            "full_curve_usable": False,
            "cross_date_join_allowed": False,
            "policy_delta_allowed": False,
            "repricing_signal_allowed": False,
            "backtest_eligible_as_official": False,
        }
        rejects(plan, altered, official, "secondary quote context not allowed")

    mutated = deepcopy(view)
    mutated["currencies"]["NZD"]["market_direction_proxy"]["policy_delta_from_proxy_allowed"] = True
    rejects(plan, mutated, official, "NZD bank bill directional proxy")

    mutated = deepcopy(view)
    mutated["currencies"]["NZD"]["change_1d_available"] = True
    rejects(plan, mutated, official, "withheld OIS repricing leak")

    mutated = deepcopy(view)
    mutated["summary"]["operational_green"] = 8
    rejects(plan, mutated, official, "summary is inconsistent")

    mutated_plan = deepcopy(plan)
    mutated_plan["governance"]["no_automatic_promotions"] = False
    rejects(mutated_plan, view, official, "may not change runtime")

    mutated_plan = deepcopy(plan)
    mutated_plan["blocked_sources"]["NZD"]["source_url"] = "http://untrusted"
    rejects(mutated_plan, view, official, "no trusted source URL")
    print("OIS_SOURCE_ACCESS_READINESS_V1_PASS")


if __name__ == "__main__":
    main()
