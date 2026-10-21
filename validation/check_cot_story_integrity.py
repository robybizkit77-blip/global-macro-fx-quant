#!/usr/bin/env python3
"""Fail-closed parity: canonical V250 CFTC → V247 narrative → runtime payload."""
from __future__ import annotations
import json
from pathlib import Path
from build_cot_stories import ORDER, build_one, signal_from_percentile
from update_live_derived_sections import locate

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "live_data" / "sections"


def main() -> int:
    # Canonical displayed percentiles round to the nearest integer (half-up).
    for pct,expected in [
        (0,"EXTREME SHORT"), (19.4999,"EXTREME SHORT"),
        (20.4999,"EXTREME SHORT"), (20.5,"NEUTRALE"),
        (79.4999,"NEUTRALE"), (79.5,"EXTREME LONG"),
        (79.807692,"EXTREME LONG"), (80,"EXTREME LONG"),
        (100,"EXTREME LONG")
    ]:
        assert signal_from_percentile(pct)==expected,(pct,expected)
    source=json.loads((DATA/"V250_COT_CHART_DATA.json").read_text())
    stories=json.loads((DATA/"V247_COT_STORIES.json").read_text())
    assert set(source)==set(ORDER)==set(stories)
    dates=set()
    for c in ORDER:
        s=source[c]
        assert len(s["dates"])==104 and all(len(s[k])==104 for k in
            ("net","long","short","percentile","netoi","dates"))
        assert s["net"][-1]==s["long"][-1]-s["short"][-1]
        dates.add(s["dates"][-1])
        expected=build_one(c,s)
        assert stories[c]==expected,f"{c}: story drift from V250 source"
        assert stories[c]["price"]=="WITHHELD"
    assert len(dates)==1
    if source["USD"]["dates"][-1]=="2026-10-13":
        # Fixed historical regression boundary; a new official CFTC date
        # must not be blocked by the October 2026 snapshot's values.
        assert source["USD"]["net"][-1]==12919
        assert source["USD"]["percentile"][-1]==79.807692
        assert stories["USD"]["signal"]=="EXTREME LONG"
    parts=[(ROOT/"payload"/f"part-{i:02d}.txt").read_text() for i in range(16)]
    payload,idx,_,_=locate(parts,"window.__GMFQ_DATA.V247_COT_STORIES=")
    assert payload==stories,"Root dashboard derived COT narrative differs from canonical section"
    assert idx in range(16)
    js=(ROOT/"dashboard"/"cotdesk-operational-v1.js").read_text()
    assert "const stateLabel=p=>{const r=Math.round(p);" in js
    print(json.dumps({"status":"PASS","as_of":next(iter(dates)),
        "usd_percentile":source["USD"]["percentile"][-1],
        "usd_rounded":int(source["USD"]["percentile"][-1]+0.5),"usd_label":stories["USD"]["signal"],
        "runtime_part":idx,"story_source_parity":"VERIFIED",
        "price_confirmation":"WITHHELD","canonical_pair_and_macro":"UNTOUCHED"}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
