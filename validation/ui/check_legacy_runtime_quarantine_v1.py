from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
PAYLOAD = ROOT / "payload"
IDS = [
    "gmfq-propagation-qa",
    "gmfq-e2e-live-italy",
    "gmfq-runtime-refresh-fix-20260930",
    "gmfq-usd-sep30-closeout-20261001",
    "gmfq-usd-sep30-closeout-finalizer-20261001",
]
FINGERPRINTS = {
    "LIVE_REFRESH_20260930_AM": "window.LIVE_REFRESH_20260930_AM=",
}


def main() -> None:
    index = INDEX.read_text(errors="replace")
    payload = "\n".join(p.read_text(errors="replace") for p in sorted(PAYLOAD.glob("part-*.txt")))

    assert "Runtime quarantine V2" in index
    assert "GMFQ_LEGACY_QUARANTINED:" in index
    assert "GMFQ_LEGACY_QUARANTINED_FINGERPRINT:" in index
    assert "matches.length!==1" in index

    counts = {}
    for script_id in IDS:
        marker = f'id="{script_id}"'
        counts[script_id] = payload.count(marker)
        assert counts[script_id] == 1, (script_id, counts[script_id])
        assert f"'{script_id}'" in index, script_id

    fingerprint_counts = {}
    for name, needle in FINGERPRINTS.items():
        fingerprint_counts[name] = payload.count(needle)
        assert fingerprint_counts[name] == 1, (name, fingerprint_counts[name])
        assert needle in index, name

    # Legacy source remains auditable/rollback-safe, but quarantine executes before document.write().
    qpos = index.index("const quarantinedLegacyScripts")
    fpos = index.index("const quarantinedLegacyFingerprints")
    wpos = index.index("document.write(html)")
    assert qpos < fpos < wpos

    print({
        "status": "PASS",
        "schema": "GMFQ_LEGACY_RUNTIME_QUARANTINE_V2",
        "quarantined_named": IDS,
        "quarantined_fingerprints": list(FINGERPRINTS),
        "payload_named_source_counts": counts,
        "payload_fingerprint_counts": fingerprint_counts,
        "payload_deleted": False,
        "runtime_execution": "BLOCKED_BEFORE_DOCUMENT_WRITE",
    })


if __name__ == "__main__":
    main()
