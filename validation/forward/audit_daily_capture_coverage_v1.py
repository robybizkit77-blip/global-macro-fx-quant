#!/usr/bin/env python3
"""Independent same-session Forward capture coverage audit (no model changes).

Run by the EXISTING ECB reference observer after its 21:15 Rome cutoff.
GREEN means a complete frozen-Core batch AND a separately integrity-checked
Quality-Aware observation are durable; it never means predictive skill.
No trades, artificial T0, calendar backfill, or model scores are generated.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.forward.admit_frozen_core_prospective_capture_v1 import (
    ROOT, FX, PAIR, CORE, assess
)
from validation.forward.log_core_decision_v1 import DECISIONS
from validation.forward.check_append_only_snapshots_gate_v1 import (
    inspect as inspect_core, utc as parse_utc
)
from validation.forward.capture_v2_quality_aware_prospective_v1 import (
    JOURNAL as QUALITY_JOURNAL, read_journal, verify_journal
)

ROME = ZoneInfo("Europe/Rome")
SCHEMA = "GMFQ_FORWARD_DAILY_COVERAGE_INDEPENDENT_AUDIT_V1"
START = date(2026, 11, 4)
ISSUE_PREFIXES = ("BLOCKED_",)


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()
            if s.strip()]


def audit(now: datetime, fx: dict, pair: dict, core: dict,
          core_rows: list[dict], quality_rows: list[dict]) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Actual timezone-aware audit time required")
    current = now.astimezone(ROME)
    day = current.date().isoformat()
    report = {
        "schema": SCHEMA,
        "as_of_utc": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "local_date_rome": day,
        "no_synthetic_fx_or_backfill": True,
        "does_not_validate_predictive_skill": True,
        "core_recomputed": False,
        "quality_aware_new_signals": False,
        "original_v2_numeric_certified": False,
        "official_price_as_of": fx.get("last_as_of"),
        "pair_setup_price_as_of": pair.get("price_asof"),
    }
    if (current.date() < START or current.weekday() >= 5
            or current.hour < 21 or (current.hour == 21 and current.minute < 15)):
        return {**report, "status": "OUTSIDE_2115_ROME_DAILY_ATTESTATION_WINDOW",
                "certified_daily_capture": False, "blocks_workflow": False}

    source = assess(now, fx, pair, core)
    failures = source["checks"]
    report["admission_checks"] = failures
    # Not enough evidence to label a missing official T0 as an ECB holiday:
    # it can also be a publication/ingestion delay or source outage.
    if "ECB_CURRENT_DAY_FIXING_NOT_PRESENT" in failures:
        return {**report, "status": "OFFICIAL_T0_NOT_CURRENT_REASON_UNDETERMINED",
                "certified_daily_capture": False, "blocks_workflow": False,
                "requires_source_review": True}
    if failures:
        name = ("BLOCKED_ECB_SOURCE_INTEGRITY" if
                ("ECB_OFFICIAL_ROW_INTEGRITY_FAILED" in failures or
                 "ECB_SOURCE_NOT_OFFICIAL_HISTORY" in failures)
                else "BLOCKED_PRICE_HANDOFF_OR_ADMISSION_CONTRACT")
        return {**report, "status": name, "certified_daily_capture": False,
                "blocks_workflow": True}

    # All source gates passed. Validate BOTH entire immutable journals
    # (including previous days) rather than trusting a job's green status.
    try:
        inspected = inspect_core(core_rows)
        certified_dates = verify_journal(quality_rows)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeError,
            OverflowError, AttributeError) as exc:
        return {**report, "status": "BLOCKED_FORWARD_JOURNAL_INTEGRITY",
                "certified_daily_capture": False, "blocks_workflow": True,
                "integrity_error_type": type(exc).__name__}

    core_today = [
        t for t in inspected["cutoffs"]
        if parse_utc(t).astimezone(ROME).date() == current.date()
    ]
    qa_today = [x for x in quality_rows if x.get("local_date_rome") == day]
    report["complete_core_28_pair_batches_today"] = len(core_today)
    report["verified_quality_aware_snapshots_today"] = len(qa_today)
    report["quality_aware_date_found_in_verified_journal"] = day in certified_dates

    if len(core_today) != 1:
        return {**report, "status": "BLOCKED_CORE_28_PAIR_BATCH_MISSING_OR_DUPLICATED",
                "certified_daily_capture": False, "blocks_workflow": True}
    if len(qa_today) != 1 or day not in certified_dates:
        return {**report, "status": "BLOCKED_QUALITY_AWARE_SNAPSHOT_MISSING_OR_DUPLICATED",
                "certified_daily_capture": False, "blocks_workflow": True}
    return {
        **report, "status": "DAILY_CORE_AND_QUALITY_AWARE_DURABLE",
        "certified_daily_capture": True, "blocks_workflow": False,
        "core_decision_cutoff": core_today[0],
        "quality_aware_snapshot_id": qa_today[0]["snapshot_id"],
        "quality_aware_reference_pairs": 28,
        "quality_aware_economic_dimensions": 24,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--enforce", action="store_true",
                   help="Fail existing daily observer only for missing eligible captures")
    args = p.parse_args()
    if not args.receipt.resolve().is_relative_to(Path("/tmp")):
        p.error("Daily coverage receipt must remain in /tmp")
    checked = audit(
        datetime.now(timezone.utc),
        json.loads(FX.read_text(encoding="utf-8")),
        json.loads(PAIR.read_text(encoding="utf-8")),
        json.loads(CORE.read_text(encoding="utf-8")),
        read_jsonl(DECISIONS),
        read_journal(QUALITY_JOURNAL),
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(checked, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    print(json.dumps(checked, sort_keys=True))
    return 2 if args.enforce and checked.get("blocks_workflow") else 0


if __name__ == "__main__":
    raise SystemExit(main())
