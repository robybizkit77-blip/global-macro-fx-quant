from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "validation/orchestration/DAILY_DATA_ORCHESTRATOR_V2_2026-10-15.json"
WORKFLOW = ROOT / ".github/workflows/daily-data-orchestrator-v2.yml"
WORKFLOWS_DIR = ROOT / ".github/workflows"


def fail(msg: str) -> None:
    raise AssertionError(msg)


def main() -> None:
    c = json.loads(CONTRACT.read_text())
    assert c["schema"] == "GMFQ_DAILY_DATA_ORCHESTRATOR_V2"
    assert c["timezone"] == "Europe/Rome"
    assert c["target_local_times"] == {
        "prebrief": "05:00",
        "premorning": "07:45",
        "morning": "09:10",
        "close": "18:30",
        "night": "00:50",
    }
    assert c["rules"]["strict_sequence"] is True
    assert c["rules"]["stop_on_child_failure"] is True
    assert c["rules"]["duplicate_collectors_forbidden"] is True
    assert c["rules"]["core_scoring_effect"] == "NONE"
    assert c["rules"]["official_promotion_effect"] == "NONE"
    assert c["rules"]["premorning_avoids_not_yet_ready_sources"] is True
    assert c["separate_cadences"]["COT"] == "cot-persistent-weekly-v1.yml"

    expected_suffix = [
        "final-e2e-certification-gate-v3.yml",
        "publish-dashboard-pages-v1.yml",
    ]
    for phase in ("prebrief", "premorning", "morning", "close", "night"):
        items = c["phases"][phase]
        assert items[-2:] == expected_suffix, (phase, items)
        assert len(items) == len(set(items)), (phase, items)
        assert "cot-persistent-weekly-v1.yml" not in items, phase
        for child in items:
            p = WORKFLOWS_DIR / child
            if not p.exists():
                fail(f"missing child workflow: {child}")
            text = p.read_text()
            if "workflow_dispatch:" not in text:
                fail(f"child workflow is not dispatchable: {child}")

    assert c["phases"]["prebrief"] == [
        "macro-persistent-daily-v1.yml",
        "rates-persistent-daily-v1.yml",
        "cb-pricing-persistent-daily-v1.yml",
        "ois-estimated-snapshot-repricing-v1.yml",
        "calendar-news-operational-refresh-v1.yml",
        "final-e2e-certification-gate-v3.yml",
        "publish-dashboard-pages-v1.yml",
    ]
    assert c["rules"]["prebrief_target_before_study"] == "08:00"
    assert c["rules"]["prebrief_never_fabricates_missing_publications"] is True
    assert c["rules"]["morning_0910_is_catch_up_not_first_refresh"] is True
    assert c["phases"]["premorning"] == [
        "rates-persistent-daily-v1.yml",
        "cb-pricing-persistent-daily-v1.yml",
        "final-e2e-certification-gate-v3.yml",
        "publish-dashboard-pages-v1.yml",
    ]
    assert "macro-persistent-daily-v1.yml" not in c["phases"]["premorning"]
    assert "ois-estimated-snapshot-repricing-v1.yml" not in c["phases"]["premorning"]
    assert "chf-residual-proxy-refresh-v1.yml" not in c["phases"]["premorning"]
    assert "jpy-reserve-balances-proxy-refresh-v1.yml" not in c["phases"]["premorning"]

    text = WORKFLOW.read_text()
    required_markers = [
        "name: Daily Data Orchestrator V2",
        "actions: write",
        "Europe/Rome",
        "dispatch_and_wait",
        "0 3 * * 1-5",
        "0 4 * * 1-5",
        "phase=prebrief",
        "45 5 * * 1-5",
        "45 6 * * 1-5",
        "phase=premorning",
        "rates-persistent-daily-v1.yml",
        "cb-pricing-persistent-daily-v1.yml",
        "macro-persistent-daily-v1.yml",
        "ois-estimated-snapshot-repricing-v1.yml",
        "price-persistent-daily-v1.yml",
        "vix-persistent-apply-v1.yml",
        "wti-persistent-rebuild-v1.yml",
        "brent-market-proxy-refresh-v1.yml",
        "final-e2e-certification-gate-v3.yml",
        "publish-dashboard-pages-v1.yml",
    ]
    for marker in required_markers:
        if marker not in text:
            fail(f"orchestrator missing marker: {marker}")

    print(json.dumps({
        "status": "PASS",
        "schema": c["schema"],
        "phases": {k: len(v) for k, v in c["phases"].items()},
        "target_local_times": c["target_local_times"],
        "cot": "SEPARATE_WEEKLY",
        "core_scoring_effect": "NONE",
        "official_promotion_effect": "NONE",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
