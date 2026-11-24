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
MANUAL_PSI=ROOT/"validation/macro/official_g8_services_source_snapshot_v1.json"
MANUAL_NZ_HOUSE=ROOT/"validation/macro/official_nzd_house_snapshot_v1.json"
SCHEMA="GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1"
FRED="https://fred.stlouisfed.org/graph/fredgraph.csv?id="
MAX_BYTES=3_000_000
# Definitions and transformations deliberately fixed and source-identifiable.
# Several historical OECD/BIS feeds have stopped updating: retain status WITHHELD;
# never use today's fetch time to make an old observation look current.
REGISTRY=[
 dict(ccy="CAD",area="demand",key="CAN_RETAIL_VOLUME_CHAINED",method="statcan_detail",
      name="Indice Fisher del volume reale retail Canada (SA)",unit="indice 2017=100",
      frequency="M",kind="percent",max_age_days=115,
      origin="Statistics Canada / 20-10-0067-01",
      source_page="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010006701"),
 dict(ccy="CAD",area="house",key="CAN_HOUSEHOLD_MORTGAGES_SA",method="statcan_detail",
      name="Stock mutui residenziali famiglie Canada (SA; proxy immobiliare)",
      unit="mln CAD SA",frequency="M",kind="percent",max_age_days=115,
      origin="Statistics Canada / 36-10-0639-01",
      source_page="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610063901"),
 dict(ccy="CAD",area="credit",key="CAN_NFC_NONMORTGAGE_LOANS_SA",method="statcan_detail",
      name="Prestiti non ipotecari società non finanziarie Canada (SA)",
      unit="mln CAD SA",frequency="M",kind="percent",max_age_days=115,
      origin="Statistics Canada / 36-10-0640-01",
      source_page="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610064001"),

 dict(ccy="AUD",area="house",key="RBA_HOUSING_CREDIT_GROWTH_MM",method="rba_credit",
      name="Crescita credito abitativo RBA (proxy immobiliare, SA, corretta rotture)",
      unit="% m/m SA",frequency="M",kind="points",max_age_days=120,
      origin="Reserve Bank of Australia / Financial Aggregates",
      source_page="https://www.rba.gov.au/statistics/frequency/fin-agg/"),
 dict(ccy="AUD",area="credit",key="RBA_BUSINESS_CREDIT_GROWTH_MM",method="rba_credit",
      name="Crescita credito alle imprese RBA (SA, corretta rotture)",
      unit="% m/m SA",frequency="M",kind="points",max_age_days=120,
      origin="Reserve Bank of Australia / Financial Aggregates",
      source_page="https://www.rba.gov.au/statistics/frequency/fin-agg/"),

 dict(ccy="AUD",area="demand",key="ABS_MHSI_TOTAL_MONTHLY_SA",method="abs_demand",
      name="Spesa famiglie totale nominale SA (proxy domanda, % m/m)",
      unit="% m/m nominale SA",frequency="M",kind="points",max_age_days=115,
      origin="Australian Bureau of Statistics / MHSI",
      source_page="https://www.abs.gov.au/statistics/economy/finance/monthly-household-spending-indicator/latest-release"),

 dict(ccy="GBP",area="industry",key="ONS_K222_DIOP",method="ons_industry",
      name="Indice della produzione industriale UK (volumi reali SA)",unit="indice CVMSA",
      frequency="M",kind="percent",max_age_days=115,origin="ONS Index of Production",
      source_page="https://www.ons.gov.uk/economy/economicoutputandproductivity/output/timeseries/k222/diop"),
 dict(ccy="GBP",area="house",key="BOE_LPMVTVX",method="boe_mortgage",
      name="Mutui approvati per acquisto casa (BoE, SA)",unit="numero autorizzazioni SA",
      frequency="M",kind="percent",max_age_days=120,origin="Bank of England IADB / LPMVTVX",
      source_page="https://www.bankofengland.co.uk/boeapps/database/BankStats.asp"),
 dict(ccy="NZD",area="house",key="STATSNZ_NEWDWELLINGS_SA",method="statsnz_house",
      name="Nuove abitazioni autorizzate (Stats NZ, SA)",unit="numero abitazioni SA",
      frequency="M",kind="percent",max_age_days=115,origin="Stats NZ / Building consents",
      source_page="https://www.stats.govt.nz/topics/building/"),

 dict(ccy="USD",area="house",key="PERMIT",method="fred",
      name="Permessi edilizi residenziali USA (SA)",unit="migliaia unità SA",frequency="M",
      kind="percent",max_age_days=115,origin="US Census Bureau via FRED",
      source_page="https://fred.stlouisfed.org/series/PERMIT"),
 dict(ccy="USD",area="industry",key="INDPRO",method="fred",
      name="Produzione industriale Fed (indice reale SA)",unit="indice 2017=100",frequency="M",
      kind="percent",max_age_days=115,origin="Federal Reserve via FRED",
      source_page="https://fred.stlouisfed.org/series/INDPRO"),
 dict(ccy="USD",area="leading",key="UMCSENT",method="fred",
      name="Fiducia consumatori University of Michigan (survey, proxy)",unit="indice NSA",frequency="M",
      kind="points",max_age_days=115,origin="University of Michigan via FRED",
      source_page="https://fred.stlouisfed.org/series/UMCSENT"),
 dict(ccy="USD",area="demand",key="PCEC96",method="fred",
      name="Spesa consumi personali reali (PCE, SAAR)",unit="mld USD concatenati SAAR",frequency="M",
      kind="percent",max_age_days=115,origin="US BEA via FRED",
      source_page="https://fred.stlouisfed.org/series/PCEC96"),
 dict(ccy="USD",area="credit",key="DRTSCILM",method="fred",
      name="SLOOS: quota banche che irrigidisce prestiti C&I",unit="saldo netto punti percentuali",frequency="Q",
      kind="points",max_age_days=250,origin="Federal Reserve SLOOS via FRED",
      source_page="https://fred.stlouisfed.org/series/DRTSCILM",up_good=False),
 dict(ccy="EUR",area="industry",key="STS_INPR_M_EA21_PRD_B-D_SCA_I21",method="eurostat_industry",
      name="Produzione industriale reale EA21 (SCA)",unit="indice 2021=100 SCA",frequency="M",
      kind="percent",max_age_days=115,origin="Eurostat / sts_inpr_m",
      source_page="https://ec.europa.eu/eurostat/databrowser/view/sts_inpr_m/default/table?lang=en"),
 dict(ccy="EUR",area="leading",key="TEIBS010_EA21_BS-ESI-I_SA",method="eurostat_esi",
      name="Economic Sentiment Indicator — Eurozona EA21",unit="indice ESI SA",frequency="M",
      kind="points",max_age_days=85,origin="Eurostat / DG ECFIN teibs010",
      source_page="https://ec.europa.eu/eurostat/databrowser/view/teibs010/default/table?lang=en"),
 dict(ccy="EUR",area="demand",key="STS_TRTU_M_EA21_VOL_SLS_G47_SCA_I21",method="eurostat_retail",
      name="Volume vendite reali al dettaglio EA21 (SCA)",unit="indice 2021=100 SCA",frequency="M",
      kind="percent",max_age_days=115,origin="Eurostat / sts_trtu_m",
      source_page="https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table?lang=en"),
 dict(ccy="EUR",area="services",key="TEIBS020_BS-SCI-BAL_SA_EA21",method="eurostat_services",
      name="Fiducia imprese servizi — Eurozona EA21 (survey SA)",unit="saldo netto destagionalizzato",
      frequency="M",kind="points",max_age_days=75,origin="Eurostat / DG ECFIN teibs020",
      source_page="https://ec.europa.eu/eurostat/databrowser/view/teibs020/default/table?lang=en"),
 dict(ccy="CHF",area="services",key="LFEASETTCHQ647S",method="fred",
      name="Occupazione nei servizi (proxy, non output)",unit="persone SA",
      frequency="Q",kind="percent",max_age_days=235,origin="OECD via FRED",
      source_page="https://fred.stlouisfed.org/series/LFEASETTCHQ647S"),
 dict(ccy="AUD",area="services",key="ABS_MHSI_SERVICES_MONTHLY_SA",method="abs_services",
      name="Spesa famiglie servizi: variazione mensile nominale (proxy domanda)",
      unit="% m/m nominale SA",frequency="M",kind="points",max_age_days=110,
      origin="Australian Bureau of Statistics / MHSI",
      source_page="https://www.abs.gov.au/statistics/economy/finance/monthly-household-spending-indicator/latest-release"),
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
assert len(REGISTRY)==31 and len({(s["ccy"],s["area"]) for s in REGISTRY})==31

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

STATCAN_DETAIL={
 "CAN_RETAIL_VOLUME_CHAINED":{
  "url":"https://www150.statcan.gc.ca/n1/tbl/csv/20100067-eng.zip",
  "file":"20100067.csv","category":"North American Industry Classification System (NAICS)",
  "value":"Retail trade [44-45]","other":"Sales, price and volume",
  "selection":"Retail sales Chained Fisher volume index (scaled to equal 100 in 2017)",
  "unit":"Index","scale":"units"},
 "CAN_HOUSEHOLD_MORTGAGES_SA":{
  "url":"https://www150.statcan.gc.ca/n1/tbl/csv/36100639-eng.zip",
  "file":"36100639.csv","category":"Credit liabilities of households",
  "value":"Residential mortgages","other":"Seasonality",
  "selection":"Seasonally adjusted data","unit":"Dollars","scale":"millions"},
 "CAN_NFC_NONMORTGAGE_LOANS_SA":{
  "url":"https://www150.statcan.gc.ca/n1/tbl/csv/36100640-eng.zip",
  "file":"36100640.csv","category":"Credit liabilities of private non-financial corporations",
  "value":"Non-mortgage loans","other":"Seasonality",
  "selection":"Seasonally adjusted data","unit":"Dollars","scale":"millions"}
}
def fetch_statcan_detail(url):
    if url not in {d["url"] for d in STATCAN_DETAIL.values()}:
        raise ValueError("Unexpected StatCan detail endpoint")
    req=Request(url,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":"application/zip"})
    with urlopen(req,timeout=25) as r:
        if r.geturl()!=url:raise ValueError("StatCan redirected outside pinned dataset")
        payload=r.read(35_000_001)
        if len(payload)>35_000_000 or not payload:
            raise ValueError("StatCan archive too large or empty")
    return payload

def parse_statcan_detail(raw,now,identifier):
    spec=STATCAN_DETAIL.get(identifier)
    if not spec:raise ValueError("Unknown StatCan series identifier")
    with ZipFile(io.BytesIO(raw)) as archive:
        if spec["file"] not in archive.namelist():
            raise ValueError("StatCan exact dataset filename changed")
        if archive.getinfo(spec["file"]).file_size>100_000_000:
            raise ValueError("StatCan uncompressed archive exceeds budget")
        values={}
        with archive.open(spec["file"]) as src:
            reader=csv.DictReader(io.TextIOWrapper(src,encoding="utf-8-sig"))
            fields={"REF_DATE","GEO","VALUE","UOM","SCALAR_FACTOR",spec["category"],spec["other"]}
            if not fields.issubset(set(reader.fieldnames or [])):
                raise ValueError("StatCan required dimensions absent")
            for row in reader:
                if row["GEO"]!="Canada" or row[spec["category"]]!=spec["value"] or row[spec["other"]]!=spec["selection"]:
                    continue
                if row["UOM"]!=spec["unit"] or row["SCALAR_FACTOR"]!=spec["scale"]:
                    raise ValueError("StatCan selected unit/scale mismatch")
                p=row["REF_DATE"]
                if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])",p):
                    raise ValueError("StatCan selected month code invalid")
                if period_end(p)>now:continue
                raw_value=row["VALUE"]
                if raw_value in ("", "..", "."):continue
                v=float(raw_value)
                if not math.isfinite(v) or v<=0 or v>1e12:
                    raise ValueError("StatCan selected value implausible")
                if p in values:raise ValueError("StatCan selected duplicate month")
                values[p]=v
    if len(values)<12:raise ValueError("StatCan selected series lacks 12 observations")
    return sorted(values.items())

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


