#!/usr/bin/env python3
"""No new NZD observation may pass publication without two reviewed source rows."""
from __future__ import annotations

import copy
import json

from check_nzd_rates_reviewed_snapshot_v1 import REGISTRY, ROOT, validate


def expect_hold(rates, registry, description):
    try:
        validate(rates, registry)
    except (ValueError, KeyError, TypeError, OSError):
        return
    raise AssertionError("unsafe NZD Rates promotion accepted: " + description)


def main():
    rates = json.loads((ROOT/"live_data/sections/NATIVE_RATES_DATA.json").read_text())
    reg = json.loads(REGISTRY.read_text())
    assert validate(rates, reg)["status"] == "PASS"
    newer = copy.deepcopy(rates)
    newer["NZD"]["date"] = "2026-10-20"
    expect_hold(newer, reg, "new unapproved date")
    wrong = copy.deepcopy(rates)
    wrong["NZD"]["2Y"] = wrong["NZD"]["2Y"] + 0.05
    expect_hold(wrong, reg, "2Y drift")
    wrong = copy.deepcopy(rates)
    wrong["NZD"]["history10"]["values"][-1] += 0.1
    expect_hold(wrong, reg, "history 10Y drift")
    wrong = copy.deepcopy(rates)
    wrong["NZD"]["tenors"][0]["date"] = "2026-10-15"
    expect_hold(wrong, reg, "tenor date drift")
    wrong = copy.deepcopy(reg)
    wrong["currencies"]["NZD"]["current_snapshot"] = "2026-10-20"
    expect_hold(rates, wrong, "registry modified alone")
    wrong = copy.deepcopy(reg)
    wrong["currencies"]["NZD"]["current_2Y"] = 4.12
    expect_hold(rates, wrong, "registry value modified alone")
    wrong = copy.deepcopy(reg)
    wrong["currencies"]["NZD"]["manual_approval_reference"] = ""
    expect_hold(rates, wrong, "missing human approval")
    wrong = copy.deepcopy(reg)
    wrong["currencies"]["NZD"]["independent_review_evidence"] = wrong["currencies"]["NZD"]["first_review_evidence"]
    expect_hold(rates, wrong, "reused review artifact")
    wrong = copy.deepcopy(reg)
    wrong["currencies"]["NZD"]["automatic_promotion_allowed"] = True
    expect_hold(rates, wrong, "automated approval")
    wrong = copy.deepcopy(rates)
    wrong["NZD"]["quality"] = "FULL_CURRENT_OFFICIAL_STAGING_REVIEW_REQUIRED"
    expect_hold(wrong, reg, "unapproved staging labelled as live")
    print("NZD_RATES_REGISTRY_TWO_REVIEW_FAIL_CLOSED_TESTS_PASS")


if __name__ == "__main__":
    main()
