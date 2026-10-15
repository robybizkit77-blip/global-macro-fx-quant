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
    themes = (ROOT / "dashboard/top-themes-operational-v1.js").read_text()
    wow = (ROOT / "dashboard/what-changed-operational-v1.js").read_text()
    ois = (ROOT / "dashboard/ois-operational-monitor-v1.js").read_text()
    freshness = (ROOT / "dashboard/editorial-freshness-guard-v1.js").read_text()

    for src in [
        "dashboard/calendar-news-operational-v1.js",
        "dashboard/top-themes-operational-v1.js",
        "dashboard/what-changed-operational-v1.js",
        "dashboard/ois-operational-monitor-v1.js",
        "dashboard/editorial-freshness-guard-v1.js",
    ]:
        must(src in index, f"index missing dynamic module {src}")

    must("data-gmfq-operational=\"wow\"" in wow, "what changed owner marker missing")
    must("NEWS_PULSE_OPERATIONAL.json" in wow, "what changed missing operational source")
    must("core_effect:'NONE'" in wow, "what changed must declare zero core effect")
    must("GMFQ_WHAT_CHANGED_OPERATIONAL_UI_V1" in wow, "what changed operational schema missing")

    must("data-gmfq-operational=\"themes\"" in themes, "themes owner marker missing")
    for source in ["NEWS_PULSE_OPERATIONAL.json","MACRO_THERMOMETER_DATA.json","OIS_OPERATIONAL_VIEW.json"]:
        must(source in themes, f"themes missing operational source {source}")
    must("core_effect:'NONE'" in themes, "themes must declare zero core effect")
    must("GMFQ_TOP_THEMES_OPERATIONAL_UI_V1" in themes, "themes operational schema missing")
    must("cal.innerHTML=calendarHtml(c)" in cal, "calendar is not explicit dynamic owner")
    must("news.innerHTML=newsHtml(n)" in cal, "news is not explicit dynamic owner")
    must("data-gmfq-operational=\"calendar\"" in cal, "calendar owner marker missing")
    must("data-gmfq-operational=\"news\"" in cal, "news owner marker missing")
    must("GMFQ_OIS_OPERATIONAL_UI_V1" in ois, "OIS owner marker missing")
    must("v401OisBlock" in ois, "OIS mount missing")

    must("GMFQ_EDITORIAL_FRESHNESS_GUARD_V2_OPERATIONAL_AUTHORITY" in freshness, "freshness V2 schema missing")
    must("CALENDAR_OPERATIONAL_VIEW.json" in freshness, "calendar operational freshness source missing")
    must("NEWS_PULSE_OPERATIONAL.json" in freshness, "news operational freshness source missing")
    must("CALENDAR_OPERATIONAL_VIEW.generated_at_utc" in freshness, "calendar authority marker missing")
    must("NEWS_PULSE_OPERATIONAL.content_as_of" in freshness, "news authority marker missing")
    must("legacy_authority:'NONE'" in freshness, "legacy freshness authority must be NONE")
    must("AUXILIARY_FEED_FRESHNESS" not in freshness, "freshness guard must not read legacy AUXILIARY_FEED_FRESHNESS")
    must("REAL_CALENDAR" not in freshness, "freshness guard must not read legacy REAL_CALENDAR")
    must("NEWS_PULSE_STRUCT" not in freshness, "freshness guard must not read legacy NEWS_PULSE_STRUCT")

    for view in ("wow","themes","calendar","news"):
        must(views[view]["owner_type"] == "DYNAMIC_REPLACE", f"{view} owner type")
        must(views[view]["legacy_payload_state"] == "SOURCE_PRESENT_NON_OWNER", f"{view} legacy state")
    must(views["ratesdesk"]["owner_type"] == "HYBRID", "ratesdesk owner type")

    for view, spec in views.items():
        if spec["owner_type"] == "PAYLOAD":
            must(spec.get("migration_state") == "KEEP", f"payload owner migration state {view}")

    print(json.dumps({
        "status": "PASS",
        "schema": d["schema"],
        "views": len(views),
        "dynamic_replace": ["wow", "themes", "calendar", "news"],
        "hybrid": ["ratesdesk"],
        "freshness_authority": {
            "calendar": "CALENDAR_OPERATIONAL_VIEW.generated_at_utc",
            "news": "NEWS_PULSE_OPERATIONAL.content_as_of",
            "legacy": "NONE"
        },
        "legacy_payload_policy": "PRESENT_BUT_NON_OWNER_UNTIL_MIGRATED"
    }, sort_keys=True))


if __name__ == "__main__":
    main()
