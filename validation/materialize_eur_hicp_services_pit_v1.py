import csv, json, os, sys, urllib.parse, urllib.request
from datetime import date

DATASET = "prc_hicp_fpd"
API = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{DATASET}"
OUT_CSV = "history/pit_v1/EUR_HICP_SERVICES_FIRST_PUBLISHED_2024_2026.csv"
OUT_JSON = "validation/EUR_HICP_SERVICES_PIT_MATERIALIZATION_2026-10-06.json"


def fetch(params):
    url = API + "?" + urllib.parse.urlencode(params, doseq=True)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r), url


def dim_lookup(dim):
    cat = dim["category"]
    idx = cat.get("index", {})
    label = cat.get("label", {})
    if isinstance(idx, list):
        return [(v, label.get(v, v)) for v in idx]
    return sorted(((code, label.get(code, code)) for code, pos in idx.items()), key=lambda x: idx[x[0]])


def pick_code(dim, predicates):
    for code, label in dim_lookup(dim):
        s = (code + " " + label).lower()
        if all(p in s for p in predicates):
            return code, label
    return None


def extract_rows(data, geo_code, service_code):
    tcat = data.get("dimension", {}).get("time", {}).get("category", {})
    tidx = tcat.get("index", {})
    if not tidx:
        return []
    times = tidx if isinstance(tidx, list) else [k for k,v in sorted(tidx.items(), key=lambda kv: kv[1])]
    values = data.get("value", {})
    rows=[]
    for i,t in enumerate(times):
        v = values.get(str(i)) if isinstance(values, dict) else (values[i] if i < len(values) else None)
        if v is not None:
            rows.append({
                "reference_month": t,
                "annual_rate_pct": v,
                "dataset": DATASET,
                "geo_code": geo_code,
                "service_code": service_code,
                "unit_code": "RCH_A"
            })
    return rows


def main():
    # Use EA only for compact dimension discovery. Values may be stored under
    # composition-specific euro-area codes (EA20 through 2025, EA21 from 2026).
    meta, meta_url = fetch({"lang":"en","geo":"EA","unit":"RCH_A","sinceTimePeriod":"2024-01"})
    dims = meta["dimension"]
    coid = "coicop18" if "coicop18" in dims else "coicop"
    service = pick_code(dims[coid], ["services"])
    if not service:
        raise SystemExit(f"Could not resolve services aggregate in {coid}")

    geo_candidates = ["EA20", "EA21", "EA", "U2"]
    queried=[]
    raw_rows=[]
    for geo_code in geo_candidates:
        params={"lang":"en","geo":geo_code,"unit":"RCH_A",coid:service[0],"sinceTimePeriod":"2024-01"}
        try:
            data, url = fetch(params)
        except Exception as exc:
            queried.append({"geo":geo_code,"url":API,"error":repr(exc),"rows":0})
            continue
        rows=extract_rows(data, geo_code, service[0])
        queried.append({"geo":geo_code,"url":url,"rows":len(rows)})
        raw_rows.extend(rows)

    # Canonical changing-composition euro area: EA20 for reference months <= 2025-12,
    # EA21 from 2026-01. Fallback to EA/U2 only if composition-specific code absent.
    by_month={}
    priority={"EA20":0,"EA21":0,"EA":1,"U2":2}
    for r in raw_rows:
        m=r["reference_month"]
        expected="EA21" if m >= "2026-01" else "EA20"
        score=0 if r["geo_code"] == expected else 10 + priority.get(r["geo_code"],9)
        if m not in by_month or score < by_month[m][0]:
            by_month[m]=(score,r)
    rows=[by_month[m][1] for m in sorted(by_month)]
    if not rows:
        raise SystemExit(f"No first-published EUR services observations returned; service={service}; queries={queried}")

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

    audit={
      "schema":"GMFQ_EUR_HICP_SERVICES_PIT_MATERIALIZATION_V1",
      "status":"PASS",
      "created_at":str(date.today()),
      "source":"Eurostat HICP first published data",
      "dataset":DATASET,
      "resolved_dimensions":{"unit":["RCH_A","Annual rate of change"],"classification_dimension":coid,"services":service},
      "geo_policy":"EA20 through 2025-12; EA21 from 2026-01; EA/U2 only fallback if needed",
      "queries":queried,
      "rows":len(rows),
      "first_reference_month":rows[0]["reference_month"],
      "last_reference_month":rows[-1]["reference_month"],
      "pit_policy":"Uses Eurostat first-published HICP dataset only; no revised-history substitution.",
      "metadata_url":meta_url,
      "changes_engine_rules":False,
      "changes_live_data":False,
      "threshold_tuning":False
    }
    os.makedirs(os.path.dirname(OUT_JSON),exist_ok=True)
    with open(OUT_JSON,"w",encoding="utf-8") as f: json.dump(audit,f,indent=2)
    print(json.dumps(audit,indent=2))

if __name__ == "__main__": main()
