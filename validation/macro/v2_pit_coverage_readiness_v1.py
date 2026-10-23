#!/usr/bin/env python3
"""G8 Macro V2 PIT source-readiness dossier. Read-only, no inferred release dates.

A series of observed historical VALUES is not a point-in-time FIRST-release
vintage archive. This gate checks latest anchors, source identities and the
missing training requirements; it cannot authorize any Macro or FX score.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.v2_shadow_features_v1 import (
    ROOT, FX, audit_current_inventory,
)
from validation.macro.v2_shadow_intensity_v1 import WINDOW

SCHEMA = "GMFQ_MACRO_V2_G8_PIT_COVERAGE_READINESS_V1"
CORE_FILE = "validation/macro/CORE_G8_OFFICIAL_RELEASE_WEB_ATTESTATIONS_2026-10-22.json"
GROWTH_FILE = "validation/macro/GROWTH_FIRST_RELEASE_OFFICIAL_WEB_ATTESTATIONS_2026-10-20.json"
GBP_FILE = "validation/macro/GBP_MGSX_ROLLING_WINDOW_FIRST_RELEASE_MAP_2026-10-20.json"
BLS_FILE = "validation/macro/fixtures/v2_bls_us_unrate_first_release_2023_12_2024_04.json"
REGISTRY = "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json"
THERMOMETER = "live_data/sections/MACRO_THERMOMETER_DATA.json"
SERIES = "live_data/sections/MACRO_SERIES.json"
CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
PILLARS = ("growth", "labour", "inflation")


def check(ok: bool, explanation: str) -> None:
    if not ok:
        raise ValueError("MACRO_V2_PIT_COVERAGE_REJECTED: " + explanation)


def finite(x: object) -> bool:
    return type(x) in (float, int) and math.isfinite(x)


def month_of(raw: str) -> str:
    check(isinstance(raw, str) and len(raw) in (7, 10),
          "period not a YYYY-MM or YYYY-MM-DD date")
    try:
        if len(raw) == 7:
            return date.fromisoformat(raw + "-01").strftime("%Y-%m")
        return date.fromisoformat(raw).strftime("%Y-%m")
    except ValueError as exc:
        raise ValueError("MACRO_V2_PIT_COVERAGE_REJECTED: invalid period") from exc


def read(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def inspect(inputs: dict[str, dict], *, as_of: date) -> dict:
    """Return 24 research slots without converting observed series to PIT vintages."""
    reg, therm, series = (inputs["registry"], inputs["therm"], inputs["series"])
    core, growth, gbp, bls = (
        inputs["core"], inputs["growth"], inputs["gbp"], inputs["bls"]
    )
    check(set(reg.get("series", {})) == {
        c + "." + d for c in CURRENCIES for d in ("inflation", "labour")
    }, "16 Core source identities changed")
    check(set(therm.get("currencies", {})) == set(FX) and set(series) == set(FX),
          "G8 source/thermometer coverage drift")
    check(core.get("schema") == "GMFQ_G8_CORE_OFFICIAL_WEB_RELEASE_ATTESTATIONS_V1"
          and core.get("historical_full_PIT_vintage_certified") is False
          and core.get("evidence_class") ==
          "OFFICIAL_PUBLISHER_RELEASE_WEB_VALUE_DATE_NOT_IMMUTABLE_BYTES",
          "core attestations cannot promote historical PIT")
    check(growth.get("schema") == "GMFQ_G8_GROWTH_FIRST_RELEASE_ATTESTATIONS_V1"
          and growth.get("attestation_does_not_certify_historical_vintage") is True
          and growth.get("attestation_does_not_recalculate_macro_scores") is True,
          "Growth latest observations cannot become complete PIT")
    check(gbp.get("schema") == "GMFQ_GBP_MGSX_ROLLING_WINDOW_FIRST_RELEASE_MAP_V1"
          and gbp.get("claim_full_historical_vintage_certified") is False
          and gbp.get("released_at_timestamps_utc") is None
          and gbp.get("series_id") == "MGSX",
          "GBP rolling-window calendar not a complete release archive")
    check(bls.get("schema") == "GMFQ_MACRO_V2_PIT_FEATURE_INPUT_V1"
          and bls.get("currency") == "USD" and bls.get("pillar") == "labour"
          and bls.get("first_release_only") is True
          and bls.get("series_id") == "LNS14000000",
          "BLS first-release pilot changed identity")
    check(all(x.get("kind") == "FIRST" and x.get("released_at")
              and x.get("evidence_ref") for x in bls.get("vintages", []))
          and len(bls["vintages"]) == 5
          and len({x["observation_period"] for x in bls["vintages"]}) == 5,
          "BLS pilot does not contain five distinct attested first releases")
    check(reg["series"]["USD.labour"]["series_id"] != bls["series_id"],
          "BLS LNS14000000 pilot is not canonical UNRATE: mapping needs separate review")

    latest_core = {}
    for a in core.get("attestations", []):
        key = a.get("key")
        check(key in reg["series"] and key not in latest_core,
              "missing, duplicate or unknown core attestation")
        ccy, pillar = key.split(".")
        record = therm["currencies"][ccy][pillar]
        check(month_of(a["observation_period"]) == month_of(record["as_of"])
              and finite(a.get("published_value"))
              and finite(record.get("latest_value"))
              and abs(a["published_value"] - record["latest_value"]) < 1e-6,
              "latest Core attestation value/period mismatch: " + key)
        released = date.fromisoformat(a["release_date"])
        check(released <= as_of and released >=
              date.fromisoformat(month_of(a["observation_period"]) + "-01"),
              "Core publication outside observation/as-of chronology: " + key)
        latest_core[key] = {
            "period": month_of(a["observation_period"]),
            "released_on": released.isoformat(),
            "publisher": a.get("publisher"),
            "utc_release_time_verified": bool(a.get("release_timestamp_local")),
            "evidence_type": "DATED_OFFICIAL_WEB_LATEST_ONLY_NO_ARCHIVE_BYTES",
        }
    check(len(latest_core) == 8, "expected eight independently sourced latest Core anchors")

    latest_growth = {}
    for a in growth.get("attestations", []):
        c = a.get("currency")
        k = a.get("series_id")
        check(c in FX and c not in latest_growth, "unknown/duplicate Growth anchor")
        matches = [r for r in series[c] if r.get("category") == "Crescita"
                   and r.get("id") == k]
        check(len(matches) == 1, "Growth attestation missing exact series identity")
        raw = matches[0]
        check(month_of(a["observation_period"]) == month_of(raw["last_date"])
              and finite(a.get("first_release_value"))
              and finite(raw.get("last_value"))
              and abs(a["first_release_value"] - raw["last_value"]) < 1e-6
              and a.get("units") == raw.get("unit"),
              "Growth latest anchor has source/metric/period drift: " + c)
        released = date.fromisoformat(a["release_date"])
        check(released <= as_of and
              released >= date.fromisoformat(month_of(a["observation_period"]) + "-01"),
              "Growth release chronology invalid: " + c)
        latest_growth[c] = {
            "series_id": k, "period": month_of(a["observation_period"]),
            "released_on": released.isoformat(),
            "source_type": "LATEST_GROWTH_OFFICIAL_WEB_NOT_FULL_FIRST_RELEASE_HISTORY",
            "full_pit_archive_verified": False,
        }
    check(len(latest_growth) == 2 and set(latest_growth) == {"AUD", "NZD"},
          "Growth attestation scope expanded without dedicated review")

    check(len(gbp.get("official_periods", [])) == 3, "GBP limited evidence-map count")
    check(gbp["official_periods"][-1]["canonical_end_month"] == "2026-08",
          "GBP ONS rolling three-month label mapping changed")
    check(not gbp.get("source_content_sha256"), "GBP archival hash status changed; review needed")

    rows = []
    for ccy in CURRENCIES:
        registered_growth = [s for s in series[ccy] if s.get("category") == "Crescita"]
        check(registered_growth, ccy + ": missing observed Growth history")
        for pillar in PILLARS:
            if pillar == "growth":
                details = {
                    "source_status": "GROWTH_OBSERVATIONS_AVAILABLE_INPUT_NOT_SELECTED",
                    "candidate_series": [r["id"] for r in registered_growth],
                    "observed_history_points_max":
                        max(len(r.get("dates", [])) for r in registered_growth),
                    "source_id": None, "frequency": None,
                    "training_first_release_minimum": None,
                    "latest_anchor": latest_growth.get(ccy),
                    "source_transport": "MULTIPLE_SERIES_UNRESOLVED",
                }
                check(details["observed_history_points_max"] >= 12,
                      ccy + ": insufficient observed Growth inventory")
            else:
                key = ccy + "." + pillar
                r = reg["series"][key]
                t = therm["currencies"][ccy][pillar]
                check(r["currency"] == ccy and r["dimension"] == pillar
                      and r["series_id"] == t["series_id"]
                      and r["frequency"] == t["frequency"]
                      and r["source_adapter_status"] == "READY"
                      and r["historical_replay_certified"] is True
                      and t["history"] and len(t["history"]) >= 24
                      and finite(t["history"][-1])
                      and finite(t["latest_value"])
                      and abs(t["latest_value"] - t["history"][-1]) <= 1e-6,
                      key + ": registry/observed history contract mismatch")
                check(r["frequency"] in WINDOW, key + ": unsupported frequency")
                details = {
                    "source_status": "CORE_OBSERVED_REGISTERED_NOT_PIT_TRAINING",
                    "candidate_series": [r["series_id"]],
                    "observed_history_points_max": len(t["history"]),
                    "source_id": r["series_id"], "frequency": r["frequency"],
                    "training_first_release_minimum": WINDOW[r["frequency"]] + 1,
                    "latest_anchor": latest_core.get(key),
                    "source_transport": r.get("transport_class"),
                }
            rows.append({
                "currency": ccy, "pillar": pillar, **details,
                "latest_anchor_only": details["latest_anchor"] is not None,
                "complete_canonical_first_release_history_certified": False,
                "full_historical_pit_for_scoring": False,
                "eligible_for_shadow_intensity_training": False,
                "eligible_for_live_scoring": False,
                "blocking_requirements": [
                    "VERSIONED_EXACT_SERIES_AND_UNIT" if pillar == "growth"
                        else "CERTIFY_SOURCE_SPECIFIC_FIRST_RELEASE_CHAIN",
                    "FIRST_RELEASE_TIMESTAMPS_AND_RAW_ARCHIVE_EVIDENCE",
                    "CONTIGUOUS_TRAINING_WINDOW_WITHOUT_REVISION_LEAKAGE",
                    "INDEPENDENT_PIT_REVIEW_AND_MODEL_APPROVAL",
                ],
            })
    # An official BLS LNS pilot is related to USD unemployment but NOT an
    # audited UNRATE history; never count its five rows toward canonical readiness.
    summary = {
        "g8_currencies": len(CURRENCIES),
        "observed_pillar_slots": len(rows),
        "registered_core_series": len(reg["series"]),
        "growth_currencies_with_observations": sum(
            r["pillar"] == "growth" for r in rows
        ),
        "latest_core_official_web_anchors": len(latest_core),
        "latest_growth_official_web_anchors": len(latest_growth),
        "first_release_pilot_rows_unmapped_to_canonical": len(bls["vintages"]),
        "gbp_ons_rolling_month_evidence_only": len(gbp["official_periods"]),
        "certified_full_first_release_histories": 0,
        "eligible_live_macro_pillars": 0,
    }
    check(len(rows) == 24 and summary["registered_core_series"] == 16
          and summary["growth_currencies_with_observations"] == 8,
          "G8 coverage cardinality")
    return {
        "schema": SCHEMA, "as_of": as_of.isoformat(),
        "status": "ALL_24_OBSERVED_BUT_NO_FULL_PIT_TRAINING_AUTHORIZED",
        "summary": summary, "rows": rows,
        "notes": [
            "120 observed monthly values are not 120 timestamped first releases.",
            "The 8 core / 2 growth official-page anchors each cover the latest period only.",
            "GBP MGSX windows are not calendar months with independently verified UTC release times.",
            "BLS LNS14000000 five-release pilot must not be silently assigned to UNRATE.",
            "Secondary/intermediary transports are not promoted by this inventory.",
            "A blank certified-PIT status is not a missing macro observation.",
        ],
        "scores_computed": False, "model_parameters_fitted": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "writes_live_data": False,
    }


def run(*, root: Path = ROOT, as_of: date | None = None) -> dict:
    as_of = as_of or datetime.now(ZoneInfo("Europe/Rome")).date()
    audit_current_inventory(root)
    return inspect({
        "registry": read(root, REGISTRY),
        "therm": read(root, THERMOMETER),
        "series": read(root, SERIES),
        "core": read(root, CORE_FILE),
        "growth": read(root, GROWTH_FILE),
        "gbp": read(root, GBP_FILE),
        "bls": read(root, BLS_FILE),
    }, as_of=as_of)


def markdown(r: dict) -> str:
    s = r["summary"]
    lines = [
        "# G8 Macro V2 — evidence readiness (research only)",
        "As of " + r["as_of"] + " · No live scores or pair mutations.",
        "",
        f"Observed pillars **{s['observed_pillar_slots']}/24**; core "
        f"**{s['registered_core_series']}/16**; Growth **"
        f"{s['growth_currencies_with_observations']}/8**.",
        f"Latest official-web anchors: Core **{s['latest_core_official_web_anchors']}** "
        f"and Growth **{s['latest_growth_official_web_anchors']}** (not complete PIT).",
        "**0/24** certified full first-release histories; **0/24** "
        "eligible for score publication.",
        "",
        "| Currency | Pillar | Frequency | Observed points | Latest anchor | PIT ready |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in r["rows"]:
        lines.append("| {currency} | {pillar} | {frequency} | {points} | {anchor} | No |".format(
            currency=item["currency"], pillar=item["pillar"],
            frequency=item["frequency"] or "unselected",
            points=item["observed_history_points_max"],
            anchor=(item["latest_anchor"]["period"] if item["latest_anchor"] else "none"),
        ))
    lines += ["", "## Remaining evidence", *("- " + n for n in r["notes"])]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", type=date.fromisoformat)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()
    receipt = run(as_of=args.asof)
    for dest, payload in (
        (args.json_out, json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"),
        (args.markdown_out, markdown(receipt)),
    ):
        if dest:
            check(dest.resolve().is_relative_to(Path("/tmp")),
                  "readiness evidence may only be written to /tmp")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(payload, encoding="utf-8")
    print(json.dumps({"status": receipt["status"], **receipt["summary"],
                      "safe_to_publish_new_D": receipt["safe_to_publish_new_D"]}))


if __name__ == "__main__":
    main()