RBA_BASE="https://www.rba.gov.au/statistics/frequency/fin-agg/"
def rba_release_url(now,months_ago):
    index=now.year*12+now.month-1-months_ago
    year,rem=divmod(index,12);month=rem+1
    return f"{RBA_BASE}{year}/fin-agg-{month:02d}{year%100:02d}.html"
def fetch_rba_aggregate(now):
    for months_ago in range(1,5):
        url=rba_release_url(now,months_ago)
        req=Request(url,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":"text/html"})
        try:
            with urlopen(req,timeout=16) as response:
                final=response.geturl()
                if final!=url:raise ValueError("RBA unexpected redirect")
                raw=response.read(2_000_001)
                if not raw or len(raw)>2_000_000:raise ValueError("invalid RBA response size")
            # Do not accept arbitrary RBA pages that merely mention the year.
            if "Financial Aggregates" not in raw.decode("utf-8","replace"):
                raise ValueError("wrong RBA release identity")
            return raw,url
        except (ValueError,OSError,TimeoutError):
            continue
    raise ValueError("No valid recent RBA financial aggregates release")
def parse_rba_aggregates(raw,now,which,release_url):
    if which not in {"RBA_HOUSING_CREDIT_GROWTH_MM","RBA_BUSINESS_CREDIT_GROWTH_MM"}:
        raise ValueError("unregistered RBA series")
    match=re.fullmatch(r"https://www\.rba\.gov\.au/statistics/frequency/fin-agg/(\d{4})/fin-agg-(\d{2})(\d{2})\.html",release_url)
    if not match or int(match[1])%100!=int(match[3]):
        raise ValueError("RBA release URL identity changed")
    year=int(match[1]);month=int(match[2])
    if not 1<=month<=12:raise ValueError("RBA invalid month")
    current=f"{year}-{month:02d}"
    prev=f"{year-1}-12" if month==1 else f"{year}-{month-1:02d}"
    if period_end(current)>now:raise ValueError("RBA release from future")
    html=raw.decode("utf-8","replace")
    if not all(token in html for token in ("Financial Aggregates","Year-ended","Monthly")):
        raise ValueError("RBA Financial Aggregates title / table identity absent")
    tables=_ReportTables();tables.feed(html)
    target="Housing" if "HOUSING" in which else "Business"
    values=[]
    for table in tables.tables:
        for row in table:
            if len(row)<3:continue
            label=re.sub(r"[^A-Za-z ]","",row[0]).strip()
            if label!=target:continue
            try: first=float(row[1].replace(",",""));second=float(row[2].replace(",",""))
            except ValueError:continue
            if not all(math.isfinite(x) and -15<=x<=15 for x in (first,second)):
                raise ValueError("RBA growth rate impossible")
            values.append((first,second))
    if len(values)!=1:raise ValueError("RBA credit subcategory ambiguous/missing")
    return [(prev,values[0][0]),(current,values[0][1])]

ONS_INDUSTRY="https://www.ons.gov.uk/economy/economicoutputandproductivity/output/timeseries/k222/diop"
BOE_IADB="https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp"
STATSNZ_BASE="https://www.stats.govt.nz/information-releases/building-consents-issued-"
def boe_mortgage_url(now):
    from urllib.parse import urlencode
    return BOE_IADB+"?"+urlencode({
      "CSVF":"TT","DAT":"RNG","FD":"1","FM":"Jan","FNY":"Y","FY":"2024",
      "Filter":"N","FromSeries":"1","SeriesCodes":"LPMVTVX",
      "TD":str(now.day),"TM":now.strftime("%b"),"TY":str(now.year),
      "ToSeries":"50","UsingCodes":"Y","VPD":"Y","html.x":"66","html.y":"26","title":"LPMVTVX"})

def fetch_boe(url):
    if not url.startswith(BOE_IADB+"?"):raise ValueError("Bank of England URL mismatch")
    req=Request(url,headers={"User-Agent":"GMFQ-Economic-Research/1.0"})
    with urlopen(req,timeout=25) as r:
        if urlsplit(r.geturl()).hostname!="www.bankofengland.co.uk":
            raise ValueError("BoE redirected away from issuer")
        data=r.read(2_500_001)
        if not data or len(data)>2_500_000:raise ValueError("BoE HTML oversized/empty")
    return data

def parse_boe_mortgage(raw,now):
    txt=raw.decode("utf-8","replace")
    if "LPMVTVX" not in txt or not re.search(r"approvals for house purchase",txt,re.I):
        raise ValueError("BoE mortgage time-series identity changed")
    p=_ReportTables();p.feed(txt)
    out={}
    for tab in p.tables:
        rows=[]
        for row in tab:
            if len(row)<2:continue
            x=re.fullmatch(r"(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{2})",row[0])
            if not x:continue
            year=2000+int(x[3]);month=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"].index(x[2])+1
            period=f"{year:04d}-{month:02d}"
            if period_end(period)>now:continue
            val=float(row[1].replace(",",""))
            if not math.isfinite(val) or not 1000<=val<=300000:raise ValueError("invalid BoE approvals")
            if period in out:raise ValueError("BoE duplicate month")
            rows.append((period,val))
        if len(rows)>=2:
            if out:raise ValueError("BoE multiple eligible tables")
            out=dict(rows)
    if len(out)<2:raise ValueError("BoE series not available in HTML table")
    return sorted(out.items())

def parse_ons_industry(raw,now):
    txt=raw.decode("utf-8","replace")
    if "IOP: B-E: PRODUCTION: CVMSA" not in txt or not re.search(r"Series ID:\s*K222",txt):
        raise ValueError("ONS K222 source identity changed")
    parser=_ReportTables();parser.feed(txt)
    out={}
    for table in parser.tables:
        for row in table:
            if len(row)!=2:continue
            mm=re.fullmatch(r"(\d{4}) (JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)",row[0],re.I)
            if not mm:continue
            year=int(mm[1]);month=["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"].index(mm[2].upper())+1
            p=f"{year:04d}-{month:02d}"
            if period_end(p)>now:continue
            val=float(row[1])
            if not math.isfinite(val) or val<=0:raise ValueError("invalid ONS production index")
            if p in out:raise ValueError("ONS repeated monthly index")
            out[p]=val
    if len(out)<12:raise ValueError("ONS K222 monthly index unavailable")
    return sorted(out.items())

def statsnz_house_url(now,months_back):
    n=now.year*12+now.month-1-months_back
    year=n//12;month=n%12+1
    return STATSNZ_BASE+date(year,month,1).strftime("%B").lower()+"-"+str(year)+"/"

def statsnz_fetch(url,now):
    # Before the new monthly release, walk the official monthly release archive.
    errors=[]
    for back in range(1,6):
        dest=statsnz_house_url(now,back)
        req=Request(dest,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":"text/html"})
        try:
            with urlopen(req,timeout=16) as r:
                if urlsplit(r.geturl()).hostname not in ("www.stats.govt.nz","stats.govt.nz"):
                    raise ValueError("Stats NZ redirected off official host")
                data=r.read(3_500_001)
                if not data or len(data)>3_500_000:
                    raise ValueError("Stats NZ release HTML empty or oversized")
            parse_statsnz_house(data,now) # fail closed on revisions/page format
            return data,dest
        except (OSError,ValueError,TimeoutError) as exc:
            errors.append(dest.split("/")[-2]+":"+str(exc)[:80])
            continue
    raise ValueError("No verified recent official Stats NZ building-consent release; "+"; ".join(errors[-4:]))

def parse_statsnz_house(raw,now):
    txt=raw.decode("utf-8","replace")
    if "New dwellings consented" not in txt or "Seasonally adjusted" not in txt:
        raise ValueError("Stats NZ new dwelling / SA identity missing")
    tables=_ReportTables();tables.feed(txt)
    eligible=[]
    for table in tables.tables:
        head=next((r for r in table[:4] if len(r)>=4 and
          "Actual" in r and "Seasonally adjusted" in r and "Trend" in r),None)
        if not head:continue
        values={}
        sa_index=head.index("Seasonally adjusted")
        for row in table:
            if len(row)<=sa_index:continue
            p=re.fullmatch(r"(\d{4})-(\d{2})-01",row[0])
            if not p:continue
            period=f"{p[1]}-{p[2]}"
            if period_end(period)>now:continue
            x=float(row[sa_index].replace(",",""))
            if not math.isfinite(x) or x<=100:raise ValueError("Stats NZ invalid dwellings")
            if period in values:raise ValueError("Stats NZ duplicate month")
            values[period]=x
        if len(values)>=2:eligible.append(sorted(values.items()))
    if len(eligible)!=1:raise ValueError("Stats NZ new dwellings SA table missing/ambiguous")
    return eligible[0]


ONS_URL="https://www.ons.gov.uk/economy/economicoutputandproductivity/output/timeseries/s2ku/ios1"
STATCAN_GDP_ZIP="https://www150.statcan.gc.ca/n1/tbl/csv/36100434-eng.zip"


BUSINESSNZ_INDEX="https://businessnz.org.nz/psi"
ABS_MHSI_SERVICES="https://www.abs.gov.au/statistics/economy/finance/monthly-household-spending-indicator/latest-release"
def abs_services_fetch(url):
    if url!=ABS_MHSI_SERVICES:raise ValueError("ABS services URL not on allowlist")
    req=Request(url,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":"text/html"})
    with urlopen(req,timeout=25) as response:
        final=response.geturl()
        if urlsplit(final).hostname not in ("www.abs.gov.au","abs.gov.au") or not final.startswith("https://"):
            raise ValueError("ABS redirect outside official site")
        data=response.read(3_500_001)
        if not data or len(data)>3_500_000:raise ValueError("invalid ABS HTML size")
    return data

def _parse_abs_monthly_chart(raw,now,title):
    """ABS exact graph/table identity: monthly % nominal SA (not volume)."""
    html=raw.decode("utf-8","replace")
    identity='aria-label="'+title+'.csv"'
    occurrences=[m.start() for m in re.finditer(re.escape(identity),html)]
    if len(occurrences)!=1:raise ValueError("ABS unique exact chart source missing")
    start=html.find("<table",occurrences[0])
    end=html.find("</table>",start)
    if start<0 or end<0 or end-start>175_000:
        raise ValueError("ABS matching services chart table missing")
    chart=html[start:end+8]
    p=_ReportTables();p.feed(chart)
    if len(p.tables)!=1:raise ValueError("ABS extracted chart count changed")
    values={}
    for row in p.tables[0]:
        if len(row)<2:continue
        m=re.fullmatch(r"([A-Za-z]{3})[- ](\d{4})",row[0])
        if not m:continue
        months=["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
        if m[1].lower() not in months:raise ValueError("ABS date label changed")
        month=months.index(m[1].lower())+1
        period=f"{m[2]}-{month:02d}"
        if period_end(period)>now:continue
        val=float(row[1].replace(",",""))
        if not math.isfinite(val) or abs(val)>100:raise ValueError("invalid ABS monthly growth rate")
        if period in values:raise ValueError("duplicate ABS period")
        values[period]=val
    if len(values)<12:raise ValueError("ABS monthly growth-rate table insufficient")
    return sorted(values.items())

def parse_abs_services(raw,now):
    return _parse_abs_monthly_chart(raw,now,
      "Household spending on services, current price, seasonally adjusted estimate")

def parse_abs_demand(raw,now):
    return _parse_abs_monthly_chart(raw,now,
      "Household spending, current price, seasonally adjusted estimate")

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
    if url not in {ONS_URL,ONS_INDUSTRY,STATCAN_GDP_ZIP}:raise ValueError("unregistered official services URL")
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

EUROSTAT_SERVICES_URL=(
 "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/teibs020?"
 "geo=EA21&s_adj=SA&indic=BS-SCI-BAL&freq=M&sinceTimePeriod=2025-01"
)
EUROSTAT_EXTRA={
 "eurostat_industry":("sts_inpr_m",{"freq":"M","geo":"EA21","indic_bt":"PRD",
      "nace_r2":"B-D","s_adj":"SCA","unit":"I21"}),
 "eurostat_esi":("teibs010",{"freq":"M","geo":"EA21","indic":"BS-ESI-I","s_adj":"SA"}),
 "eurostat_retail":("sts_trtu_m",{"freq":"M","geo":"EA21","indic_bt":"VOL_SLS",
      "nace_r2":"G47","s_adj":"SCA","unit":"I21"}),
}
def euro_extra_url(method):
    dataset,filters=EUROSTAT_EXTRA[method]
    from urllib.parse import urlencode
    return "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"+dataset+"?"+urlencode({
      **filters,"sinceTimePeriod":"2024-01"})

def parse_euro_extra(raw,now,method):
    """Exact dimension selectors and one time series per Eurostat requested category."""
    if method not in EUROSTAT_EXTRA:raise ValueError("unknown Eurostat method")
    dataset,selected=EUROSTAT_EXTRA[method]
    d=json.loads(raw.decode("utf-8"))
    if d.get("class")!="dataset" or not isinstance(d.get("value"),dict):
        raise ValueError("Eurostat "+dataset+" invalid JSON-stat dataset")
    ids=d.get("id",[]); shape=d.get("size",[])
    if len(ids)!=len(shape) or set(ids)!=set(selected)|{"time"}:
        raise ValueError("Eurostat "+dataset+" dimensions changed")
    dimensions=d.get("dimension",{})
    fixed={}
    for k,option in selected.items():
        choices=dimensions.get(k,{}).get("category",{}).get("index",{})
        if not isinstance(choices,dict) or len(choices)!=1 or option not in choices:
            raise ValueError("Eurostat "+dataset+" selector changed: "+k)
        fixed[k]=choices[option]
    periods=dimensions.get("time",{}).get("category",{}).get("index",{})
    if not isinstance(periods,dict) or not periods:
        raise ValueError("Eurostat "+dataset+" period axis missing")
    out={}
    for p,ix in periods.items():
        if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])",p): continue
        if period_end(p)>now:continue
        coords={**fixed,"time":ix}
        index=0
        for dimension,size in zip(ids,shape):index=index*size+coords[dimension]
        value=d["value"].get(str(index))
        if value is None:continue
        y=float(value)
        if not math.isfinite(y) or abs(y)>1000000:
            raise ValueError("Eurostat "+dataset+" value implausible")
        if p in out:raise ValueError("Eurostat "+dataset+" repeated period")
        out[p]=y
    if len(out)<12:raise ValueError("Eurostat "+dataset+" insufficient history")
    return sorted(out.items())

def parse_eurostat_services(raw:bytes,now:date):
    """Exact Eurostat/DG ECFIN EA21 services confidence (BS-SCI-BAL, SA, monthly).
    Fail closed if selection is ambiguous, changed, or not updated.
    """
    d=json.loads(raw.decode("utf-8"))
    if d.get("class")!="dataset" or not isinstance(d.get("value"),dict):
        raise ValueError("Eurostat services JSON-stat dataset missing")
    ids=d.get("id",[])
    shape=d.get("size",[])
    expected={"freq":"M","geo":"EA21","s_adj":"SA","indic":"BS-SCI-BAL"}
    if set(ids)!=set(expected)|{"time"} or len(ids)!=len(shape):
        raise ValueError("Eurostat services dimensions changed")
    dims=d.get("dimension",{})
    positions={}
    for field,key in expected.items():
        values=dims.get(field,{}).get("category",{}).get("index",{})
        if not isinstance(values,dict) or len(values)!=1 or key not in values:
            raise ValueError("Eurostat services source selector changed: "+field)
        positions[field]=values[key]
    time_index=dims.get("time",{}).get("category",{}).get("index",{})
    if not isinstance(time_index,dict):raise ValueError("Eurostat services dates missing")
    obs={}
    for p,index in time_index.items():
        if not re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])",p):
            continue
        if period_end(p)>now:continue
        coords={**positions,"time":index}
        k=0
        for field,size in zip(ids,shape):
            k=k*size+coords[field]
        val=d["value"].get(str(k))
        if val is None:continue
        f=float(val)
        if not math.isfinite(f) or abs(f)>100:raise ValueError("Eurostat services balance invalid")
        if p in obs:raise ValueError("Eurostat services duplicate period")
        obs[p]=f
    if len(obs)<12:raise ValueError("Eurostat services too few observations")
    return sorted(obs.items())

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
      "up_good":spec.get("up_good",True),
      "quality":"SOURCE_REVISED_RESEARCH_NOT_PIT"}
    return payload,{"status":"READY_DESCRIPTIVE_REVISED","last_observation":newest,"days_since_period_end":age}

