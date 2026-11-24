#!/usr/bin/env python3
import copy
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from archive_nzd_asx_proxy_v1 import ARCHIVE, append, validate

rows=[validate(json.loads(line)) for line in ARCHIVE.read_text().splitlines() if line.strip()]
assert len({r["feed"]["as_of"] for r in rows})>=5
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/"archive.jsonl"
    p.write_bytes(ARCHIVE.read_bytes())
    before=p.read_bytes()
    feed=copy.deepcopy(rows[-1]["feed"])
    ts=datetime.fromisoformat(feed["generated_at_utc"])
    feed["generated_at_utc"]=(ts+timedelta(minutes=1)).isoformat()
    assert append(p,feed,True)["appended"]==0
    assert p.read_bytes()==before
    new=copy.deepcopy(feed)
    h=new["horizons"]["6m"]
    h["settlement_price"]=round(h["settlement_price"]+.01,4)
    h["implied_bank_bill_rate"]=round(100-h["settlement_price"],4)
    assert append(p,new,False)["would_append"]==1
    assert p.read_bytes()==before
    assert append(p,new,True)["appended"]==1
    assert p.read_bytes().startswith(before)
    assert append(p,new,True)["appended"]==0
    bad=copy.deepcopy(feed);bad["governance"]["substitutes_for_ois_level"]=True
    try:
        append(p,bad,True)
    except ValueError:
        pass
    else:
        raise AssertionError("Forbidden OIS promotion accepted")
print("NZD_ASX_CAPTURE_ARCHIVE_PASS")
