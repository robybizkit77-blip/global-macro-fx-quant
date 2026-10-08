#!/usr/bin/env python3
"""Fixture-only contract test for the adapter -> normalized candidate bridge."""
from __future__ import annotations
import json, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
HELPER = ROOT / "validation/macro_adapter_pit_handoff.py"
FIXTURE = ROOT / "validation/fixtures/jpy_estat_unemployment_2026-08.json"

# Import the bridge without running its CLI: regression coverage for the
# target-specific wrapper that protects fixed-target adapters from generic
# flags they do not support.
sys.path.insert(0, str(ROOT / "validation"))
import macro_adapter_pit_handoff as handoff

with tempfile.TemporaryDirectory(prefix="gmfq-adapter-cli-") as tmp:
    cmd, raw, audit = handoff.adapter_command(
        ROOT / "validation/sources/jpy_estat_unemployment.py", "JPY", "labour", FIXTURE, pathlib.Path(tmp)
    )
    assert "--dimension" not in cmd, cmd
    assert "--output" in cmd and "--audit-output" in cmd and "--fixture" in cmd, cmd
    assert raw.parent == audit.parent == pathlib.Path(tmp), (raw, audit)

with tempfile.TemporaryDirectory(prefix="gmfq-adapter-pit-") as tmp:
    tmp = pathlib.Path(tmp); candidate = tmp / "candidate.json"; audit = tmp / "audit.json"
    subprocess.run([sys.executable, str(HELPER), "--currency", "JPY", "--dimension", "labour", "--fixture", str(FIXTURE), "--output", str(candidate), "--audit-output", str(audit)], cwd=ROOT, check=True)
    c, a = json.loads(candidate.read_text()), json.loads(audit.read_text())
    assert c["authority"] == "Statistics Bureau of Japan" and c["transport"] == "OFFICIAL_DIRECT", c
    assert c["macro_series_id"] == "JP_UNEMP_RATE_history_value" and c["candidate_only"] is True, c
    assert a["status"] == "PASS" and a["registry_promotion"] == "NOT_ATTEMPTED" and a["mode"] == "fixture", a
    # The bridge must create output parents itself; callers need not pre-create
    # the requested handoff directory.
    assert candidate.is_file() and audit.is_file(), (candidate, audit)
print(json.dumps({"status":"PASS","fixture_handoff":True,"live_data_written":False,"registry_promotion":"NOT_ATTEMPTED"}))
