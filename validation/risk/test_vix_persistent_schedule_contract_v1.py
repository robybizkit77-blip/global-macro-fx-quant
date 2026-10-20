#!/usr/bin/env python3
"""Regression: delayed scheduled VIX refreshes must never turn into silent green skips.

This audits the *operational* VIX workflow, preserving strict official source
freshness, semantic append scope, lease-protected main writes and idempotence.
No market data or website changes.
"""
from __future__ import annotations
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
WORKFLOW=ROOT/".github/workflows/vix-persistent-apply-v1.yml"
CANDIDATE=ROOT/"validation/fetch_cboe_vix_candidate_v2.py"
APPLY=ROOT/"validation/apply_cboe_vix_candidate_v1.py"


def policy_text():
    return WORKFLOW.read_text(encoding="utf-8")


class VIXScheduleTests(unittest.TestCase):
    def test_schedule_admission_is_unconditional_after_checkout(self):
        text=policy_text()
        gate=text.split("      - name: Admit delayed Rome schedule runs",1)[1].split(
            "      - uses: actions/setup-python@v5",1)[0]
        self.assertIn("id: gate",gate)
        self.assertIn("echo 'should_run=true' >> \"$GITHUB_OUTPUT\"",gate)
        self.assertNotIn("should_run=false",gate)
        self.assertNotIn("23:15 23:45",gate)
        self.assertNotIn("== *",gate)

    def test_utc_duplicate_slots_cover_both_rome_timezones_and_late_runs(self):
        text=policy_text()
        crons=re.findall(r"^\s+- cron: '(\d+) (\d+) \* \* 1-5'$",
                         text,re.MULTILINE)
        self.assertEqual({(int(h),int(m)) for m,h in crons},
                         {(21,15),(21,45),(22,15),(22,45)})
        rome=ZoneInfo("Europe/Rome")
        for day in ((2026,7,20),(2026,11,16)):
            times=[]
            for m,h in crons:
                instant=datetime(*day,int(h),int(m),tzinfo=timezone.utc)
                local=instant.astimezone(rome)
                times.append((local.hour,local.minute))
            self.assertTrue(any((hour,minute)==(23,15) for hour,minute in times))
            self.assertTrue(any((hour,minute)==(23,45) for hour,minute in times))

    def test_every_admitted_run_rechecks_official_Cboe_freshness(self):
        workflow=policy_text()
        fetch=CANDIDATE.read_text(encoding="utf-8")
        self.assertIn("validation/fetch_cboe_vix_candidate_v2.py",workflow)
        self.assertIn("candidate.outputs.status == 'UPDATE_AVAILABLE'",workflow)
        self.assertIn("candidate.outputs.status == 'NO_CHANGE'",workflow)
        self.assertIn("business_day_lag",workflow)
        self.assertIn("max_business_day_lag",workflow)
        self.assertIn("if lag > max_lag:",fetch)
        self.assertIn("cfg['source_url']",fetch)
        self.assertIn("'GREEN_OFFICIAL_SOURCE_CANDIDATE'",fetch)

    def test_latest_close_append_is_anchored_and_idempotent(self):
        workflow=policy_text()
        apply=APPLY.read_text(encoding="utf-8")
        self.assertIn("anchor not in source",apply)
        self.assertIn("anchor mismatch runtime=",apply)
        self.assertIn("day > anchor",apply)
        self.assertIn("other_risk_keys_preserved",workflow)
        self.assertIn("git restore --source=HEAD --worktree -- live_data payload",workflow)
        self.assertIn("git push --force-with-lease=refs/heads/main:$BASE",workflow)
        self.assertIn("test \"$(git rev-parse origin/main)\" = \"$BASE\"",workflow)

    def test_postapply_certification_runs_after_successful_main_persistence(self):
        post=(ROOT/".github/workflows/vix-postapply-certification-v1.yml").read_text(
            encoding="utf-8")
        self.assertIn("workflow_run:",post)
        self.assertIn("'VIX Persistent Apply V1'",post)
        self.assertIn("types: [completed]",post)
        self.assertIn("github.event.workflow_run.conclusion == 'success'",post)
        self.assertIn("github.event.workflow_run.head_branch == 'main'",post)
        self.assertIn("git cat-file -e \"$DATA_COMMIT^\"",post)
        self.assertIn("v['last_date']==c['latest_date']",post)
        self.assertIn("VIX_POSTAPPLY_IDEMPOTENCE_PASS",post)
        self.assertIn("fetch-depth: 0",post)

    def test_no_early_source_lag_check_bypass(self):
        source=CANDIDATE.read_text(encoding="utf-8")
        apply=APPLY.read_text(encoding="utf-8")
        self.assertIn("max_business_day_lag_vs_price",source)
        self.assertIn("unexpected VIX max business-day lag policy",source)
        self.assertIn("runtime_anchor_date",apply)
        self.assertIn("non-VIX risk data changed unexpectedly",apply)


if __name__=="__main__":
    unittest.main()
