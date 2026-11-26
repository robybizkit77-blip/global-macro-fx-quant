"""Read-only independent durability check for the new uniform Macro cohort.
A successful workflow or the prior Quality-Aware cohort is not proof of capture.
"""
from datetime import datetime, timezone
import json
from validation.forward.capture_v2_uniform_macro_prospective_v1 import (
    JOURNAL, FIRST_DAY, ROME, verify, read_journal,
)
from validation.forward.admit_frozen_core_prospective_capture_v1 import FX, PAIR, CORE, assess

def audit(now, fx, pair, core, rows):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware audit time required")
    local=now.astimezone(ROME)
    day=local.date().isoformat()
    base={"local_date_rome":day,"frozen_capture_dates":len(rows),
          "durable_uniform_capture":False,"predictive_skill_certified":False,
          "writes_live_data":False,"blocks_workflow":False}
    if local.date()<FIRST_DAY or local.weekday()>=5 or (local.hour,local.minute)<(21,15):
        return {**base,"status":"OUTSIDE_UNIFORM_ATTESTATION_WINDOW"}
    try:
        dates=verify(rows)
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError):
        return {**base,"status":"BLOCKED_UNIFORM_JOURNAL_INTEGRITY","blocks_workflow":True}
    if day in dates:
        row=next(x for x in rows if x["local_date_rome"]==day)
        return {**base,"status":"DURABLE_UNIFORM_RESEARCH_CAPTURE",
                "durable_uniform_capture":True,"snapshot_sha256":row["snapshot_sha256"]}
    admission=assess(now,fx,pair,core)
    return {**base,"status":"BLOCKED_UNIFORM_CAPTURE_MISSING" if not admission["checks"] else "UNIFORM_CAPTURE_NOT_ADMITTED",
            "admission_checks":admission["checks"],"blocks_workflow":not admission["checks"]}

if __name__=="__main__":
    r=audit(datetime.now(timezone.utc),json.loads(FX.read_text()),json.loads(PAIR.read_text()),
            json.loads(CORE.read_text()),read_journal(JOURNAL))
    print(json.dumps(r,sort_keys=True))
    raise SystemExit(2 if r["blocks_workflow"] else 0)
