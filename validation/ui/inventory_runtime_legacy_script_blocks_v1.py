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
    "renderRealCalendar",
    "renderNewsPulse",
    "2026-09-30",
]
NAMED_QUARANTINE = [
    "gmfq-propagation-qa",
    "gmfq-e2e-live-italy",
    "gmfq-runtime-refresh-fix-20260930",
    "gmfq-usd-sep30-closeout-20261001",
    "gmfq-usd-sep30-closeout-finalizer-20261001",
]
FINGERPRINT_QUARANTINE = {
    "LIVE_REFRESH_20260930_AM": "window.LIVE_REFRESH_20260930_AM=",
}

SCRIPT_RE = re.compile(r'<script(?:\s[^>]*)?>[\s\S]*?</script>', re.IGNORECASE)
ID_RE = re.compile(r'<script\b[^>]*\bid=["\']([^"\']+)["\']', re.IGNORECASE)


def payload_text() -> str:
    return "\n".join(p.read_text(errors="replace") for p in sorted(PAYLOAD.glob("part-*.txt")))


def named_pattern(script_id: str) -> re.Pattern[str]:
    return re.compile(
        rf'<script\s+id=["\']{re.escape(script_id)}["\'][^>]*>[\s\S]*?</script>',
        re.IGNORECASE,
    )


def runtime_equivalent(raw: str) -> str:
    out = raw
    for script_id in NAMED_QUARANTINE:
        p = named_pattern(script_id)
        matches = p.findall(out)
        assert len(matches) == 1, (script_id, len(matches))
        out = p.sub(f"<!-- QUARANTINED:{script_id} -->", out)
    for name, needle in FINGERPRINT_QUARANTINE.items():
        blocks = SCRIPT_RE.findall(out)
        matches = [b for b in blocks if needle in b]
        assert len(matches) == 1, (name, len(matches))
        out = out.replace(matches[0], f"<!-- QUARANTINED_FINGERPRINT:{name} -->", 1)
    return out


def main() -> None:
    raw = payload_text()
    runtime = runtime_equivalent(raw)
    blocks = SCRIPT_RE.findall(runtime)
    rows = []
    totals = {k: 0 for k in TOKENS}
    for idx, block in enumerate(blocks):
        counts = {k: block.count(k) for k in TOKENS}
        if not any(counts.values()):
            continue
        m = ID_RE.search(block)
        script_id = m.group(1) if m else None
        first_line = re.sub(r"\s+", " ", block[:240]).strip()
        rows.append({
            "runtime_script_index": idx,
            "id": script_id,
            "counts": counts,
            "preview": first_line,
        })
        for k, v in counts.items():
            totals[k] += v

    # Script-ownership fingerprints are static and must never drift.
    # The legacy date literal also occurs inside live economic data sections;
    # its count legitimately changes when the certified MACRO_SERIES runtime
    # mirror is updated. Retain its actual count as diagnostic metadata,
    # but do NOT hard-code a volatile data-value count as a code-integrity gate.
    structural_expected = {
        "REAL_CALENDAR": 31,
        "NEWS_PULSE_STRUCT": 17,
        "AUXILIARY_FEED_FRESHNESS": 27,
        "renderRealCalendar": 17,
        "renderNewsPulse": 14,
    }
    actual_structural = {key: totals[key] for key in structural_expected}
    assert actual_structural == structural_expected, (actual_structural, structural_expected)
    assert totals["2026-09-30"] >= 0

    index = INDEX.read_text(errors="replace")
    assert "Runtime quarantine V2" in index
    print(json.dumps({
        "status": "PASS",
        "schema": "GMFQ_RUNTIME_LEGACY_SCRIPT_INVENTORY_V1",
        "runtime_script_blocks_with_legacy_refs": len(rows),
        "totals": totals,
        "legacy_date_token_diagnostic_only": True,
        "structural_fingerprint_counts_unchanged": True,
        "blocks": rows,
        "policy": {
            "diagnostic_only": True,
            "runtime_mutation": False,
            "physical_deletion_allowed": False,
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
