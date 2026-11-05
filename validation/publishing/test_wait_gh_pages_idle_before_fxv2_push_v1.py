#!/usr/bin/env python3
"""Offline contract for official Pages deployment-overlap guard."""
import unittest

from validation.publishing.wait_gh_pages_idle_before_fxv2_push_v1 import (
    ACTIVE, active_pages, await_idle
)


def run(id, *, name="pages build and deployment", branch="gh-pages",
        status="in_progress"):
    return {"id":id,"name":name,"head_branch":branch,"status":status,
            "head_sha":"a"*40}


class PagesIdleGuardTest(unittest.TestCase):
    def test_busy_pages_job_blocks_gh_pages_push(self):
        jobs=[[run(301)],[run(301,status="completed")],[]]
        checks=[]
        result=await_idle(lambda:jobs.pop(0),lambda secs:checks.append(secs),
                          attempts=3,delay=1)
        self.assertEqual(result["status"],"IDLE_VERIFIED")
        self.assertEqual(result["attempts"],3)
        self.assertEqual(checks,[1,1])

    def test_immediate_idle_requires_consecutive_probes(self):
        waits=[]
        r=await_idle(lambda:[],lambda secs:waits.append(secs),attempts=3,delay=1)
        self.assertEqual(r["status"],"IDLE_VERIFIED")
        self.assertEqual(r["attempts"],2)
        self.assertEqual(waits,[1])
        self.assertTrue(r["no_publication_claim"])

    def test_reappearing_queued_job_resets_idle_streak(self):
        jobs=[[],[run(12,status="queued")],[],[]]
        r=await_idle(lambda:jobs.pop(0),lambda _:None,attempts=4,delay=1)
        self.assertEqual(r["status"],"IDLE_VERIFIED")
        self.assertEqual(r["attempts"],4)

    def test_busy_timeout_fails_closed_not_green(self):
        r=await_idle(lambda:[run(55)],lambda _:None,attempts=3,delay=1)
        self.assertEqual(r["status"],"BLOCKED_BY_ACTIVE_PAGES_DEPLOYMENT")
        self.assertEqual(r["active"][0]["id"],55)
        self.assertTrue(r["no_publication_claim"])

    def test_other_workflows_and_branches_do_not_block(self):
        jobs=[run(1,branch="main"),run(2,name="FX Quant V2 Daily Browser QA"),
              run(3,status="completed"),run(4,status="queued"),
              run(5,status="waiting"),run(6,status="in_progress")]
        self.assertEqual([j["id"] for j in active_pages(jobs)],[4,5,6])
        self.assertIn("in_progress",ACTIVE)

    def test_bad_gate_limits_rejected(self):
        with self.assertRaises(ValueError):
            await_idle(lambda:[],lambda _:None,attempts=1)
        with self.assertRaises(ValueError):
            await_idle(lambda:[],lambda _:None,delay=0)

    def test_api_outage_fail_closed(self):
        def broken():raise RuntimeError("failed source")
        with self.assertRaisesRegex(RuntimeError,"failed source"):
            await_idle(broken,lambda _:None,attempts=2,delay=1)


if __name__=="__main__":
    unittest.main()
