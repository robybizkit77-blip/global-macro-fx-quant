#!/usr/bin/env python3
"""Complete the approved two-file daily Briefing PR after its existing QA."""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import time
from datetime import datetime, time as clock_time
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from validation.publishing.verify_pages_http_delivery_v1 import BASE_URL, verify

REPO = "robybizkit77-blip/global-macro-fx-quant"
PUBLISHER = REPO.split("/")[0]
QA_WORKFLOW = "FX Quant NEXT isolated design and interaction QA"
REPORTS = "site/fx-quant-v2/next/reports"
INDEX = f"{REPORTS}/daily-latest.json"
ROME = ZoneInfo("Europe/Rome")
REQUIRED_CHECKS = {
    "browser-qa", "contract", "research-coherence", "visual-qa",
    "v2-browser-audit", "v2-freshness-audit", "v2-working-rate-model-tests",
}


def api(path: str, body: dict | None = None) -> dict | list:
    command = ["gh", "api", f"repos/{REPO}/{path}"]
    if body is not None:
        command += ["--method", "PUT", "--input", "-"]
    result = subprocess.run(
        command, input=json.dumps(body) if body is not None else None,
        capture_output=True, text=True, check=True, timeout=25,
    )
    return json.loads(result.stdout)


def report_name(day: str) -> str:
    return f"Briefing_Forex_Commodities_{day}_V3_MORNING_RESEARCH_DESK.html"


def content(path: str, ref: str) -> bytes:
    item = api(f"contents/{path}?ref={ref}")
    if item["encoding"] != "base64":
        raise ValueError(f"Cannot verify exact file bytes for {path}")
    return base64.b64decode(item["content"])


def eligible_pr(pr: dict, run: dict) -> bool:
    return ((pr.get("state") == "open" or pr.get("merged")) and not pr.get("draft")
            and pr["base"]["ref"] == "main" and pr["base"]["repo"]["full_name"] == REPO
            and pr["head"]["repo"]["full_name"] == REPO
            and pr["user"]["login"] == PUBLISHER and pr["head"]["sha"] == run["head_sha"])


def scope_matches(files: list, name: str) -> bool:
    return len(files) == 2 and {
        (file["filename"], file["status"]) for file in files
    } == {(INDEX, "modified"), (f"{REPORTS}/{name}", "added")}


def check_status(checks: list) -> tuple[list[str], list[str]]:
    by_name = {check["name"]: check for check in checks
               if check.get("app", {}).get("slug") == "github-actions"}
    pending = []
    failed = []
    for name in sorted(REQUIRED_CHECKS):
        check = by_name.get(name)
        if check is None or check["status"] != "completed":
            pending.append(name)
        elif check["conclusion"] != "success":
            failed.append(name)
    return pending, failed


def pull_number(run: dict) -> int | None:
    # GitHub returned an empty pull_requests array on the 18 November browser run.
    refs = run.get("pull_requests") or []
    if len(refs) == 1:
        return refs[0]["number"]
    query = urlencode({"head": f"{PUBLISHER}:{run['head_branch']}", "base": "main", "state": "all"})
    matches = [pr["number"] for pr in api(f"pulls?{query}")
               if pr["head"]["sha"] == run["head_sha"]]
    return matches[0] if len(matches) == 1 else None


