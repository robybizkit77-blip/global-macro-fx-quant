#!/usr/bin/env python3
"""Read-only bridge from a registered official macro adapter to a PIT candidate.

The bridge deliberately produces only an ephemeral candidate and audit receipt.
It never invokes an apply/publish command and it rejects anything outside the
frozen 8 x 2 core registry.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json"
SERIES = ROOT / "live_data/sections/MACRO_SERIES.json"
HEAT = ROOT / "live_data/sections/MACRO_THERMOMETER_DATA.json"


def load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git_head() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def registered_target(currency: str, dimension: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    registry = load(REGISTRY)
    scope = registry.get("scope", {})
    if scope.get("core_series_count") != 16:
        raise ValueError("registry core-series scope is not frozen at 16")
    key = f"{currency}.{dimension}"
    entry = registry.get("series", {}).get(key)
    if not isinstance(entry, dict) or entry.get("source_adapter_status") != "READY":
        raise ValueError(f"{key} is not a READY core source adapter")
    if currency not in scope.get("currencies", []) or dimension not in scope.get("dimensions", []):
        raise ValueError(f"{key} lies outside the core registry scope")

    # A certified direct adapter supersedes a mirror/intermediary named on the
    # legacy entry.  Never silently route through the legacy transport.
    certified = entry.get("certified_adapter")
    if certified:
        if certified.get("transport_class") != "OFFICIAL_DIRECT" or not certified.get("read_only"):
            raise ValueError(f"{key} certified adapter is not direct/read-only")
        adapter = certified.get("adapter")
        transport = certified.get("transport_class")
    else:
        adapter = entry.get("adapter")
        transport = entry.get("transport_class")
    if not isinstance(adapter, str) or not adapter.startswith("validation/sources/"):
        raise ValueError(f"{key} has no approved source adapter")

    series, heat = load(SERIES), load(HEAT)
    h = heat["currencies"][currency][dimension]
    hits = [r for r in series[currency] if r.get("id") == f"{entry['series_id']}_history_value"]
    if len(hits) != 1:
        raise ValueError(f"{key} does not map to exactly one canonical MACRO_SERIES row")
    if (h.get("series_id"), h.get("frequency"), h.get("transformation")) != (
        entry["series_id"], entry["frequency"], entry["transformation"],
    ):
        raise ValueError(f"{key} runtime contract differs from frozen registry")
    return entry, {"adapter": adapter, "transport": transport}, hits[0]["id"]


def adapter_command(adapter: pathlib.Path, currency: str, dimension: str, fixture: pathlib.Path | None, work: pathlib.Path) -> tuple[list[str], pathlib.Path, pathlib.Path]:
    """Translate a registered target into its adapter's actual CLI contract.

    Source adapters pre-date this bridge and do not share one CLI.  Keep that
    difference here instead of teaching an official source adapter bridge-only
    flags.  The dispatch is deliberately keyed by target, so an adapter cannot
    accidentally be invoked for a dimension it does not implement.
    """
    raw = work / "adapter-candidate.json"
    audit = work / "adapter-audit.json"
    cmd = [sys.executable, str(adapter)]
    target = (currency, dimension)
    if adapter.name == "us_bls_core_macro.py":
        out_dir = work / "bls"
        cmd += ["--output-dir", str(out_dir)]
        if fixture:
            cmd += ["--fixture", str(fixture)]
        return cmd, out_dir / f"{dimension}-candidate.json", out_dir / "source-audit.json"
    # These official Japanese adapters each represent one fixed target and do
    # not accept --dimension.  Passing the generic flag was the original
    # bridge failure for JPY.labour.
    if target == ("JPY", "labour") and adapter.name == "jpy_estat_unemployment.py":
        cmd += ["--output", str(raw), "--audit-output", str(audit)]
    elif target == ("JPY", "inflation") and adapter.name == "jpy_statistics_bureau_cpi.py":
        cmd += ["--output", str(raw), "--audit-output", str(audit)]
    else:
        cmd += ["--dimension", dimension, "--output", str(raw), "--audit-output", str(audit)]
    if fixture:
        cmd += ["--fixture", str(fixture)]
    return cmd, raw, audit


def run_adapter(adapter: pathlib.Path, currency: str, dimension: str, fixture: pathlib.Path | None, work: pathlib.Path) -> tuple[dict[str, Any], dict[str, Any]]:
    cmd, raw, audit = adapter_command(adapter, currency, dimension, fixture, work)
    subprocess.run(cmd, cwd=ROOT, check=True)
    if not raw.is_file() or not audit.is_file():
        raise ValueError("adapter did not produce both candidate and audit")
    candidate, adapter_audit = load(raw), load(audit)
    if adapter_audit.get("candidate_only") is not True or adapter_audit.get("live_data_written") is not False:
        raise ValueError("adapter audit is not candidate-only/read-only")
    return candidate, adapter_audit


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a normalized, read-only macro PIT candidate from a registered adapter")
    ap.add_argument("--currency", required=True)
    ap.add_argument("--dimension", required=True, choices=("inflation", "labour"))
    ap.add_argument("--output", required=True, type=pathlib.Path)
    ap.add_argument("--audit-output", required=True, type=pathlib.Path)
    ap.add_argument("--fixture", type=pathlib.Path, help="Optional official-format fixture; validates the handoff without a live claim")
    args = ap.parse_args()
    currency = args.currency.upper()
    entry, route, expected_series = registered_target(currency, args.dimension)
    fixture = args.fixture.resolve() if args.fixture else None
    if fixture and not fixture.is_file():
        raise ValueError(f"fixture missing: {fixture}")
    work = args.output.parent / ".adapter-pit-work"
    work.mkdir(parents=True, exist_ok=True)
    raw, adapter_audit = run_adapter(ROOT / route["adapter"], currency, args.dimension, fixture, work)

    required = ("currency", "dimension", "macro_series_id", "observation_date", "value", "source", "series_id", "frequency", "transformation")
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"adapter candidate missing fields: {missing}")
    expected = {"currency": currency, "dimension": args.dimension, "macro_series_id": expected_series,
                "series_id": entry["series_id"], "frequency": entry["frequency"], "transformation": entry["transformation"]}
    actual = {key: raw.get(key) for key in expected}
    if actual != expected:
        raise ValueError(f"adapter candidate target mismatch: expected={expected} actual={actual}")

    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    provenance = {
        "authority": entry["authority"], "source": raw["source"], "transport": route["transport"],
        "adapter": route["adapter"], "adapter_mode": "fixture" if fixture else "live",
        "retrieved_at": retrieved_at, "head_sha": git_head(), "source_url": raw.get("source_url") or adapter_audit.get("source_url"),
        "adapter_audit": adapter_audit,
    }
    normalized = dict(raw)
    normalized.update({"authority": entry["authority"], "transport": route["transport"], "retrieved_at": retrieved_at,
                       "head_sha": provenance["head_sha"], "provenance": provenance,
                       "candidate_only": True, "live_data_written": False, "registry_promotion": "NOT_ATTEMPTED"})
    receipt = {"schema": "GMFQ_MACRO_ADAPTER_PIT_HANDOFF_V1", "status": "PASS", "target": expected,
               "candidate_only": True, "live_data_written": False, "registry_promotion": "NOT_ATTEMPTED",
               "adapter_route": route, "mode": provenance["adapter_mode"], "provenance": provenance}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.audit_output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
