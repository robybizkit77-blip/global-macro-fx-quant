#!/usr/bin/env python3
import json, re, urllib.request
from pathlib import Path
from datetime import datetime

OUT=Path("validation/pit_batch/fed_g17")
OUT.mkdir(parents=True, exist_ok=True)

REVH="https://www.federalreserve.gov/releases/g17/Current/ipdisk/revh_sa.txt"
DATES="https://www.federalreserve.gov/releases/G17/release_dates.htm"

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GMFQ-validation/1.0"})
    with urllib.request.urlopen(req,timeout=120) as r:
        return r.read().decode("utf-8","replace")

def parse_series(txt,key):
    rows={}
    pat=re.compile(r'^"'+re.escape(key)+r'"\s+(\d{4})\s+(.+)$',re.M)
    for m in pat.finditer(txt):
        y=int(m.group(1))
        vals=[]
        for t in m.group(2).split():
            vals.append(None if t.lower()=="na" else float(t))
        for idx,v in enumerate(vals[:12],1):
            rows[f"{y:04d}-{idx:02d}"]=v
    return rows

def previous_month(ym):
    y,m=map(int,ym.split("-"))
    if m==1: return f"{y-1:04d}-12"
    return f"{y:04d}-{m-1:02d}"

revh=get(REVH)
init=parse_series(revh,"init.b50001.s")
rev1=parse_series(revh,"rev1.b50001.s")

# First-release monthly percent change per Fed revision-history methodology:
# initial current-month level / first-revised prior-month level - 1.
first={}
for ym,v in init.items():
    pm=previous_month(ym)
    pv=rev1.get(pm)
    if v is not None and pv not in (None,0):
        first[ym]=100.0*(v/pv-1.0)

# Historical release dates. The Fed page labels each release by release month.
html=get(DATES)
# Robustly match strings such as "September 2021" and "15-September-2021".
pairs=re.findall(r'([A-Z][a-z]+)\s+(20(?:20|21|22|23|24|25|26))[^0-9]{0,80}(\d{1,2}-[A-Z][a-z]+-20\d{2})',html,re.S)
release_dates={}
for mon,yr,dstr in pairs:
    try:
        dt=datetime.strptime(dstr,"%d-%B-%Y")
    except ValueError:
        continue
    release_month=f"{dt.year:04d}-{dt.month:02d}"
    obs=previous_month(release_month)
    release_dates[obs]=dt.strftime("%Y-%m-%d")

# Fallback: the HTML may contain rows with date first and no nearby heading. Extract all 2020-26
# dates and use calendar month -> prior observation month. This is safe because this is the official
# historical release-date table for monthly G.17 releases; annual-revision duplicates are excluded
# by retaining at most one regular monthly date per month and preferring dates before day 25.
all_dates=[]
for dstr in re.findall(r'(\d{1,2}-[A-Z][a-z]+-20(?:20|21|22|23|24|25|26))',html):
    try: dt=datetime.strptime(dstr,"%d-%B-%Y")
    except ValueError: continue
    all_dates.append(dt)
for dt in all_dates:
    if dt.day>24: 
        continue
    rel=f"{dt.year:04d}-{dt.month:02d}"
    obs=previous_month(rel)
    release_dates.setdefault(obs,dt.strftime("%Y-%m-%d"))

rows=[]
for ym in sorted(first):
    if ym<"2020-01" or ym>"2026-08": continue
    rows.append({
      "observation_month":ym,
      "release_date":release_dates.get(ym),
      "first_release_mom_pct":round(first[ym],6),
      "initial_index_level":init.get(ym),
      "prior_month_rev1_index_level":rev1.get(previous_month(ym))
    })

report={
 "schema":"GMFQ_FED_G17_INDPRO_PIT_BATCH_V1",
 "created_at":"2026-10-02",
 "provider":"Federal Reserve G.17",
 "runtime_id":"US_INDPRO_history_value",
 "category":"Crescita",
 "source":{
   "revision_history":REVH,
   "historical_release_dates":DATES
 },
 "methodology":{
   "formula":"100 * (init[t] / rev1[t-1] - 1)",
   "market_availability":"Official G.17 historical monthly release date mapped to the prior observation month.",
   "no_lookahead":True
 },
 "rows":rows,
 "qa":{
   "rows_total":len(rows),
   "rows_with_release_date":sum(1 for r in rows if r["release_date"]),
   "rows_missing_release_date":[r["observation_month"] for r in rows if not r["release_date"]],
   "start":rows[0]["observation_month"] if rows else None,
   "end":rows[-1]["observation_month"] if rows else None
 }
}
(OUT/"FED_G17_INDPRO_PIT_BATCH_V1_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report["qa"],indent=2))
