#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "validation" / "sources" / "eur_eurostat_core.py"
BUILDER = ROOT / "validation" / "build_macro_candidate.py"
FIXTURES = {
    "inflation": ROOT / "validation" / "fixtures" / "eur_eurostat_hicp_contract.json",
    "labour": ROOT / "validation" / "fixtures" / "eur_eurostat_unemployment_contract.json",
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
    run(
        str(ADAPTER),
        "--dimension", dimension,
        "--fixture", str(FIXTURES[dimension]),
        "--output", str(candidate),
        "--audit-output", str(audit),
    )
    c = json.loads(candidate.read_text())
    a = json.loads(audit.read_text())

    assert c["currency"] == "EUR", c
    assert c["dimension"] == dimension, c
    assert c["source"] == "Eurostat", c
    assert c["frequency"] == "M", c
    assert isinstance(c["macro_series_id"], str) and c["macro_series_id"], c
    assert a["candidate_only"] is True and a["live_data_written"] is False, a
    assert a["mode"] == "fixture", a

    if dimension == "inflation":
        assert c["series_id"] == "EA_HICP_HEADLINE_YOY", c
        assert c["transformation"] == "reported_yoy_rate", c
        assert c["observation_date"] == "2026-10", c
        assert abs(float(c["value"]) - 3.9) < 1e-12, c
        assert a["dataset"] == "prc_hicp_minr", a
        assert a["prior_period"] == "2026-09" and abs(float(a["prior_value"]) - 3.8) < 1e-12, a
    else:
        assert c["series_id"] == "EA_UNEMP", c
        assert c["transformation"] == "level", c
        assert c["observation_date"] == "2026-09", c
        assert abs(float(c["value"]) - 6.5) < 1e-12, c
        assert a["dataset"] == "une_rt_m", a
        assert a["prior_period"] == "2026-08" and abs(float(a["prior_value"]) - 6.4) < 1e-12, a

    run(str(BUILDER), "--candidate", str(candidate), "--output-dir", str(built))
    summary = json.loads((built / "summary.json").read_text())
    assert summary["status"] == "PASS", summary
    assert summary["live_data_modified"] is False, summary
    assert summary["currency"] == "EUR" and summary["dimension"] == dimension, summary
    assert summary["observation_date"] == c["observation_date"], (summary, c)
    assert abs(float(summary["new_value"]) - float(c["value"])) < 1e-12, (summary, c)
    return {
        "dimension": dimension,
        "dataset": a["dataset"],
        "observation_date": c["observation_date"],
        "value": c["value"],
        "live_data_modified": False,
    }


def main() -> int:
    before = {str(p): digest(p) for p in LIVE_FILES}
    with tempfile.TemporaryDirectory(prefix="gmfq-eur-eurostat-") as td:
        root = Path(td)
        results = [check_dimension("inflation", root), check_dimension("labour", root)]
    after = {str(p): digest(p) for p in LIVE_FILES}
    assert before == after, (before, after)
    print(json.dumps({"status": "PASS", "source": "Eurostat", "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
