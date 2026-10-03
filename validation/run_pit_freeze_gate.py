#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "validation/PIT_DATASET_FREEZE_V1_2026-10-03.json"
OUT = ROOT / "validation/PIT_FREEZE_GATE_V1_2026-10-03.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    freeze = load(FREEZE)
    results = []
    hard_failures = []
    for ccy, cfg in freeze["currencies"].items():
        manifest_path = ROOT / cfg["manifest"]
        if not manifest_path.exists():
            hard_failures.append(f"{ccy}: manifest missing: {cfg['manifest']}")
            continue
        manifest = load(manifest_path)
        eligible = manifest.get("eligible_pit_core_now", {})
        growth = eligible.get("growth", [])
        labour = eligible.get("labour", [])
        pending = eligible.get("pending", [])
        withheld = eligible.get("withheld", [])
        if pending:
            hard_failures.append(f"{ccy}: pending series remain: {pending}")
        # Ensure every eligible series is explicitly PIT_READY in the manifest when a series map exists.
        series_map = manifest.get("series", {})
        for sid in list(growth) + list(labour):
            st = series_map.get(sid, {}).get("status")
            if st != "PIT_READY":
                hard_failures.append(f"{ccy}: eligible series {sid} has status {st!r}, expected PIT_READY")
        # No withheld series may appear as eligible.
        overlap = sorted(set(withheld) & (set(growth) | set(labour)))
        if overlap:
            hard_failures.append(f"{ccy}: withheld/eligible overlap: {overlap}")
        results.append({
            "currency": ccy,
            "freeze_status": cfg["status"],
            "growth_eligible": growth,
            "labour_eligible": labour,
            "withheld_count": len(withheld),
            "pending_count": len(pending),
            "macro_replay_mode": (
                "BOTH_BLOCKS" if growth and labour else
                "GROWTH_ONLY" if growth else
                "LABOUR_ONLY" if labour else
                "WITHHELD_NO_MACRO_VOTE"
            )
        })

    payload = {
        "schema": "GMFQ_PIT_FREEZE_GATE_V1",
        "created_at": "2026-10-03",
        "engine_rules_fingerprint": freeze["engine_freeze"]["rules_fingerprint"],
        "dataset_freeze": str(FREEZE.relative_to(ROOT)),
        "hard_failures": hard_failures,
        "passed": not hard_failures,
        "currencies": results,
        "replay_policy": "Only PIT_READY series vote. WITHHELD currencies/blocks stay withheld. No revised-history fallback."
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if hard_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
