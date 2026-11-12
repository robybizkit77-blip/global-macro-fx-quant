#!/usr/bin/env python3
"""Prove DST, daily source refresh and quota-aware eolas vendor eligibility."""
from __future__ import annotations
import datetime as dt
import unittest
from fxv2_chf_nzd_schedule_gate_v1 import gate, MORNING_CEST, MORNING_CET, LATER_SOURCE_SLOTS

def utc(y, m, d, hh, mm):
    return dt.datetime(y,m,d,hh,mm,tzinfo=dt.timezone.utc)

class SourceScheduleGate(unittest.TestCase):
    def test_summer_valid_0630_only(self):
        self.assertEqual(gate("schedule",MORNING_CEST,utc(2026,10,19,4,30)),
                         (True,False,"ROME_0630_PREOPEN_SOURCE_REFRESH"))
        self.assertEqual(gate("schedule",MORNING_CET,utc(2026,10,19,5,30)),
                         (False,False,"DUPLICATE_DST_SLOT"))

    def test_winter_valid_0630_only(self):
        self.assertEqual(gate("schedule",MORNING_CET,utc(2026,11,5,5,30)),
                         (True,True,"ROME_0630_PREOPEN_SOURCE_REFRESH"))
        self.assertEqual(gate("schedule",MORNING_CEST,utc(2026,11,5,4,30)),
                         (False,False,"DUPLICATE_DST_SLOT"))

    def test_dst_transition_first_business_days(self):
        self.assertTrue(gate("schedule",MORNING_CEST,utc(2027,3,29,4,31))[0])
        self.assertTrue(gate("schedule",MORNING_CET,utc(2026,10,26,5,31))[0])
        self.assertFalse(gate("schedule",MORNING_CET,utc(2027,3,29,5,31))[0])

    def test_delayed_cron_still_captures_and_only_one_vendor_attempt(self):
        self.assertEqual(gate("schedule",MORNING_CET,utc(2026,11,5,8,47)),
                         (True,True,"ROME_0630_PREOPEN_SOURCE_REFRESH"))
        for cron in LATER_SOURCE_SLOTS:
            accepted, vendor, reason = gate("schedule",cron,utc(2026,11,5,19,0))
            self.assertTrue(accepted)
            self.assertFalse(vendor)
            self.assertEqual(reason,"LATER_OFFICIAL_SOURCE_RETRY")

    def test_weekends_invalid_schedule_and_explicit_dispatch_allowed(self):
        self.assertEqual(gate("schedule",MORNING_CET,utc(2026,11,7,5,30)),
                         (False,False,"NOT_A_ROMAN_WORKDAY"))
        self.assertEqual(gate("workflow_dispatch","",utc(2026,11,7,5,30)),
                         (True,False,"EVENT_OR_MANUAL_SOURCE_REFRESH"))
        self.assertEqual(gate("workflow_dispatch","",utc(2026,11,7,5,30),eolas_pro=True),
                         (True,True,"EVENT_OR_MANUAL_SOURCE_REFRESH"))
        self.assertEqual(gate("pull_request","",utc(2026,11,7,5,30)),
                         (True,False,"EVENT_OR_MANUAL_SOURCE_REFRESH"))
        self.assertEqual(gate("push","",utc(2026,11,7,5,30)),
                         (True,False,"EVENT_OR_MANUAL_SOURCE_REFRESH"))
        self.assertEqual(gate("schedule","0 0 * * 1-5",utc(2026,11,5,7,30)),
                         (False,False,"UNKNOWN_SCHEDULE_SLOT"))


    def test_free_eolas_budget_still_runs_official_sources_daily(self):
        import calendar
        for year in (2026,2027,2028):
            for month in range(1,13):
                eligible=0
                for day in range(1,calendar.monthrange(year,month)[1]+1):
                    local=dt.date(year,month,day)
                    if local.weekday()>=5: continue
                    # Check source refresh daily and only Tue/Thu vendor.
                    is_cest = 4 <= month <= 9
                    if month in (3,10): continue  # DST-specific tests below
                    hour=4 if is_cest else 5
                    cron=MORNING_CEST if is_cest else MORNING_CET
                    refresh,vendor,_=gate("schedule",cron,utc(year,month,day,hour,30))
                    self.assertTrue(refresh)
                    self.assertEqual(vendor,local.weekday() in (1,3))
                    eligible+=int(vendor)
                self.assertLessEqual(eligible,10)

    def test_eolas_paid_plan_daily_opt_in(self):
        self.assertEqual(gate("schedule",MORNING_CEST,utc(2026,10,19,4,30),eolas_pro=True),
                         (True,True,"ROME_0630_PREOPEN_SOURCE_REFRESH"))
        self.assertEqual(gate("schedule",MORNING_CET,utc(2026,10,19,5,30),eolas_pro=True),
                         (False,False,"DUPLICATE_DST_SLOT"))
        self.assertEqual(gate("schedule",MORNING_CET,utc(2026,11,6,5,30),eolas_pro=True),
                         (True,True,"ROME_0630_PREOPEN_SOURCE_REFRESH"))
        for cron in LATER_SOURCE_SLOTS:
            self.assertFalse(gate("schedule",cron,utc(2026,11,6,19,0),eolas_pro=True)[1])

    def test_workflow_preopen_contract_and_vendor_limit(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github/workflows/fxv2-chf-nzd-benchmark-research.yml").read_text()
        for name in (MORNING_CEST, MORNING_CET):
            self.assertIn("cron: '" + name + "'", workflow)
        self.assertIn("id: gate", workflow)
        self.assertIn("EOLAS_PRO_ENABLED:",workflow)
        self.assertIn("steps.gate.outputs.should_run == 'true'", workflow)
        self.assertIn("VENDOR_SLOT: ${{ steps.gate.outputs.vendor_slot }}", workflow)
        self.assertIn("--upstream-source-verified",workflow)
        self.assertIn("steps.parent_rates.outputs.source_verified",workflow)
        self.assertIn("actions: read",workflow)
        self.assertIn("certify_rates_parent_source_execution_v1.py",workflow)
        self.assertIn('if [ "$VENDOR_SLOT" != "true" ]; then', workflow)
        self.assertIn("report_fxv2_chf_nzd_freshness_v1.py", workflow)
        self.assertIn("fxv2-chf-nzd-freshness-receipt.json", workflow)

    def test_successful_same_day_main_rates_recovers_without_paid_vendor(self):
        parent = {
            "upstream_name": "Rates Persistent Daily V1",
            "upstream_branch": "main",
            "upstream_conclusion": "success",
            "upstream_event": "workflow_run",
            "upstream_started_at": "2026-11-05T07:10:21Z",
            "upstream_source_verified": True,
        }
        self.assertEqual(
            gate("workflow_run", "", utc(2026,11,5,8,32), **parent),
            (True, False, "INDEPENDENT_SUCCESSFUL_MAIN_RATES_RECOVERY"))
        self.assertEqual(
            gate("workflow_run", "", utc(2026,11,5,5,15), **dict(
                parent, upstream_started_at="2026-11-05T04:50:00Z")),
            (False, False, "BEFORE_MORNING_LOCAL_SLOT"))
        self.assertEqual(
            gate("workflow_run", "", utc(2026,7,2,6,24), **dict(
                parent, upstream_started_at="2026-07-02T05:01:00Z")),
            (True, False, "INDEPENDENT_SUCCESSFUL_MAIN_RATES_RECOVERY"))

    def test_green_rates_without_real_source_steps_is_never_recovery(self):
        parent = {
            "upstream_name": "Rates Persistent Daily V1",
            "upstream_branch": "main",
            "upstream_conclusion": "success",
            "upstream_event": "workflow_run",
            "upstream_started_at": "2026-11-12T10:54:54Z",
        }
        self.assertEqual(gate("workflow_run", "", utc(2026,11,12,10,55),**parent),
                         (False,False,"PARENT_RATES_SOURCE_NOT_EXECUTED"))
        self.assertEqual(gate("workflow_run","",utc(2026,11,12,10,55),
                              **dict(parent,upstream_source_verified=False)),
                         (False,False,"PARENT_RATES_SOURCE_NOT_EXECUTED"))
        self.assertEqual(gate("workflow_run","",utc(2026,11,12,10,55),
                              **dict(parent,upstream_source_verified=True)),
                         (True,False,"INDEPENDENT_SUCCESSFUL_MAIN_RATES_RECOVERY"))

    def test_recovery_rejects_failure_pr_stale_weekend_and_future(self):
        parent = {
            "upstream_name": "Rates Persistent Daily V1",
            "upstream_branch": "main",
            "upstream_conclusion": "success",
            "upstream_event": "schedule",
            "upstream_started_at": "2026-11-05T07:10:21Z",
            "upstream_source_verified": True,
        }
        for field, value in (
            ("upstream_name","Other workflow"),
            ("upstream_branch","feature/fix"),
            ("upstream_conclusion","failure"),
            ("upstream_event","pull_request"),
        ):
            with self.subTest(field=field):
                bad = dict(parent, **{field:value})
                self.assertEqual(
                    gate("workflow_run","",utc(2026,11,5,8,32),**bad),
                    (False,False,"UNTRUSTED_OR_FAILED_RATES_PARENT"))
        for value in ("2026-11-04T07:10:21Z", "2026-11-06T07:10:21Z"):
            self.assertEqual(
                gate("workflow_run","",utc(2026,11,5,8,32),**dict(
                    parent,upstream_started_at=value)),
                (False,False,"PARENT_OUTSIDE_CURRENT_ROME_DAY"))
        for value in ("invalid", "", "2026-11-05T07:10:21"):
            self.assertEqual(
                gate("workflow_run","",utc(2026,11,5,8,32),**dict(
                    parent,upstream_started_at=value)),
                (False,False,"UNVERIFIED_PARENT_START_TIME"))
        self.assertEqual(
            gate("workflow_run","",utc(2026,11,7,8,32),**dict(
                parent,upstream_started_at="2026-11-07T07:10:21Z")),
            (False,False,"NOT_A_ROMAN_WORKDAY"))

    def test_rated_recovery_is_wired_and_vendor_retries_not_duplicated(self):
        from pathlib import Path
        workflow=(Path(__file__).resolve().parents[2] /
                  ".github/workflows/fxv2-chf-nzd-benchmark-research.yml").read_text()
        self.assertIn("workflows: ['Rates Persistent Daily V1']",workflow)
        self.assertIn("types: [completed]",workflow)
        for argument in ("--upstream-name", "--upstream-branch",
                         "--upstream-conclusion", "--upstream-event",
                         "--upstream-started-at"):
            self.assertIn(argument,workflow)
        self.assertIn("VENDOR_SLOT: ${{ steps.gate.outputs.vendor_slot }}", workflow)

    def test_reject_naive_clock_and_early_run(self):
        with self.assertRaisesRegex(ValueError, "aware"):
            gate("schedule",MORNING_CET,dt.datetime(2026,11,5,5,30))
        self.assertEqual(gate("schedule",MORNING_CET,utc(2026,11,5,4,20)),
                         (False,False,"BEFORE_MORNING_LOCAL_SLOT"))

if __name__=="__main__":
    unittest.main()
