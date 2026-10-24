#!/usr/bin/env python3
"""Offline regression: Pages OIS parity must validate the operational view.

Never infer green/withheld counts from the canonical OIS_DATA source or
silently promote informational futures to certified OIS.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
WF=ROOT/".github/workflows/publish-dashboard-pages-v1.yml"
CANONICAL=ROOT/"live_data/sections/OIS_DATA.json"
OPERATIONAL=ROOT/"live_data/sections/OIS_OPERATIONAL_VIEW.json"


def main():
    text=WF.read_text(encoding="utf-8")
    # Check the exact script that runs on a real Pages main/push deployment,
    # not merely a check on a synthetic fixture.
    expected="obj=json.loads(operational.read_text())"
    assert expected in text
    assert "operational=pathlib.Path('live_data/sections/OIS_OPERATIONAL_VIEW.json')" in text
    assert "assert obj['schema']=='GMFQ_OIS_OPERATIONAL_VIEW_V1'" in text
    assert "obj=json.loads(pathlib.Path(paths[0]).read_text())" not in text
    assert "assert obj['summary']['g8_total']==8" in text
    assert "assert not check(obj,datetime.now(timezone.utc).date())" in text

    canonical=json.loads(CANONICAL.read_text(encoding="utf-8"))
    operational=json.loads(OPERATIONAL.read_text(encoding="utf-8"))
    assert "summary" not in canonical, "canonical official data must not be coerced into operational view"
    assert canonical.get("schema_version")
    assert operational["schema"]=="GMFQ_OIS_OPERATIONAL_VIEW_V1"
    s=operational["summary"]
    assert s["g8_total"]==8
    assert s["operational_green"]+s["operational_withheld"]==8
    assert s["green_official"]+s["green_estimated"]==s["operational_green"]
    assert set(operational["currencies"])=={"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"}
    for ccy,row in operational["currencies"].items():
        if row["operational_status"]=="GREEN_ESTIMATED":
            assert row["quality"]!="OFFICIAL_CERTIFIED",ccy
            assert row.get("backtest_eligible_as_official") is False,ccy
    print("PAGES_OPERATIONAL_G8_OIS_SUMMARY_SOURCE_PASS")


if __name__=="__main__":
    main()
