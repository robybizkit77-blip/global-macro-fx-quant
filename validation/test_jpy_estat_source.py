#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "validation" / "sources" / "jpy_estat_unemployment.py"
BUILDER = ROOT / "validation" / "build_macro_candidate.py"
FIXTURE = ROOT / "validation" / "fixtures" / "jpy_estat_unemployment_2026-08.json"


def run(*args: str) -> None:
    subprocess.run(list(args), cwd=ROOT, check=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gmfq-jpy-estat-") as td:
        t = Path(td)
        candidate = t / "candidate.json"
        audit = t / "audit.json"
        out = t / "built"

        run(sys.executable, str(ADAPTER), "--fixture", str(FIXTURE), "--output", str(candidate), "--audit-output", str(audit))
        c = json.loads(candidate.read_text(encoding="utf-8"))
        a = json.loads(audit.read_text(encoding="utf-8"))

        expected = {
            "currency": "JPY",
            "dimension": "labour",
            "observation_date": "2026-08",
            "value": 2.6,
        }
        for k, v in expected.items():
            if c.get(k) != v:
                raise SystemExit(f"candidate mismatch {k}: got={c.get(k)!r} expected={v!r}")
        if a.get("prior_period") != "2026-07" or a.get("prior_value") != 2.4:
            raise SystemExit(f"prior observation mismatch: {a}")
        if abs(float(a.get("delta")) - 0.2) > 1e-12:
            raise SystemExit(f"delta mismatch: {a.get('delta')}")
        if a.get("mode") != "fixture" or a.get("live_data_written") is not False:
            raise SystemExit(f"unsafe adapter audit: {a}")

        before_series = (ROOT / "live_data" / "sections" / "MACRO_SERIES.json").read_bytes()
        before_heat = (ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json").read_bytes()
        run(sys.executable, str(BUILDER), "--candidate", str(candidate), "--output-dir", str(out))
        after_series = (ROOT / "live_data" / "sections" / "MACRO_SERIES.json").read_bytes()
        after_heat = (ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json").read_bytes()
        if before_series != after_series or before_heat != after_heat:
            raise SystemExit("live_data changed during candidate build")

        summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        if summary.get("status") != "PASS" or summary.get("live_data_modified") is not False:
            raise SystemExit(f"builder contract failed: {summary}")
        if summary.get("observation_date") != "2026-08" or float(summary.get("new_value")) != 2.6:
            raise SystemExit(f"builder propagated wrong observation: {summary}")

        print(json.dumps({
            "status": "PASS",
            "source": "Statistics Bureau of Japan / e-Stat",
            "fixture_latest": "2026-08",
            "fixture_value": 2.6,
            "fixture_prior": 2.4,
            "builder_status": summary.get("status"),
            "series_action": summary.get("series_action"),
            "live_data_modified": False,
            "credential_committed": False,
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
