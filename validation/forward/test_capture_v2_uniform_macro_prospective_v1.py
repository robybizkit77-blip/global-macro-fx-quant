import copy
from datetime import date, datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from validation.forward import capture_v2_uniform_macro_prospective_v1 as mod
from validation.forward.test_capture_v2_quality_aware_prospective_v1 import (
    QualityAwareProspectiveCaptureTests as QA,
)

class UniformFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QA.setUpClass()
        cls.anchor=QA().make()
        cls.now=QA.now+timedelta(seconds=10)
        cls.u=mod.uniform_run()
        cls.m=mod.momentum_run()
        cls.u["as_of"]=cls.m["as_of"]=QA.day

    def test_pre_registration_no_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"ledger.jsonl"
            r=mod.attempt(now=datetime.fromisoformat("2026-11-26T20:00:00+01:00"),path=path)
            self.assertEqual(r["status"],"NOT_BEFORE_NEW_COHORT")
            self.assertFalse(path.exists())

    def test_new_freeze_no_overwrite_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"ledger.jsonl"
            with patch.object(mod,"FIRST_DAY",date.fromisoformat(QA.day)), \
                 patch.object(mod,"read_journal",side_effect=lambda p:
                    [self.anchor] if p==mod.QUALITY_JOURNAL else
                    ([__import__("json").loads(x) for x in p.read_text().splitlines()] if p.exists() else [])), \
                 patch.object(mod,"file_sha",return_value="a"*64), \
                 patch.object(mod.subprocess,"check_output",return_value="b"*40), \
                 patch.object(mod,"uniform_run",return_value=self.u), \
                 patch.object(mod,"momentum_run",return_value=self.m):
                r=mod.attempt(now=self.now,path=path,dry_run=True)
                self.assertEqual(r["status"],"UNIFORM_RESEARCH_FREEZE_DRY_RUN")
                self.assertFalse(path.exists())
                r=mod.attempt(now=self.now,path=path)
                self.assertEqual(r["status"],"UNIFORM_RESEARCH_FREEZE_APPENDED")
                before=path.read_bytes()
                self.assertEqual(mod.attempt(now=self.now,path=path)["status"],
                                 "EXISTING_UNIFORM_DATE_NO_OVERWRITE")
                self.assertEqual(path.read_bytes(),before)
                row=mod.read_journal(path)[0]
                self.assertEqual(mod.validate(row),QA.day)
                for key in ("prediction_made","eligible_for_trading","can_feed_existing_H1"):
                    bad=copy.deepcopy(row)
                    bad[key]=True
                    bad["snapshot_sha256"]=mod.sha({k:v for k,v in bad.items() if k!="snapshot_sha256"})
                    with self.assertRaises(ValueError):
                        mod.validate(bad)
                with self.assertRaises(ValueError):
                    mod.verify([row,row])

    def test_source_change_blocks(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(mod,"FIRST_DAY",date.fromisoformat(QA.day)), \
             patch.object(mod,"read_journal",side_effect=lambda p: [self.anchor] if p==mod.QUALITY_JOURNAL else []), \
             patch.object(mod,"file_sha",return_value="c"*64):
            path=Path(tmp)/"ledger.jsonl"
            self.assertEqual(mod.attempt(now=self.now,path=path)["status"],
                             "BLOCKED_SOURCE_CHANGED_SINCE_QUALITY_ANCHOR")
            self.assertFalse(path.exists())
