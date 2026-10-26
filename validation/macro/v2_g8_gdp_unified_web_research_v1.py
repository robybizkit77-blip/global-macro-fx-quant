"""Research-only G8 GDP 2024Q1-2026Q2 unified release statement view.

Never writes live data, certifies historic release-day bytes, or supplies
Macro scoring, Beta/Forward, or FX pair ranking.
"""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlsplit
from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot

FIX = Path(__file__).parent / "fixtures"
QUARTER_FILES = (
    "v2_g8_gdp_q2_2022_official_web_release_research_v1.json",
    "v2_g8_gdp_q3_2022_official_web_release_research_v1.json",
    "v2_g8_gdp_q4_2022_official_web_release_research_v1.json",
    "v2_g8_gdp_q1_2023_official_web_release_research_v1.json",
    "v2_g8_gdp_q2_2023_official_web_release_research_v1.json",
    "v2_g8_gdp_q3_2023_official_web_release_research_v1.json",
    "v2_g8_gdp_q4_2023_official_web_release_research_v1.json",
    "v2_g8_gdp_q1_2024_official_web_release_research_v1.json",
    "v2_g8_gdp_q2_2024_official_web_release_research_v1.json",
    "v2_g8_gdp_q3_2024_official_web_release_research_v1.json",
    "v2_g8_gdp_q4_2024_official_web_release_research_v1.json",
    "v2_g8_gdp_q1_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q2_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q3_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q4_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_multiquarter_partial_official_research_v1.json",
)
Q2_2026_LEDGER = "v2_g8_quarterly_gdp_q2_2026_web_release_ledger_v1.json"
CURRENCIES = set("USD EUR GBP JPY CHF CAD AUD NZD".split())

def read_rows(root=FIX):
    rows=[]
    for name in QUARTER_FILES:
        record=json.loads((root/name).read_text(encoding="utf-8"))
        if record.get("eligible_for_macro_scoring") is not False:
            raise ValueError("research-only fixture attempted score promotion")
        rows.extend(record["records"])
    validate(rows)
    return rows

def unified_research_rows(root=FIX):
    """Merge legacy 2026Q2 publisher record WITHOUT silently cloning US advance."""
    rows=read_rows(root)
    old=json.loads((root/Q2_2026_LEDGER).read_text(encoding="utf-8"))
    if (old.get("observed_first_web_releases") != 8
        or old.get("observed_follow_up_revisions") != 2
        or old.get("eligible_for_macro_scoring") is not False):
        raise ValueError("original 2026Q2 publisher ledger scope changed")
    observed={(x["currency"],x["reference_quarter"],x["stage_order"]):x for x in rows}
    if len(observed)!=len(rows):
        raise ValueError("research fixture duplicate GDP release stage")
    old_first=set()
    q2_rows=0
    for x in old["records"]:
        if x["reference_quarter"] != "2026Q2":
            raise ValueError("unapproved original ledger period")
        c=x["currency"]
        if c not in CURRENCIES:
            raise ValueError("unapproved GDP currency")
        if x["stage_order"]==0:
            old_first.add(c)
        key=(c,"2026Q2",x["stage_order"])
        normalized={**x,
            "verified_publisher_host":urlsplit(x["source_url"]).hostname,
            "eligible_for_macro_scoring":False,
            "PIT_training_vintage_certified":False,
            "source_ledger_origin":"LEGACY_2026Q2_PUBLISHER_WEB_ONLY",
        }
        if key in observed:
            existing=observed[key]
            for field in ("reported_value","reported_unit","publisher_release_day","source_url"):
                if existing[field] != normalized[field]:
                    raise ValueError("overlapping GDP vintage disagrees: "+field)
            if key!=("USD","2026Q2",0):
                raise ValueError("unexpected overlapping GDP vintage")
        else:
            rows.append(normalized)
            observed[key]=normalized
            q2_rows+=1
    if old_first!=CURRENCIES or q2_rows!=9:
        # 7 other initial statements + EUR/GBP revisions = 9; US stage0
        # is already in normalized ledger and MUST NOT be double counted.
        raise ValueError("unexpected GDP legacy bridge cardinality")
    return validate(rows)

def research_receipt(root=FIX, cutoff="2026-10-26T00:00:00Z"):
    rows=unified_research_rows(root)
    first={(r["currency"],r["reference_quarter"]) for r in rows if r["stage_order"]==0}
    quarters={r["reference_quarter"] for r in rows}
    by_currency={c:len([q for cur,q in first if cur==c]) for c in sorted(CURRENCIES)}
    return {
        "schema":"GMFQ_GDP_G8_UNIFIED_WEB_RELEASE_RESEARCH_ONLY_V1",
        "quarters_documented":len(quarters),
        "first_publisher_statements_documented":len(first),
        "first_statement_quarters_per_currency":by_currency,
        "research_events_documented":len(rows),
        "source_statement_record_only":True,
        "release_day_bytes_historical_archive_certified":False,
        "intraday_PIT_certified":False,
        "cross_country_metric_definition_harmonized":False,
        "historical_training_approved":False,
        "safe_to_update_live_macro_D":False,
        "safe_to_use_for_beta":False,
        "safe_to_use_for_forward":False,
        "safe_to_change_28_pairs":False,
        "available_by_cutoff":snapshot(rows,cutoff),
    }
