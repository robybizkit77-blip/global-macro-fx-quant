#!/usr/bin/env python3
import argparse
import json
import re
import urllib.request

ANCHORS = {
    "2019-01": {
        "url": "https://www.meti.go.jp/english/statistics/tyo/iip/b2015_201901se.html",
        "release_date": "2019-02-28",
        "release_time_jst": "08:50",
        "production_sa_index": 100.8,
    },
    "2020-01": {
        "url": "https://www.meti.go.jp/english/statistics/tyo/iip/b2015_202001se.html",
        "release_date": "2020-02-28",
        "release_time_jst": "08:50",
        "production_sa_index": 99.6,
    },
    "2023-01": {
        "url": "https://www.meti.go.jp/english/statistics/tyo/iip/b2015_202301se.html",
        "release_date": "2023-02-28",
        "release_time_jst": "08:50",
        "production_sa_index": 91.4,
    },
}

MONTH_NAMES = {
    1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
    7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"
}


def fetch(url):
    headers={
        "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language":"en-US,en;q=0.9,ja;q=0.7",
        "Referer":"https://www.meti.go.jp/english/statistics/tyo/iip/",
        "Cache-Control":"no-cache",
    }
    req=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(req,timeout=30) as r:
        raw=r.read().decode("utf-8","replace")
        status=getattr(r,"status",200)
    text=re.sub(r"<[^>]+>"," ",raw)
    text=re.sub(r"&nbsp;|&#160;"," ",text)
    text=re.sub(r"\s+"," ",text)
    return status,text


def parse(month,url):
    status,text=fetch(url)
    y,m=map(int,month.split("-"))
    month_name=MONTH_NAMES[m]
    rel=re.search(
        rf"Preliminary\s+report\s+for\s+{month_name}\s+{y}\s*\(released\s+at\s+(\d{{1,2}}:\d{{2}}),\s+([A-Za-z]+)\s+(\d{{1,2}}),\s+(\d{{4}})\)",
        text,re.I
    )
    prod=re.search(r"Production\s+([0-9]+(?:\.[0-9]+)?)\s+[-+0-9.]",text,re.I)
    release_date=None
    release_time=None
    if rel:
        release_time=rel.group(1).zfill(5)
        mon={v:k for k,v in MONTH_NAMES.items()}[rel.group(2).capitalize()]
        release_date=f"{int(rel.group(4)):04d}-{mon:02d}-{int(rel.group(3)):02d}"
    return {
        "reference_month":month,
        "source_url":url,
        "http_status":status,
        "release_date":release_date,
        "release_time_jst":release_time,
        "production_sa_index":float(prod.group(1)) if prod else None,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    rows=[]
    for month,exp in ANCHORS.items():
        r=parse(month,exp["url"])
        r["expected_anchor"]={k:v for k,v in exp.items() if k!="url"}
        r["anchor_match"]=(
            r["release_date"]==exp["release_date"] and
            r["release_time_jst"]==exp["release_time_jst"] and
            r["production_sa_index"]==exp["production_sa_index"]
        )
        rows.append(r)
    passed=all(r["http_status"]==200 and r["anchor_match"] for r in rows)
    out={
        "schema":"GMFQ_JPY_IIP_FIRST_RELEASE_FEASIBILITY_V1",
        "status":"PASS" if passed else "FAIL",
        "source":"METI Indices of Industrial Production archived Preliminary Reports",
        "series":"seasonally adjusted Production index",
        "rows":rows,
        "publication_timestamp_in_source":True,
        "revised_history_fallback_used":False,
        "growth_series_count":1,
        "pit_activation":False,
    }
    with open(args.output,"w",encoding="utf-8") as f:
        json.dump(out,f,indent=2,ensure_ascii=False); f.write("\n")
    print(json.dumps(out,indent=2,ensure_ascii=False))
    if not passed: raise SystemExit(1)

if __name__=="__main__":
    main()
