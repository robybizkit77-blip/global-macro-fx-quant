"""Official revised sector output research. No changes to live_data or scoring."""
import argparse,json,math
from datetime import datetime,timezone,date
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from validation.sources.gbp_ons_core import API_BASE,extract_months
from validation.macro.prepare_eur_gbp_revised_v1 import fetch
ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT/"validation/macro/SECTOR_OUTPUT_RESEARCH_V1.json"
URI="/economy/economicoutputandproductivity/output/timeseries/s2ku/ios1"
URL=API_BASE+"?"+urlencode({"uri":URI})
ID="UK_SERVICES_REAL_OUTPUT_S2KU"
def require(ok,msg):
    if not ok:raise ValueError(msg)
def collect_ons(today,fetcher=fetch):
    raw=fetcher(URL)
    p=json.loads(raw)
    desc=p["description"]
    require(str(desc.get("cdid","")).upper()=="S2KU","ONS wrong series ID")
    title=str(desc.get("title","")).casefold()
    require(all(x in title for x in ("ios","services","index")),"ONS services title mismatch")
    require("index" in str(desc.get("unit","")).casefold(),"ONS services unit mismatch")
    pairs=[(d[:7],v) for d,v in extract_months(p) if d[:7]>="2019-10"]
    require(len(pairs)>=36,"ONS history too short")
    serial=[date.fromisoformat(d+"-01").year*12+int(d[5:]) for d,v in pairs]
    require(all(b-a==1 for a,b in zip(serial,serial[1:])),"ONS missing/duplicate months")
    require(pairs[-1][0]<today.isoformat()[:7],"ONS future or incomplete month")
    require(all(math.isfinite(v) and v>0 for d,v in pairs),"ONS nonpositive level")
    return {"series_id":ID,"currency":"GBP","pillar":"services","measurement":"QUANTITY",
            "label":"Produzione reale dei servizi — ONS","frequency":"M","unit":str(desc["unit"]),
            "source_url":URL,"source_series_id":"S2KU","source_title":desc["title"],
            "source_sha256":sha256(raw).hexdigest(),"dates":[d for d,v in pairs],"values":[v for d,v in pairs],
            "latest_period":pairs[-1][0],"source_series_first_release_PIT_certified":False,
            "quality":"ONS_CURRENT_REVISED_HISTORY_NOT_PIT"}
def refresh(path,today,fetcher=fetch,strict=False):
    old=json.loads(path.read_text())
    require(old["schema"]=="GMFQ_SECTOR_OUTPUT_RESEARCH_V1","wrong archive schema")
    try:
        row=collect_ons(today,fetcher)
        prior=old["series"].get(ID)
        if prior:
            require(row["latest_period"]>=prior["latest_period"],"ONS source regressed")
            require(set(prior["dates"])<=set(row["dates"]),"ONS history coverage regressed")
        if row!=prior:
            old["series"][ID]=row
            path.write_text(json.dumps(old,ensure_ascii=False,indent=2)+"\n")
        print("SECTOR_OUTPUT_SOURCE_PASS",ID,row["latest_period"],len(row["dates"]),row["values"][-1],flush=True)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print("SECTOR_OUTPUT_WITHHELD_OR_PRIOR_RETAINED",ID,str(exc),flush=True)
        if strict:raise
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--strict",action="store_true")
    a=p.parse_args()
    refresh(ARCHIVE,datetime.now(timezone.utc).date(),strict=a.strict)
