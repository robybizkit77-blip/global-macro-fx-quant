from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
PAYLOAD = ROOT / "payload"
IDS = [
    "gmfq-propagation-qa",
    "gmfq-e2e-live-italy",
    "gmfq-runtime-refresh-fix-20260930",
]


def main() -> None:
    index = INDEX.read_text(errors="replace")
    payload = "\n".join(p.read_text(errors="replace") for p in sorted(PAYLOAD.glob("part-*.txt")))

    assert "Runtime quarantine V1" in index
    assert "GMFQ_LEGACY_QUARANTINED:" in index
    assert "matches.length!==1" in index

    counts = {}
    for script_id in IDS:
        marker = f'id="{script_id}"'
        counts[script_id] = payload.count(marker)
        assert counts[script_id] == 1, (script_id, counts[script_id])
        assert f"'{script_id}'" in index, script_id

    # The legacy source remains auditable/rollback-safe, but execution must be
    # removed from the assembled HTML before document.write().
    qpos = index.index("const quarantinedLegacyScripts")
    wpos = index.index("document.write(html)")
    assert qpos < wpos

    print({
        "status": "PASS",
        "schema": "GMFQ_LEGACY_RUNTIME_QUARANTINE_V1",
        "quarantined": IDS,
        "payload_source_counts": counts,
        "payload_deleted": False,
        "runtime_execution": "BLOCKED_BEFORE_DOCUMENT_WRITE",
    })


if __name__ == "__main__":
    main()
