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
    vals = dim_lookup(dim)
    for code, label in vals:
        s = (code + " " + label).lower()
        if all(p in s for p in predicates):
            return code, label
    return None


def main():
    meta, meta_url = fetch({"lang":"en","sinceTimePeriod":"2024-01"})
    dims = meta["dimension"]
    geo = pick_code(dims["geo"], ["euro area"])
    unit = None
    for cand in (["annual","rate"],["annual rate"],["rch_a"]):
        unit = pick_code(dims["unit"], cand)
        if unit: break
    coid = "coicop18" if "coicop18" in dims else "coicop"
    service = pick_code(dims[coid], ["services"])
    if not (geo and unit and service):
        raise SystemExit(f"Could not resolve dimensions geo={geo} unit={unit} service={service} coid={coid}")
    params = {"lang":"en","geo":geo[0],"unit":unit[0],coid:service[0],"sinceTimePeriod":"2024-01"}
    data, data_url = fetch(params)
    tdim = data["dimension"]["time"]["category"]
    tidx = tdim["index"]
    times = tidx if isinstance(tidx, list) else [k for k,v in sorted(tidx.items(), key=lambda kv: kv[1])]
    values = data.get("value", {})
    rows=[]
    for i,t in enumerate(times):
        v = values.get(str(i)) if isinstance(values, dict) else values[i]
        if v is not None:
            rows.append({"reference_month":t,"annual_rate_pct":v,"dataset":DATASET,"geo_code":geo[0],"service_code":service[0],"unit_code":unit[0]})
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    audit={
      "schema":"GMFQ_EUR_HICP_SERVICES_PIT_MATERIALIZATION_V1",
      "status":"PASS" if rows else "FAIL",
      "created_at":str(date.today()),
      "source":"Eurostat HICP first published data",
      "dataset":DATASET,
      "resolved_dimensions":{"geo":geo,"unit":unit,"classification_dimension":coid,"services":service},
      "rows":len(rows),
      "first_reference_month": rows[0]["reference_month"] if rows else None,
      "last_reference_month": rows[-1]["reference_month"] if rows else None,
      "pit_policy":"Uses Eurostat first-published HICP dataset only; no revised-history substitution.",
      "metadata_url":meta_url,
      "query_url":data_url,
      "changes_engine_rules":False,
      "changes_live_data":False,
      "threshold_tuning":False
    }
    os.makedirs(os.path.dirname(OUT_JSON),exist_ok=True)
    with open(OUT_JSON,"w",encoding="utf-8") as f: json.dump(audit,f,indent=2)
    print(json.dumps(audit,indent=2))
    if not rows: sys.exit(1)

if __name__ == "__main__": main()
