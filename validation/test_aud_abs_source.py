#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "validation" / "sources" / "aud_abs_core.py"
BUILDER = ROOT / "validation" / "build_macro_candidate.py"
FIXTURES = {
    "inflation": ROOT / "validation" / "fixtures" / "aud_abs_cpi_contract.json",
    "labour": ROOT / "validation" / "fixtures" / "aud_abs_unemployment_contract.json",
}
LIVE_FILES = [
    ROOT / "live_data" / "sections" / "MACRO_SERIES.json",
    ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def check_dimension(dimension: str, root: Path) -> dict:
    candidate = root / f"{dimension}-candidate.json"
    audit = root / f"{dimension}-audit.json"
    built = root / f"{dimension}-built"
    run(str(ADAPTER), "--dimension", dimension, "--fixture", str(FIXTURES[dimension]), "--output", str(candidate), "--audit-output", str(audit))
    c = json.loads(candidate.read_text())
    a = json.loads(audit.read_text())
    assert c["currency"] == "AUD" and c["dimension"] == dimension, c
    assert c["source"] == "Australian Bureau of Statistics", c
    assert a["candidate_only"] is True and a["live_data_written"] is False and a["mode"] == "fixture", a

    if dimension == "inflation":
        assert c["macro_series_id"] == "AU_CPI_HEADLINE_Q_YOY_history_value", c
        assert c["series_id"] == "AU_CPI_HEADLINE_Q_YOY", c
        assert c["frequency"] == "Q" and c["transformation"] == "reported_yoy_rate", c
        assert c["observation_date"] == "2026-06" and abs(float(c["value"]) - 3.8) < 1e-12, c
    else:
        assert c["macro_series_id"] == "AU_UNEMP_RATE_history_value", c
        assert c["series_id"] == "AU_UNEMP_RATE", c
        assert c["frequency"] == "M" and c["transformation"] == "level", c
        assert c["observation_date"] == "2026-08" and abs(float(c["value"]) - 4.6) < 1e-12, c

    run(str(BUILDER), "--candidate", str(candidate), "--output-dir", str(built))
    summary = json.loads((built / "summary.json").read_text())
    assert summary["status"] == "PASS" and summary["live_data_modified"] is False, summary
    assert summary["currency"] == "AUD" and summary["dimension"] == dimension, summary
    assert summary["observation_date"] == c["observation_date"], (summary, c)
    assert abs(float(summary["new_value"]) - float(c["value"])) < 1e-12, (summary, c)
    if dimension == "inflation":
        assert summary["series_action"] == "REPLACE_EXISTING", summary
        assert abs(float(summary["old_value"]) - 3.9) < 1e-12, summary
    else:
        assert summary["series_action"] == "APPEND_NEW", summary
    return {"dimension": dimension, "observation_date": c["observation_date"], "value": c["value"], "series_action": summary["series_action"]}


def main() -> int:
    before = {str(p): digest(p) for p in LIVE_FILES}
    with tempfile.TemporaryDirectory(prefix="gmfq-aud-abs-") as td:
        root = Path(td)
        results = [check_dimension("inflation", root), check_dimension("labour", root)]
    after = {str(p): digest(p) for p in LIVE_FILES}
    assert before == after, (before, after)
    print(json.dumps({"status": "PASS", "source": "Australian Bureau of Statistics", "results": results, "live_data_modified": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
