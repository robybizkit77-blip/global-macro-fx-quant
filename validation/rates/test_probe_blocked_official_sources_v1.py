#!/usr/bin/env python3
"""Exact-source, no-promotion and negative transport-fixture tests."""
import datetime as dt
import io
import json
import urllib.error
from zoneinfo import ZoneInfo
from probe_blocked_official_sources_v1 import SOURCES,build,classify,probe

ROME=ZoneInfo("Europe/Rome")
assert len(SOURCES)==3
assert all(url.startswith("https://data.snb.ch/") or url.startswith("https://www.rbnz.govt.nz/")
           for url,kind in SOURCES.values())
assert "lastUpdate" in SOURCES["CHF_SNB_LATEST_UPDATE"][0]
assert "hb2-daily-close.xlsx" in SOURCES["NZD_RBNZ_B2_OFFICIAL_XLSX"][0]
assert classify(code=403,kind="xlsx")=="ACCESS_BLOCKED"
assert classify(code=429,kind="metadata")=="SOURCE_UNREACHABLE_OR_THROTTLED"
assert classify(code=404,kind="html")=="OFFICIAL_RESOURCE_NOT_FOUND"
assert classify(code=None,error="TimeoutError",kind="metadata")=="SOURCE_UNREACHABLE_OR_THROTTLED"
assert classify(code=200,content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                prefix=b"PK\x03\x04test",kind="xlsx")=="REACHABLE_UNVERIFIED_CONTENT"
assert classify(code=200,content_type="text/html",prefix=b"<html>blocked</html>",kind="xlsx")=="UNEXPECTED_FORMAT"
assert classify(code=200,content_type="application/json",prefix=b'{"lastUpdate":"2026-10-01"}',
                kind="metadata")=="REACHABLE_UNVERIFIED_CONTENT"
assert classify(code=200,content_type="text/html",prefix=b'<!doctype html><html>',
                kind="html")=="REACHABLE_UNVERIFIED_CONTENT"
assert classify(code=200,content_type="text/html",prefix=b"<html>broken</html>",
                kind="metadata")=="UNEXPECTED_FORMAT"

class FakeResponse:
    def __init__(self,code,ctype,data):
        self.status=code
        self.headers={"Content-Type":ctype}
        self.data=io.BytesIO(data)
    def __enter__(self):return self
    def __exit__(self,*a):self.data.close()
    def read(self,n):return self.data.read(n)

def available(req,timeout):
    assert timeout <= 12
    u=req.full_url
    assert u.startswith("https://data.snb.ch/") or u.startswith("https://www.rbnz.govt.nz/")
    if "/lastUpdate" in u: return FakeResponse(200,"application/json",b'{"lastUpdate":"2026-10-01"}')
    if u.endswith(".xlsx"): return FakeResponse(200,"application/octet-stream",b"PK\x03\x04hello")
    return FakeResponse(200,"text/html",b"<!doctype html><html>Official source only</html>")

def blocked(req,timeout):
    u=req.full_url
    if u.endswith(".xlsx"):
        raise urllib.error.HTTPError(u,403,"Forbidden",{"Content-Type":"text/html"},None)
    if "/lastUpdate" in u:
        raise urllib.error.URLError("offline")
    return FakeResponse(200,"text/html",b"<html><body>official page</body></html>")

now=dt.datetime(2026,10,23,12,30,tzinfo=ROME)
a=build(available,now)
b=build(blocked,now)
assert a["schema"]=="GMFQ_OFFICIAL_BLOCKED_RATES_ACCESS_V1"
assert len(a["results"])==3
assert all(r["access"]=="REACHABLE_UNVERIFIED_CONTENT" for r in a["results"].values())
assert b["results"]["CHF_SNB_LATEST_UPDATE"]["access"]=="SOURCE_UNREACHABLE_OR_THROTTLED"
assert b["results"]["NZD_RBNZ_B2_OFFICIAL_XLSX"]["access"]=="ACCESS_BLOCKED"
assert b["results"]["NZD_RBNZ_B2_PUBLIC_TABLE"]["access"]=="REACHABLE_UNVERIFIED_CONTENT"
for report in (a,b):
    assert report["probe_status"]=="EVIDENCE_ONLY"
    assert report["core_model_effect"]=="NONE"
    for r in report["results"].values():
        assert r["eligible_for_automatic_promotion"] is False
        assert r["source_2y_10y_verified"] is False
        assert r["effect_on_rates"]=="NONE"
        assert r["effect_on_macro"]=="NONE"
        assert not any(k in r for k in ("2Y","10Y","values","observations"))
        assert r["url"].startswith("https://")
    # Must be serializable as audit evidence and not contain downloaded bodies.
    assert len(json.dumps(report)) < 4000
print("OFFICIAL_BLOCKED_RATES_PROBE_NO_PROMOTION_PASS")
