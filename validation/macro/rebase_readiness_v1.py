#!/usr/bin/env python3
"""PIT source-to-engine bridge diagnostics for a FUTURE G8 Macro rebase.

READ ONLY. This intentionally CANNOT output a replacement D.json. Registered
observations are not a certified reconstruction of the versioned 3-pillar
structural scoring function, and observation dates are not release timestamps.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
FX = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD", "CHF")
DIMS = ("inflation", "labour")
PAIRS = {frozenset(x) for x in itertools.combinations(FX, 2)}
PATHS = {
    "model": "live_data/sections/D.json",
    "series": "live_data/sections/MACRO_SERIES.json",
    "heat": "live_data/sections/MACRO_THERMOMETER_DATA.json",
    "registry": "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json",
    "rates": "live_data/sections/NATIVE_RATES_DATA.json",
    "ois": "live_data/sections/OIS_OPERATIONAL_VIEW.json",
    "pair_setup": "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
}


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError("MACRO_REBASE_SOURCE_INVALID: " + message)


def valid_number(value) -> bool:
    return type(value) in (float, int) and math.isfinite(value)


def period_key(raw, frequency: str) -> str:
    require(isinstance(raw, str), "observation period must be a string")
    if frequency in ("M", "Q") and re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", raw):
        try:
            anchor = date.fromisoformat(raw[:7] + "-01" if len(raw) == 7 else raw)
        except ValueError as exc:
            raise ValueError("MACRO_REBASE_SOURCE_INVALID: invalid observation period") from exc
        return anchor.strftime("%Y-%m")
    if frequency == "Q" and re.fullmatch(r"\d{4}Q[1-4]", raw):
        return raw[:4] + "-" + str(3 * int(raw[-1])).zfill(2)
    require(False, f"unrecognized {frequency} observation period {raw!r}")


def period_not_future(raw, frequency, today):
    key = period_key(raw, frequency)
    require(key <= today.strftime("%Y-%m"),
            f"future observation period {raw}")


def g8_coverage(model, series, heat, registry, rates, ois, setup, today):
    require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(model.get("asOf"))) is not None,
            "D.asOf not dated")
    mday = date.fromisoformat(model["asOf"])
    require(mday <= today, "future D.asOf")
    require(set(model.get("currencies") or []) == set(FX), "D G8 list incomplete")
    require(set(model.get("macro") or {}) >= set(FX), "D Macro fields incomplete")
    require(heat.get("schema_version") == "GMFQ_MACRO_HEATMAP_V1" and
            heat.get("status") == "ACTIVE", "Macro thermometer contract")
    require(registry.get("scope", {}).get("core_series_count") == 16,
            "PIT registry core 16-series contract")
    require(set(registry.get("scope", {}).get("currencies", [])) == set(FX),
            "PIT registry G8 coverage")
    require(set(registry.get("scope", {}).get("dimensions", [])) == set(DIMS),
            "PIT registry dimensions")
    require(set(rates) >= set(FX) and set(ois.get("currencies") or {}) >= set(FX),
            "Rates/pricing G8 feed missing")
    require(set(series) >= set(FX) and set(heat.get("currencies") or {}) >= set(FX),
            "Macro source G8 feed missing")
    require(set(registry.get("series") or {}) ==
            {c + "." + dim for c in FX for dim in DIMS},
            "Registry has missing or unrecognized core target")
    require(setup.get("schema") == "GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1" and
            setup.get("pair_count") == 28 and len(setup.get("pairs") or {}) == 28,
            "Pair model snapshot missing")
    require(setup.get("macro_baseline_asof") == model["asOf"],
            "Pair Macro provenance inconsistent with D.asOf")
    require(setup.get("entry_level_published") is False and
            setup.get("thesis_is_not_entry") is True,
            "Pair price/entry separation lost")
    observed_pairs = set()
    for name, row in setup["pairs"].items():
        require(re.fullmatch(r"[A-Z]{6}", name) is not None,
                f"invalid pair key {name}")
        key = frozenset((name[:3], name[3:]))
        require(key in PAIRS and key not in observed_pairs,
                f"duplicated or invalid pair {name}")
        observed_pairs.add(key)
        require(row.get("canonical_pair") == name[:3] + "/" + name[3:],
                f"canonical pair label mismatch {name}")
        require(isinstance(row.get("decision_frame"), dict) and
                isinstance(row.get("setup"), dict), f"incomplete Pair frame {name}")
    require(observed_pairs == PAIRS, "one of 28 G8 combinations missing")

    mapped = {}
    growth_total = 0
    for c in FX:
        current = model["macro"][c]
        require(all(valid_number(current.get(field))
                    for field in ("growth", "inflation", "labour")),
                f"{c}: canonical scalar Macro scores missing")
        targets = {}
        for dim in DIMS:
            key = c + "." + dim
            entry = registry["series"][key]
            require(entry.get("source_adapter_status") == "READY",
                    f"{key}: source adapter not READY")
            replay = entry.get("historical_replay_evidence") or {}
            target_id = replay.get("macro_series_id") or (entry["series_id"] + "_history_value")
            matches = [r for r in series[c] if r.get("id") == target_id]
            require(len(matches) == 1, f"{key}: expected exactly one registered historical row")
            r = matches[0]
            h = heat["currencies"][c].get(dim) or {}
            require((h.get("series_id"), h.get("frequency"), h.get("transformation")) ==
                    (entry.get("series_id"), entry.get("frequency"), entry.get("transformation")),
                    f"{key}: live heatmap does not match frozen registry")
            dates, values = r.get("dates"), r.get("values")
            require(isinstance(dates, list) and isinstance(values, list) and
                    len(dates) >= 2 and len(dates) == len(values),
                    f"{key}: invalid source history")
            require(period_key(dates[-1], entry["frequency"]) ==
                    period_key(h.get("as_of"), entry["frequency"]),
                    f"{key}: heat/source observation date mismatch")
            period_not_future(dates[-1], entry["frequency"], today)
            require(valid_number(h.get("latest_value")) and
                    valid_number(values[-1]), f"{key}: nonfinite latest observation")
            require(isinstance(h.get("validation"), dict) and
                    all(h["validation"].get(flag) is True
                        for flag in ("source", "history", "latest", "transformation")),
                    f"{key}: source/history validation not PASS")
            # Inflation via an INDEX is expressed as % YoY in the heatmap.
            # Never assume it must equal the index level in MACRO_SERIES.
            target = {
                "source_status": "READY_REGISTERED_PIT_HISTORY",
                "observation_as_of": h["as_of"],
                "release_timestamp": None,
                "release_timestamp_status": "NOT_PRESENT_IN_RUNTIME",
                "frequency": entry["frequency"],
                "series_id": entry["series_id"],
                "canonical_macro_series_id": target_id,
                "source": h.get("source"),
                "transformation": entry["transformation"],
                "series_value": values[-1],
                "transformed_value": h["latest_value"],
                "historical_replay_certified": entry.get("historical_replay_certified") is True,
                "score_mapping_status": "UNSPECIFIED_FOR_D",
            }
            targets[dim] = target
        growth_rows = []
        for row in series[c]:
            if row.get("category") != "Crescita":
                continue
            dates = row.get("dates") or []
            values = row.get("values") or []
            if len(dates) < 2 or len(dates) != len(values):
                continue
            if not valid_number(values[-1]):
                continue
            stamp = dates[-1]
            # Growth rows may be monthly, quarterly or period-end dated.
            frequency = row.get("frequency") or "M"
            if frequency not in ("M", "Q"):
                continue
            period_not_future(stamp, frequency, today)
            growth_rows.append({
                "series_id": row.get("id"),
                "label": row.get("label"),
                "observation_as_of": stamp,
                "frequency": frequency,
                "latest_value": values[-1],
                "source_file": row.get("source_file"),
                "score_weight": None,
                "release_timestamp": None,
            })
        require(growth_rows, f"{c}: no dated Growth source can be inventoried")
        growth_total += len(growth_rows)
        rd = rates[c]
        rate_day = rd.get("date")
        require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(rate_day)) is not None and
                date.fromisoformat(rate_day) <= today, f"{c}: invalid Rates date")
        official = ("OFFICIAL" in str(rd.get("quality") or "") and
                    valid_number(rd.get("2Y")) and valid_number(rd.get("10Y")))
        age = (today - date.fromisoformat(rate_day)).days
        rate_ok = official and age <= 5
        op = ois["currencies"][c]
        oday = op.get("as_of")
        require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(oday)) is not None and
                date.fromisoformat(oday) <= today, f"{c}: invalid OIS date")
        ostatus = op.get("operational_status")
        require(ostatus in ("GREEN_OFFICIAL", "GREEN_ESTIMATED", "WITHHELD"),
                f"{c}: unexpected OIS status")
        oofficial = (ostatus == "GREEN_OFFICIAL" and
                     op.get("quality") == "OFFICIAL_CERTIFIED" and
                     op.get("official_status") == "ACTIVE" and
                     (today - date.fromisoformat(oday)).days <= 5)
        # Old canonical scalar scores are NOT transformations of the heatmap
        # percentile; do not print a fabricated proposed score.
        mapped[c] = {
            "historical_model_as_of": model["asOf"],
            "historical_scores_not_recalculated": {
                k: current[k] for k in ("growth", "inflation", "labour")},
            "inflation": targets["inflation"],
            "labour": targets["labour"],
            "growth_source_inventory": growth_rows,
            "growth_score_status": "VERSIONED_RULE_NOT_CERTIFIED",
            "rates_2y_10y": {
                "as_of": rate_day, "official_current": rate_ok,
                "status": "OFFICIAL_CURRENT" if rate_ok else "WITHHELD"},
            "policy_pricing": {
                "as_of": oday,
                "source_status": ostatus,
                "official_current": oofficial,
                "status": "OFFICIAL_CURRENT" if oofficial else "NO_OFFICIAL_REPRICING",
            },
            "rebase_ready": False,
            "proposed_scores": None,
        }

    proposed_pairs = {
        key: {
            "historical_macro_baseline": model["asOf"],
            "historical_favored": row["setup"].get("structuralFav"),
            "historical_macro_side": row["decision_frame"].get("macroSide"),
            "historical_policy_side": row["decision_frame"].get("policySide"),
            "proposed_favored": None,
            "proposed_macro_side": None,
            "proposed_policy_side": None,
            "certified_delta": None,
            "status": "WITHHELD_UNTIL_VERSIONED_SCORE_REBASE",
        } for key, row in sorted(setup["pairs"].items())
    }
    return {
        "schema": "GMFQ_G8_MACRO_REBASE_READINESS_V1",
        "run_as_of": today.isoformat(),
        "canonical_macro_baseline_as_of": model["asOf"],
        "pair_price_as_of": setup.get("price_asof"),
        "source_lineage": "PASS",
        "structural_rebase": "BLOCKED_SCORE_CONTRACT",
        "safe_to_publish_D": False,
        "safe_to_update_structural_pair_preferences": False,
        "registered_macro_series": 16,
        "growth_sources_inventoried": growth_total,
        "tracked_currencies": 8,
        "tracked_pairs": 28,
        "required_to_unblock": [
            "Versioned 8-country Growth/Labour/Inflation score formula with inputs, transformations, weights and cycle mapping",
            "Release timestamps / point-in-time availability for every score-driving observation, not only observation periods",
            "CB/rates scoring and exact-date quality gate, including WITHHELD and estimated instruments",
            "Independent before/after D.json score and 28-pair regression validation, OOS fingerprint policy",
        ],
        "note": ("Read-only candidate INPUT MANIFEST, not a recalculated D.json. "
                 "Registered histories and thermometer percentiles are not versioned canonical FX scores."),
        "currencies": mapped,
        "pairs": proposed_pairs,
    }


def markdown(report):
    out = [
        "## Macro G8 → motore FX: ricertificazione strutturale",
        f"**Provenienza:** {report['source_lineage']} · **Ricalcolo:** {report['structural_rebase']} · "
        f"**D.json pubblicabile:** NO",
        "",
        f"Baseline esistente: {report['canonical_macro_baseline_as_of']} · "
        f"Prezzo Pair: {report['pair_price_as_of']}",
        "",
        "| Valuta | Inflazione | Lavoro | Crescita inventariata | Rates | OIS/futures ufficiali |",
        "|---|---|---|---:|---|---|",
    ]
    for c, x in report["currencies"].items():
        out.append(
            f"| {c} | {x['inflation']['observation_as_of']} | "
            f"{x['labour']['observation_as_of']} | {len(x['growth_source_inventory'])} | "
            f"{x['rates_2y_10y']['status']} | {x['policy_pricing']['status']} |")
    out += [
        "",
        f"**{report['registered_macro_series']}/16** core Macro mappate · "
        f"**{report['tracked_pairs']}/28** coppie inventariate · "
        f"**{report['growth_sources_inventoried']}** serie Growth tracciate",
        "",
        "### Mancanze prima del ricalcolo",
    ]
    out += ["- " + x for x in report["required_to_unblock"]]
    out += [
        "",
        "**Vietato** pubblicare nuovi score e nuove preferenze strutturali senza formula "
        "certificata e prova PIT. Le date delle osservazioni non equivalgono alle date "
        "di rilascio; una serie trimestrale non è un fixing FX.",
        "",
    ]
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=ROOT)
    p.add_argument("--asof", default=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat())
    p.add_argument("--out", type=Path)
    p.add_argument("--markdown", type=Path)
    a = p.parse_args()
    repo = a.repo_root
    read = lambda name: json.loads((repo / PATHS[name]).read_text(encoding="utf-8"))
    report = g8_coverage(*(read(k) for k in PATHS), date.fromisoformat(a.asof))
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if a.markdown:
        a.markdown.parent.mkdir(parents=True, exist_ok=True)
        a.markdown.write_text(markdown(report), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "source_lineage", "structural_rebase", "safe_to_publish_D",
        "canonical_macro_baseline_as_of", "registered_macro_series",
        "growth_sources_inventoried", "tracked_currencies", "tracked_pairs")},
        ensure_ascii=False))


if __name__ == "__main__":
    main()
