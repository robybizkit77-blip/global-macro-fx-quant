#!/usr/bin/env python3
"""Crosswalk G8 Growth/Inflation observations to limited official web release anchors.

Research only. A source's current historical series is NOT a chain of first-release
vintages, and the newest observed series is NOT automatically the economic driver.
"""
import argparse
import json
import math
from datetime import date
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT, require
from validation.macro.v2_growth_inflation_g8_desk_inventory_v1 import inspect

CORE = "validation/macro/CORE_G8_OFFICIAL_RELEASE_WEB_ATTESTATIONS_2026-10-22.json"
GROWTH = "validation/macro/GROWTH_FIRST_RELEASE_OFFICIAL_WEB_ATTESTATIONS_2026-10-20.json"
EUR = "validation/macro/MACRO_V2_EUR_HICP_SEP_2026_RELEASE_SEQUENCE_2026-10-24.json"
SERIES = "live_data/sections/MACRO_SERIES.json"
CORE_IDS = {
    "USD.inflation": "US_CPIAUCSL_history_value",  # SA CPI index (not YoY rate)
    "CAD.inflation": "CA_CPI_HEADLINE_YOY_history_value",
    "GBP.inflation": "UK_CPI_HEADLINE_YOY_history_value",
    "NZD.inflation": "NZ_CPI_HEADLINE_YOY_history_value",
}


def month(raw):
    require(isinstance(raw, str) and len(raw) >= 7, "missing reference month")
    value = raw[:7]
    require(len(value) == 7 and value[4] == "-" and value[:4].isdigit()
            and value[5:].isdigit() and 1 <= int(value[5:]) <= 12,
            "bad reference month")
    return value


def check_event(source, cutoff):
    when = date.fromisoformat(source["published_on"])
    require(when <= cutoff, "official web anchor after research cutoff")
    require(source["source_url"].startswith("https://"), "official URL required")
    require(month(source["reference_period"]) <= when.strftime("%Y-%m"),
            "release chronology before observation period")


def read_json(root, path):
    return json.loads((root / path).read_text(encoding="utf-8"))


