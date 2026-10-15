from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "validation/ui/DASHBOARD_UI_OWNERSHIP_REGISTRY_V1_2026-10-15.json"
EXPECTED = [
    "overview","wow","themes","calendar","news","risk","currencies","pairs",
    "macro","inflationlabour","ratesdesk","cbdesk","liquiditydesk","cot","method","forwarddesk"
]


def must(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> None:
    d = json.loads(REG.read_text())
    must(d["schema"] == "GMFQ_DASHBOARD_UI_OWNERSHIP_REGISTRY_V1", "schema")
    must(d["policy"]["one_visible_owner_per_view"] is True, "single-owner policy")
    must(d["policy"]["desktop_mobile_owner_parity"] is True, "viewport parity")
    views = d["views"]
    must(list(views.keys()) == EXPECTED, f"view order/coverage drift: {list(views.keys())}")
    must(len(views) == 16, "must cover 16 views")

    index = (ROOT / "index.html").read_text()
    cal = (ROOT / "dashboard/calendar-news-operational-v1.js").read_text()
    ois = (ROOT / "dashboard/ois-operational-monitor-v1.js").read_text()

    for src in [
        "dashboard/calendar-news-operational-v1.js",
        "dashboard/ois-operational-monitor-v1.js",
        "dashboard/editorial-freshness-guard-v1.js",
    ]:
        must(src in index, f"index missing dynamic module {src}")

    must("cal.innerHTML=calendarHtml(c)" in cal, "calendar is not explicit dynamic owner")
    must("news.innerHTML=newsHtml(n)" in cal, "news is not explicit dynamic owner")
    must("data-gmfq-operational=\"calendar\"" in cal, "calendar owner marker missing")
    must("data-gmfq-operational=\"news\"" in cal, "news owner marker missing")
    must("GMFQ_OIS_OPERATIONAL_UI_V1" in ois, "OIS owner marker missing")
    must("v401OisBlock" in ois, "OIS mount missing")

    must(views["calendar"]["owner_type"] == "DYNAMIC_REPLACE", "calendar owner type")
    must(views["news"]["owner_type"] == "DYNAMIC_REPLACE", "news owner type")
    must(views["ratesdesk"]["owner_type"] == "HYBRID", "ratesdesk owner type")
    must(views["calendar"]["legacy_payload_state"] == "SOURCE_PRESENT_NON_OWNER", "calendar legacy state")
    must(views["news"]["legacy_payload_state"] == "SOURCE_PRESENT_NON_OWNER", "news legacy state")

    for view, spec in views.items():
        if spec["owner_type"] == "PAYLOAD":
            must(spec.get("migration_state") == "KEEP", f"payload owner migration state {view}")

    print(json.dumps({
        "status": "PASS",
        "schema": d["schema"],
        "views": len(views),
        "dynamic_replace": ["calendar", "news"],
        "hybrid": ["ratesdesk"],
        "legacy_payload_policy": "PRESENT_BUT_NON_OWNER_UNTIL_MIGRATED"
    }, sort_keys=True))


if __name__ == "__main__":
    main()
