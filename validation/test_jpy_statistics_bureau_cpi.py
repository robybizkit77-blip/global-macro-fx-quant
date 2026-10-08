#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "validation" / "fixtures" / "jpy_statistics_bureau_cpi_fixture.html"
ADAPTER = ROOT / "validation" / "sources" / "jpy_statistics_bureau_cpi.py"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gmfq-jpy-cpi-") as td:
        out = Path(td) / "candidate.json"
        audit = Path(td) / "audit.json"
        subprocess.run(
            [
                "python",
                str(ADAPTER),
                "--fixture",
                str(FIXTURE),
                "--output",
                str(out),
                "--audit-output",
                str(audit),
            ],
            cwd=ROOT,
            check=True,
        )
        c = json.loads(out.read_text(encoding="utf-8"))
        a = json.loads(audit.read_text(encoding="utf-8"))

    assert c["currency"] == "JPY"
    assert c["dimension"] == "inflation"
    assert c["observation_date"] == "2026-08"
    assert abs(float(c["value"]) - 1.9) < 1e-12
    assert c["series_id"] == "JP_CPI_HEADLINE_YOY"
    assert c["frequency"] == "M"
    assert c["source"] == "Statistics Bureau of Japan / CPI"
    assert a["authority"] == "Statistics Bureau of Japan"
    assert a["mode"] == "fixture"
    assert a["candidate_only"] is True
    assert a["live_data_written"] is False
    assert "総合指数" in a["matched_semantics"]
    print(json.dumps({
        "status": "PASS",
        "source": "Statistics Bureau of Japan official CPI page",
        "fixture_period": c["observation_date"],
        "fixture_value": c["value"],
        "macro_series_id": c["macro_series_id"],
        "series_id": c["series_id"],
        "live_data_modified": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
