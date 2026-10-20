#!/usr/bin/env python3
"""Read-only Macro qualitative-label reapproval queue against frozen source checkpoint.

A change to official inputs opens a review task for currency Macro or Policy
labels and every containing G8 pair. It does NOT calculate a score, update
currencyIntelData, redate D.json, or promote estimated rates/CB to official.
Dates are OBSERVATION dates; they are NOT release timestamps.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.rebase_readiness_v1 import ROOT, FX, PATHS, g8_coverage

CHECKPOINT = ROOT / "validation/macro/MACRO_LABEL_SOURCE_CHECKPOINT_2026-10-20.json"
SCHEMA = "GMFQ_MACRO_QUALITATIVE_LABEL_CHECKPOINT_V1"
RECEIPT = "GMFQ_MACRO_QUALITATIVE_REAPPROVAL_QUEUE_V1"


def require(ok, text):
    if not ok:
        raise ValueError("QUALITATIVE_REVIEW_GATE_REJECTED: " + text)


def numeric(x):
    return type(x) in (int, float) and math.isfinite(x)


def check_vector(entry, name):
    dates, values = entry.get("dates"), entry.get("values")
    require(isinstance(dates, list) and isinstance(values, list) and
            len(dates) >= 2 and len(dates) == len(values), name + " invalid history")
    require(all(isinstance(d, str) and d for d in dates), name + " invalid history dates")
    require(len(set(dates)) == len(dates) and dates == sorted(dates),
            name + " nonmonotonic or duplicate observations")
    require(all(numeric(v) for v in values), name + " nonfinite history")
    return dates, values


def history_delta(old, new):
    """Read-only comparison: additions, rollback, latest and older revisions."""
    old_dates, old_values = check_vector(old, old.get("id", "checkpoint"))
    new_dates, new_values = check_vector(new, new.get("id", "live"))
    past = dict(zip(old_dates, old_values))
    current = dict(zip(new_dates, new_values))
    removed = sorted(set(past) - set(current))
    added = sorted(set(current) - set(past))
    changed = sorted(d for d in set(past) & set(current) if past[d] != current[d])
    flags = []
    if added:
        flags.append("NEW_OBSERVATION" if not removed and all(x > old_dates[-1] for x in added)
                     else "HISTORY_RESTRUCTURED")
    if removed:
        flags.append("HISTORY_REMOVED")
    if changed:
        flags.append("LATEST_REVISION" if old_dates[-1] in changed else "HISTORICAL_REVISION")
        if len(changed) > 1 or (len(changed) == 1 and changed[0] != old_dates[-1]):
            if "HISTORICAL_REVISION" not in flags:
                flags.append("HISTORICAL_REVISION")
    if not flags and (old.get("frequency"), old.get("source_file")) != (
            new.get("frequency"), new.get("source_file")):
        flags.append("METADATA_DRIFT")
    return {
        "changed": bool(flags),
        "flags": flags,
        "checkpoint_latest": old_dates[-1],
        "observed_latest": new_dates[-1],
        "added_periods": added,
        "revised_periods": changed,
        "removed_periods": removed,
    }


def observed_votes(setup):
    votes = {c: {"macro": None, "policy": None} for c in FX}
    for code, row in setup["pairs"].items():
        require(isinstance(code, str) and len(code) == 6,
                "pair name invalid")
        st = row["decision_frame"]["structural"]
        for channel in ("macro", "policy"):
            for c, value in ((code[:3], st[channel]["a"]), (code[3:], st[channel]["b"])):
                require(c in votes and value in (-1, 0, 1) and type(value) is int,
                        c + " invalid " + channel + " vote")
                prior = votes[c][channel]
                require(prior is None or prior == value,
                        c + " conflicting " + channel + " votes across pairs")
                votes[c][channel] = value
    require(all(all(v is not None for v in s.values()) for s in votes.values()),
            "not all G8 qualitative votes present")
    return votes


def build(checkpoint, model, series, heat, registry, rates, ois, setup, today):
    # Full previously certified source/28-pair identity contract.
    lineage = g8_coverage(model, series, heat, registry, rates, ois, setup, today)
    require(lineage["source_lineage"] == "PASS" and
            lineage["structural_rebase"] == "BLOCKED_SCORE_CONTRACT" and
            lineage["safe_to_publish_D"] is False, "source lineage status changed")
    require(checkpoint.get("schema") == SCHEMA and
            checkpoint.get("checkpoint_kind") ==
            "SOURCE_OBSERVATION_CHECKPOINT_NOT_CERTIFIED_D_BASELINE", "checkpoint scope")
    require(checkpoint.get("qualitative_labels_recertified") is False and
            checkpoint.get("macro_scores_recalculated") is False,
            "checkpoint cannot certify model")
    require(checkpoint.get("canonical_model_asof") == model.get("asOf") and
            setup.get("macro_baseline_asof") == model.get("asOf"),
            "historical Macro model baseline was modified; requires independent certification")
    captured = date.fromisoformat(checkpoint["captured_date"])
    require(captured <= today and date.fromisoformat(model["asOf"]) <= captured,
            "checkpoint/date causal order")
    require(set(checkpoint.get("currencies", {})) == set(FX), "checkpoint G8 incomplete")
    assert checkpoint.get("snapshot_counts", {}).get("registered_core") == 16
    assert checkpoint.get("snapshot_counts", {}).get("growth_sources") == 21
    assert checkpoint.get("snapshot_counts", {}).get("pairs") == 28

    actual_votes = observed_votes(setup)
    report = {}
    changed_ccys = set()
    counts = {"CORE": 0, "GROWTH": 0, "RATES": 0, "OIS": 0}
    for c in FX:
        baseline = checkpoint["currencies"][c]
        require(baseline.get("frozen_votes") == actual_votes[c],
                c + ": unapproved qualitative label change in pair feed")
        rows = {r.get("id"): r for r in series[c]}
        require(len(rows) == len(series[c]), c + ": duplicated MACRO_SERIES IDs")
        events = []
        for dim in ("inflation", "labour"):
            target = baseline["core"][dim]
            reg = registry["series"][c + "." + dim]
            expected_id = reg.get("historical_replay_evidence", {}).get("macro_series_id") or \
                (reg["series_id"] + "_history_value")
            require(target["id"] == expected_id and target["source_id"] == reg["series_id"]
                    and target["transform"] == reg["transformation"]
                    and target["frequency"] == reg["frequency"],
                    c + "." + dim + ": frozen registry mapping changed")
            live = rows.get(expected_id)
            require(live is not None, c + "." + dim + ": missing canonical series")
            observed = {
                "id": expected_id, "dates": live["dates"], "values": live["values"],
                "frequency": reg["frequency"],
            }
            delta = history_delta(target, observed)
            thermo = heat["currencies"][c][dim]
            if target["heat_asof"] != thermo["as_of"] or \
               target["heat_value"] != thermo["latest_value"]:
                if "HEATMAP_CHANGED" not in delta["flags"]:
                    delta["flags"].append("HEATMAP_CHANGED")
                    delta["changed"] = True
            if delta["changed"]:
                events.append({"category": "CORE", "dimension": dim,
                               "series_id": expected_id,
                               "checkpoint_heat_asof": target["heat_asof"],
                               "current_heat_asof": thermo["as_of"],
                               **delta})
                counts["CORE"] += 1
        require(set(baseline.get("growth", {})) ==
                {r["id"] for r in series[c] if r.get("category") == "Crescita"
                 and isinstance(r.get("dates"), list) and len(r["dates"]) >= 2
                 and isinstance(r.get("values"), list) and len(r["dates"]) == len(r["values"]) and
                 all(numeric(v) for v in r["values"])},
                c + ": Growth source inventory changed; explicit checkpoint review required")
        for id, old in baseline["growth"].items():
            live = rows.get(id)
            require(live is not None and live.get("category") == "Crescita",
                    c + ": missing Growth source " + id)
            new = {
                "id": id, "dates": live["dates"], "values": live["values"],
                "frequency": live.get("frequency") or "M",
                "source_file": live.get("source_file") or None,
            }
            delta = history_delta(old, new)
            if delta["changed"]:
                events.append({"category": "GROWTH", "series_id": id, **delta})
                counts["GROWTH"] += 1

        r = rates[c]
        before_rate = baseline["rates"]
        current_rate = {
            "date": r["date"], "quality": r["quality"],
            "two_y": r.get("2Y"), "ten_y": r.get("10Y"),
        }
        if before_rate != current_rate:
            events.append({"category": "RATES", "reason": "RATES_SOURCE_SNAPSHOT_CHANGED",
                           "checkpoint": before_rate, "current": current_rate,
                           "official_current": lineage["currencies"][c]["rates_2y_10y"]["official_current"]})
            counts["RATES"] += 1
        pricing = ois["currencies"][c]
        before_ois = baseline["ois"]
        now_ois = {
            "date": pricing["as_of"], "operational": pricing["operational_status"],
            "official_status": pricing["official_status"], "quality": pricing["quality"],
        }
        if before_ois != now_ois:
            events.append({"category": "OIS", "reason": "OIS_SOURCE_STATUS_OR_DATE_CHANGED",
                           "checkpoint": before_ois, "current": now_ois,
                           "official_current": lineage["currencies"][c]["policy_pricing"]["official_current"]})
            counts["OIS"] += 1
        if events:
            changed_ccys.add(c)
        report[c] = {
            "reapproval_needed_since_checkpoint": bool(events),
            "historical_macro_vote": actual_votes[c]["macro"],
            "historical_policy_vote": actual_votes[c]["policy"],
            "current_macro_vote": None,
            "current_policy_vote": None,
            "changed_inputs": events,
            "source_release_timestamp": None,
            "bias_promoted": False,
        }
    impacted = sorted(k for k in setup["pairs"] if k[:3] in changed_ccys or k[3:] in changed_ccys)
    return {
        "schema": RECEIPT,
        "run_as_of": today.isoformat(),
        "checkpoint_as_of": checkpoint["captured_date"],
        "historical_macro_baseline_as_of": model["asOf"],
        "status": "REVIEW_REQUIRED" if changed_ccys else "NO_SOURCE_DELTA_SINCE_CHECKPOINT",
        "source_lineage": "PASS",
        "canonical_macro_baseline_current": (today - date.fromisoformat(model["asOf"])).days <= 10,
        "source_checkpoint_not_historical_PIT": True,
        "source_release_timestamps_not_inferred": True,
        "label_reapproval_not_auto_promotion": True,
        "safe_to_publish_new_D": False,
        "eligible_for_structural_rebase": False,
        "source_change_counts": counts,
        "changed_currencies": sorted(changed_ccys),
        "changed_currencies_count": len(changed_ccys),
        "impacted_pairs": impacted,
        "impacted_pairs_count": len(impacted),
        "observed_currencies_count": 8,
        "observed_pairs_count": 28,
        "frozen_qualitative_votes": 8,
        "currencies": report,
        "unblock_requires": [
            "Versioned economic score and qualitative label calculation",
            "Official source release timestamps proving PIT input availability",
            "CB repricing with verified official date and source",
            "OOS rule fingerprint and independent structural rebase QA",
        ],
    }


def readable(r):
    result = [
        "## Macro → FX: coda di ricertificazione dei giudizi qualitativi",
        "",
        f"**Stato:** {r['status']} · **Baseline D storica:** {r['historical_macro_baseline_as_of']} "
        f"· **Checkpoint fonti:** {r['checkpoint_as_of']}",
        "",
        "| Valuta | Core | Crescita | Tassi | Pricing | Coppie coinvolte |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for c, row in r["currencies"].items():
        ev = row["changed_inputs"]
        count = {k: sum(x["category"] == k for x in ev)
                 for k in ("CORE", "GROWTH", "RATES", "OIS")}
        result.append(f"| {c} | {count['CORE']} | {count['GROWTH']} | {count['RATES']} | "
                      f"{count['OIS']} | {sum(c == x[:3] or c == x[3:] for x in r['impacted_pairs'])} |")
    result += [
        "",
        f"**Nuove verifiche qualitative da aprire:** {r['changed_currencies_count']} valute · "
        f"{r['impacted_pairs_count']} coppie potenzialmente coinvolte.",
        "",
        "**Nessuna nuova direzione Macro/Policy pubblicata.** I dati cambiati "
        "non sono voti, i periodi osservati non certificano l'ora di rilascio "
        "e la baseline D originale resta storica.",
    ]
    return "\n".join(result) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=ROOT)
    p.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    p.add_argument("--asof", default=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat())
    p.add_argument("--out", type=Path)
    p.add_argument("--markdown", type=Path)
    a = p.parse_args()
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    inputs = {key: read(a.repo_root / path) for key, path in PATHS.items()}
    receipt = build(read(a.checkpoint), *(inputs[k] for k in PATHS),
                    date.fromisoformat(a.asof))
    serialized = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(serialized, encoding="utf-8")
    if a.markdown:
        a.markdown.parent.mkdir(parents=True, exist_ok=True)
        a.markdown.write_text(readable(receipt), encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in
                     ("status", "checkpoint_as_of", "historical_macro_baseline_as_of",
                      "source_change_counts", "changed_currencies_count",
                      "impacted_pairs_count", "eligible_for_structural_rebase")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
