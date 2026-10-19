#!/usr/bin/env python3
"""Adversarial regression: a 10Y spot observation never upgrades paired CHF/OIS."""
from __future__ import annotations

from datetime import date
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_chf_snb_10y_context_v1 import SOURCE, build, parse_official_html

TODAY = date(2026, 10, 19)
MATCH = "Yield on Swiss Confederation bonds 0.577% 19.10.2026 (Spot interest rate for 10-year maturities)"


def body(text):
    return ("<!doctype html><html><head><title>SNB official rates</title></head><body>" +
            "<h1>SNB Current interest rates</h1>" + "<p>Official publication information. </p>"*20 +
            text + "</body></html>").encode()


def rejects(text, part):
    try:
        parse_official_html(body(text), TODAY)
    except ValueError as exc:
        assert part in str(exc), (part,str(exc))
        return
    raise AssertionError("Invalid SNB observation was accepted")


def main():
    observed = parse_official_html(body("<div>Yield on Swiss Confederation bonds</div><span>0.577%</span>"
                                        "<time>19.10.2026</time><i>(Spot interest rate for 10-year maturities)</i>"), TODAY)
    assert observed["as_of"]=="2026-10-19"
    assert abs(observed["value_percent"]-0.577)<1e-12
    candidate=build(observed, hashlib.sha256(body(MATCH)).hexdigest())
    assert candidate["source_url"]==SOURCE
    assert candidate["tenor"]=="10Y" and candidate["status"]=="OFFICIAL_PUBLISHED_10Y_INFORMATIONAL"
    assert candidate["operational_rates_2y10y_untouched"] is True
    assert all(candidate[key] is False for key in
        ("has_current_2y","eligible_for_curve_spreads","eligible_for_core_signals",
         "eligible_for_backtests","ois_or_saron"))
    rejects(MATCH+" "+MATCH,"ambiguous")
    rejects("Yield on Swiss Confederation bonds 0.577% 19.10.2026 (Spot interest rate for 2-year maturities)","missing")
    rejects("Yield on Swiss Confederation bonds 0.577% 18.09.2026 (Spot interest rate for 10-year maturities)","not current")
    rejects("Yield on Swiss Confederation bonds 0.577% 20.10.2026 (Spot interest rate for 10-year maturities)","not current")
    rejects("Yield on Swiss Confederation bonds 25.000% 19.10.2026 (Spot interest rate for 10-year maturities)","bounded")
    rejects("<script>"+MATCH+"</script><p>Swiss bonds cannot be inferred from scripts.</p>","missing")
    rejects("Swiss 10Y yield 0.577% 19.10.2026","missing")
    print("SNB_PUBLIC_10Y_CONTEXT_NO_CORE_SOURCE_TEST_GREEN")


if __name__=="__main__":
    main()
