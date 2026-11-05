#!/usr/bin/env python3
"""Prevent FX Quant V2 gh-pages pushes during an active GitHub Pages deployment.

GitHub rejects overlapping Pages deployments with HTTP 400, even if the V2
publisher workflow itself is serialized. This source-only gate consults the
actual Pages-generated workflow runs before any new gh-pages writer runs.
It never treats a publisher checkout or push as a successful site deployment.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import time
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

ACTIVE = frozenset({"queued", "in_progress", "pending", "waiting", "requested"})
NAME = "pages build and deployment"
SCHEMA = "GMFQ_FXV2_GH_PAGES_IDLE_BEFORE_PUBLISH_V1"


def active_pages(runs: list[dict]) -> list[dict]:
    """Only actual Pages deployments for this repository's gh-pages branch."""
    return [
        {"id":r["id"], "status":r["status"],
         "created_at":r.get("created_at"), "head_sha":r.get("head_sha")}
        for r in runs
        if r.get("name") == NAME and r.get("head_branch") == "gh-pages"
        and r.get("status") in ACTIVE and isinstance(r.get("id"), int)
    ]


def await_idle(fetch_runs, sleep, *, attempts: int = 90, delay: int = 10) -> dict:
    """Two consecutive idle probes avoid transient queue propagation races.

    No branch writes occur while this gate is open. After it passes, the
    publisher re-fetches approved main and re-renders the V2-only output.
    """
    if attempts < 2 or delay < 1:
        raise ValueError("attempts >= 2 and delay >= 1 required")
    clean = 0
    last = []
    for i in range(attempts):
        last = active_pages(fetch_runs())
        clean = 0 if last else clean + 1
        print("FXV2_PAGES_DEPLOY_GUARD " + json.dumps({
            "attempt":i+1, "idle_streak":clean, "active_pages":last
        }), flush=True)
        if clean >= 2:
            return {"schema":SCHEMA, "status":"IDLE_VERIFIED",
                    "attempts":i+1, "active":[], "no_publication_claim":True}
        if i + 1 < attempts:
            sleep(delay)
    return {"schema":SCHEMA, "status":"BLOCKED_BY_ACTIVE_PAGES_DEPLOYMENT",
            "attempts":attempts, "active":last, "no_publication_claim":True}


def github_runs(repo: str, token: str) -> list[dict]:
    if not token or not repo or repo.count("/") != 1:
        raise ValueError("GitHub token/repository missing")
    url = "https://api.github.com/repos/" + repo + "/actions/runs?per_page=100"
    req = Request(url, headers={
        "Authorization":"Bearer " + token,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"FXV2-Pages-Deployment-Idle-Guard/1.0",
    })
    with urlopen(req, timeout=20) as resp:
        if resp.status != 200:
            raise RuntimeError("GitHub Actions API HTTP " + str(resp.status))
        body = json.load(resp)
    runs = body.get("workflow_runs")
    if not isinstance(runs, list):
        raise RuntimeError("GitHub Actions API missing workflow_runs")
    return runs


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--attempts", type=int, default=90)
    p.add_argument("--delay", type=int, default=10)
    a = p.parse_args()
    repo = os.environ.get("GH_REPO","")
    token = os.environ.get("GH_TOKEN","")
    result = await_idle(lambda: github_runs(repo,token),time.sleep,
                        attempts=a.attempts,delay=a.delay)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("FXV2_GH_PAGES_IDLE_RESULT "+json.dumps(result,ensure_ascii=False),flush=True)
    summary=os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary,"a",encoding="utf-8") as out:
            out.write("### GitHub Pages V2 collision guard\n")
            out.write("- "+result["status"]+" after "+str(result["attempts"])+" independent checks\n")
            out.write("- This proves **only idle Pages deployment queue**, not live data freshness or delivery.\n")
    return 0 if result["status"]=="IDLE_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
