#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "validation" / "macro" / "MACRO_SOURCE_REGISTRY_2026-10-08.json"
HEATMAP = ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json"
SERIES = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
BUILDER = ROOT / "validation" / "build_macro_candidate.py"

CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
DIMENSIONS = ("inflation", "labour")
ALLOWED_ADAPTER_STATUS = {
    "READY",
    "NEEDS_SOURCE_ADAPTER",
    "NEEDS_OFFICIAL_DIRECT_TRANSPORT",
    "WITHHELD_NON_OFFICIAL_TRANSPORT",
}
WEAK_TRANSPORT = {"SECONDARY_MIRROR", "INTERMEDIARY_TRANSPORT"}


def load(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fail(message: str) -> None:
    raise ValueError(message)


def main() -> int:
    reg = load(REGISTRY)
    heat = load(HEATMAP)
    macro = load(SERIES)

    if reg.get("schema") != "GMFQ_MACRO_SOURCE_REGISTRY_V1":
        fail("unexpected macro source registry schema")
    if heat.get("schema_version") != "GMFQ_MACRO_HEATMAP_V1":
        fail("unexpected macro heatmap schema")
    if not BUILDER.exists():
        fail("generic macro candidate builder missing")

    expected = {f"{c}.{d}" for c in CURRENCIES for d in DIMENSIONS}
    actual = set(reg.get("series", {}))
    if actual != expected:
        fail(f"registry scope mismatch missing={sorted(expected-actual)} extra={sorted(actual-expected)}")
    if reg.get("scope", {}).get("core_series_count") != len(expected):
        fail("registry core_series_count mismatch")
    if reg.get("candidate_layer", {}).get("status") != "READY":
        fail("generic candidate layer must remain READY")
    if reg.get("candidate_layer", {}).get("writes_live_data") is not False:
        fail("candidate layer must be read-only")
    if reg.get("rules", {}).get("automatic_publication") is not False:
        fail("automatic publication must remain disabled")

    rows = []
    statuses = Counter()
    replay_certified = []
    for key in sorted(expected):
        r = reg["series"][key]
        currency, dimension = key.split(".")
        if r.get("currency") != currency or r.get("dimension") != dimension:
            fail(f"registry identity mismatch for {key}")
        status = r.get("source_adapter_status")
        if status not in ALLOWED_ADAPTER_STATUS:
            fail(f"invalid source_adapter_status for {key}: {status}")

        h = heat.get("currencies", {}).get(currency, {}).get(dimension)
        if not isinstance(h, dict):
            fail(f"heatmap entry missing for {key}")
        for field in ("series_id", "source", "frequency", "transformation"):
            if r.get(field) != h.get(field):
                fail(f"{key} {field} drift registry={r.get(field)!r} heatmap={h.get(field)!r}")
        if not h.get("as_of"):
            fail(f"{key} missing heatmap as_of")
        validation = h.get("validation", {})
        required_validation = ("source", "history", "latest", "transformation")
        if not all(validation.get(x) is True for x in required_validation):
            fail(f"{key} heatmap validation not fully green: {validation}")

        transport = r.get("transport_class")
        if transport == "SECONDARY_MIRROR" and status != "WITHHELD_NON_OFFICIAL_TRANSPORT":
            fail(f"{key} secondary mirror must be WITHHELD")
        if transport == "INTERMEDIARY_TRANSPORT" and status == "READY":
            fail(f"{key} intermediary transport cannot be READY")
        if status == "READY" and transport in WEAK_TRANSPORT:
            fail(f"{key} weak transport cannot be READY")

        if currency not in macro or not isinstance(macro[currency], list) or not macro[currency]:
            fail(f"MACRO_SERIES coverage missing for {currency}")

        statuses[status] += 1
        if r.get("historical_replay_certified"):
            replay_certified.append(key)
        rows.append({
            "key": key,
            "authority": r.get("authority"),
            "transport_class": transport,
            "source_adapter_status": status,
            "historical_replay_certified": bool(r.get("historical_replay_certified")),
            "heatmap_as_of": h.get("as_of"),
            "latest_value": h.get("latest_value"),
        })

    if replay_certified != ["JPY.labour"]:
        fail(f"unexpected replay certification set: {replay_certified}")

    out = {
        "status": "PASS",
        "schema": "GMFQ_MACRO_SOURCE_REGISTRY_AUDIT_V1",
        "core_series": len(rows),
        "candidate_layer_ready": len(rows),
        "source_adapter_status_counts": dict(sorted(statuses.items())),
        "historical_replay_certified": replay_certified,
        "automatic_publication": False,
        "rows": rows,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise
