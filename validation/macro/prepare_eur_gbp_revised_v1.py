"""Current revised EUR/GBP research histories: exact publisher series, no PIT or FX promotion."""
from __future__ import annotations
import argparse,copy,json,math,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
from validation.sources.eur_eurostat_core import API_BASE as EUROSTAT,extract_series
from validation.sources.gbp_ons_core import API_BASE as ONS,extract_months,month_shift

SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
CONFIG={
 ("EUR","EA_HICP_CORE_YOY_history_value"):("EA_HICP_CORE_YOY_history.csv","Percent YoY","TOT_X_NRG_FOOD"),
 ("EUR","EA_HICP_SERVICES_YOY_history_value"):("EA_HICP_SERVICES_YOY_history.csv","Percent YoY","SERV"),
 ("GBP","UK_CPI_CORE_YOY_history_value"):("UK_CPI_CORE_YOY_history.csv","Percent","/economy/inflationandpriceindices/timeseries/dko8/mm23"),
 ("GBP","UK_PRODUCTION_history_value"):("UK_PRODUCTION_history.csv","Index","/economy/economicoutputandproductivity/output/timeseries/k222/diop"),
 ("GBP","UK_EMPLOYMENT_RATE_history_value"):("UK_EMPLOYMENT_RATE_history.csv","Percent","/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/timeseries/lf24/lms"),
 ("GBP","UK_RETAIL_VOL_history_value"):("UK_RETAIL_VOL_history.csv","Index","/businessindustryandtrade/retailindustry/timeseries/j5ek/drsi"),
}
SCHEMA="GMFQ_EUR_GBP_REVISED_RESEARCH_HISTORIES_V1"
def require(ok,why):
    if not ok:raise ValueError(why)
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ-official-research/1.0","Accept":"application/json"}),timeout=30) as res:
        final=urlsplit(res.geturl())
        require(res.status==200 and final.scheme=="https" and final.hostname==urlsplit(url).hostname,"unexpected publisher response")
        raw=res.read(6_000_001)
    require(0<len(raw)<=6_000_000,"invalid source response size")
    return raw
def prepare_row(currency,ident,row,now,fetcher):
    source_file,old_unit,code=CONFIG[(currency,ident)]
    require(row["source_file"]==source_file and row["frequency"]=="M" and row["unit"]==old_unit,"local series identity mismatch")
    require(len(row["dates"])==len(row["values"]) and row["dates"][-1]==row["last_date"] and row["values"][-1]==row["last_value"],"inconsistent local row")
    if currency=="EUR":
        filters={"freq":"M","unit":"RCH_A","coicop18":code,"geo":"EA"}
        url=EUROSTAT+"/prc_hicp_minr?"+urlencode({"lang":"EN",**filters,"sinceTimePeriod":"2019-10"})
        raw=fetcher(url);payload=json.loads(raw)
        require(set(payload["id"])==set(filters)|{"time"},"Eurostat dimensions not fully constrained")
        observations=extract_series(payload,filters)
        definition={"dataset":"prc_hicp_minr","filters":filters,"geography":"EA changing composition"}
    else:
        url=ONS+"?"+urlencode({"uri":code})
        raw=fetcher(url);payload=json.loads(raw)
        desc=payload.get("description",{})
        expected_id=code.split("/")[-2].upper()
        require(str(desc.get("cdid","")).upper()==expected_id,"ONS CDID mismatch")
        title=str(desc.get("title","")).casefold()
        if expected_id=="DKO8":
            require("12mth" in title and all(x in title for x in ("excluding","energy","food","alcohol","tobacco")),"ONS core CPI title mismatch")
        elif expected_id=="K222":
            require(all(x in title for x in ("iop","b-e","production","cvmsa")) and "index" in str(desc.get("unit","")).casefold(),"ONS production identity mismatch")
        elif expected_id=="LF24":
            require(all(x in title for x in ("employment rate","16 to 64","seasonally adjusted")),"ONS employment identity mismatch")
        else:
            require(all(x in title for x in ("volume","seasonally adjusted","all retailers","inc fuel","index")),"ONS retail identity mismatch")
        observations=extract_months(payload)
        definition={"cdid":expected_id,"dataset":code.split("/")[-1].upper(),"official_uri":code,"title":desc.get("title"),"publisher_unit":desc.get("unit")}
    if ident=="UK_EMPLOYMENT_RATE_history_value":
        # LF24 month labels are the centre of rolling three-month windows.
        # Identify the legacy convention empirically before replacing any history.
        old_definition=row.get("current_vintage_provenance",{}).get("definition",{})
        if old_definition.get("cdid")=="LF24":
            shift=old_definition["legacy_period_shift_months"]
            require(shift in (0,1),"invalid certified period convention")
        else:
            errors={}
            for shift in (0,1):
                lookup={month_shift(d,shift)[:7]:v for d,v in observations}
                diffs=[abs(float(v)-lookup[str(d)[:7]]) for d,v in zip(row["dates"],row["values"]) if str(d)[:7] in lookup]
                require(len(diffs)>=36,"insufficient employment overlap")
                errors[shift]=statistics.mean(diffs)
            shift=min(errors,key=errors.get)
            require(errors[shift]<=0.35 and errors[1-shift]-errors[shift]>=0.025,"ambiguous LFS centre/end month convention: "+str(errors))
        observations=[(month_shift(d,shift),v) for d,v in observations]
        definition.update(legacy_period_shift_months=shift,period_semantics="ROLLING_3_MONTH_CENTRE" if shift==0 else "ROLLING_3_MONTH_END")
    start=str(row["dates"][0])[:7]
    pairs=[(d[:7],v) for d,v in observations if d[:7]>=start]
    require(bool(pairs),"empty history")
    ds,vs=map(list,zip(*pairs))
    def ordinal(d):return int(d[:4])*12+int(d[5:7])
    require(ds[0]==start and ds[-1]>=str(row["last_date"])[:7] and ds[-1]<now.date().isoformat()[:7],"source does not cover canonical period or is future")
    require(all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])) and all(math.isfinite(v) for v in vs),"incomplete revised source history")
    require(set(str(x)[:7] for x in row["dates"])<=set(ds),"historical coverage regression")
    if ident=="UK_RETAIL_VOL_history_value":require(all(v>0 for v in vs),"nonpositive retail volume index")
    if ident=="UK_PRODUCTION_history_value":
        require(all(v>0 for v in vs),"nonpositive production index")
        lookup=dict(zip(ds,vs))
        ratios=[float(v)/lookup[str(d)[:7]] for d,v in zip(row["dates"],row["values"])]
        require(len(ratios)>=36,"insufficient production overlap")
        scale=statistics.median(ratios)
        require(0.8<=scale<=1.2 and max(abs(r/scale-1) for r in ratios)<=0.08,"production source overlap incompatible")
    if ident=="UK_EMPLOYMENT_RATE_history_value":
        require(all(0<v<100 for v in vs),"invalid employment percentage")
    before=row["last_date"]
    old=row.get("current_vintage_provenance",{})
    changed=row["dates"]!=ds or row["values"]!=vs or old.get("definition")!=definition
    if changed:
        row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],
            current_vintage_provenance={"status":"OFFICIAL_CURRENT_REVISED_HISTORY_NOT_PIT","source_url":url,"definition":definition,
            "source_json_sha256":sha256(raw).hexdigest(),"runner_first_seen_utc":now.isoformat(),
            "source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True})
    return {"currency":currency,"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1],"source_url":url}
def prepare(current,*,now,fetcher=fetch):
    require(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);receipts=[]
    for currency,ident in CONFIG:
        try:
            hits=[r for r in out[currency] if r["id"]==ident];require(len(hits)==1,"unique series required")
            row=copy.deepcopy(hits[0])
            result=prepare_row(currency,ident,row,now,fetcher)
            hits[0].update(row);receipts.append(result)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            receipts.append({"currency":currency,"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":SCHEMA,"observed_at_utc":now.isoformat(),"series":receipts,"status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",required=True,type=Path);p.add_argument("--receipt",required=True,type=Path);a=p.parse_args()
    require(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary outputs only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True)
    a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
