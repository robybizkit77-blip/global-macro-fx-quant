#!/usr/bin/env python3
"""Fixture-only contract test for the adapter -> normalized candidate bridge."""
from __future__ import annotations
import json, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
HELPER = ROOT / "validation/macro_adapter_pit_handoff.py"
FIXTURE = ROOT / "validation/fixtures/jpy_estat_unemployment_2026-08.json"

with tempfile.TemporaryDirectory(prefix="gmfq-adapter-pit-") as tmp:
    tmp = pathlib.Path(tmp); candidate = tmp / "candidate.json"; audit = tmp / "audit.json"
    subprocess.run([sys.executable, str(HELPER), "--currency", "JPY", "--dimension", "labour", "--fixture", str(FIXTURE), "--output", str(candidate), "--audit-output", str(audit)], cwd=ROOT, check=True)
    c, a = json.loads(candidate.read_text()), json.loads(audit.read_text())
    assert c["authority"] == "Statistics Bureau of Japan" and c["transport"] == "OFFICIAL_DIRECT", c
    assert c["macro_series_id"] == "JP_UNEMP_RATE_history_value" and c["candidate_only"] is True, c
    assert a["status"] == "PASS" and a["registry_promotion"] == "NOT_ATTEMPTED" and a["mode"] == "fixture", a
print(json.dumps({"status":"PASS","fixture_handoff":True,"live_data_written":False,"registry_promotion":"NOT_ATTEMPTED"}))
