#!/usr/bin/env python3
"""Independent source-controlled Quality-Aware Forward V2 verification.

Reads the committed quality-aware journal AFTER the primary Core push.
Can still be GREEN when the distinct original V2 research capture is RED;
never promotes the Quality-Aware cohort to FX predictions, PIT or H1.
No writes to production journals, market feeds, Core or 28 pair states.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.forward.capture_v2_quality_aware_prospective_v1 import (
    JOURNAL, SCHEMA as SNAPSHOT_SCHEMA, read_journal, verify_journal,
)

ROME = ZoneInfo("Europe/Rome")
FIRST_DAY = date(2026, 11, 2)
SCHEMA = "GMFQ_V2_QUALITY_AWARE_PERSISTED_INDEPENDENT_CERTIFICATE_V1"


def audit(*, now, admitted: bool, core_persisted: bool, path=JOURNAL) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("An actual timezone-aware verification instant is required")
    rome = now.astimezone(ROME)
    day = rome.date()
    base = {
        "schema": SCHEMA, "checked_at_utc": now.astimezone(timezone.utc).isoformat(),
        "local_date_rome": day.isoformat(),
        "quality_aware_cohort_certified": False,
        "original_V2_success_not_required": True,
        "original_V2_failure_not_masked": True,
        "can_promote_D_or_28_pairs": False,
        "can_validate_H1_or_FX_predictive_skill": False,
        "source_controlled_journal_verified": False,
    }
    if day < FIRST_DAY or rome.weekday() >= 5 or rome.hour < 19:
        return {**base, "status": "OUTSIDE_FUTURE_QUALITY_AWARE_CUTOFF_NO_CLAIM"}
    if not admitted:
        return {**base, "status": "NO_OFFICIAL_T0_ADMISSION_NO_CAPTURE_CLAIM"}
    if not core_persisted:
        return {**base, "status": "BLOCKED_PRIMARY_CORE_PERSISTENCE_NOT_CERTIFIED"}
    if not Path(path).is_file():
        return {**base, "status": "BLOCKED_QUALITY_AWARE_JOURNAL_NOT_IN_MAIN"}
    try:
        rows = read_journal(Path(path))
        dates = verify_journal(rows)  # all dates, signatures, 24+28, no duplicates
        today = [r for r in rows if r.get("local_date_rome") == day.isoformat()]
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeError, OverflowError):
        return {**base, "status": "BLOCKED_QUALITY_AWARE_JOURNAL_INTEGRITY"}
    if day.isoformat() not in dates or len(today) != 1:
        return {**base, "status": "BLOCKED_QUALITY_AWARE_TODAY_NOT_DURABLE"}
    row = today[0]
    if (row.get("schema") != SNAPSHOT_SCHEMA
            or row.get("official_ecb_t0_date") != day.isoformat()
            or len(row.get("observed_t0_ref", {})) != 28
            or len(row.get("economic_observations", {})) != 8
            or row.get("numeric_z_imputation_count") != 0
            or row.get("V2_FX_signal_computed") is not False
            or row.get("can_feed_preregistered_H1") is not False):
        return {**base, "status": "BLOCKED_QUALITY_AWARE_CURRENT_COHORT_CONTRACT"}
    return {
        **base, "status": "QUALITY_AWARE_DURABLE_RESEARCH_COHORT_CERTIFIED",
        "quality_aware_cohort_certified": True,
        "source_controlled_journal_verified": True,
        "snapshot_id": row["snapshot_id"],
        "snapshot_sha256": row["snapshot_sha256"],
        "official_ecb_t0_date": row["official_ecb_t0_date"],
        "economic_dimensions": 24,
        "fx_reference_pairs": 28,
        "missing_research_z_count": row["strict_robust_z_missing_count"],
        "original_V2_numeric_candidate_certified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admitted", choices=("true", "false"), required=True)
    parser.add_argument("--core-persisted", choices=("true", "false"), required=True)
    parser.add_argument("--journal", type=Path, default=JOURNAL)
    args = parser.parse_args()
    result = audit(now=datetime.now(timezone.utc),
                   admitted=args.admitted == "true",
                   core_persisted=args.core_persisted == "true",
                   path=args.journal)
    print(json.dumps(result, sort_keys=True))
    # "Not yet eligible"/"no T0" is informational, never a false green
    # certification. An admitted but missing/corrupt record fails closed.
    return 2 if result["status"].startswith("BLOCKED_") else 0


if __name__ == "__main__":
    raise SystemExit(main())
