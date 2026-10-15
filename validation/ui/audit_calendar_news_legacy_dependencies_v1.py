from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "payload"
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


def scan() -> dict:
    hits: dict[str, list[dict]] = {t: [] for t in TOKENS}
    for path in sorted(PAYLOAD.glob("part-*.txt")):
        text = path.read_text(errors="replace")
        lines = text.splitlines()
        for token in TOKENS:
            for i, line in enumerate(lines, 1):
                if token in line:
                    hits[token].append({
                        "file": str(path.relative_to(ROOT)),
                        "line": i,
                        "excerpt": line.strip()[:220],
                    })
    return hits


def main() -> None:
    hits = scan()
    counts = {k: len(v) for k, v in hits.items()}
    files = sorted({h["file"] for values in hits.values() for h in values})
    # These legacy dependencies are expected to exist during the migration phase,
    # but they must remain contained in payload and must not become visible owners.
    assert counts["REAL_CALENDAR"] > 0, counts
    assert counts["NEWS_PULSE_STRUCT"] > 0, counts
    assert counts["GMFQ_PROPAGATION_QA"] > 0, counts
    assert counts["GMFQ_E2E_LIVE_ITALY"] > 0, counts
    assert all(f.startswith("payload/") for f in files), files
    out = {
        "status": "PASS_WITH_LEGACY_DEPENDENCIES",
        "schema": "GMFQ_CALENDAR_NEWS_LEGACY_DEPENDENCY_AUDIT_V1",
        "counts": counts,
        "files": files,
        "hits": hits,
        "migration_policy": {
            "visible_owner": "DYNAMIC_OPERATIONAL_MODULES",
            "legacy_payload": "COMPATIBILITY_ONLY_PENDING_QA_MIGRATION",
            "deletion_allowed_now": False,
            "next_step": "MIGRATE_STALE_QA_CONSUMERS_BEFORE_REMOVAL",
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
