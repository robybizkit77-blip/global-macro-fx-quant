#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "validation" / "fixtures" / "us_bls_cpi_contract.json"
ADAPTER = ROOT / "validation" / "sources" / "us_bls_cpi.py"
BUILDER = ROOT / "validation" / "build_macro_candidate.py"
LIVE_FILES = [
    ROOT / "live_data" / "sections" / "MACRO_SERIES.json",
    ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def main() -> int:
    before = {str(p): digest(p) for p in LIVE_FILES}
    with tempfile.TemporaryDirectory(prefix="gmfq-us-bls-cpi-") as td:
        out = Path(td)
        candidate = out / "candidate.json"
        audit = out / "audit.json"
        built = out / "built"

        run(
            str(ADAPTER),
            "--fixture", str(FIXTURE),
            "--output", str(candidate),
            "--audit-output", str(audit),
        )
        c = json.loads(candidate.read_text())
        a = json.loads(audit.read_text())

        assert c["currency"] == "USD", c
        assert c["dimension"] == "inflation", c
        assert c["observation_date"] == "2026-09", c
        assert abs(float(c["value"]) - 3.8) < 1e-10, c
        assert c["series_id"] == "CPIAUCSL", c
        assert c["frequency"] == "M", c
        assert c["transformation"] == "yoy_pct_from_index", c
        assert c["source"] == "U.S. Bureau of Labor Statistics", c
        assert isinstance(c["macro_series_id"], str) and c["macro_series_id"], c

        assert a["upstream_series_id"] == "CUSR0000SA0", a
        assert a["latest_period"] == "2026-09", a
        assert abs(float(a["latest_yoy"]) - 3.8) < 1e-10, a
        assert a["prior_yoy_period"] == "2026-08", a
        assert abs(float(a["prior_yoy"]) - 3.5) < 1e-10, a
        assert a["mode"] == "fixture", a
        assert a["candidate_only"] is True, a
        assert a["live_data_written"] is False, a

        run(str(BUILDER), "--candidate", str(candidate), "--output-dir", str(built))
        summary = json.loads((built / "summary.json").read_text())
        assert summary["status"] == "PASS", summary
        assert summary["live_data_modified"] is False, summary
        assert summary["currency"] == "USD" and summary["dimension"] == "inflation", summary
        assert summary["observation_date"] == c["observation_date"], (summary, c)
        assert abs(float(summary["new_value"]) - float(c["value"])) < 1e-10, (summary, c)

    after = {str(p): digest(p) for p in LIVE_FILES}
    assert before == after, (before, after)
    print(json.dumps({
        "status": "PASS",
        "source": "BLS",
        "series": "CUSR0000SA0",
        "target_series": "CPIAUCSL",
        "observation_date": "2026-09",
        "yoy": 3.8,
        "live_data_modified": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
