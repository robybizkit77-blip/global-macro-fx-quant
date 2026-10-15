from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "payload"
INDEX = ROOT / "index.html"
TOKENS = [
    "REAL_CALENDAR",
    "NEWS_PULSE_STRUCT",
    "AUXILIARY_FEED_FRESHNESS",
    "LIVE_REFRESH_20260930_AM",
    "GMFQ_PROPAGATION_QA",
    "GMFQ_E2E_LIVE_ITALY",
    "gmfq-runtime-refresh-fix-20260930",
    "renderRealCalendar",
    "renderNewsPulse",
    "2026-09-30",
]
QUARANTINED_IDS = [
    "gmfq-propagation-qa",
    "gmfq-e2e-live-italy",
    "gmfq-runtime-refresh-fix-20260930",
]


def combined_payload() -> str:
    return "\n".join(p.read_text(errors="replace") for p in sorted(PAYLOAD.glob("part-*.txt")))


def strip_quarantined(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    out = text
    for script_id in QUARANTINED_IDS:
        pattern = re.compile(
            rf'<script\s+id=["\']{re.escape(script_id)}["\'][^>]*>[\s\S]*?</script>',
            re.IGNORECASE,
        )
        matches = pattern.findall(out)
        counts[script_id] = len(matches)
        assert len(matches) == 1, (script_id, len(matches))
        out = pattern.sub(f"<!-- GMFQ_LEGACY_QUARANTINED:{script_id} -->", out)
    return out, counts


def token_counts(text: str) -> dict[str, int]:
    return {token: text.count(token) for token in TOKENS}


def main() -> None:
    raw = combined_payload()
    runtime_equivalent, quarantine_counts = strip_quarantined(raw)
    raw_counts = token_counts(raw)
    runtime_counts = token_counts(runtime_equivalent)
    removed_counts = {k: raw_counts[k] - runtime_counts[k] for k in TOKENS}

    index = INDEX.read_text(errors="replace")
    for script_id in QUARANTINED_IDS:
        assert f"'{script_id}'" in index, script_id
    assert "GMFQ_LEGACY_QUARANTINED:" in index

    # The three stale QA/mutator authorities must be completely absent from the
    # runtime-equivalent payload after applying the production quarantine.
    assert runtime_counts["GMFQ_PROPAGATION_QA"] == 0, runtime_counts
    assert runtime_counts["GMFQ_E2E_LIVE_ITALY"] == 0, runtime_counts
    assert runtime_counts["gmfq-runtime-refresh-fix-20260930"] == 0, runtime_counts

    remaining = {
        k: v
        for k, v in runtime_counts.items()
        if v > 0
        and k not in {
            "GMFQ_PROPAGATION_QA",
            "GMFQ_E2E_LIVE_ITALY",
            "gmfq-runtime-refresh-fix-20260930",
        }
    }
    deletion_allowed = not any(
        runtime_counts[k] > 0
        for k in (
            "REAL_CALENDAR",
            "NEWS_PULSE_STRUCT",
            "renderRealCalendar",
            "renderNewsPulse",
            "LIVE_REFRESH_20260930_AM",
            "2026-09-30",
        )
    )

    out = {
        "status": "PASS_RUNTIME_QUARANTINE_ACCOUNTED",
        "schema": "GMFQ_CALENDAR_NEWS_LEGACY_DEPENDENCY_AUDIT_V2",
        "raw_source_counts": raw_counts,
        "runtime_equivalent_counts": runtime_counts,
        "removed_from_runtime_counts": removed_counts,
        "quarantined_script_instances": quarantine_counts,
        "remaining_runtime_legacy": remaining,
        "migration_policy": {
            "visible_owner": "DYNAMIC_OPERATIONAL_MODULES",
            "legacy_payload_source_retained": True,
            "three_stale_mutators_runtime_quarantined": True,
            "physical_deletion_allowed_now": deletion_allowed,
            "next_step": (
                "PHYSICAL_REMOVAL_CAN_BE_PLANNED"
                if deletion_allowed
                else "MIGRATE_REMAINING_RUNTIME_COMPATIBILITY_CONSUMERS"
            ),
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
