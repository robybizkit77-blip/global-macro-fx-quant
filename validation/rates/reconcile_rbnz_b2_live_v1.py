"""Current B2 government benchmark reconciliation; read-only, no cross-roll inference."""
import datetime as dt
import hashlib
import io
import json
import math
from urllib.request import Request, urlopen
from openpyxl import load_workbook
from validation.rates.collect_rbnz_b2_daily_web_v1 import fetch, parse, NZ, ROLL, BOND_2, BOND_10, USER_AGENT
from validation.rates.reconcile_rbnz_b2_xlsx_oct29_v1 import URL

GROUP = "Secondary market government bond closing yields"
SPECS = {"2Y":("2 year","INM.DG102.NZZCF","%pa"),
         "10Y":("10 year","INM.DG110.NZZCF","%pa"),
         "bond2":(BOND_2,"INM.DG19.NS2904ZC","%"),
         "bond10":(BOND_10,"INM.DG19.NS3704ZC","%")}

def must(ok,msg):
    if not ok: raise ValueError("B2_CURRENT_RECONCILIATION: "+msg)

def parse_workbook(raw,web):
    must(raw.startswith(b"PK") and 1000<len(raw)<10_000_000,"bad workbook")
    wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    try:
        desc=wb["Table Description"];desc.reset_dimensions()
        meta={r[0]:r[1] for r in desc.values if len(r)>=2 and isinstance(r[0],str)}
        must(meta.get("Published By")=="Reserve Bank of New Zealand" and
             meta.get("Table")=="Daily wholesale interest rates (% pa) - B2","wrong publication")
        must(isinstance(meta.get("Published Date"),dt.datetime) and
             meta["Published Date"].date().isoformat()==web["release_date"],"release mismatch")
        ws=wb["Data"];ws.reset_dimensions()
        it=iter(ws.values);h=[next(it) for _ in range(5)]
        cols={}
        for key,(label,sid,unit) in SPECS.items():
            matches=[i for i,v in enumerate(h[4]) if v==sid]
            must(len(matches)==1,"ambiguous series ID "+sid)
            i=matches[0]
            must(h[0][i]==GROUP and h[1][i]==label and h[3][i]==unit,"identity/unit drift "+sid)
            cols[key]=i
        must(web["benchmark_roll_date"]==ROLL and web["benchmark_2Y"]==BOND_2 and web["benchmark_10Y"]==BOND_10,"benchmark schedule drift")
        rows={}
        for r in it:
            if not r or not isinstance(r[0],dt.datetime): continue
            d=r[0].date().isoformat()
            if d<ROLL: continue
            must(d not in rows and d<=web["release_date"],"duplicate/future date")
            values={k:r[i] for k,i in cols.items()}
            must(all(type(v) in (float,int) and math.isfinite(v) and -5<v<25 for v in values.values()),"invalid yield "+d)
            must(abs(values["2Y"]-values["bond2"])<0.00001 and abs(values["10Y"]-values["bond10"])<0.00001,"bond mapping mismatch "+d)
            rows[d]={k:values[k] for k in ("2Y","10Y")}
        overlap=web["post_roll_table_rows"]
        must(len(overlap)>=5 and len({r["date"] for r in overlap})==len(overlap),"insufficient overlap")
        for r in overlap:
            must(r["date"] in rows and all(abs(rows[r["date"]][k]-r[k])<0.00001 for k in ("2Y","10Y")),"HTML/XLSX mismatch "+r["date"])
        must(max(rows)==web["as_of"] and ROLL in rows,"latest date or roll anchor missing")
        must(rows[ROLL]=={"2Y":3.96,"10Y":4.9},"roll anchor mismatch")
        latest=rows[web["as_of"]]
        must(latest=={k:web[k] for k in ("2Y","10Y")},"latest mismatch")
        return {"status":"OFFICIAL_B2_HTML_XLSX_POSTROLL_MATCH_REVIEW_ONLY","as_of":web["as_of"],
                "release_date":web["release_date"],"source_url":URL,"sha256":hashlib.sha256(raw).hexdigest(),
                "series_ids":{k:v[1] for k,v in SPECS.items()},"roll_date":ROLL,"matched_web_rows":len(overlap),
                "post_roll_rows":len(rows),"2Y":latest["2Y"],"10Y":latest["10Y"],
                "curve_bp":round((latest["10Y"]-latest["2Y"])*100,2),
                "history":[{"date":d,**rows[d]} for d in sorted(rows)],
                "same_issuer_two_formats":True,"cross_roll_change_allowed":False,
                "eligible_for_automatic_promotion":False,"writes_live_rates":False,"first_release_pit_verified":False}
    finally:
        wb.close()

def main():
    web=parse(fetch(),now_nz=dt.datetime.now(NZ))
    req=Request(URL,headers={"User-Agent":USER_AGENT})
    with urlopen(req,timeout=25) as r:
        must(r.status==200 and r.geturl()==URL,"unexpected source response")
        raw=r.read(10_000_001)
    result=parse_workbook(raw,web)
    print("B2_LIVE_RECONCILIATION",json.dumps(result,sort_keys=True))

if __name__=="__main__": main()
