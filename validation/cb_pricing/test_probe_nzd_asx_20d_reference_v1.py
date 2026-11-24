#!/usr/bin/env python3
import json
from probe_nzd_asx_20d_reference_v1 import probe,SOURCE
from collect_nzd_asx_directional_proxy_v1 import _report_url,_business_days_before
from datetime import date

feed=json.loads(SOURCE.read_text())
target=_business_days_before(date.fromisoformat(feed["as_of"]),20)
expected_url=_report_url(target)
def report(contracts):
    rows=["<tr><td>BB - 90 Day Bank Bill</td></tr>"]
    for label,price in contracts:
        cells=[label,"","","","",str(price),"0.00"]
        rows.append("<tr>"+"".join("<td>"+x+"</td>" for x in cells)+"</tr>")
    return "<table>"+"".join(rows)+"</table>"
contracts=[(p["expiry_label"],round(p["settlement_price"]+.1,4)) for p in feed["horizons"].values()]
def fetch(url):
    assert url==expected_url
    return report(contracts)
r=probe(feed,fetch)
assert r["status"]=="REFERENCE_PARSED"
assert r["reference_date"]==target.isoformat()
assert set(r["horizons"])==set(feed["horizons"])
assert all(x["change_bp"]==10 for x in r["horizons"].values())
assert not r["official_ois_created"]
def denied(url):
    raise OSError("fixture")
assert probe(feed,denied)["status"]=="REFERENCE_UNAVAILABLE"
ambiguous=probe(feed,lambda _:report(contracts+[contracts[1]]))
assert "6m" not in ambiguous["horizons"]
print("NZD_ASX_EXACT_20D_REFERENCE_PROBE_PASS")
