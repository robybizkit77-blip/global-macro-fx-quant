"""Recover missing Morning Macro/FX edition via the existing early-morning guard.

Never certify delivery from an Actions success badge. Check the *public*
edition, inspect active writer runs, and allow at most two manual recoveries.
This dispatcher cannot change macro scores, rates or FX pair rankings.
"""
from __future__ import annotations

from datetime import datetime, time
import json
import os
import subprocess
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
WORKFLOW = "fxv2-morning-public-proof.yml"
PUBLIC = ("https://robybizkit77-blip.github.io/global-macro-fx-quant/"
          "site/fx-quant-v2/next/morning-desk-current.json")
ACTIVE = {"queued", "in_progress", "requested", "waiting", "pending"}


def decide(now: datetime, public: dict | None, runs: list[dict]) -> dict:
    local = now.astimezone(ROME)
    today = local.date().isoformat()
    if local.weekday() >= 5 or not time(7, 10) <= local.time() < time(10, 45):
        return {"action": "SKIP_OUTSIDE_MORNING_WINDOW"}
    if (isinstance(public, dict) and public.get("schema") == "GMFQ_MORNING_MACRO_FX_V1"
            and public.get("edition_date") == today
            and public.get("observation_cutoff_exclusive") == today
            and public.get("edition_status") in {"MORNING_SNAPSHOT", "LATE_MORNING_SNAPSHOT"}):
        return {"action": "SKIP_CURRENT_PUBLIC_EDITION", "edition": today}
    today_runs = []
    for run in runs:
        try:
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")).astimezone(ROME)
        except (KeyError, ValueError, TypeError):
            continue
        if created.date().isoformat() == today and run.get("head_branch") == "main":
            today_runs.append(run)
    if any(r.get("status") in ACTIVE for r in today_runs):
        return {"action": "SKIP_EDITORIAL_WRITER_ACTIVE", "edition": today}
    recoveries = sum(r.get("event") == "workflow_dispatch" for r in today_runs)
    if recoveries >= 2:
        return {"action": "BLOCK_RECOVERY_LIMIT", "edition": today,
                "recoveries": recoveries}
    return {"action": "DISPATCH", "edition": today,
            "recoveries": recoveries, "public_date": public.get("edition_date") if isinstance(public, dict) else None}


def public_edition() -> dict | None:
    try:
        req = Request(PUBLIC + "?recovery=" + datetime.now(ROME).strftime("%Y%m%d%H%M%S"),
                      headers={"Cache-Control": "no-cache", "User-Agent": "FXQuantMorningRecovery/1.0"})
        with urlopen(req, timeout=15) as response:
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, TimeoutError):
        return None


def main() -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    now = datetime.now(ROME)
    # Do not query or dispatch anything outside the morning window.
    preliminary = decide(now, None, [])
    if preliminary["action"] == "SKIP_OUTSIDE_MORNING_WINDOW":
        decision = preliminary
    else:
        runs = json.loads(subprocess.check_output([
            "gh", "api", f"repos/{repo}/actions/workflows/{WORKFLOW}/runs?per_page=100"
        ], text=True, timeout=35))["workflow_runs"]
        decision = decide(now, public_edition(), runs)
        if decision["action"] == "DISPATCH":
            subprocess.run(["gh", "api", "--method", "POST",
                            f"repos/{repo}/actions/workflows/{WORKFLOW}/dispatches",
                            "-f", "ref=main"], check=True, timeout=35)
    print("MORNING_EDITORIAL_AUTORECOVERY", json.dumps(decision, sort_keys=True))
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
        summary.write("### Morning Macro/FX edition recovery\n")
        summary.write("- Decision: **" + decision["action"] + "**\n")
        if decision.get("edition"):
            summary.write("- Rome edition: " + decision["edition"] + "\n")


if __name__ == "__main__":
    main()