def build(series, core, growth, euro, *, as_of=date(2026, 10, 24)):
    inventory = inspect(series, as_of=as_of)
    require(core["historical_full_PIT_vintage_certified"] is False
            and growth["attestation_does_not_certify_historical_vintage"] is True
            and euro["full_historical_first_release_chain_certified"] is False,
            "evidence upgraded beyond official web scope")
    observed = {}
    for ccy, values in series.items():
        for row in values:
            require(row["id"] not in observed, "duplicate series identity")
            observed[row["id"]] = (ccy, row)
    anchors = {}

    def add(ccy, pillar, series_id, period, value, published_on, publisher, url, event):
        key = ccy + "." + pillar
        require(key not in anchors or event != "LATEST_OFFICIAL_WEB",
                "duplicate latest release anchor")
        require(series_id in observed and observed[series_id][0] == ccy,
                "attestation series identity not in observed registry: " + series_id)
        record = observed[series_id][1]
        require(record["category"] == ("Crescita" if pillar == "growth" else "Inflazione"),
                "attestation economic pillar mismatch")
        item = {"currency": ccy, "pillar": pillar, "series_id": series_id,
                "reference_period": month(period), "published_on": published_on,
                "published_value_for_metric": value, "publisher": publisher,
                "source_url": url, "event_type": event}
        check_event(item, as_of)
        anchors.setdefault(key, []).append(item)

    for a in core["attestations"]:
        key = a["key"]
        if key not in CORE_IDS:
            continue
        add(key.split(".")[0], "inflation", CORE_IDS[key], a["observation_period"],
            a["raw_series_value"], a["release_date"], a["publisher"], a["url"],
            "LATEST_OFFICIAL_WEB")

    for a in growth["attestations"]:
        add(a["currency"], "growth", a["series_id"], a["observation_period"],
            a["first_release_value"], a["release_date"], a["publisher"],
            a["official_source_url"], "LATEST_OFFICIAL_WEB")

    require(euro["series_id"] == "EA_HICP_HEADLINE_YOY_history_value"
            and euro["currency"] == "EUR" and euro["pillar"] == "inflation"
            and euro["unit"] == "Percent YoY", "Eurostat contract drift")
    eur_events = euro["observations"]
    require([x["event_type"] for x in eur_events] ==
            ["FLASH_ESTIMATE", "DETAILED_RELEASE"],
            "Eurostat flash and final must be distinct ordered events")
    require(eur_events[0]["published_on"] < eur_events[1]["published_on"],
            "Eurostat event chronology drift")
    for x in eur_events:
        add("EUR", "inflation", euro["series_id"], euro["reference_period"],
            x["value"], x["published_on"], euro["publisher"],
            x["source_url"], x["event_type"])

    rows = []
    for slot in inventory["rows"]:
        key = slot["currency"] + "." + slot["pillar"]
        matching = anchors.get(key, [])
        current_matches = []
        for evidence in matching:
            candidate = observed[evidence["series_id"]][1]
            candidate_period = month(candidate["last_date"])
            same_period = candidate_period == evidence["reference_period"]
            same_value = (type(candidate["last_value"]) in (float, int)
                          and math.isfinite(candidate["last_value"])
                          and abs(candidate["last_value"] -
                                  evidence["published_value_for_metric"]) < 1e-6)
            current_matches.append({
                **evidence,
                "observed_candidate_period": candidate_period,
                "candidate_observation_same_period": same_period,
                "candidate_value_matches_web_anchor": same_value if same_period else None,
                "selected_in_generic_latest_period_inventory":
                    evidence["series_id"] == slot["series_id"],
                "source_event_historical_or_revision_warning":
                    ("SAME_PERIOD_DIFFERENT_VALUE_REVIEW_REVISION" if same_period and not same_value
                     else "ANCHOR_FOR_PRIOR_OBSERVATION_PERIOD" if not same_period else None),
            })
        rows.append({
            "currency": slot["currency"], "pillar": slot["pillar"],
            "inventory_selected_series_id": slot["series_id"],
            "inventory_selected_period": slot["reference_period_raw"],
            "official_web_anchor_events": current_matches,
            "web_anchor_event_count": len(current_matches),
            "has_official_web_anchor": bool(current_matches),
            "selected_series_has_an_anchor":
                any(e["selected_in_generic_latest_period_inventory"] for e in current_matches),
            "release_timestamp_first_vintage_verified": False,
            "historical_pit_full_chain_certified": False,
            "new_macro_score_allowed": False,
        })
    require(len(rows) == 16, "G8 Growth/Inflation slot drift")
    return {
        "schema": "GMFQ_MACRO_V2_G8_GROWTH_INFLATION_OFFICIAL_RELEASE_CROSSWALK_V1",
        "as_of": as_of.isoformat(),
        "status": "LATEST_OFFICIAL_WEB_ANCHORS_DESCRIPTIVE_NOT_PIT",
        "summary": {
            "observed_research_slots": 16,
            "slots_with_limited_official_web_anchor": sum(r["has_official_web_anchor"] for r in rows),
            "slots_without_official_web_anchor": sum(not r["has_official_web_anchor"] for r in rows),
            "slots_where_generic_selected_series_has_an_anchor":
                sum(r["selected_series_has_an_anchor"] for r in rows),
            "distinct_release_events": sum(r["web_anchor_event_count"] for r in rows),
            "historical_full_pit_certified_slots": 0,
            "new_live_score_eligible_slots": 0,
        },
        "rows": rows,
        "cautions": [
            "An official latest web release is not an authenticated historical vintage archive.",
            "The most recently observed Growth series is not the economically selected driver.",
            "An unchanged flash-to-final value is still two market information events.",
            "Raw index values and transformed YoY metrics must not be compared directly.",
            "Missing or diverging current observations can reflect updates or revisions; do not auto-overwrite.",
        ],
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "eligible_for_backtest": False,
        "writes_live_data": False,
    }


def run():
    return build(read_json(ROOT, SERIES), read_json(ROOT, CORE),
                 read_json(ROOT, GROWTH), read_json(ROOT, EUR))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = run()
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")), "research receipts only /tmp")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