def curated_official_businessnz(spec,now):
    """Source-verified, manual fallback; NEVER label this as a fetched update."""
    if spec["method"]!="biznz":raise ValueError("fallback only authorized for PSI")
    doc=json.loads(MANUAL_PSI.read_text(encoding="utf-8"))
    expected={"schema":"GMFQ_OFFICIAL_SERVICES_FALLBACK_V1","country":"NZD",
      "area":"services","series_id":"BNZ_BUSINESSNZ_PSI","frequency":"M",
      "source_issuer":"BusinessNZ","seasonal_adjustment":"Seasonally adjusted","baseline":50}
    for key,value in expected.items():
        if doc.get(key)!=value:raise ValueError("manual PSI provenance mismatch")
    uri=doc.get("source_url")
    if not isinstance(uri,str) or not re.fullmatch(
        r"https://businessnz\.org\.nz/psi/[a-z0-9-]+",uri):
        raise ValueError("manual PSI must link to dated official release")
    checked=date.fromisoformat(doc["verified_on"])
    released=date.fromisoformat(doc["official_release_date"])
    if not released<=checked<=now:raise ValueError("manual PSI verification time invalid")
    dates=doc.get("dates");values=doc.get("values")
    if not isinstance(dates,list) or len(dates)!=2 or not isinstance(values,list) or len(values)!=2:
        raise ValueError("manual PSI exact two observations required")
    obs=[]
    for p,v in zip(dates,values):
        period_end(p)
        if not isinstance(v,(int,float)) or not math.isfinite(v) or not 20<=v<=80:
            raise ValueError("manual PSI value outside official survey scale")
        obs.append((p,float(v)))
    if obs!=sorted(obs):raise ValueError("manual PSI dates not ascending")
    item,status=candidate(spec,obs,now)
    if item is None:return None,{"status":"WITHHELD_STALE","reason":"Manually verified PSI snapshot expired"}
    item.update({"quality":"SOURCE_VERIFIED_MANUAL_NONPIT",
        "source_file":"BusinessNZ · verifica manuale "+doc["verified_on"]+" (accesso automatico bloccato)",
        "source_page":uri,
        "manual_verified_on":doc["verified_on"],
        "official_release_date":doc["official_release_date"]})
    return item,{"status":"READY_MANUAL_VERIFIED_NOT_AUTOMATIC",
      "last_observation":item["observation_as_of"],
      "verified_on":doc["verified_on"],
      "source_page":uri}

