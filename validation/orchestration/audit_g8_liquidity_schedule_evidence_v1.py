"""Read-only scheduled execution evidence for the 24 G8 research channels.
A successful run is not proof of a new release or public HTTP delivery.
Never dispatch, modify feeds, or promote FX inputs.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import json
import os
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
# File, channel count, relevant collector paths, essential production steps.
SPECS=[
 ("us-h8-bank-credit-research-refresh-v1.yml","USD",3,["liquidity/refresh_us_h8_bank_credit_fred_v1.py"],["Collect Fed H8 bank credit, SLOOS and M2 via FRED"]),
 ("ecb-eur-nfc-credit-research-refresh-v1.yml","EUR",3,["liquidity/refresh_ecb_eur_nfc_credit_v1.py","liquidity/probe_ecb_eur_bls_actual_v1.py"],["Fetch ECB BSI NFC credit and ILM excess liquidity (research-only)","Verify official ECB BLS actual enterprise series and historical overlap"]),
 ("boe-gbp-reserves-research-refresh-v1.yml","GBP",1,["liquidity/refresh_boe_gbp_reserves_v1.py"],["Fetch BoE official weekly reserve balances as separate research"]),
 ("boe-gbp-secured-credit-research-refresh-v1.yml","GBP",2,["liquidity/refresh_boe_gbp_secured_credit_v1.py"],["Fetch exact BoE secured credit and corporate credit availability survey"]),
 ("boj-jpy-bank-credit-research-refresh-v1.yml","JPY",2,["liquidity/refresh_boj_jpy_bank_credit_research_v1.py","fetch_boj_jpy_bank_credit_candidate.py"],["Fetch existing official BoJ MD11 exact-series verified candidate"]),
 ("jpy-reserve-balances-proxy-refresh-v1.yml","JPY",1,["estimated/refresh_jpy_reserve_balances_proxy_v1.py"],["Refresh JPY reserve-balances official proxy"]),
 ("chf-residual-proxy-refresh-v1.yml","CHF",3,["estimated/refresh_chf_residual_proxies_v1.py"],["Refresh CHF official residual proxies"]),
 ("cad-business-credit-official-research-refresh-v1.yml","CAD",3,["liquidity/refresh_boc_cad_business_credit_v1.py"],["Fetch issuer credit, Lynx balances and SLOS with guarded research-only apply"]),
 ("rba-aud-business-credit-growth-research-refresh-v1.yml","AUD",2,["liquidity/refresh_rba_aud_business_credit_growth_v1.py"],["Download latest RBA Financial Aggregates release and validate adjusted growth"]),
 ("rba-aud-es-balances-research-refresh-v1.yml","AUD",1,["liquidity/refresh_rba_aud_es_balances_v1.py"],["Fetch weekly RBA balance-sheet ES reserves as source-isolated research"]),
 ("fx-next-rbnz-liquidity.yml","NZD",3,["publishing/collect_next_rbnz_liquidity.py"],["Refresh official D10, C50 and C60 data"]),
]
GRACE=timedelta(hours=2)
def dt(s):
    return datetime.fromisoformat(s.replace("Z","+00:00"))

def latest_due(cron, now):
    minute,hour,dom,month,dow=cron.split()
    if dom!="*" or month!="*":
        raise ValueError("Unsupported cron")
    days=set(range(7)) if dow=="*" else set()
    for part in ([] if dow=="*" else dow.split(",")):
        if "-" in part:
            a,b=map(int,part.split("-"));days.update(range(a,b+1))
        else:days.add(int(part))
    cutoff=now-GRACE
    for n in range(8):
        x=(cutoff-timedelta(days=n)).replace(hour=int(hour),minute=int(minute),second=0,microsecond=0)
        if x<=cutoff and (x.weekday()+1)%7 in days:return x
    raise ValueError("No due slot")

def latest_due_for_crons(crons, now):
    if not crons or len(set(crons)) != len(crons):
        raise ValueError("Missing or duplicate UTC cron")
    return max(latest_due(cron, now) for cron in crons)


def assess(run, jobs, required, due, changed, version_ok):
    if not run or dt(run["created_at"])<max(due,changed):
        return "WAIT_NEXT_SLOT_AFTER_CHANGE" if due<changed else "MISSING_RECENT_SCHEDULE"
    if run.get("event")!="schedule" or run.get("head_branch")!="main":
        return "NOT_SCHEDULED_MAIN"
    if run.get("status")!="completed":return "SCHEDULE_IN_PROGRESS"
    if run.get("conclusion")!="success":return "SCHEDULE_FAILED"
    if not version_ok:return "SOURCE_VERSION_NOT_PROVEN"
    executed={s["name"] for j in jobs if j.get("conclusion")=="success"
              for s in j.get("steps",[]) if s.get("status")=="completed" and s.get("conclusion")=="success"}
    if not set(required)<=executed:return "ACQUISITION_STEP_NOT_PROVEN"
    return "RECENT_SCHEDULE_STEPS_OBSERVED"

def api(endpoint):
    return json.loads(subprocess.check_output(["gh","api","--method","GET",endpoint],text=True,timeout=25))

def inspect(spec, now, repo):
    file,ccy,count,paths,required=spec
    out={"workflow":file,"currency":ccy,"channels":count}
    try:
        workflow=".github/workflows/"+file
        text=(ROOT/workflow).read_text()
        crons=re.findall(r"cron:\s*['\"]([^'\"]+)['\"]",text)
        due=latest_due_for_crons(crons,now)
        from urllib.parse import urlencode
        versions=[]
        for path in [workflow]+["validation/"+p for p in paths]:
            query=urlencode({"sha":"main","path":path,"per_page":1})
            commit=api(f"repos/{repo}/commits?{query}")[0]
            versions.append((dt(commit["commit"]["committer"]["date"]),commit["sha"]))
        changed=max(x[0] for x in versions)
        runs=api(f"repos/{repo}/actions/workflows/{file}/runs?branch=main&event=schedule&per_page=5")["workflow_runs"]
        run=max(runs,key=lambda x:x["created_at"]) if runs else None
        out.update(cron_utc=crons[0] if len(crons)==1 else crons,latest_due_after_grace=due.isoformat(),latest_relevant_change=changed.isoformat())
        jobs=[];version_ok=False
        if run:
            out.update(run_id=run["id"],run_url=run["html_url"],created_at=run["created_at"],run_started_at=run.get("run_started_at"),conclusion=run.get("conclusion"))
            if dt(run["created_at"])>=max(due,changed) and run.get("conclusion")=="success" and run.get("event")=="schedule":
                version_ok=all(api(f"repos/{repo}/compare/{sha}...{run['head_sha']}")["status"] in ("ahead","identical") for _,sha in versions)
                jobs=api(f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
            out["hours_after_reference_slot"]=round((dt(run["created_at"])-due).total_seconds()/3600,2)
        out["status"]=assess(run,jobs,required,due,changed,version_ok)
    except (OSError,ValueError,KeyError,IndexError,TypeError,subprocess.SubprocessError) as exc:
        out.update(status="EVIDENCE_UNAVAILABLE",error=str(exc)[:240])
    return out

def selftest():
    assert sum(s[2] for s in SPECS)==24 and len(SPECS)==11
    now=dt("2026-11-24T17:30:00Z")
    due=latest_due("39 8 * * 4,5",now)
    assert due==dt("2026-11-20T08:39:00Z")
    assert latest_due("23 2 * * *",now)==dt("2026-11-24T02:23:00Z")
    assert latest_due("51 6 * * 1-5",dt("2026-11-23T07:00:00Z"))==dt("2026-11-20T06:51:00Z")
    ecb_crons=["23 7 * * 1-5","23 11 * * 1-5"]
    assert latest_due_for_crons(ecb_crons,dt("2026-11-27T07:36:00Z"))==dt("2026-11-26T11:23:00Z")
    assert latest_due_for_crons(ecb_crons,dt("2026-11-27T10:00:00Z"))==dt("2026-11-27T07:23:00Z")
    assert latest_due_for_crons(ecb_crons,dt("2026-11-27T13:30:00Z"))==dt("2026-11-27T11:23:00Z")
    base={"created_at":now.isoformat(),"event":"schedule","head_branch":"main","status":"completed","conclusion":"success"}
    job={"conclusion":"success","steps":[{"name":"acquire","status":"completed","conclusion":"success"}]}
    assert assess(base,[job],["acquire"],due,due,True)=="RECENT_SCHEDULE_STEPS_OBSERVED"
    assert assess(base,[],["acquire"],due,due,True)=="ACQUISITION_STEP_NOT_PROVEN"
    assert assess(base,[job],["acquire"],due,due,False)=="SOURCE_VERSION_NOT_PROVEN"
    assert assess(dict(base,event="push"),[job],["acquire"],due,due,True)=="NOT_SCHEDULED_MAIN"
    assert assess(dict(base,conclusion="failure"),[],["acquire"],due,due,True)=="SCHEDULE_FAILED"
    assert assess(None,[],["acquire"],due,now,False)=="WAIT_NEXT_SLOT_AFTER_CHANGE"
    assert assess(None,[],["acquire"],due,due,False)=="MISSING_RECENT_SCHEDULE"
    print("G8_LIQUIDITY_SCHEDULE_EVIDENCE_SELFTEST_PASS")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if args.selftest:return selftest()
    now=datetime.now(timezone.utc);repo=os.environ["GITHUB_REPOSITORY"]
    rows=[inspect(spec,now,repo) for spec in SPECS]
    observed=sum(x["channels"] for x in rows if x["status"]=="RECENT_SCHEDULE_STEPS_OBSERVED")
    report={"checked_at_utc":now.isoformat(),"producers":rows,"channels_with_recent_scheduled_step_evidence":observed,
            "status":"ALL_PRODUCER_STEPS_OBSERVED" if observed==24 else "SCHEDULE_EVIDENCE_INCOMPLETE",
            "scope":"Execution only. Not proof of per-lane successful source receipts, fresh release, exact cron slot identity, punctuality, or public delivery."}
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
    summary=os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary,"a") as f:
            f.write(f"\n## G8 liquidity schedule evidence: {observed}/24 associated channels\n\n"+report["scope"]+"\n\n")
            for row in rows:f.write(f"- {row['currency']} / {row['workflow']}: **{row['status']}** — {row.get('run_url','no run')}\n")
if __name__=="__main__":main()
