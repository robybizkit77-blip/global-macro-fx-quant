#!/usr/bin/env python3
"""Candidate-only cross-asset data fetcher. Never writes live_data.
Uses public FRED CSV exports, with original CBOE/EIA attribution.
Run: python validation/build_market_risk_candidate.py --output /tmp/market-risk-candidate.json
"""
import argparse,csv,datetime as dt,io,json,urllib.request

SERIES={
 "VIX":{"id":"VIXCLS","source":"CBOE via FRED","unit":"index","max_age_days":5},
 "WTI":{"id":"DCOILWTICO","source":"U.S. EIA via FRED","unit":"USD/barrel","max_age_days":7},
}

def parse_csv(raw):
    rd=csv.DictReader(io.StringIO(raw))
    if not rd.fieldnames or rd.fieldnames[0] not in ("DATE","observation_date"):
        raise ValueError("unrecognized FRED CSV header")
    value_col=next((c for c in rd.fieldnames[1:] if c),None)
    if not value_col: raise ValueError("missing value column")
    rows=[]
    for row in rd:
        date=row[rd.fieldnames[0]]
        try:
            d=dt.date.fromisoformat(date)
            v=float(row[value_col])
            if not (-1e9<v<1e9):continue
            rows.append((d,v))
        except (ValueError,TypeError):continue
    return sorted(set(rows))

def build(fetch, today):
    result={"schema":"GMFQ_MARKET_RISK_CANDIDATE_V1","as_of":today.isoformat(),
            "status":"CANDIDATE_REQUIRES_VALIDATION","instruments":{}}
    for name,meta in SERIES.items():
        url=f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={meta['id']}"
        entry={"source":meta["source"],"series":meta["id"],"unit":meta["unit"],
               "url":url,"status":"WITHHELD"}
        try:
            rows=[r for r in parse_csv(fetch(url)) if r[0]<=today]
            if not rows:raise ValueError("no observations")
            last=rows[-1][0]; age=(today-last).days
            if age>meta["max_age_days"]:raise ValueError("stale observation")
            # Persist only genuine historical observations; do not forward fill.
            entry.update(status="CANDIDATE",date=last.isoformat(),value=rows[-1][1],
                         history=[{"date":d.isoformat(),"value":v} for d,v in rows[-260:]])
        except Exception as exc:
            entry["reason"]=type(exc).__name__+': '+str(exc)
        result["instruments"][name]=entry
    return result

def http_fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"GMFQ-risk-research/1.0"}),timeout=18) as response:
        return response.read().decode("utf-8-sig")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True);args=p.parse_args()
    candidate=build(http_fetch,dt.datetime.now(dt.timezone.utc).date())
    with open(args.output,"w",encoding="utf-8") as f:json.dump(candidate,f,indent=2)
    print(json.dumps({"status":candidate["status"],"instruments":{k:v["status"] for k,v in candidate["instruments"].items()}}))
