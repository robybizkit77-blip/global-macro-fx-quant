#!/usr/bin/env python3
"""Wait for public FXV2 GitHub Pages exact bytes before post-publish browser QA.

A successful repo push or publishing workflow isn't proof that the CDN serves
that revision. This tests bytes only, not the economic freshness of any source.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

from validation.publishing.check_fxv2_morning_public_v1 import fetch_one

# One atomic gh-pages V2 sync should serve exactly these canonical surfaces.
# This is a deployment gate, not a claim that the latest market sources exist.
# Check every navigable V2 page, not merely a subset. In particular tassi.html
# must match the served CDN revision before rate-provenance browser assertions.
# The CHF/NZD research sidecars must be from the same synced deployment.
PROBES=(
  "index.html","valute.html","coppie.html","tassi.html",
  "ois.html","macro.html","banche.html","cot.html",
  "cross-asset.html","liquidita-credito.html","calendario-news.html","research.html",
  "assets/pair-macro-observed-context-v1.js",
  "assets/liquidity-credit-feed-v1.js",
  "assets/rates-working-model-v1.js",
  "chf-nzd-benchmark-research.json",
  "chf-snb-paired-history.json",
  "nzd-asx-government-anchor-v1.json",
  "ois-pricing-snapshot.json",
  "pricing-relative-28pairs-research.json",
  "assets/ois-relative-parity-v1.js",
)
SCHEMA="GMFQ_FXV2_POST_PUBLISH_PUBLIC_REVISION_GATE_V1"

def wait(probe, pause, attempts=18):
    if attempts<1: raise ValueError("at least one attempt required")
    last=[]
    for i in range(attempts):
        with ThreadPoolExecutor(max_workers=6) as pool:
            rows=list(pool.map(probe,PROBES))
        mismatch=[r for r in rows if not (
            r.get("status")=="MATCH" and r.get("http")==200 and
            r.get("expected_sha256")==r.get("public_sha256"))]
        last=mismatch
        if not mismatch:
            return {"schema":SCHEMA,"status":"EXACT_PUBLIC_REVISION_MATCH",
                    "attempts":i+1,"matched":len(PROBES),"total":len(PROBES),
                    "economic_freshness_certified":False,"public_files_checked":rows}
        print("FXV2_PUBLIC_NOT_YET_CURRENT",json.dumps({
            "attempt":i+1,"mismatch_count":len(mismatch),
            "paths":[r.get("path") for r in mismatch],
        }),flush=True)
        if i+1<attempts: pause(9)
    return {"schema":SCHEMA,"status":"PUBLIC_REVISION_STILL_MISSING",
            "attempts":attempts,"matched":len(PROBES)-len(last),"total":len(PROBES),
            "economic_freshness_certified":False,"unmatched":last}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="fxv2-browser-evidence/public-revision.json")
    ap.add_argument("--attempts",type=int,default=18)
    args=ap.parse_args()
    report=wait(lambda p:fetch_one(p,attempts=1),time.sleep,args.attempts)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("FXV2_PUBLIC_REVISION_GATE",json.dumps({
       k:report[k] for k in ("status","attempts","matched","total")
    }))
    return 0 if report["status"]=="EXACT_PUBLIC_REVISION_MATCH" else 1

if __name__=="__main__":
    raise SystemExit(main())
