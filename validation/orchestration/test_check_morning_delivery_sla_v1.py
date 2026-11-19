#!/usr/bin/env python3
"""Deterministic Rome 08:00 SLA contract, including the 2026 DST transition."""
from __future__ import annotations

import copy
import datetime as dt
import io
import json
from unittest.mock import patch
import zipfile
from zoneinfo import ZoneInfo

from check_morning_delivery_sla_v1 import confirmed_pages_receipt, evaluate, find_pages_receipt

ROME = ZoneInfo("Europe/Rome")


def at(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


good = {
    "schema": "GMFQ_MORNING_READINESS_V1",
    "operational_state": "DAILY_READY_WITH_DOCUMENTED_GAPS",
    "refresh_pipeline_outcome": "success",
    "critical_daily_problems": [],
    "checked_at_rome": "2026-10-26T07:44:00+01:00",
}

for phase in ("prebrief", "premorning"):
    ontime = evaluate(phase, good, at("2026-10-26T07:59:59+01:00"))
    assert ontime["status"] == "PASS_PHASE_COMPLETED_BY_0800", ontime
    assert ontime["on_time"] is True
    assert ontime["weekday_delivery_window"] is True
    assert ontime["target_rome"] == "2026-10-26T08:00:00+01:00"
    late = evaluate(phase, good, at("2026-10-26T08:00:01+01:00"))
    assert late["status"] == "PHASE_COMPLETED_AFTER_0800"
    assert late["source_and_publication_sequence_successful"] is True
    assert late["on_time"] is False
    assert ontime["pages_public_delivery"]["status"] == "PUBLIC_BY_0800_UNPROVEN"

# Meeting the clock SLA does not erase dated market content caveats.
warning = dict(good, documented_nonblocking_gaps=["NEWS_CONTENT_OLDER_THAN_PREVIOUS_SESSION"])
warning_result = evaluate("premorning", warning, at("2026-10-26T07:59:59+01:00"))
assert warning_result["status"] == "PASS_PHASE_COMPLETED_BY_0800"
assert warning_result["documented_nonblocking_gaps"] == ["NEWS_CONTENT_OLDER_THAN_PREVIOUS_SESSION"]

# A manual or delayed workflow on the weekend must not claim the
# weekday 08:00 study-briefing SLA, even with otherwise valid daily evidence.
for weekend, checked_at in (
    ("2026-10-24T07:59:00+02:00", "2026-10-24T07:44:00+02:00"),
    ("2026-10-25T07:59:00+01:00", "2026-10-25T07:44:00+01:00"),
):
    weekend_report = dict(good, checked_at_rome=checked_at)
    result = evaluate("prebrief", weekend_report, at(weekend))
    assert result["status"] == "FAIL_OUTSIDE_WEEKDAY_DELIVERY_WINDOW"
    assert result["weekday_delivery_window"] is False
    assert result["source_and_publication_sequence_successful"] is True
    assert result["on_time"] is False

# 25 October CEST->CET: the previous Friday is not a reason to shift 08:00.
before_dst = copy.deepcopy(good)
before_dst["checked_at_rome"] = "2026-10-23T07:44:00+02:00"
out = evaluate("premorning", before_dst, at("2026-10-23T07:59:00+02:00"))
assert out["target_rome"] == "2026-10-23T08:00:00+02:00" and out["on_time"]

# Replayed Friday receipt, future-dated audit, missing artifact and bad runs all fail.
for changed in (
    None,
    {},
    dict(good, checked_at_rome="2026-10-23T07:59:00+02:00"),
    dict(good, checked_at_rome="2026-10-26T08:01:00+01:00"),
    dict(good, checked_at_rome="2026-10-26T07:44:00"),
    dict(good, operational_state="DAILY_INPUTS_INCOMPLETE"),
    dict(good, refresh_pipeline_outcome="failure"),
    dict(good, critical_daily_problems=["PAIR_SOURCE_INTEGRITY"]),
):
    state = evaluate("prebrief", changed, at("2026-10-26T07:59:00+01:00"))
    assert state["status"] == "FAIL_INCOMPLETE_OR_UNVERIFIED", state

try:
    evaluate("night", good, at("2026-10-26T07:59:00+01:00"))
except ValueError:
    pass
else:
    raise AssertionError("Non-morning phases must never certify 08:00")

try:
    evaluate("prebrief", good, dt.datetime(2026, 10, 26, 7, 59))
except ValueError:
    pass
else:
    raise AssertionError("Naive timestamps must never certify Rome 08:00")

# 19 November: an independent Pages delivery preceded the delayed phase.
now = at("2026-11-19T13:13:11+01:00")
run = {
    "id": 44459646524,
    "path": ".github/workflows/publish-dashboard-pages-v1.yml",
    "created_at": "2026-11-19T04:37:54Z",
    "event": "workflow_dispatch",
    "head_branch": "main",
    "status": "completed",
    "conclusion": "success",
}
receipt = {
    "schema": "GMFQ_INDEPENDENT_PAGES_0800_SLA_V1",
    "scope": "EXACT_PUBLIC_HTTP_FILES_AND_MORNING_SOURCE_GATE_ONLY",
    "status": "PASS_PUBLIC_HTTP_BY_0800",
    "target_rome": "2026-11-19T08:00:00+01:00",
    "source_checked_at_rome": "2026-11-19T05:38:11+01:00",
    "public_verified_at_rome": "2026-11-19T05:39:33+01:00",
    "evaluated_at_rome": "2026-11-19T05:39:33+01:00",
    "source_pass": True,
    "on_time_delivery_proven": True,
    "public_exact_bytes_pass": True,
    "verified_file_count": 43,
}
archive_bytes = io.BytesIO()
with zipfile.ZipFile(archive_bytes, "w") as archive:
    archive.writestr("pages-0800-delivery-sla.json", json.dumps(receipt))
artifacts = {"artifacts": [{"id": 14500050693, "name": "pages-delivery-proof", "expired": False}]}
with patch("check_morning_delivery_sla_v1.github_api", side_effect=(
    json.dumps({"workflow_runs": [run]}).encode(),
    json.dumps(artifacts).encode(),
    archive_bytes.getvalue(),
)) as api:
    pages = find_pages_receipt("owner/repo", now)
    assert api.call_args_list[-1].args == ("repos/owner/repo/actions/artifacts/14500050693/zip",)
result = evaluate("prebrief", dict(good, checked_at_rome=now.isoformat()), now, pages)
assert result["status"] == "PHASE_COMPLETED_AFTER_0800"
assert result["on_time"] is False
assert result["pages_public_delivery"] == {
    "status": "PASS_PUBLIC_HTTP_BY_0800",
    "publisher_run_id": run["id"],
    "public_verified_at_rome": "2026-11-19T05:39:33+01:00",
    "verified_file_count": 43,
}, result
failed = evaluate("prebrief", None, now, pages)
assert failed["status"] == "FAIL_INCOMPLETE_OR_UNVERIFIED"
assert failed["pages_public_delivery"] == pages

for wrong_run, wrong_receipt, checked_now in (
    (dict(run, head_branch="feature"), receipt, now),
    (dict(run, event="pull_request"), receipt, now),
    (dict(run, conclusion="failure"), receipt, now),
    (run, dict(receipt, public_exact_bytes_pass=False), now),
    (run, dict(receipt, public_verified_at_rome="2026-11-19T08:00:01+01:00",
               evaluated_at_rome="2026-11-19T08:00:01+01:00"), now),
    (run, dict(receipt, public_verified_at_rome="2026-11-19T05:39:33"), now),
    (run, receipt, at("2026-11-19T05:39:32+01:00")),
    (run, receipt, at("2026-11-20T13:13:11+01:00")),
):
    assert confirmed_pages_receipt(wrong_run, wrong_receipt, checked_now) is None

with patch("check_morning_delivery_sla_v1.github_api", return_value=b'{"workflow_runs":[]}'):
    assert find_pages_receipt("owner/repo", now)["status"] == "PUBLIC_BY_0800_UNPROVEN"
with patch("check_morning_delivery_sla_v1.github_api", side_effect=OSError):
    assert find_pages_receipt("owner/repo", now)["status"] == "PUBLISHER_EVIDENCE_LOOKUP_FAILED"

print("MORNING_0800_DELIVERY_SLA_CET_CEST_PASS")
