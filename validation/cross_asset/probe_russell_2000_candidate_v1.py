"""Read-only candidate probe: no production or public feed writes."""
import datetime as dt
import json
import math
import urllib.request
from zoneinfo import ZoneInfo

URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5ERUT?interval=1d&range=3mo"

def parse(payload, cutoff):
    chart = payload["chart"]
    if chart.get("error") or len(chart.get("result") or []) != 1:
        raise ValueError("Chart response unavailable")
    item = chart["result"][0]
    meta = item["meta"]
    if meta.get("symbol") != "^RUT" or meta.get("instrumentType") != "INDEX" or meta.get("currency") != "USD":
        raise ValueError("Not the USD Russell 2000 cash index")
    if meta.get("exchangeTimezoneName") != "America/New_York" or meta.get("dataGranularity") != "1d":
        raise ValueError("Unexpected market timezone or granularity")
    stamps = item["timestamp"]
    closes = item["indicators"]["quote"][0]["close"]
    if len(stamps) != len(closes):
        raise ValueError("Timestamp/close length mismatch")
    rows = []
    for ts, value in zip(stamps, closes):
        day = dt.datetime.fromtimestamp(ts, ZoneInfo("America/New_York")).date()
        if day >= cutoff or value is None:
            continue  # do not treat the current New York session as final
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 100 < value < 10000 or day.weekday() >= 5:
            raise ValueError("Invalid closing observation")
        rows.append((day.isoformat(), round(value, 5)))
    if len(rows) < 10 or [x[0] for x in rows] != sorted(set(x[0] for x in rows)):
        raise ValueError("Insufficient or unordered closes")
    if (cutoff-dt.date.fromisoformat(rows[-1][0])).days > 6:
        raise ValueError("Source stale")
    # Independent Cboe published 2026-11-24 close, not an input to the series.
    check = dict(rows).get("2026-11-24")
    if check is None or abs(check - 2684.942) > 0.05:
        raise ValueError("Independent closing-level reconciliation failed")
    return rows

def main():
    req = urllib.request.Request(URL, headers={"User-Agent":"GMFQ research source feasibility probe", "Accept":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            if res.status != 200:
                raise ValueError("Unexpected HTTP status")
            raw = res.read(1000001)
        if len(raw) > 1000000:
            raise ValueError("Unexpected response size")
        rows = parse(json.loads(raw), dt.datetime.now(ZoneInfo("America/New_York")).date())
        print(json.dumps({"status":"CANDIDATE_SOURCE_VALIDATED","symbol":"^RUT","date":rows[-1][0],"value":rows[-1][1],"previous_date":rows[-2][0],"previous":rows[-2][1],"observations":len(rows),"independent_reference":"Cboe Nov 24, 2026","production_write":False,"redistribution_rights_verified":False}))
    except Exception as exc:
        print(json.dumps({"status":"CANDIDATE_SOURCE_NOT_VALIDATED","error":str(exc),"production_write":False}))
        raise SystemExit(1)

if __name__ == "__main__":
    main()
