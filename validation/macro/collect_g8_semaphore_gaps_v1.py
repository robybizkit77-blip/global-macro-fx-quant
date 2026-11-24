#!/usr/bin/env python3
"""Supplemental G8 economic traffic-light research, never FX Core or canonical Macro.
Official and research series via FRED, ONS, Statistics Canada and Eurostat.
Fails closed on stale, missing, changed-source or ambiguous observations.
All data are current revised vintages, not point-in-time historical releases.
"""
from __future__ import annotations
import argparse
import csv
import io
from zipfile import ZipFile
from datetime import date, datetime, timezone
from io import StringIO
from html.parser import HTMLParser
from html import unescape
import json
import math
from pathlib import Path
import re
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[2]
TARGET=ROOT/"site/fx-quant-v2/next/semaphore-supplement-v1.json"
SCHEMA="GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1"
FRED="https://fred.stlouisfed.org/graph/fredgraph.csv?id="
MAX_BYTES=3_000_000
# Definitions and transformations deliberately fixed and source-identifiable.
# Several historical OECD/BIS feeds have stopped updating: retain status WITHHELD;
# never use today's fetch time to make an old observation look current.
REGISTRY=[
 dict(ccy="CHF",area="services",key="LFEASETTCHQ647S",method="fred",
      name="Occupazione nei servizi (proxy, non output)",unit="persone SA",
      frequency="Q",kind="percent",max_age_days=235,origin="OECD via FRED",
      source_page="https://fred.stlouisfed.org/series/LFEASETTCHQ647S"),
 dict(ccy="AUD",area="services",key="LFEASETTAUQ647S",method="fred",
      name="Occupazione nei servizi (proxy, non output)",unit="persone SA",
      frequency="Q",kind="percent",max_age_days=235,origin="OECD via FRED",
      source_page="https://fred.stlouisfed.org/series/LFEASETTAUQ647S"),
 dict(ccy="NZD",area="services",key="BNZ_BUSINESSNZ_PSI",method="biznz",
      name="BNZ–BusinessNZ PSI servizi destagionalizzato",unit="indice diffusione (soglia 50)",
      frequency="M",kind="points",max_age_days=110,origin="BusinessNZ",
      source_page="https://businessnz.org.nz/psi"),
 dict(ccy="USD",area="services",key="CES0800000001",method="fred",
      name="Occupazione privata nei servizi (proxy, non output)",unit="mila occupati SA",
      frequency="M",kind="percent",max_age_days=105,origin="BLS via FRED",
      source_page="https://fred.stlouisfed.org/series/CES0800000001"),
 dict(ccy="GBP",area="services",key="ONS_S2KU_IOS1",method="ons",
      name="Index of Services (volumi reali destagionalizzati)",unit="indice volumi SA",
      frequency="M",kind="percent",max_age_days=110,origin="UK Office for National Statistics",
      source_page="https://www.ons.gov.uk/economy/economicoutputandproductivity/output/timeseries/s2ku/ios1"),
 dict(ccy="CAD",area="services",key="36100434_SERVICES_T003",method="statcan_services",
      name="PIL reale settore servizi (mensile, SA)",unit="mln CAD reali SAAR",
      frequency="M",kind="percent",max_age_days=110,origin="Statistics Canada table 36-10-0434-01",
      source_page="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401"),
 dict(ccy="EUR",area="house",key="EA21_STS_COBP_M",method="eurostat",
      name="Permessi per nuove abitazioni EA21 (escluse residenze collettive)",unit="indice 2021=100",
      frequency="M",kind="percent",max_age_days=115,
      source_page="https://ec.europa.eu/eurostat/databrowser/view/sts_cobp_m/default/table?lang=en",
      origin="Eurostat / sts_cobp_m"),
 dict(ccy="JPY",area="house",key="JPNWSCNDW01MLSAM",method="fred",
      name="Nuove costruzioni residenziali",unit="abitazioni SA",frequency="M",
      kind="percent",max_age_days=110,origin="OECD tramite FRED",
      source_page="https://fred.stlouisfed.org/series/JPNWSCNDW01MLSAM"),
 dict(ccy="AUD",area="industry",key="PRMNTO01AUQ657S",method="fred",
      name="Manifattura: crescita trimestrale SA",unit="% QoQ",frequency="Q",
      kind="points",max_age_days=250,origin="OECD tramite FRED",
      source_page="https://fred.stlouisfed.org/series/PRMNTO01AUQ657S"),
 dict(ccy="NZD",area="house",key="NZLPERMITMISMEI",method="fred",
      name="Permessi residenziali",unit="indice 2015=100 SA",frequency="M",
      kind="percent",max_age_days=110,origin="OECD tramite FRED",
      source_page="https://fred.stlouisfed.org/series/NZLPERMITMISMEI"),
 dict(ccy="NZD",area="industry",key="PRMNTO01NZQ657S",method="fred",
      name="Manifattura: crescita trimestrale SA",unit="% QoQ",frequency="Q",
      kind="points",max_age_days=250,origin="OECD tramite FRED",
      source_page="https://fred.stlouisfed.org/series/PRMNTO01NZQ657S"),
 dict(ccy="NZD",area="leading",key="NZLLOLITOAASTSAM",method="fred",
      name="OECD CLI Nuova Zelanda",unit="indice SA",frequency="M",
      kind="points",max_age_days=115,origin="OECD tramite FRED",
      source_page="https://fred.stlouisfed.org/series/NZLLOLITOAASTSAM"),
 dict(ccy="NZD",area="credit",key="QNZPBMXDCA",method="fred",
      name="Credito bancario settore privato, corretto per rotture",unit="mld NZD NSA",frequency="Q",
      kind="percent",max_age_days=250,origin="BIS tramite FRED",
      source_page="https://fred.stlouisfed.org/series/QNZPBMXDCA"),
 dict(ccy="CAD",area="industry",key="16100047_MANUFACTURING_SA",method="statcan",
      name="Vendite manifatturiere (nominali, destagionalizzate)",unit="migliaia CAD nominali SA",frequency="M",
      kind="percent",max_age_days=110,origin="Statistics Canada table 16-10-0047-01",
      source_page="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610004701"),
]
assert len(REGISTRY)==14 and len({(s["ccy"],s["area"]) for s in REGISTRY})==14

def fetch(url:str)->bytes:
    host=urlsplit(url).hostname
    if host not in {"fred.stlouisfed.org","ec.europa.eu"} or not url.startswith("https://"):
        raise ValueError("source host outside immutable allowlist")
    req=Request(url,headers={"User-Agent":"GMFQ-Economic-Research/1.0",
                              "Accept":"text/csv,application/json"})
    with urlopen(req,timeout=18) as response:
        final=response.geturl()
        if urlsplit(final).hostname!=host or not final.startswith("https://"):
            raise ValueError("untrusted redirect")
        data=response.read(MAX_BYTES+1)
        if not data or len(data)>MAX_BYTES:
            raise ValueError("oversized/empty source")
    return data

STATCAN_CSV="https://www150.statcan.gc.ca/n1/tbl/csv/16100047-eng.zip"
def fetch_statcan(url):
    if url!=STATCAN_CSV:raise ValueError("StatCan source URL not on allowlist")
    req=Request(url,headers={"User-Agent":"GMFQ-Economic-Research/1.0",
                             "Accept":"application/zip"})
    with urlopen(req,timeout=35) as response:
        if not response.geturl().startswith("https://www150.statcan.gc.ca/"):
            raise ValueError("StatCan source redirect outside allowlist")
        compressed=response.read(35_000_001)
        if not compressed or len(compressed)>35_000_000:
            raise ValueError("empty or oversized StatCan archive")
    return compressed

def parse_statcan(raw,now):
    """Extract the unique monthly Canada SA manufacturing total, not a subindustry."""
    with ZipFile(io.BytesIO(raw)) as z:
        names=[n for n in z.namelist() if n=="16100047.csv"]
        if len(names)!=1:raise ValueError("StatCan CSV identity changed")
        if z.getinfo(names[0]).file_size>400_000_000:
            raise ValueError("StatCan uncompressed archive exceeds budget")
        with z.open(names[0]) as f:
            rdr=csv.DictReader(io.TextIOWrapper(f,encoding="utf-8-sig"))
            required={"REF_DATE","GEO","Principal statistics","Seasonal adjustment",
                      "North American Industry Classification System (NAICS)","VALUE",
                      "UOM","SCALAR_FACTOR"}
            if not required.issubset(set(rdr.fieldnames or [])):
                raise ValueError("StatCan columns changed")
            values={}
            for row in rdr:
                if row["GEO"]!="Canada" or row["Principal statistics"]!="Sales of goods manufactured (shipments)" or \
                  row["Seasonal adjustment"]!="Seasonally adjusted" or \
                  row["North American Industry Classification System (NAICS)"]!="Manufacturing [31-33]":
                    continue
                if row["UOM"]!="Dollars" or row["SCALAR_FACTOR"]!="thousands":
                    raise ValueError("StatCan manufacturing unit changed")
                p=row["REF_DATE"]
                if not re.fullmatch(r"\d{4}-\d{2}",p):
                    raise ValueError("StatCan period format changed")
                if period_end(p)>now:continue
                value=float(row["VALUE"])
                if not math.isfinite(value) or value<=0:raise ValueError("bad StatCan value")
                if p in values:raise ValueError("ambiguous duplicate StatCan total")
                values[p]=value
    if len(values)<12:raise ValueError("insufficient StatCan history")
    return sorted(values.items())


ONS_URL="https://www.ons.gov.uk/economy/economicoutputandproductivity/output/timeseries/s2ku/ios1"
STATCAN_GDP_ZIP="https://www150.statcan.gc.ca/n1/tbl/csv/36100434-eng.zip"


BUSINESSNZ_INDEX="https://businessnz.org.nz/psi"
def biznz_fetch(url):
    """Issuer article selected through the live PSI index, never via news snippets."""
    if url!=BUSINESSNZ_INDEX:raise ValueError("invalid BusinessNZ root URL")
    def get(page):
        if not re.fullmatch(r"https://businessnz\.org\.nz/psi(?:/[a-z0-9-]+)?",page):
            raise ValueError("BusinessNZ URL outside issuer path")
        req=Request(page,headers={"User-Agent":"GMFQ-Economic-Research/1.0",
                                  "Accept":"text/html"})
        with urlopen(req,timeout=22) as r:
            target=r.geturl().rstrip("/")
            if not re.fullmatch(r"https://businessnz\.org\.nz/psi(?:/[a-z0-9-]+)?",target):
                raise ValueError("BusinessNZ redirect outside official PSI")
            data=r.read(2_500_001)
            if not data or len(data)>2_500_000:raise ValueError("BusinessNZ HTML oversized")
        return data
    home=get(url).decode("utf-8","replace")
    # Latest PSI release comes first on the official index; exclude navigation.
    paths=re.findall(r'href=["\'](https?://businessnz\.org\.nz)?(/psi/[a-z0-9-]+)(?:/)?["\']',home,re.I)
    candidates=[]
    for _,tail in paths:
        if tail not in candidates and tail not in ("/psi","/psi/"):
            candidates.append(tail)
    for tail in candidates[:5]:
        page="https://businessnz.org.nz"+tail
        try:
            item=get(page)
            if b"PSI Time Series Table" in item and (b"BusinessNZ PSI" in item or b"BusinessNZ" in item):
                return item
        except (ValueError,OSError,TimeoutError):continue
    raise ValueError("BusinessNZ live PSI table not located")

class _ReportTables(HTMLParser):
    def __init__(self):
        super().__init__();self.tables=[];self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="table" and self.table is None:self.table=[]
        elif tag=="tr" and self.table is not None:self.row=[]
        elif tag in ("td","th") and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()));self.cell=None
        elif tag=="tr" and self.row is not None:
            self.table.append(self.row);self.row=None
        elif tag=="table" and self.table is not None:
            self.tables.append(self.table);self.table=None

