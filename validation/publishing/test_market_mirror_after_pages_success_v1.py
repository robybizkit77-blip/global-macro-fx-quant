#!/usr/bin/env python3
"""Fail closed if rates pages + direct feed mirrors can end out of sync."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
market=(ROOT/'.github/workflows/publish-control-room-market-data-v1.yml').read_text()
pages=(ROOT/'.github/workflows/publish-dashboard-pages-v1.yml').read_text()

assert "'Publish Dashboard Pages V1'" in market.split('workflow_run:',1)[1].split('workflow_dispatch:',1)[0], (
    'Market-feed publishing must also follow completed Pages pipeline')
assert "github.event.workflow_run.conclusion == 'success'" in market
assert "github.event.workflow_run.head_branch == 'main'" in market
assert "contents: write" in market
# PR tests use isolated groups; production root and the market mirror owner
# MUST still serialize on the exact same production group.
for workflow, pr_name in ((market, "market-data-validation-pr"),
                          (pages, "pages-validation-pr")):
    queue = workflow.split("concurrency:", 1)[1].split("jobs:", 1)[0]
    assert "github.event_name == 'pull_request'" in queue
    assert "format('" + pr_name + "-{0}', github.event.pull_request.number)" in queue
    assert "|| 'publish-dashboard-pages-v1'" in queue
    assert "cancel-in-progress: false" in queue
    assert "queue: max" in queue
assert "format('pages-validation-pr-{0}'" not in market
assert "format('market-data-validation-pr-{0}'" not in pages
# A shared group without queue:max silently replaces pending mirror runs.
# Preserve both pending runs without permitting concurrent gh-pages writes.
assert market.split("concurrency:",1)[1].split("jobs:",1)[0].count("queue: max") == 1
assert pages.split("concurrency:",1)[1].split("jobs:",1)[0].count("queue: max") == 1
assert "'Publish Control Room Market Data V1'" not in pages.split('workflow_run:',1)[1].split('workflow_dispatch:',1)[0], (
    'Avoid publication trigger cycle from Market into Pages')
assert "'Rates Persistent Daily V1'" in pages
assert "'Rates Persistent Daily V1'" in market
assert "'live_data/sections/NATIVE_RATES_DATA.json'" in market
assert "verify_control_room_market_delivery_v1.py" in market
assert "check_live_update_contract.py" in pages
assert "rebuild_live_data_runtime.py --verify-only" in pages
assert "git push --force-with-lease=refs/heads/gh-pages:" in market
assert "git push --force-with-lease=refs/heads/gh-pages:" in pages
print('RATES_PUBLIC_PAGES_THEN_MARKET_FEED_MIRROR_CASCADE_NO_CYCLE_PASS')
