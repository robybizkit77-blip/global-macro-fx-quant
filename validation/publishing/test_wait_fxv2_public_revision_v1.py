#!/usr/bin/env python3
"""Deterministic deployment-race retry tests for FXV2 public browser gate."""
from validation.publishing.wait_fxv2_public_revision_v1 import PROBES,wait
import unittest
from collections import Counter

def entry(p,ok=True):
    return {"path":p,"http":200 if ok else 404,"status":"MATCH" if ok else "MISMATCH_OR_UNAVAILABLE",
            "expected_sha256":"a"*64,"public_sha256":"a"*64 if ok else "b"*64}

class DeployGate(unittest.TestCase):
    def test_read_public_exact_bytes_before_reporting_success(self):
        n=Counter();delays=[]
        def probe(p):
            n[p]+=1
            return entry(p,n[p]>=2)
        r=wait(probe,lambda x:delays.append(x),attempts=3)
        self.assertEqual(r["status"],"EXACT_PUBLIC_REVISION_MATCH")
        self.assertEqual(r["attempts"],2)
        self.assertEqual(r["matched"],len(PROBES))
        self.assertFalse(r["economic_freshness_certified"])
        self.assertEqual(delays,[9])
    def test_error_does_not_become_success(self):
        r=wait(lambda p:entry(p,False),lambda x:None,attempts=2)
        self.assertEqual(r["status"],"PUBLIC_REVISION_STILL_MISSING")
        self.assertEqual(len(r["unmatched"]),len(PROBES))
    def test_missing_one_surface_blocks_claim(self):
        r=wait(lambda p:entry(p,p!="ois.html"),lambda x:None,attempts=1)
        self.assertEqual([x["path"] for x in r["unmatched"]],["ois.html"])
    def test_empty_attempts_rejected(self):
        with self.assertRaises(ValueError):
            wait(lambda p:entry(p),lambda x:None,attempts=0)

if __name__=="__main__":
    unittest.main()
