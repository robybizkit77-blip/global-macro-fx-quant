#!/usr/bin/env python3
"""Freeze first-seen macro data and the published shadow-model decision.

Appends a capture to research/g8-growth-prospective/observations/<Rome day>.json.
A capture is NOT an issuer first release or a point-in-time historical backtest.
No overwrite; no change to live_data, model, FX rankings, signals or reports.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
MACRO = "live_data/sections/MACRO_SERIES.json"
MODEL = "site/fx-quant-v2/next/g8-growth-shadow.js"
DIRECTORY = "research/g8-growth-prospective/observations"
FX = ("USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def get_git_snapshot(root: Path, revision: str) -> tuple[str, bytes, bytes]:
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", revision+"^{commit}"],
        cwd=root, text=True).strip()
    assert len(commit) == 40
    macro_bytes = subprocess.check_output(["git", "show", f"{commit}:{MACRO}"], cwd=root)
    model_bytes = subprocess.check_output(["git", "show", f"{commit}:{MODEL}"], cwd=root)
    return commit, macro_bytes, model_bytes


def execute_model(series_bytes: bytes, model_bytes: bytes, asof: str) -> dict:
    # Runs the exact JS used by the site; never reimplements its decisions.
    with tempfile.TemporaryDirectory(prefix="g8-snapshot-") as tmp:
        folder = Path(tmp)
        model_path, series_path = folder / "model.cjs", folder / "series.json"
        model_path.write_bytes(model_bytes)
        series_path.write_bytes(series_bytes)
        code = (
          "const fs=require('fs');"
          "const m=require(process.argv[1]);"
          "const series=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));"
          "process.stdout.write(JSON.stringify(m.analyze({macroSeries:series,now:process.argv[3]})));"
        )
        proc = subprocess.run(
            ["node", "-e", code, str(model_path), str(series_path), asof],
            text=True, capture_output=True, timeout=15, check=True)
        return json.loads(proc.stdout)


def selected_series(series: dict, model: dict, asof: str) -> dict:
    out = {}
    for ccy in FX:
        identity = model["currencies"][ccy].get("seriesId") or model.get("targets", {}).get(ccy, {}).get("id")
        # For failed models, read the fixed target from the published code's
        # result only if supplied; never select an unrelated series.
        # The default target IDs are explicit and locked for the first release.
        fixed = {
          "USD":"US_PCEC96_history_value","EUR":"EA_RETAIL_VOL_history_value",
          "GBP":"UK_RETAIL_VOL_history_value","JPY":"JP_RETAIL_history_value",
          "CHF":"CH_RETAIL_REAL_history_value","CAD":"CA_REAL_GDP_M_history_value",
          "AUD":"AU_REAL_GDP_QOQ_ABS_history_value","NZD":"NZ_REAL_GDP_Q_history_value"
        }[ccy]
        if identity is not None and identity != fixed:
            raise ValueError(f"Model-target mismatch {ccy}: {identity}")
        hits = [r for r in series.get(ccy, []) if r.get("id") == fixed]
        if len(hits) != 1:
            raise ValueError(f"Expected one canonical series for {ccy}: {fixed}")
        row = hits[0]
        dates, values = row.get("dates"), row.get("values")
        if not isinstance(dates, list) or not isinstance(values, list) or len(dates) != len(values):
            raise ValueError(f"Malformed {ccy} date/value observations")
        seen, observed = set(), []
        for d, v in zip(dates, values):
            period = d[:7] if isinstance(d, str) else ""
            if len(period) != 7 or period[4] != "-":
                raise ValueError(f"Malformed {ccy} observation period")
            if period > asof[:7]:
                # Keep the bytes and SHA of the full source in provenance.
                # No future record may enter the frozen information set.
                continue
            if period in seen:
                raise ValueError(f"Duplicate {ccy} historical period {period}")
            seen.add(period)
            if not isinstance(v,(int,float)) or isinstance(v,bool):
                raise ValueError(f"Non-numeric canonical observation {ccy} {period}")
            observed.append({"period": period, "value": v})
        if not observed:
            raise ValueError(f"No admissible {ccy} source observations")
        if [r["period"] for r in observed] != sorted(r["period"] for r in observed):
            raise ValueError(f"Nonmonotone {ccy} source history")
        out[ccy] = {"series_id":fixed,"series_label":row.get("label"),
                    "source":row.get("source_file"),"observations":observed,
                    "latest_observation_period":observed[-1]["period"],
                    "historical_vintage": "FIRST_SEEN_IN_THIS_SYSTEM_NOT_ISSUER_FIRST_RELEASE"}
    return out


def build_receipt(macro_bytes: bytes, model_bytes: bytes, commit: str,
                  capture_time: datetime) -> dict:
    if capture_time.tzinfo is None:
        raise ValueError("UTC-aware capture datetime required")
    utc = capture_time.astimezone(timezone.utc)
    rome = utc.astimezone(ZoneInfo("Europe/Rome"))
    asof = rome.date().isoformat()
    series = json.loads(macro_bytes)
    model = execute_model(macro_bytes, model_bytes, asof)
    if model.get("status") != "RESEARCH_ONLY_NOT_PIT" or model.get("schema") != "GMFQ_G8_GROWTH_SHADOW_V1":
        raise ValueError("Shadow model unexpectedly promoted to operational status")
    if set(model.get("currencies", {})) != set(FX):
        raise ValueError("Expected all 8 G8 shadow model outputs")
    freeze = selected_series(series, model, asof)
    for ccy in FX:
        result = model["currencies"][ccy]
        if result.get("quality") not in {"RETROSPECTIVE_NOT_POINT_IN_TIME","NOT_PIT"}:
            raise ValueError("Unqualified model result vintage "+ccy)
        if result.get("candidate"):
            target = result.get("nextObservationPeriod")
            if not target or target <= freeze[ccy]["latest_observation_period"]:
                raise ValueError("Forecast target must be strictly after latest known observation")
    return {
        "schema":"GMFQ_G8_GROWTH_PROSPECTIVE_CAPTURE_V1",
        "captured_at_utc":utc.isoformat().replace("+00:00","Z"),
        "captured_at_rome":rome.isoformat(),
        "capture_rome_date":asof,
        "source_main_commit":commit,
        "source_macro_sha256":sha256_bytes(macro_bytes),
        "source_model_sha256":sha256_bytes(model_bytes),
        "sources_are_versioned_at_capture": True,
        "issuer_release_vintage_verified":False,
        "issuer_release_timestamp_verified":False,
        "forecast_is_issuer_pre_release_certified":False,
        "model_is_operational":False,
        "affects_fx_rankings_or_signals":False,
        "forecast_evidence":model,
        "selected_macro_vintage":freeze,
        "notice":"Immutable first-seen GitHub snapshot at actual capture time, not an issuer release-vintage; source history may contain revisions prior to capture. Prospective evaluation starts only for forecasts whose target observations are not already in this capture."
    }


def github_json(method: str, url: str, token: str, payload: dict | None = None):
    headers={"Accept":"application/vnd.github+json",
             "Authorization":"Bearer "+token,
             "X-GitHub-Api-Version":"2026-03-10"}
    raw=json.dumps(payload,ensure_ascii=False).encode("utf-8") if payload is not None else None
    if raw:headers["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=raw,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=20) as resp:
            return resp.status,json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body=exc.read().decode("utf-8",errors="replace")
        if exc.code in (404,409,422):
            return exc.code,{"message":body[:500]}
        raise


def publish_once(receipt: dict, token: str, repo: str, expected_day: str) -> dict:
    capture_day=receipt["capture_rome_date"]
    if capture_day != expected_day or expected_day != datetime.now(ZoneInfo("Europe/Rome")).date().isoformat():
        raise ValueError("Publishing past-dated or future-dated forecasts is prohibited")
    if not token or not repo or "/" not in repo:
        raise ValueError("GitHub auth and repository identity required")
    relative=f"{DIRECTORY}/{capture_day}.json"
    url=f"https://api.github.com/repos/{repo}/contents/{relative}"
    status,existing=github_json("GET",url,token)
    if status==200:
        return {"status":"ALREADY_CAPTURED_IMMUTABLE","path":relative,
                "sha":existing.get("sha"),"wrote":False}
    if status!=404:
        raise RuntimeError(f"Unexpected GitHub existence check: {status}")
    encoded=base64.b64encode((json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode("utf-8")).decode("ascii")
    for attempt in range(3):
        status,result=github_json("PUT",url,token,{
           "message":f"Research-only G8 first-seen forecast capture {capture_day} [skip ci]",
           "content":encoded,"branch":"main"})
        if status in (200,201):
            return {"status":"CREATED_IMMUTABLE","path":relative,
                    "sha":result.get("content",{}).get("sha"),"wrote":True}
        if status not in (409,422):
            raise RuntimeError(f"GitHub append-only write failed: {status}")
        status,exists=github_json("GET",url,token)
        if status==200:
            return {"status":"ALREADY_CAPTURED_IMMUTABLE","path":relative,
                    "sha":exists.get("sha"),"wrote":False}
        if status!=404:
            raise RuntimeError(f"Unsafe retry: GET returned {status}")
        time.sleep(1+attempt)
    raise RuntimeError("GitHub write conflicts: no forecast capture published")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--revision",default="origin/main")
    parser.add_argument("--publish",action="store_true")
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    commit,macro,model=get_git_snapshot(ROOT,args.revision)
    receipt=build_receipt(macro,model,commit,now)
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(receipt,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
    q=receipt["forecast_evidence"]["qualified"]
    print("G8_CAPTURE_FIRST_SEEN_NOT_PIT",receipt["capture_rome_date"],"QUALIFIED",q)
    if args.publish:
        result=publish_once(receipt,os.environ.get("GITHUB_TOKEN",""),
                            os.environ.get("GITHUB_REPOSITORY",""),
                            now.astimezone(ZoneInfo("Europe/Rome")).date().isoformat())
        print("G8_CAPTURE_PUBLISH",json.dumps(result,sort_keys=True))
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
                f.write("\n### G8 prospective shadow forecast — first-seen record\n")
                f.write("- Result: **"+result["status"]+"**\n")
                f.write("- Path: \`"+result["path"]+"\`\n")
                f.write("- Research-only pseudo-OOS candidates: "+(", ".join(q) or "none")+"\n")
                f.write("- **Issuer first-release PIT NOT verified. No FX score or signal impact.**\n")


if __name__=="__main__":
    main()
