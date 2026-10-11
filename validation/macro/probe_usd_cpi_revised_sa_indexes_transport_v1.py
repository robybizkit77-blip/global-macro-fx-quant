#!/usr/bin/env python3
from __future__ import annotations
import argparse, io, json, pathlib, re, urllib.error, urllib.request, zipfile

# Annual BLS files preserve the recalculated five-year SA vintage published with January CPI.
YEARS = [2017, 2018, 2019, 2023, 2024, 2025]
BASE = "https://www.bls.gov/cpi/tables/seasonal-adjustment/revised-seasonally-adjusted-indexes-{year}.xlsx"
UA = "Mozilla/5.0 (compatible; GLOBAL-MACRO-FX-QUANT/1.0; research validation)"


def inspect(year: int) -> dict:
    url = BASE.format(year=year)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.1", "Connection":"close"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read(); status=getattr(r,"status",200); ctype=r.headers.get("Content-Type","")
    except urllib.error.HTTPError as e:
        return {"year":year,"url":url,"ok":False,"http_status":e.code,"error":repr(e)}
    except Exception as e:
        return {"year":year,"url":url,"ok":False,"error":repr(e)}
    out={"year":year,"url":url,"http_status":status,"content_type":ctype,"bytes":len(raw),"ok":False}
    try:
        z=zipfile.ZipFile(io.BytesIO(raw))
        texts=[]
        for name in z.namelist():
            if name.endswith('.xml') and (name.startswith('xl/worksheets/') or name=='xl/sharedStrings.xml'):
                texts.append(z.read(name).decode('utf-8',errors='replace'))
        blob=' '.join(texts)
        norm=re.sub(r'<[^>]+>',' ',blob)
        out.update({
            "xlsx_valid":True,
            "canonical_series_id_present": bool(re.search(r'CUSR0000SA0', norm, flags=re.I)),
            "all_items_present": bool(re.search(r'All items', norm, flags=re.I)),
            "seasonally_adjusted_present": bool(re.search(r'seasonally adjusted', norm, flags=re.I)),
            "xml_chars": len(blob),
        })
        out["ok"] = status==200 and out["xlsx_valid"]
    except Exception as e:
        out.update({"xlsx_valid":False,"parse_error":repr(e)})
    return out


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    rows=[inspect(y) for y in YEARS]
    transport_ok=all(r.get('ok') for r in rows)
    any_canonical=any(r.get('canonical_series_id_present') for r in rows)
    out={
        "schema":"GMFQ_USD_CPI_REVISED_SA_INDEX_FILES_TRANSPORT_V1",
        "status":"DISCOVERY_PASS" if transport_ok else "DISCOVERY_PARTIAL_OR_WITHHELD",
        "rows":rows,
        "transport_ok":transport_ok,
        "any_canonical_series_id_present":any_canonical,
        "authority":"U.S. Bureau of Labor Statistics",
        "purpose":"Test official archived annual revised seasonally-adjusted index workbooks as a keyless source for historical CPI SA vintages.",
        "certification_implied":False,
        "no_production_write":True
    }
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(out,indent=2,sort_keys=True))
    return 0

if __name__=='__main__': raise SystemExit(main())
