"""Official revised sector output research. No changes to live_data or scoring."""
import argparse,json,math,csv,io,re
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
    # ONS's series page explicitly identifies S2KU as an index; its API
    # unit field can be blank or use a base-year notation rather than "Index".
    # Retain the publisher's raw metadata and reject explicit rate/currency units.
    unit=str(desc.get("unit") or "").strip()
    normalized=unit.casefold()
    require(not any(x in normalized for x in ("percent","%","pounds","gbp","growth","change","million")),"ONS services unit contradicts index: "+repr(unit))
    require(title=="ios: services: index-1dp","ONS services exact title mismatch")
    require(str(desc.get("datasetId") or desc.get("dataset_id") or "IOS1").upper()=="IOS1","ONS dataset mismatch")
    pairs=[(d[:7],v) for d,v in extract_months(p) if d[:7]>="2019-10"]
    require(len(pairs)>=36,"ONS history too short")
    serial=[date.fromisoformat(d+"-01").year*12+int(d[5:]) for d,v in pairs]
    require(all(b-a==1 for a,b in zip(serial,serial[1:])),"ONS missing/duplicate months")
    require(pairs[-1][0]<today.isoformat()[:7],"ONS future or incomplete month")
    require(all(math.isfinite(v) and v>0 for d,v in pairs),"ONS nonpositive level")
    return {"series_id":ID,"currency":"GBP","pillar":"services","measurement":"QUANTITY",
            "label":"Produzione reale dei servizi — ONS","frequency":"M","unit":"Index (ONS IoS, seasonally adjusted)","publisher_unit_raw":unit,
            "source_url":URL,"source_series_id":"S2KU","source_title":desc["title"],
            "source_sha256":sha256(raw).hexdigest(),"dates":[d for d,v in pairs],"values":[v for d,v in pairs],
            "latest_period":pairs[-1][0],"source_series_first_release_PIT_certified":False,
            "quality":"ONS_CURRENT_REVISED_HISTORY_NOT_PIT"}
CAD_SPECS={
    "CA_MANUFACTURING_REAL_GDP":("manufacturing","PIL reale manifattura",{"manufacturing","manufacturing [31-33]"}),
    "CA_SERVICES_REAL_GDP":("services","PIL reale servizi",{"services-producing industries","services-producing industries [t003]"})
}
CAD_URL="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401"
def collect_cad(raw,today):
    from validation.sources.cad_statcan_core import norm
    found={k:{} for k in CAD_SPECS}
    vectors={k:set() for k in CAD_SPECS}
    reader=csv.DictReader(io.StringIO(raw))
    require({"REF_DATE","GEO","UOM","SCALAR_FACTOR","VECTOR","VALUE","Prices","Seasonal adjustment"}<=set(reader.fieldnames or []),"StatCan sector header mismatch")
    for r in reader:
        if (norm(r.get("GEO"))!="canada" or norm(r.get("Seasonal adjustment"))!="seasonally adjusted at annual rates"
            or norm(r.get("Prices"))!="chained (2017) dollars" or norm(r.get("UOM"))!="dollars"
            or norm(r.get("SCALAR_FACTOR"))!="millions"):continue
        industry=next((norm(v) for k,v in r.items() if "industry classification" in k.casefold()),"")
        for ident,(pillar,label,aliases) in CAD_SPECS.items():
            if industry not in aliases or r["VALUE"] in (None,""):continue
            d=r["REF_DATE"]
            require(bool(re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])",d)),"invalid StatCan period")
            if d<"2019-10":continue
            require(d not in found[ident],"duplicate StatCan sector period")
            v=float(r["VALUE"]);require(math.isfinite(v) and v>0,"invalid StatCan sector level")
            found[ident][d]=v;vectors[ident].add(r["VECTOR"])
    out=[]
    for ident,(pillar,label,aliases) in CAD_SPECS.items():
        ds=sorted(found[ident]);require(len(ds)>=36 and len(vectors[ident])==1,"StatCan unique sector series not found: "+ident)
        serial=[int(d[:4])*12+int(d[5:]) for d in ds]
        require(all(b-a==1 for a,b in zip(serial,serial[1:])) and ds[-1]<today.isoformat()[:7],"StatCan sector gaps/future")
        out.append(dict(series_id=ident,currency="CAD",pillar=pillar,measurement="QUANTITY",label=label,
            frequency="M",unit="million chained 2017 CAD SAAR",source_url=CAD_URL,source_table="36100434",
            source_series_id=next(iter(vectors[ident])),source_sha256=sha256(raw.encode()).hexdigest(),
            dates=ds,values=[found[ident][d] for d in ds],latest_period=ds[-1],
            source_series_first_release_PIT_certified=False,quality="STATCAN_CURRENT_REVISED_HISTORY_NOT_PIT"))
    require(out[0]["dates"]==out[1]["dates"],"CAD sectors not aligned")
    return out

def refresh_cad(path,today,strict=False):
    from validation.sources.cad_statcan_core import download_csv,StatCanTransportUnavailable
    try:
        rows=collect_cad(download_csv("36100434"),today)
        old=json.loads(path.read_text())
        require(old["schema"]=="GMFQ_SECTOR_OUTPUT_RESEARCH_V1","wrong archive schema")
        changed=False
        for r in rows:
            prior=old["series"].get(r["series_id"])
            if prior:
                require(prior["source_series_id"]==r["source_series_id"] and set(prior["dates"])<=set(r["dates"]),"StatCan sector identity/coverage regression")
            if prior!=r:old["series"][r["series_id"]]=r;changed=True
        if changed:path.write_text(json.dumps(old,ensure_ascii=False,indent=2)+"\n")
        for r in rows:print("SECTOR_OUTPUT_SOURCE_PASS",r["series_id"],r["latest_period"],len(r["dates"]),r["values"][-1],r["source_series_id"],flush=True)
    except (OSError,ValueError,KeyError,TypeError,StatCanTransportUnavailable) as exc:
        print("CAD_SECTOR_WITHHELD_OR_PRIOR_RETAINED",str(exc),flush=True)
        if strict:raise

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
    refresh_cad(ARCHIVE,datetime.now(timezone.utc).date(),strict=a.strict)
