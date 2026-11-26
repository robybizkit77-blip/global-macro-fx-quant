"""Prospective V2 uniform-normalization research cohort, never a live signal.

Separate from original and Quality-Aware V1 cohorts. No historical backfill.
The current Quality-Aware freeze provides the same-day official ECB anchors;
all its source hashes must still match the checkout before new features freeze.
"""
from datetime import date, datetime, timezone
import json
from pathlib import Path
import subprocess

from validation.forward.capture_v2_research_prospective_evidence_v1 import (
    ROOT, ROME, canonical, sha, file_sha, cutoff_valid,
)
from validation.forward.capture_v2_quality_aware_prospective_v1 import (
    JOURNAL as QUALITY_JOURNAL, SOURCE_PATHS, read_journal, verify_journal,
    validate_snapshot as validate_quality,
)
from validation.macro.v2_uniform_dispersion_comparison_v1 import (
    run as uniform_run, domestic_panel, POLICY,
)
from validation.macro.v2_current_activity_momentum_v1 import run as momentum_run

SCHEMA = "GMFQ_V2_UNIFORM_MACRO_PROSPECTIVE_RESEARCH_V1"
FIRST_DAY = date(2026, 11, 27)
JOURNAL = ROOT / "validation/forward/candidate_shadow_snapshots/V2_UNIFORM_MACRO_PROSPECTIVE_V1.jsonl"


def require(ok, reason):
    if not ok:
        raise ValueError("UNIFORM_MACRO_FREEZE_BLOCKED: "+reason)


def validate(row):
    require(row.get("schema")==SCHEMA and row.get("policy")==POLICY and
            row.get("snapshot_sha256")==sha({k:v for k,v in row.items() if k!="snapshot_sha256"}),
            "schema, policy or seal")
    stamp=datetime.fromisoformat(row["capture_at_utc"])
    require(stamp.tzinfo is not None and stamp.utcoffset() is not None, "aware timestamp")
    local=stamp.astimezone(ROME)
    require(local.date()>=FIRST_DAY and local.weekday()<5 and local.hour>=19
            and row["local_date_rome"]==local.date().isoformat(), "invalid cohort date")
    anchor=row["quality_anchor"]
    require(validate_quality(anchor)==row["local_date_rome"], "same-day official anchor")
    require(datetime.fromisoformat(anchor["capture_at_utc"].replace("Z","+00:00"))<=stamp,
            "anchor captured after new features")
    u=row["uniform_research"]
    m=row["momentum_research"]
    require(u["as_of"]==m["as_of"]==row["local_date_rome"], "source cutoff")
    require(u["policy"]==POLICY and not u["safe_to_publish_D"]
            and not u["safe_to_update_pairs"] and not u["safe_for_beta_forward"]
            and not u["writes_live_data"] and not m["writes_live_data"],
            "unexpected source promotion")
    require(u["domestic_panel_RESEARCH_ONLY"]==domestic_panel({**u["rows"],**u["growth_rows"]}),
            "domestic formula not reproducible")
    require(set(m["countries"])==set(anchor["economic_observations"]), "momentum coverage")
    require(all(row.get(k) is False for k in ("historical_PIT_certified","prediction_made",
            "eligible_for_trading","can_feed_existing_H1","future_outcomes_observed")),
            "forbidden predictive claim")
    head=row["source_git_head"]
    require(isinstance(head,str) and len(head)==40 and all(c in "0123456789abcdef" for c in head),
            "source commit identity")
    return row["local_date_rome"]


def verify(rows):
    seen=set()
    for row in rows:
        day=validate(row)
        require(day not in seen,"duplicate cohort date")
        seen.add(day)
    return seen


def attempt(*, now, dry_run=False, path=JOURNAL):
    stamp, day=cutoff_valid(now,now)
    if date.fromisoformat(day)<FIRST_DAY:
        return {"status":"NOT_BEFORE_NEW_COHORT","date":day}
    if day in verify(read_journal(path)):
        return {"status":"EXISTING_UNIFORM_DATE_NO_OVERWRITE","date":day}
    anchors=read_journal(QUALITY_JOURNAL)
    if day not in verify_journal(anchors):
        return {"status":"BLOCKED_NO_SAME_DAY_QUALITY_ANCHOR","date":day}
    anchor=next(r for r in anchors if r["local_date_rome"]==day)
    current_hashes=lambda:{k:file_sha(p) for k,p in SOURCE_PATHS.items()}
    before=current_hashes()
    if before!=anchor["source_file_sha256"]:
        return {"status":"BLOCKED_SOURCE_CHANGED_SINCE_QUALITY_ANCHOR","date":day}
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    u,m=uniform_run(),momentum_run()
    require(before==current_hashes(),"source changed during freeze")
    body={"schema":SCHEMA,"policy":POLICY,"local_date_rome":day,
          "capture_at_utc":stamp.isoformat(),"source_git_head":head,
          "quality_anchor":anchor,"uniform_research":u,"momentum_research":m,
          "historical_PIT_certified":False,"prediction_made":False,
          "eligible_for_trading":False,"can_feed_existing_H1":False,
          "future_outcomes_observed":False}
    body["snapshot_sha256"]=sha(body)
    validate(body)
    if not dry_run:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("ab") as f:
            f.write(canonical(body))
    return {"status":"UNIFORM_RESEARCH_FREEZE_DRY_RUN" if dry_run else "UNIFORM_RESEARCH_FREEZE_APPENDED",
            "date":day,"snapshot_sha256":body["snapshot_sha256"]}


if __name__=="__main__":
    print(json.dumps(attempt(now=datetime.now(timezone.utc)),sort_keys=True))