def curated_statsnz_house(spec,now):
    """Official-release manual snapshot when Stats NZ download is blocked.
    Never describe it as automatically refreshed.
    """
    if spec["method"]!="statsnz_house":raise ValueError("fallback only Stats NZ")
    d=json.loads(MANUAL_NZ_HOUSE.read_text(encoding="utf-8"))
    expected={"schema":"GMFQ_NZD_HOUSING_OFFICIAL_SNAPSHOT_V1",
      "ccy":"NZD","area":"house","source_series_id":"STATSNZ_NEWDWELLINGS_SA",
      "source_issuer":"Stats NZ","freq":"M","status":"MANUAL_OFFICIAL_RELEASE_NOT_LIVE"}
    for k,v in expected.items():
        if d.get(k)!=v:raise ValueError("Stats NZ snapshot provenance changed")
    page=d.get("source_url")
    if page!="https://www.stats.govt.nz/information-releases/building-consents-issued-september-2026/":
        raise ValueError("Stats NZ manual release URL is not exact verified record")
    verified=date.fromisoformat(d["verified_on"])
    release=date.fromisoformat(d["official_release_date"])
    if not release<=verified<=now:raise ValueError("Stats NZ snapshot impossible dates")
    dates=d.get("dates");values=d.get("values")
    if not isinstance(dates,list) or len(dates)!=2 or not isinstance(values,list) or len(values)!=2:
        raise ValueError("Stats NZ snapshot requires two dated observations")
    if dates!=["2026-08","2026-09"]:raise ValueError("Stats NZ snapshot original months changed")
    if any(not isinstance(x,(int,float)) or not math.isfinite(x) or x<=100 or x>100000 for x in values):
        raise ValueError("Stats NZ release values implausible")
    item,status=candidate(spec,list(zip(dates,values)),now)
    if item is None:return None,{"status":"WITHHELD_STALE","reason":"Verified snapshot expired"}
    item.update({"quality":"SOURCE_VERIFIED_MANUAL_NONPIT","source_page":page,
        "source_file":"Stats NZ · verifica manuale "+d["verified_on"]+" (accesso automatico bloccato)",
        "manual_verified_on":d["verified_on"],"official_release_date":d["official_release_date"]})
    return item,{"status":"READY_MANUAL_VERIFIED_NOT_AUTOMATIC",
      "last_observation":item["observation_as_of"],
      "verified_on":d["verified_on"],"source_page":page}

