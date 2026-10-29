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
        "prebrief": "04:43",
        "premorning": "07:45",
        "morning": "09:10",
        "close": "18:30",
        "night": "00:50",
    }
    assert c["rules"]["prebrief_avoids_top_of_hour_load"] is True
    assert c["rules"]["prebrief_dst_gate_tested"] is True
    assert "'43 2 * * 1-5|2'|'43 3 * * 1-5|1') phase=prebrief" in WORKFLOW.read_text()
    assert "Test 04:43 Rome off-hour DST prebrief schedule" in WORKFLOW.read_text()
    assert c["rules"]["strict_sequence"] is True
    # Regression: cancel-in-progress=false alone is NOT sufficient. GitHub
    # replaces an existing pending workflow when a second pending arrives,
    # unless the multi-pending concurrency queue is explicitly enabled.
    assert c["rules"]["preserve_pending_scheduled_phases"] is True
    assert c["rules"]["workflow_concurrency_pending_queue"] == "max"
    assert c["rules"]["workflow_concurrency_cancel_in_progress"] is False
    workflow_text = WORKFLOW.read_text()
    concurrency_section = workflow_text.split("\nconcurrency:\n", 1)
    assert len(concurrency_section) == 2
    block = concurrency_section[1].split("\nenv:\n", 1)[0]
    assert "group: daily-data-orchestrator-v2" in block
    assert "queue: max" in block
    assert "cancel-in-progress: false" in block

    assert c["rules"]["stop_on_child_failure"] is True
    assert c["rules"]["duplicate_collectors_forbidden"] is True
    assert c["rules"]["core_scoring_effect"] == "NONE"
    assert c["rules"]["official_promotion_effect"] == "NONE"
    assert c["rules"]["premorning_avoids_not_yet_ready_sources"] is True
    assert c["rules"]["premorning_calendar_news_selective_retry"] is True
    assert c["separate_cadences"]["COT"] == "cot-persistent-weekly-v1.yml"
    assert c["separate_cadences"]["CB_PRICING_MORNING"] == "cb-pricing-persistent-daily-v1.yml"
    assert c["rules"]["prebrief_cb_pricing_independent_source_outage_isolation"] is True
    assert "cb-pricing-persistent-daily-v1.yml" not in c["phases"]["prebrief"]
    assert "cb-pricing-persistent-daily-v1.yml" not in c["phases"]["premorning"]
    assert c["rules"]["morning_0910_cb_independent_source_outage_isolation"] is True
    assert "cb-pricing-persistent-daily-v1.yml" not in c["phases"]["morning"]
    assert "cb-pricing-persistent-daily-v1.yml" not in c["phases"]["prebrief"]
    assert "cb-pricing-persistent-daily-v1.yml" not in c["phases"]["premorning"]
    cb = (WORKFLOWS_DIR / c["separate_cadences"]["CB_PRICING_MORNING"]).read_text()
    assert "schedule:" in cb and "workflow_dispatch:" in cb
    # Exact UTC pairs support early independent 06:00/06:30/07:00 Rome slots.
    assert "0 4 * * 1-5" in cb and "0 5 * * 1-5" in cb
    assert "30 5 * * 1-5" in cb and "0 6 * * 1-5" in cb
    assert "python3 validation/cb_pricing/cb_pricing_schedule_gate_v1.py" in cb

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
        "ois-estimated-snapshot-repricing-v1.yml",
        "calendar-news-operational-refresh-v1.yml",
        "vix-persistent-apply-v1.yml",
        "final-e2e-certification-gate-v3.yml",
        "publish-dashboard-pages-v1.yml",
    ]
    assert c["rules"]["prebrief_target_before_study"] == "08:00"
    assert c["rules"]["prebrief_never_fabricates_missing_publications"] is True
    assert c["rules"]["prebrief_recovers_official_previous_close_vix"] is True
    assert c["rules"]["morning_0910_is_catch_up_not_first_refresh"] is True
    assert c["phases"]["premorning"] == [
        "calendar-news-operational-refresh-v1.yml",
        "rates-persistent-daily-v1.yml",
        "final-e2e-certification-gate-v3.yml",
        "publish-dashboard-pages-v1.yml",
    ]
    assert "macro-persistent-daily-v1.yml" not in c["phases"]["premorning"]
    assert "ois-estimated-snapshot-repricing-v1.yml" not in c["phases"]["premorning"]
    assert "calendar-news-operational-refresh-v1.yml" in c["phases"]["premorning"]
    assert 'plan_premorning_calendar_news_recovery_v1.py' in WORKFLOW.read_text()
    assert 'SKIPPED** (both sources already rechecked today' in WORKFLOW.read_text()
    assert 'RETRY** (missing or stale same-day source receipt)' in WORKFLOW.read_text()
    assert "chf-residual-proxy-refresh-v1.yml" not in c["phases"]["premorning"]
    assert "jpy-reserve-balances-proxy-refresh-v1.yml" not in c["phases"]["premorning"]

    # The separate News updater must try early before the 08:00 desk,
    # because delayed GitHub cron can arrive well after its scheduled UTC minute.
    news = (WORKFLOWS_DIR / "calendar-news-operational-refresh-v1.yml").read_text()
    assert "17 4 * * 1-5" in news
    assert "17 6 * * *" in news
    text = WORKFLOW.read_text()
    # No duplicate CB acquisition in 05:00, 07:45 OR 09:10,
    # preserving independent 06:00/06:30/07:00 publisher-reconciled CB refresh.
    segment = text[text.index("              prebrief)"):text.index("              morning)", text.index("              prebrief)"))]
    assert "cb-pricing-persistent-daily-v1.yml" not in segment
    morning_segment = text[text.index("              morning)"):text.index("              close)", text.index("              morning)"))]
    assert "cb-pricing-persistent-daily-v1.yml" not in morning_segment
    assert "calendar-news-operational-refresh-v1.yml" in morning_segment
    assert "ois-estimated-snapshot-repricing-v1.yml" in morning_segment
    required_markers = [
        "name: Daily Data Orchestrator V2",
        "actions: write",
        "Europe/Rome",
        "dispatch_and_wait",
        "return_run_details=true",
        "X-GitHub-Api-Version: 2026-03-10",
        "run_id=$(jq -er '.workflow_run_id",
        "response_run_url=$(jq -er '.run_url",
        "response_html_url=$(jq -er '.html_url",
        "Workflow dispatch response did not identify the expected run",
        "child_event=$(jq -r '.event // empty'",
        "child_branch=$(jq -r '.head_branch // empty'",
        "child_sha=$(jq -r '.head_sha // empty'",
        "child_url=$(jq -r '.html_url // empty'",
        'Child run identity failed:',
        'actions/runs/${run_id}',
        "43 2 * * 1-5",
        "43 3 * * 1-5",
        "phase=prebrief",
        "check_morning_readiness_v1.py",
        "test_check_morning_readiness_v1.py",
        "morning-readiness-v1.json",
        "Audit true source dates for the morning study",
        "id: refresh",
        "steps.refresh.outcome",
        '--pipeline-outcome "$REFRESH_OUTCOME"',
        "always() && (steps.phase.outputs.phase == 'prebrief'",
        "refresh_pipeline_outcome",
        "45 5 * * 1-5",
        "45 6 * * 1-5",
        "phase=premorning",
        "rates-persistent-daily-v1.yml",
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

    # Audit evidence must retain the exact downstream run identity, including
    # failures, BEFORE the existing fail-closed gate allows the next child.
    child_receipt = 'echo "- [${wf} · run #${run_id}]('
    required_success_gate = '[[ "$conclusion" == "success" ]] || return 1'
    assert text.count(child_receipt) == 1
    assert text.count(required_success_gate) == 1
    assert text.index(child_receipt) < text.index(required_success_gate)
    # The parent must never dispatch its explicit 05:00/07:45 Pages job
    # before checking source freshness on the latest main checkout.
    assert 'Checkout main for pre-publication source audit' in text
    # All active phases, including 09:10 manual morning / close / night,
    # run the source-backed child-step proof. They MUST check out the repo
    # before executing that Python file, even if no pre-publication audit runs.
    checkout_segment = text.split(
        '      - name: Checkout main for pre-publication source audit\\n', 1
    )[1].split('      - name: Run serialized refresh sequence\\n', 1)[0]
    assert "if: ${{ steps.phase.outputs.phase != 'skip' }}" in checkout_segment
    assert 'uses: actions/checkout@v4' in checkout_segment
    assert 'ref: main' in checkout_segment
    assert text.index('      - name: Checkout main for pre-publication source audit') < text.index(
        '      - name: Run serialized refresh sequence'
    )
    assert 'if [[ "$wf" == "publish-dashboard-pages-v1.yml" ]] &&' in text
    assert 'git fetch origin --no-tags --depth=1' in text
    assert 'git reset --hard origin/main' in text
    assert 'python3 validation/orchestration/check_morning_readiness_v1.py' in text
    assert '--strict-daily --pipeline-outcome success' in text
    assert 'Main changed after pre-publication readiness audit' in text
    assert 'path: |' in text
    assert '/tmp/morning-readiness*.json' in text
    assert '/tmp/morning-delivery-sla-v1.json' in text
    assert text.index('if [[ "$wf" == "publish-dashboard-pages-v1.yml" ]] &&') < text.index('dispatch_and_wait "$wf"')
    # A workflow may end successfully after the user starts studying.
    # Never mistake late-but-valid public files for an on-time 08:00 delivery.
    assert 'Test 08:00 Rome delivery SLA and failure receipts' in text
    assert 'Certify 08:00 morning delivery deadline' in text
    assert 'check_morning_delivery_sla_v1.py' in text
    assert 'test_check_morning_delivery_sla_v1.py' in text
    assert '--readiness /tmp/morning-readiness-v1.json' in text
    assert '--output /tmp/morning-delivery-sla-v1.json' in text
    assert 'MORNING_0800_SLA_RESULT' in text
    assert '/tmp/morning-delivery-sla-v1.json' in text
    assert text.index('Audit true source dates for the morning study') < text.index('Certify 08:00 morning delivery deadline') < text.index('Retain morning source readiness evidence')

    # A green child workflow can still skip the essential scheduled-work
    # step. Inspect the exact run's jobs and steps before dispatching the next
    # child. Legitimate no-change data is not a failed acquisition.
    assert 'Test fail-closed evidence for all orchestrated child steps' in text
    assert 'check_child_execution_steps_v1.py' in text
    assert 'test_check_child_execution_steps_v1.py' in text
    assert 'actions/runs/${run_id}/jobs?per_page=100' in text
    assert '--workflow "$wf"' in text
    assert 'CHILD_REQUIRED_STEPS_NOT_EXECUTED' in text
    assert 'Retain exact child-step proof for all orchestration phases' in text
    assert 'path: /tmp/orchestration-child-step-evidence/*-proof.json' in text
    step_gate_call = 'if python3 validation/orchestration/check_child_execution_steps_v1.py'
    assert text.index('[[ "$conclusion" == "success" ]] || return 1') < text.index(step_gate_call)
    assert text.index(step_gate_call) < text.index('return 0', text.index(step_gate_call))
    # Retry read-only run and job lookups on transient API transport failure,
    # but never repeat the ambiguous workflow-dispatch POST.
    assert text.count('dispatch_result=$(gh api --method POST') == 1
    assert 'if ! json=$(gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}"); then' in text
    assert 'CHILD_RUN_API_TRANSIENT' in text
    assert 'if gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}/jobs?per_page=100" > "$child_jobs_file"; then' in text
    assert 'CHILD_JOBS_API_TRANSIENT' in text
    assert 'rm -f "$child_jobs_file"' in text
    assert 'Test transient GitHub run/job reads without duplicate dispatch' in text

    # Feb 2026 GitHub API returns the exact dispatched run ID, instead of
    # guessing from adjacent/manual dispatches or relying on polling order.
    assert '"${api}/dispatches" -f ref=main -F return_run_details=true' in text
    assert 'run_id=$(jq -er' in text
    assert '"$response_run_url" != "https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}"' in text
    assert '"$response_html_url" != "https://github.com/${GITHUB_REPOSITORY}/actions/runs/${run_id}"' in text
    assert 'sort_by(.id)' not in text
    assert 'before=$(gh api' not in text
    assert '/runs?branch=main&event=workflow_dispatch' not in text
    assert text.index('run_id=$(jq -er') < text.index('for _ in $(seq 1 360); do')
    assert '[[ "$child_event" != "workflow_dispatch"' in text
    assert '"$child_branch" != "main"' in text

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