def parse_businessnz_psi(raw,now):
    """Read national headline seasonally-adjusted PSI, no PCI or global PMI substitution."""
    html=raw.decode("utf-8","replace")
    if "PSI Time Series Table" not in html or "Performance of Services Index" not in html:
        raise ValueError("BusinessNZ PSI source identity changed")
    parser=_ReportTables();parser.feed(html)
    result=[]
    for table in parser.tables:
        header=next((r for r in table if len(r)>=3 and any(
            re.fullmatch(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) 20\d{2}",c,re.I)
            for c in r)),None)
        headline=next((r for r in table if len(r)>=3 and
            re.fullmatch(r"BNZ\s*[\u2013\-]\s*BusinessNZ PSI",r[0],re.I)),None)
        if not header or not headline:continue
        dates=[c for c in header if re.fullmatch(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) 20\d{2}",c,re.I)]
        # Preserve header-to-value alignment; first field is the name.
        if len(dates)!=len(headline)-1:continue
        vals={}
        for dat,val in zip(dates,headline[1:]):
            month_str,year_str=dat.split()
            month=["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"].index(month_str.lower())+1
            p=f"{int(year_str)}-{month:02d}"
            if period_end(p)>now:continue
            x=float(val)
            if not math.isfinite(x) or not 20<=x<=80:raise ValueError("invalid PSI index")
            if p in vals:raise ValueError("duplicate PSI month")
            vals[p]=x
        if len(vals)>=2:
            result.append(sorted(vals.items()))
    if len(result)!=1:raise ValueError("BusinessNZ exact national PSI table absent/ambiguous")
    return result[0]

def fetch_issuer(url):
    if url not in {ONS_URL,STATCAN_GDP_ZIP}:raise ValueError("unregistered official services URL")
    req=Request(url,headers={"User-Agent":"GMFQ-Economic-Research/1.0",
      "Accept":"text/html,application/zip"})
    with urlopen(req,timeout=35) as response:
        final=response.geturl()
        if not final.startswith("https://") or urlsplit(final).hostname!=urlsplit(url).hostname:
            raise ValueError("official source redirect to other host")
        data=response.read(55_000_001)
        if not data or len(data)>55_000_000:
            raise ValueError("empty/oversized official services response")
        return data

def parse_ons_services(raw,now):
    """Extract ONLY the monthly total Index of Services S2KU from the issuer table."""
    from html.parser import HTMLParser
    class Tokens(HTMLParser):
        def __init__(self):
            super().__init__();self.data=[]
        def handle_data(self,data):
            t=data.strip()
            if t:self.data.append(t)
    h=Tokens();h.feed(raw.decode("utf-8","replace"))
    content=" | ".join(h.data)
    if "IoS: Services: Index-1dp" not in content or not re.search(r"Series ID:\s*(?:\\|\s)*S2KU",content):
        raise ValueError("ONS total services index identity changed")
    monthly={}
    for m in re.finditer(r"\b(\d{4})\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b\s*\|\s*(\d+(?:\.\d+)?)",content):
        year=int(m[1]);month=["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"].index(m[2])+1
        p=f"{year:04d}-{month:02d}"
        if period_end(p)>now:continue
        if p in monthly:raise ValueError("duplicate ONS month")
        value=float(m[3])
        if not math.isfinite(value) or value<=0:raise ValueError("invalid ONS index")
        monthly[p]=value
    if len(monthly)<12:raise ValueError("ONS monthly table unavailable")
    return sorted(monthly.items())

def parse_statcan_services(raw,now):
    """Exact Statistics Canada T003 services aggregate; no sum of subindustries."""
    with ZipFile(io.BytesIO(raw)) as z:
        names=[n for n in z.namelist() if n=="36100434.csv"]
        if len(names)!=1:raise ValueError("StatCan GDP file identity changed")
        if z.getinfo(names[0]).file_size>500_000_000:raise ValueError("oversized StatCan GDP archive")
        with z.open(names[0]) as f:
            rdr=csv.DictReader(io.TextIOWrapper(f,encoding="utf-8-sig"))
            need={"REF_DATE","GEO","North American Industry Classification System (NAICS)",
                  "Prices","Seasonal adjustment","VALUE"}
            if not need.issubset(set(rdr.fieldnames or [])):
                raise ValueError("StatCan GDP column identity changed")
            rows={}
            for row in rdr:
                if row["GEO"]!="Canada" or row["North American Industry Classification System (NAICS)"]!="Services-producing industries [T003]":
                    continue
                if row["Prices"]!="Chained (2017) dollars" or row["Seasonal adjustment"]!="Seasonally adjusted at annual rates":
                    continue
                p=row["REF_DATE"]
                if not re.fullmatch(r"\d{4}-\d{2}",p):raise ValueError("StatCan GDP period changed")
                if period_end(p)>now:continue
                try:val=float(row["VALUE"])
                except (TypeError,ValueError):continue
                if not math.isfinite(val) or val<=0:raise ValueError("invalid StatCan GDP value")
                if p in rows:raise ValueError("duplicate services GDP aggregate")
                rows[p]=val
    if len(rows)<12:raise ValueError("StatCan services aggregate missing/incompatible")
    return sorted(rows.items())

def period(date_string, frequency):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",date_string):
        raise ValueError("unrecognized observation date")
    x=date.fromisoformat(date_string)
    if frequency=="Q":
        return f"{x.year}-Q{(x.month-1)//3+1}"
    return f"{x.year}-{x.month:02d}"

def period_end(p):
    if m:=re.fullmatch(r"(\d{4})-Q([1-4])",p):
        year=int(m[1]); month=int(m[2])*3
    elif m:=re.fullmatch(r"(\d{4})-(\d{2})",p):
        year=int(m[1]);month=int(m[2])
        if not 1<=month<=12:raise ValueError("invalid monthly period")
    else: raise ValueError("invalid period")
    if month==12: return date(year,12,31)
    return date.fromordinal(date(year,month+1,1).toordinal()-1)

def parse_fred(raw:bytes,key:str,frequency:str,now:date):
    rdr=csv.DictReader(StringIO(raw.decode("utf-8-sig")))
    if rdr.fieldnames not in (["observation_date",key],["DATE",key]):
        raise ValueError("FRED header/source ID changed")
    result={}
    for row in rdr:
        p=period(row[rdr.fieldnames[0]],frequency)
        if period_end(p)>now: continue
        raw_value=row[key]
        if raw_value in {"", "."}: continue
        value=float(raw_value)
        if not math.isfinite(value) or abs(value)>1e15: raise ValueError("nonfinite/implausible value")
        if p in result: raise ValueError("duplicate official period")
        result[p]=value
    if len(result)<12: raise ValueError("insufficient history")
    return sorted(result.items())

def parse_eurostat(raw:bytes,now:date):
    """JSON-stat v2: accept only *one exact* EA20 / permits-dwellings / adjusted index.
    Do not collapse multiple dimensions or select a convenient value implicitly.
    """
    payload=json.loads(raw.decode("utf-8"))
    if payload.get("class")!="dataset" or not isinstance(payload.get("value"),dict):
        raise ValueError("Eurostat JSON-stat identity changed")
    dims=payload.get("dimension",{})
    ids=payload.get("id",[])
    sizes=payload.get("size",[])
    if len(ids)!=len(sizes) or not ids or "time" not in ids:
        raise ValueError("invalid Eurostat shape")
    allowed={"freq":{"M"},"geo":{"EA21"},"indic_bt":{"BPRM_DW"},
             "s_adj":{"SCA"},"unit":{"I21"},"cpa2_1":{"CPA_F41001_X_410014"}}
    selected={}
    for k in ids:
        index=dims.get(k,{}).get("category",{}).get("index",{})
        if not isinstance(index,dict):raise ValueError("invalid Eurostat category map")
        choices=[v for v in allowed.get(k,set()) if v in index]
        if k!="time":
            if len(choices)!=1:raise ValueError("missing/ambiguous Eurostat dimension "+k)
            selected[k]=index[choices[0]]
    if payload.get("size",[0])[ids.index("time")]<12:raise ValueError("too few periods")
    vals=payload["value"]
    out={}
    for period_raw,pos in dims["time"]["category"]["index"].items():
        if not re.fullmatch(r"\d{4}-\d{2}",period_raw):continue
        stamp=period_raw+"-01"
        p=period(stamp,"M")
        if period_end(p)>now:continue
        coords={**selected,"time":pos}
        i=0
        for k,n in zip(ids,sizes):
            i=i*n+coords[k]
        v=vals.get(str(i))
        if v is None:continue
        f=float(v)
        if not math.isfinite(f):raise ValueError("nonfinite Eurostat observation")
        out[p]=f
    if len(out)<12:raise ValueError("insufficient Eurostat observations")
    return sorted(out.items())

def contiguous_last_two(obs,frequency):
    a,b=obs[-2:]
    left,right=a[0],b[0]
    if frequency=="M":
        y,m=map(int,left.split("-")); ny,nm=map(int,right.split("-"))
        if ny*12+nm-y*12-m !=1:raise ValueError("monthly gap in latest observations")
    else:
        y=int(left[:4]);q=int(left[-1]);ny=int(right[:4]);nq=int(right[-1])
        if ny*4+nq-y*4-q!=1:raise ValueError("quarterly gap in latest observations")
    return [list(a),list(b)]

def candidate(spec,observations,now):
    newest=observations[-1][0]
    age=(now-period_end(newest)).days
    if age>spec["max_age_days"]:
        return None,{"status":"WITHHELD_STALE","last_observation":newest,"days_since_period_end":age}
    if age<0:raise ValueError("future period")
    points=contiguous_last_two(observations,spec["frequency"])
    payload={"ccy":spec["ccy"],"area":spec["area"],
      "id":"SEM_G8_"+spec["ccy"]+"_"+spec["area"].upper(),
      "label":spec["name"],"frequency":spec["frequency"],"unit":spec["unit"],
      "dates":[x[0] for x in points],"values":[x[1] for x in points],
      "category":"Semaforo supplementare","source_file":spec["origin"],
      "source_page":spec["source_page"],"source_series_id":spec["key"],
      "metric_kind":spec["kind"],"observation_as_of":newest,
      "diffusion_threshold":50 if spec["method"]=="biznz" else None,
      "quality":"SOURCE_REVISED_RESEARCH_NOT_PIT"}
    return payload,{"status":"READY_DESCRIPTIVE_REVISED","last_observation":newest,"days_since_period_end":age}

def collect(now=None,fetcher=fetch):
    now=now or datetime.now(timezone.utc).date()
    out={"schema":SCHEMA,"as_of":now.isoformat(),"source_count":len(REGISTRY),
      "series":[],"audit":{},"notes":"Latest revised observations, not PIT, no FX score."}
    for spec in REGISTRY:
        code=spec["ccy"]+"_"+spec["area"]
        url=FRED+spec["key"] if spec["method"]=="fred" else (
          BUSINESSNZ_INDEX if spec["method"]=="biznz" else
          STATCAN_CSV if spec["method"]=="statcan" else
          ONS_URL if spec["method"]=="ons" else
          STATCAN_GDP_ZIP if spec["method"]=="statcan_services" else
          "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_cobp_m?"
          "geo=EA21&indic_bt=BPRM_DW&cpa2_1=CPA_F41001_X_410014&s_adj=SCA&unit=I21&lang=EN")
        try:
            raw=(biznz_fetch(url) if spec["method"]=="biznz" else
                 fetch_statcan(url) if spec["method"]=="statcan" else
                 fetch_issuer(url)) if spec["method"] in {"biznz","statcan","ons","statcan_services"} and fetcher is fetch else fetcher(url)
            observations=(parse_fred(raw,spec["key"],spec["frequency"],now)
                          if spec["method"]=="fred" else
                          parse_businessnz_psi(raw,now) if spec["method"]=="biznz" else
                          parse_statcan(raw,now) if spec["method"]=="statcan" else
                          parse_ons_services(raw,now) if spec["method"]=="ons" else
                          parse_statcan_services(raw,now) if spec["method"]=="statcan_services" else parse_eurostat(raw,now))
            item,status=candidate(spec,observations,now)
            if item is not None:out["series"].append(item)
            out["audit"][code]={"...":None,**status,"source_page":spec["source_page"],
                                 "origin":spec["origin"]}
            out["audit"][code].pop("...")
        except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError) as exc:
            out["audit"][code]={"status":"WITHHELD_FETCH_OR_VALIDATION","reason":str(exc)[:180],
                                 "source_page":spec["source_page"],"origin":spec["origin"]}
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default=str(TARGET))
    ap.add_argument("--dry-run",action="store_true")
    x=ap.parse_args()
    out=collect()
    content=json.dumps(out,ensure_ascii=False,indent=2)+"\n"
    if not x.dry_run: Path(x.output).write_text(content,encoding="utf-8")
    print(json.dumps({"status":"CAPTURED_REVISED_NOT_PIT",
      "ready":len(out["series"]),"total":len(REGISTRY),
      "audit":{k:v["status"] for k,v in out["audit"].items()},
      "withheld_reasons":{k:v.get("reason","") for k,v in out["audit"].items() if v["status"]=="WITHHELD_FETCH_OR_VALIDATION"}},ensure_ascii=False))
if __name__=="__main__":main()