def finish(run: dict) -> str | None:
    if (run.get("name") != QA_WORKFLOW or run.get("event") != "pull_request"
            or run.get("conclusion") != "success"
            or run.get("head_repository", {}).get("full_name") != REPO):
        return None
    number = pull_number(run)
    if number is None:
        return None
    pr = api(f"pulls/{number}")
    if not eligible_pr(pr, run):
        return None
    today = datetime.now(ROME).date().isoformat()
    name = report_name(today)
    if pr.get("changed_files") != 2 or not scope_matches(api(f"pulls/{number}/files"), name):
        return None
    sha = run["head_sha"]
    if json.loads(content(INDEX, sha)) != {"file": name}:
        raise ValueError("Briefing index does not select the dated HTML")
    if not content(f"{REPORTS}/{name}", sha).strip():
        raise ValueError("Briefing HTML is empty")

    deadline = time.monotonic() + 240
    while True:
        pending, failed = check_status(api(f"commits/{sha}/check-runs?per_page=100")["check_runs"])
        if failed:
            raise ValueError(f"Briefing PR #{number} failed checks: {failed}")
        if not pending:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Briefing PR #{number} pending checks: {pending}")
        print(f"BRIEFING_QA_PENDING pr={number} checks={pending}", flush=True)
        time.sleep(10)

    # The producer or a duplicate event may already have merged the same PR.
    # Verify its exact index/blob and allow the existing publisher to continue.
    pr = api(f"pulls/{number}")
    if not pr.get("merged"):
        if not eligible_pr(pr, run):
            return None
        current_name = json.loads(content(INDEX, "main"))["file"]
        if current_name >= name:
            raise ValueError("The main index already selects this edition or a newer one")
        try:
            merged = api(f"pulls/{number}/merge", {"sha": sha, "merge_method": "squash"})
        except subprocess.CalledProcessError:
            if not api(f"pulls/{number}").get("merged"):
                raise
        else:
            if not merged.get("merged"):
                raise ValueError(f"Briefing PR #{number} was not merged")
    for path in (INDEX, f"{REPORTS}/{name}"):
        if content(path, "main") != content(path, sha):
            raise ValueError(f"Briefing merge did not preserve exact bytes at {path}")
    print(f"BRIEFING_MAIN_VERIFIED pr={number} checked_head={sha} file={name}", flush=True)
    return name


def verify_public(name: str) -> None:
    if name != report_name(datetime.now(ROME).date().isoformat()):
        raise ValueError("Refusing to certify a Briefing from a different day")
    if json.loads(Path(INDEX).read_bytes()) != {"file": name}:
        raise ValueError("Checked-out main does not select this Briefing")
    paths = (INDEX, f"{REPORTS}/{name}")
    for path in paths:
        published = subprocess.check_output(["git", "show", f"origin/gh-pages:{path}"])
        if published != Path(path).read_bytes():
            raise ValueError(f"Main and gh-pages differ at {path}")
    immediate = verify(Path.cwd(), BASE_URL, paths, budget_seconds=0, interval_seconds=8)
    if immediate["status"] != "PASS":
        # A GITHUB_TOKEN branch write can suppress the default build event.
        # Request the same Pages build endpoint already used by sidecar publishers.
        request = subprocess.run(
            ["gh", "api", "--method", "POST", f"repos/{REPO}/pages/builds"],
            capture_output=True, text=True, timeout=25,
        )
        if request.returncode:
            print(f"BRIEFING_PAGES_BUILD_REQUEST_NOT_ACCEPTED: {request.stderr[:250]}", flush=True)
        else:
            print("BRIEFING_PAGES_BUILD_REQUEST_ACCEPTED", flush=True)
    result = verify(
        Path.cwd(), BASE_URL, paths,
        budget_seconds=240, interval_seconds=8,
    ) if immediate["status"] != "PASS" else immediate
    verified = datetime.fromisoformat(result["verified_at_utc"]).astimezone(ROME)
    result["verified_at_rome"] = verified.isoformat()
    result["proved_by_0800"] = result["status"] == "PASS" and verified.time() <= clock_time(8)
    print("BRIEFING_PUBLIC_HTTP_PROOF", json.dumps(result, sort_keys=True), flush=True)
    if result["status"] != "PASS":
        raise SystemExit("Briefing index or HTML did not converge on public Pages")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-public")
    args = parser.parse_args()
    if args.verify_public:
        verify_public(args.verify_public)
        return
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())
    name = finish(event["workflow_run"])
    if name:
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
            print(f"briefing={name}", file=output)


if __name__ == "__main__":
    main()