def collect(now=None,fetcher=fetch):
    now=now or datetime.now(timezone.utc).date()
    out={"schema":SCHEMA,"as_of":now.isoformat(),"source_count":len(REGISTRY),
      "series":[],"audit":{},"notes":"Latest revised observations, not PIT, no FX score."}
    for spec in REGISTRY:
        code=spec["ccy"]+"_"+spec["area"]
        url=FRED+spec["key"] if spec["method"]=="fred" else (
          STATCAN_DETAIL[spec["key"]]["url"] if spec["method"]=="statcan_detail" else
          RBA_BASE if spec["method"]=="rba_credit" else
          boe_mortgage_url(now) if spec["method"]=="boe_mortgage" else
          statsnz_house_url(now,2) if spec["method"]=="statsnz_house" else
          ONS_INDUSTRY if spec["method"]=="ons_industry" else
          euro_extra_url(spec["method"]) if spec["method"] in EUROSTAT_EXTRA else
          EUROSTAT_SERVICES_URL if spec["method"]=="eurostat_services" else
          BUSINESSNZ_INDEX if spec["method"]=="biznz" else
          ABS_MHSI_SERVICES if spec["method"] in {"abs_services","abs_demand"} else
          STATCAN_CSV if spec["method"]=="statcan" else
          ONS_URL if spec["method"]=="ons" else
          STATCAN_GDP_ZIP if spec["method"]=="statcan_services" else
          "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_cobp_m?"
          "geo=EA21&indic_bt=BPRM_DW&cpa2_1=CPA_F41001_X_410014&s_adj=SCA&unit=I21&lang=EN")
        try:
            fetched=(statsnz_fetch(url,now) if spec["method"]=="statsnz_house" and fetcher is fetch else
                fetch_rba_aggregate(now) if spec["method"]=="rba_credit" and fetcher is fetch else None)
            raw=(fetched[0] if fetched is not None else
                 fetch_boe(url) if spec["method"]=="boe_mortgage" and fetcher is fetch else
                 biznz_fetch(url) if spec["method"]=="biznz" else
                 fetch_statcan_detail(url) if spec["method"]=="statcan_detail" else
                 abs_services_fetch(url) if spec["method"] in {"abs_services","abs_demand"} else
                 fetch_statcan(url) if spec["method"]=="statcan" else
                 fetch_issuer(url)) if spec["method"] in {"biznz","abs_services","abs_demand","rba_credit","statcan_detail","statcan","ons","ons_industry","statcan_services","boe_mortgage","statsnz_house"} and fetcher is fetch else fetcher(url)
            observations=(parse_statcan_detail(raw,now,spec["key"]) if spec["method"]=="statcan_detail" else
                          parse_rba_aggregates(raw,now,spec["key"],fetched[1] if fetched else rba_release_url(now,2))
                          if spec["method"]=="rba_credit" else
                          parse_statsnz_house(raw,now) if spec["method"]=="statsnz_house" else
                          parse_boe_mortgage(raw,now) if spec["method"]=="boe_mortgage" else
                          parse_ons_industry(raw,now) if spec["method"]=="ons_industry" else
                          parse_euro_extra(raw,now,spec["method"]) if spec["method"] in EUROSTAT_EXTRA else
                          parse_eurostat_services(raw,now) if spec["method"]=="eurostat_services" else
                          parse_fred(raw,spec["key"],spec["frequency"],now)
                          if spec["method"]=="fred" else
                          parse_businessnz_psi(raw,now) if spec["method"]=="biznz" else
                          parse_abs_services(raw,now) if spec["method"]=="abs_services" else
                          parse_abs_demand(raw,now) if spec["method"]=="abs_demand" else
                          parse_statcan(raw,now) if spec["method"]=="statcan" else
                          parse_ons_services(raw,now) if spec["method"]=="ons" else
                          parse_statcan_services(raw,now) if spec["method"]=="statcan_services" else parse_eurostat(raw,now))
            item,status=candidate(spec,observations,now)
            if item is not None:
                if fetched is not None:item["source_page"]=fetched[1]
                out["series"].append(item)
            out["audit"][code]={"...":None,**status,"source_page":spec["source_page"],
                                 "origin":spec["origin"]}
            out["audit"][code].pop("...")
        except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError) as exc:
            if spec["method"]=="statsnz_house":
                try:
                    item,status=curated_statsnz_house(spec,now)
                    if item:out["series"].append(item)
                    out["audit"][code]={**status,"automatic_fetch":"BLOCKED_OR_UNVALIDATED",
                        "automatic_error":str(exc)[:220]}
                    continue
                except (ValueError,KeyError,IndexError,UnicodeError,OSError) as manual_exc:
                    out["audit"][code]={"status":"WITHHELD_FETCH_OR_VALIDATION",
                       "reason":"No verified current Stats NZ: "+str(manual_exc)[:120],
                       "automatic_error":str(exc)[:180],
                       "source_page":spec["source_page"],"origin":spec["origin"]}
                    continue
            if spec["method"]=="biznz":
                try:
                    fallback,status=curated_official_businessnz(spec,now)
                    if fallback:out["series"].append(fallback)
                    out["audit"][code]={**status,"automatic_fetch":"BLOCKED_OR_UNVALIDATED",
                        "automatic_error":str(exc)[:100]}
                    continue
                except (ValueError,KeyError,IndexError,UnicodeError,OSError) as cur_exc:
                    out["audit"][code]={"status":"WITHHELD_FETCH_OR_VALIDATION",
                        "reason":"No current verified PSI: "+str(cur_exc)[:140],
                        "automatic_error":str(exc)[:100],
                        "source_page":spec["source_page"],"origin":spec["origin"]}
                    continue
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
