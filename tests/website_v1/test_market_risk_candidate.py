import datetime as dt
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location("risk",Path(__file__).resolve().parents[2]/"validation"/"build_market_risk_candidate.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
today=dt.date(2026,10,18)
def sample(url):
    code="VIXCLS" if "VIXCLS" in url else "DCOILWTICO"
    return f"DATE,{code}\n2026-10-15,18.3\n2026-10-16,19.1\n"
r=mod.build(sample,today)
assert set(r["instruments"])=={"VIX","WTI"}
assert all(v["status"]=="CANDIDATE" and v["date"]=="2026-10-16" for v in r["instruments"].values())
r2=mod.build(lambda u:"DATE,VALUE\n2026-09-01,99.0\n",today)
assert all(v["status"]=="WITHHELD" for v in r2["instruments"].values())
r3=mod.build(lambda u:"DATE,VALUE\n2026-10-19,99.0\n",today)
assert all(v["status"]=="WITHHELD" for v in r3["instruments"].values())
print("PASS market risk candidate: fresh, stale, future-dated")
