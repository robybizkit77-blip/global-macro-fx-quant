#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "validation" / "macro_source_registry.json"

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]
DIMENSIONS = ["inflation", "labour"]
EXPECTED = {(c, d) for c in CURRENCIES for d in DIMENSIONS}
VALID_STATUS = {
    "PLANNED_UNVALIDATED",
    "SOURCE_IDENTIFIED_UNVALIDATED",
    "ADAPTER_READY_LIVE_CI_PENDING",
    "ADAPTER_READY_CREDENTIAL_REQUIRED",
    "VALIDATED",
}


def fail(msg: str) -> None:
    raise SystemExit(f"REGISTRY_FAIL: {msg}")


def main() -> int:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    policies = data.get("policies", {})
    streams = data.get("streams")
    if not isinstance(streams, list):
        fail("streams must be a list")
    if policies.get("expected_core_streams") != 16:
        fail("expected_core_streams must be 16")
    if policies.get("allow_silent_fallback") is not False:
        fail("silent fallback must remain disabled")
    if policies.get("allow_unvalidated_series_ids") is not False:
        fail("unvalidated series IDs must remain disabled")
    if policies.get("live_write_from_source_adapter") is not False:
        fail("source adapters must remain read-only")

    seen: set[tuple[str, str]] = set()
    ready = 0
    validated = 0
    planned = 0
    identified = 0

    for i, row in enumerate(streams):
        if not isinstance(row, dict):
            fail(f"stream[{i}] is not an object")
        key = (row.get("currency"), row.get("dimension"))
        if key not in EXPECTED:
            fail(f"unexpected stream key {key!r}")
        if key in seen:
            fail(f"duplicate stream key {key!r}")
        seen.add(key)
        if row.get("role") != "core":
            fail(f"{key}: role must be core")
        if row.get("frequency") != "M":
            fail(f"{key}: core stream frequency must be monthly in registry v1")
        status = row.get("status")
        if status not in VALID_STATUS:
            fail(f"{key}: invalid status {status!r}")
        if not row.get("official_authority"):
            fail(f"{key}: official authority is required")

        upstream = row.get("upstream_series_id")
        adapter = row.get("adapter_path")
        source_url = row.get("source_url")
        transformation = row.get("transformation")
        unit = row.get("unit")

        if status == "PLANNED_UNVALIDATED":
            planned += 1
            if upstream is not None or adapter is not None:
                fail(f"{key}: planned-unvalidated stream must not claim upstream ID or adapter")
        elif status == "SOURCE_IDENTIFIED_UNVALIDATED":
            identified += 1
            if not all([upstream, source_url, transformation, unit]):
                fail(f"{key}: source-identified stream must have source metadata")
            if adapter is not None:
                fail(f"{key}: source-identified stream must not claim an adapter yet")
        else:
            ready += 1
            if not all([upstream, adapter, source_url, transformation, unit]):
                fail(f"{key}: adapter-ready/validated stream is missing required source metadata")
            adapter_path = ROOT / str(adapter)
            if not adapter_path.exists():
                fail(f"{key}: adapter path does not exist: {adapter}")

        if status == "ADAPTER_READY_CREDENTIAL_REQUIRED":
            if row.get("requires_credential") is not True or not row.get("credential_env"):
                fail(f"{key}: credential-required stream must name its environment variable")
        if status == "ADAPTER_READY_LIVE_CI_PENDING" and row.get("requires_credential") is not False:
            fail(f"{key}: no-auth CI-pending stream must explicitly set requires_credential=false")
        if status == "VALIDATED":
            validated += 1

    missing = EXPECTED - seen
    extra = seen - EXPECTED
    if missing or extra:
        fail(f"registry coverage mismatch: missing={sorted(missing)} extra={sorted(extra)}")
    if len(streams) != 16:
        fail(f"registry must contain exactly 16 core streams; got {len(streams)}")

    summary = {
        "status": "PASS",
        "schema_version": data.get("schema_version"),
        "streams": len(streams),
        "adapter_ready_or_validated": ready,
        "source_identified_unvalidated": identified,
        "validated": validated,
        "planned_unvalidated": planned,
        "coverage": "8 currencies x 2 core dimensions",
        "live_write_from_source_adapter": False,
        "silent_fallback": False,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
