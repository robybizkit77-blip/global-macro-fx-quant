#!/usr/bin/env python3
"""Standalone Macro Series Pages mirror owner, strict hash/public proof contract."""
from __future__ import annotations
from pathlib import Path
import json
from check_control_room_feed_mirrors_v1 import main as check_mirrors
from verify_pages_http_delivery_v1 import FILES

ROOT=Path(__file__).resolve().parents[2]

def main():
    workflow=(ROOT/".github/workflows/publish-dashboard-pages-v1.yml").read_text(encoding="utf-8")
    active=(ROOT/"site/control-room-preview/home-navigation-v10.js").read_text(encoding="utf-8")
    proof=(ROOT/"validation/publishing/verify_pages_http_delivery_v1.py").read_text(encoding="utf-8")
    canonical="live_data/sections/MACRO_SERIES.json"
    heat="live_data/sections/MACRO_THERMOMETER_DATA.json"
    assert canonical in FILES and heat in FILES
    assert FILES.count(canonical)==1
    assert active.count("feed('MACRO_SERIES.json')")==0, "Standalone is not a Home direct source"
    # The Pages runner must watch the source AND actually copy, stage and
    # verify it; a manually retained gh-pages blob is never a source of truth.
    assert workflow.count("'"+canonical+"'")>=3, "PR/push and scope triggers missing"
    loop=next(s for s in workflow.splitlines() if s.strip().startswith("for f in ")
              and "OIS_DATA.json OIS_OPERATIONAL_VIEW.json" in s)
    assert "MACRO_SERIES.json" in loop
    assert canonical in next(s for s in workflow.splitlines()
                             if s.strip().startswith("git add -- index.html payload/part-*.txt"))
    assert "'"+canonical+"'" in workflow, "canonical source not scope-whitelisted"
    assert '"'+canonical+'"' in proof, "CDN exact byte evidence missing"
    assert "Verify published files against validated main" in workflow
    assert "verify_pages_http_delivery_v1 import FILES" in workflow
    s=json.loads((ROOT/canonical).read_text(encoding="utf-8"))
    heatmap=json.loads((ROOT/heat).read_text(encoding="utf-8"))
    g8=set("USD EUR GBP JPY CHF CAD AUD NZD".split())
    assert set(s)==g8 and set(heatmap["currencies"])==g8
    assert all(isinstance(s[c],list) and len(s[c])>=10 for c in g8)
    assert all({"inflation","labour"}<=set(heatmap["currencies"][c]) for c in g8)
    check_mirrors()  # Exact active feed ownership does not change.
    print("MACRO_SERIES_SINGLE_PAGES_OWNER_SOURCE_COPIED_AND_HTTP_HASHED_PASS")

if __name__=="__main__":
    main()
