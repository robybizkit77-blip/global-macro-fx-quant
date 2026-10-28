"""Offline conflict/recovery proof for Oct30 issuer-actual safe GitHub writer."""
from __future__ import annotations
import unittest
from datetime import datetime,timezone

from validation.macro.publish_oct30_official_actual_retry_v1 import (
    retry_transaction,MAX_ATTEMPTS,SCHEMA
)
from validation.macro.one_date_oct30_official_actual_fast_poll_gate_v1 import gate
from validation.macro.freeze_pre_release_consensus_v1 import LEDGER,read_existing
from validation.macro.capture_official_postrelease_actuals_v1 import OUT

class ActualPublicationRetryTests(unittest.TestCase):
    def test_one_conflict_rechecks_official_source_again_on_new_main(self):
        calls=[]
        def observe():
            calls.append("official_fetch")
            return {"new_actuals":1,"total_actuals":1}
        attempts=iter((False,True))
        def commit():
            calls.append("CAS_publish")
            return next(attempts)
        def reset():
            calls.append("reconcile_from_main")
        result=retry_transaction(observe,commit,reset)
        self.assertEqual(result["status"],"OFFICIAL_ACTUAL_RECORDED_ON_MAIN")
        self.assertTrue(result["published"])
        self.assertEqual(result["attempts"],2)
        self.assertEqual(calls,[
            "official_fetch","CAS_publish","reconcile_from_main",
            "official_fetch","CAS_publish"
        ])
        self.assertEqual(len(result["history"]),1)

    def test_main_already_has_actual_after_conflict_never_overwrites(self):
        calls=[]
        seen=iter(({"new_actuals":1},{"new_actuals":0}))
        def observe():
            calls.append("official_fetch")
            return next(seen)
        def commit():
            calls.append("CAS_publish")
            return False
        def reset():calls.append("reconcile_from_main")
        result=retry_transaction(observe,commit,reset)
        self.assertEqual(result["status"],"NO_NEW_OFFICIAL_ACTUAL_SOURCE")
        self.assertFalse(result["published"])
        self.assertEqual(result["attempts"],2)
        self.assertEqual(calls,[
            "official_fetch","CAS_publish","reconcile_from_main",
            "official_fetch"
        ])

    def test_fail_closed_after_three_remote_conflicts_not_forever(self):
        calls=[]
        def observe():
            calls.append("f")
            return {"new_actuals":1}
        def commit():
            calls.append("x")
            return False
        def reset():calls.append("r")
        with self.assertRaisesRegex(RuntimeError,
                                     "UNRESOLVED_AFTER_3_ATTEMPTS"):
            retry_transaction(observe,commit,reset)
        self.assertEqual(calls,["f","x","r","f","x","r","f","x"])
        self.assertEqual(calls.count("r"),2)

    def test_no_issuer_actual_means_no_news_pulse_rebuild_or_git_commit(self):
        calls=[]
        def observe():calls.append("f");return {"new_actuals":0}
        def blocked():
            raise AssertionError("no actual => no commit/no reset")
        result=retry_transaction(observe,blocked,blocked)
        self.assertEqual(result["status"],"NO_NEW_OFFICIAL_ACTUAL_SOURCE")
        self.assertEqual(result["attempts"],1)
        self.assertFalse(result["published"])
        self.assertEqual(calls,["f"])

    def test_single_attempt_only_and_no_invalid_retry_budget(self):
        for count in (0,4,-1,1.0,True):
            with self.assertRaises(ValueError):
                retry_transaction(lambda: {"new_actuals":1},
                                  lambda: True,lambda:None,attempts=count)
        result=retry_transaction(lambda: {"new_actuals":1},
                                  lambda:True,lambda:None,attempts=1)
        self.assertEqual(result["attempts"],1)

    def test_live_repo_event_clock_gate_before_oct30_does_not_download_or_write(self):
        before=LEDGER.read_bytes(),OUT.read_bytes()
        result=gate(read_existing(LEDGER),read_existing(OUT),
                    datetime(2026,10,28,10,30,tzinfo=timezone.utc))
        self.assertFalse(result["should_poll"])
        self.assertEqual(result["status"],"OUTSIDE_ONCE_ONLY_RELEASE_DAY")
        self.assertEqual(before,(LEDGER.read_bytes(),OUT.read_bytes()))

if __name__=="__main__":
    unittest.main()
