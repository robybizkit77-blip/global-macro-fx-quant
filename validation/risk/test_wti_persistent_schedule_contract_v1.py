#!/usr/bin/env python3
"""WTI regression: delayed GitHub cron runs must fetch official EIA, never silently skip."""
from __future__ import annotations
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
WORKFLOW=ROOT/".github/workflows/wti-persistent-rebuild-v1.yml"
POST=ROOT/".github/workflows/wti-postapply-certification-v1.yml"
EIA=ROOT/"validation/fetch_eia_direct_wti_candidate_v1.py"
APPLY=ROOT/"validation/apply_eia_direct_wti_candidate_v1.py"


class WTIScheduleTests(unittest.TestCase):
    def test_all_delayed_schedule_runs_fetch_eia(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        gate=text.split("      - name: Admit delayed EIA checks",1)[1].split(
            "      - name: Regression-test delayed EIA checks",1)[0]
        self.assertIn("echo 'should_run=true'",gate)
        self.assertNotIn("should_run=false",gate)
        self.assertNotIn("00:15 00:45",gate)
        self.assertIn("WTI_SCHEDULER_ADMISSION_PASS",gate)
        self.assertIn("validation/fetch_eia_direct_wti_candidate_v1.py",text)
        self.assertIn("Install XLS reader",text)
        self.assertIn("candidate.outputs.status == 'NO_CHANGE'",text)
        self.assertIn("candidate.outputs.status == 'UPDATE_AVAILABLE'",text)

    def test_daytime_saturday_recovery_and_cet_cest(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        cron=re.findall(r"^\s+- cron: '(\d+) (\d+) \* \* 1-6'$",text,re.MULTILINE)
        self.assertEqual({(int(h),int(m)) for m,h in cron},{(7,45),(12,45)})
        rome=ZoneInfo("Europe/Rome")
        for day,expected in [
            ((2026,10,24),[(9,45),(14,45)]),
            ((2026,11,21),[(8,45),(13,45)]),
        ]:
            seen=sorted((datetime(*day,int(h),int(m),tzinfo=timezone.utc)
                         .astimezone(rome).hour,
                         datetime(*day,int(h),int(m),tzinfo=timezone.utc)
                         .astimezone(rome).minute) for m,h in cron)
            self.assertEqual(seen,expected)
        self.assertIn("WTI_EIA_SOURCE_PUBLICATION_PENDING",text)
        self.assertIn("WTI_RUNTIME_ALREADY_CURRENT",text)

    def test_canonical_source_and_guarded_wti_only_apply(self):
        fetch=EIA.read_text(encoding="utf-8")
        apply=APPLY.read_text(encoding="utf-8")
        workflow=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("RWTCd.xls",fetch)
        self.assertIn("'U.S. Energy Information Administration'",fetch)
        self.assertIn("'RWTC'",fetch)
        self.assertIn("source_dates != sorted(source_dates)",apply)
        self.assertIn("'overlap_mismatch_count'",apply)
        self.assertIn("non-WTI risk data changed unexpectedly",apply)
        self.assertIn("git push --force-with-lease=refs/heads/main:$BASE",workflow)
        self.assertIn('test "$(git rev-parse origin/main)" = "$BASE"',workflow)
        self.assertIn("git restore --source=HEAD --worktree -- live_data payload",workflow)

    def test_independent_postapply_chain(self):
        post=POST.read_text(encoding="utf-8")
        self.assertIn("workflow_run:",post)
        self.assertIn("'WTI Persistent Rebuild V1'",post)
        self.assertIn("types: [completed]",post)
        self.assertIn("github.event.workflow_run.conclusion == 'success'",post)
        self.assertIn("github.event.workflow_run.head_branch == 'main'",post)
        self.assertIn("w['last_date']==c['last_date']==dates[-1]",post)
        self.assertIn("WTI_POSTAPPLY_IDEMPOTENCE_PASS",post)
        self.assertIn("fetch-depth: 0",post)


if __name__=="__main__":
    unittest.main()
