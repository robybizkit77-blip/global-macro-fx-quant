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
MANUAL_NZ_CREDIT=ROOT/"validation/macro/official_nzd_credit_snapshot_v1.json"
MANUAL_NZ_HOUSE=ROOT/"validation/macro/official_nzd_house_snapshot_v1.json"
SCHEMA="GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1"
FRED="https://fred.stlouisfed.org/graph/fredgraph.csv?id="
MAX_BYTES=3_000_000
# Definitions and transformations deliberately fixed and source-identifiable.
# Several historical OECD/BIS feeds have stopped updating: retain status WITHHELD;
# never use today's fetch time to make an old observation look current.
BOJ_CREDIT_URL="https://www.stat-search.boj.or.jp/ssi/mtshtml/md13_m_1_en.html"
RBNZ_CREDIT_URL="https://www.rbnz.govt.nz/statistics/series/lending-and-monetary/Registered-banks-and-non-bank-lending-institutions-sector-lending"
SNB_CREDIT_URL="https://data.snb.ch/api/cube/bakredinausbm/data/csv/en?fromDate=2023-01"
SNB_CREDIT_META="https://data.snb.ch/api/cube/bakredinausbm/dimensions/en"
REGISTRY=[
 dict(ccy="CHF",area="credit",key="SNB_BAKREDINAUSBM_AV1_I_T1_F",method="snb_credit",
      name="Credito domestico utilizzato, totale prestiti (SNB; stock nominale)",unit="mln CHF nominali",frequency="M",
      kind="percent",max_age_days=85,origin="Swiss National Bank / bakredinausbm",
      source_page="https://data.snb.ch/en/topics/banken/cube/bakredinausbm"),
 dict(ccy="JPY",area="credit",key="BOJ_MD13_FAAPOBAL1_YOY",method="boj_credit",
      name="Crescita prestiti e sconti delle banche maggiori e regionali (BoJ)",unit="% a/a",frequency="M",
      kind="points",max_age_days=85,origin="Bank of Japan / MD13'FAAPOBAL1@",
      source_page=BOJ_CREDIT_URL),
 dict(ccy="GBP",area="leading",key="GBRLOLITOAASTSAM",method="fred",
      name="OECD CLI Regno Unito (indicatore anticipatore)",unit="indice SA",frequency="M",kind="points",max_age_days=85,
      origin="OECD tramite FRED",up_good=True,
      source_page="https://fred.stlouisfed.org/series/GBRLOLITOAASTSAM"),
 dict(ccy="JPY",area="jobs",key="LRUNTTTTJPM156S",method="fred",
      name="Tasso disoccupazione Giappone 15+ SA",unit="% SA",frequency="M",kind="points",max_age_days=85,
      origin="OECD tramite FRED",up_good=False,
      source_page="https://fred.stlouisfed.org/series/LRUNTTTTJPM156S"),
 dict(ccy="JPY",area="industry",key="JPNPRMNTO01GPSAM",method="fred",
      name="Crescita produzione manifatturiera Giappone (SA)",unit="% m/m SA",frequency="M",kind="points",max_age_days=85,
      origin="OECD tramite FRED",up_good=True,
      source_page="https://fred.stlouisfed.org/series/JPNPRMNTO01GPSAM"),
 dict(ccy="JPY",area="demand",key="SLRTTO01JPQ657S",method="fred",
      name="Crescita volumi retail Giappone SA",unit="% q/q SA",frequency="Q",kind="points",max_age_days=175,
      origin="OECD tramite FRED",up_good=True,
      source_page="https://fred.stlouisfed.org/series/SLRTTO01JPQ657S"),
 dict(ccy="CHF",area="house",key="QCHR368BIS",method="fred",
      name="Prezzi immobiliari residenziali reali (variazione annua; proxy immobiliare)",unit="% a/a",frequency="Q",kind="points",max_age_days=175,
      origin="BIS tramite FRED",up_good=True,
      source_page="https://fred.stlouisfed.org/series/QCHR368BIS"),
 dict(ccy="CHF",area="industry",key="PRMNTO01CHQ657S",method="fred",
      name="Crescita produzione manifatturiera Svizzera SA",unit="% q/q SA",frequency="Q",kind="points",max_age_days=175,
      origin="OECD tramite FRED",up_good=True,
      source_page="https://fred.stlouisfed.org/series/PRMNTO01CHQ657S"),
 dict(ccy="CHF",area="demand",key="SLRTTO01CHQ657S",method="fred",
      name="Crescita volumi retail Svizzera SA",unit="% q/q SA",frequency="Q",kind="points",max_age_days=175,
      origin="OECD tramite FRED",up_good=True,
      source_page="https://fred.stlouisfed.org/series/SLRTTO01CHQ657S"),
 dict(ccy="AUD",area="jobs",key="LRUNTTTTAUM156S",method="fred",
      name="Tasso disoccupazione Australia 15+ SA",unit="% SA",frequency="M",kind="points",max_age_days=85,
      origin="OECD tramite FRED",up_good=False,
      source_page="https://fred.stlouisfed.org/series/LRUNTTTTAUM156S"),
 dict(ccy="AUD",area="leading",key="AUSLOLITOAASTSAM",method="fred",
      name="OECD CLI Australia (indicatore anticipatore)",unit="indice SA",frequency="M",kind="points",max_age_days=85,
      origin="OECD tramite FRED",up_good=True,
      source_page="https://fred.stlouisfed.org/series/AUSLOLITOAASTSAM"),
 dict(ccy="NZD",area="demand",key="SLRTTO01NZQ657S",method="fred",
      name="Crescita volumi retail Nuova Zelanda SA",unit="% q/q SA",frequency="Q",kind="points",max_age_days=175,
      origin="OECD tramite FRED",up_good=True,
      source_page="https://fred.stlouisfed.org/series/SLRTTO01NZQ657S"),

 dict(ccy="CAD",area="demand",key="CAN_RETAIL_REAL_LASPEYRES",method="statcan_detail",
      name="Vendite retail reali a prezzi costanti 2017 Canada (SA)",unit="mln CAD reali 2017 SA",
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
 dict(ccy="EUR",area="house",key="EA21_PRC_HPI_Q_TOTAL_RCH_A",method="eurostat_house_price",
      name="Prezzi residenziali nominali EA21 (variazione annua; proxy immobiliare)",unit="% a/a",
      frequency="Q",kind="points",max_age_days=175,
      source_page="https://ec.europa.eu/eurostat/databrowser/view/prc_hpi_q/default/table?lang=en",
      origin="Eurostat / prc_hpi_q"),
 dict(ccy="JPY",area="house",key="JPNRGDPPRI",method="fred",
      name="Investimenti residenziali privati reali Giappone (SA)",unit="mld JPY concatenati 2015 SA",frequency="Q",
      kind="percent",max_age_days=175,origin="Cabinet Office tramite FRED",
      source_page="https://fred.stlouisfed.org/series/JPNRGDPPRI"),
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
 dict(ccy="NZD",area="credit",key="RBNZ_C5_BUSINESS_YOY",method="rbnz_credit",
      name="Crescita prestiti alle imprese NZ, corretta per rotture (RBNZ C5)",unit="% a/a",frequency="M",
      kind="points",max_age_days=85,origin="Reserve Bank of New Zealand / C5",
      source_page="https://www.rbnz.govt.nz/statistics/series/lending-and-monetary/Registered-banks-and-non-bank-lending-institutions-sector-lending"),
 dict(ccy="CAD",area="industry",key="16100047_MANUFACTURING_SA",method="statcan",
      name="Vendite manifatturiere (nominali, destagionalizzate)",unit="migliaia CAD nominali SA",frequency="M",
      kind="percent",max_age_days=110,origin="Statistics Canada table 16-10-0047-01",
      source_page="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610004701"),
]
assert len(REGISTRY)==43 and len({(s["ccy"],s["area"]) for s in REGISTRY})==43

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
 "CAN_RETAIL_REAL_LASPEYRES":{
  "url":"https://www150.statcan.gc.ca/n1/tbl/csv/20100067-eng.zip",
  "file":"20100067.csv","category":"North American Industry Classification System (NAICS)",
  "value":"Retail trade [44-45]","other":"Sales, price and volume",
  "selection":"Retail sales at 2017 constant prices (Unchained Laspeyres Index)",
  "unit":"Dollars","scale":"millions"},
 "CAN_HOUSEHOLD_MORTGAGES_SA":{
  "url":"https://www150.statcan.gc.ca/n1/tbl/csv/36100639-eng.zip",
  "file":"36100639.csv","category":"Credit liabilities of households",
  "value":"Residential mortgages","other":"Seasonality",
  "selection":"Seasonally adjusted data","unit":"Dollars","scale":"millions",
  "vector":"v1231415621"},
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
        values={};references={}
        with archive.open(spec["file"]) as src:
            reader=csv.DictReader(io.TextIOWrapper(src,encoding="utf-8-sig"))
            fields={"REF_DATE","GEO","VALUE","UOM","SCALAR_FACTOR",spec["category"],spec["other"]}
            if "vector" in spec:fields.add("VECTOR")
            if not fields.issubset(set(reader.fieldnames or [])):
                raise ValueError("StatCan required dimensions absent")
            for row in reader:
                if row["GEO"]!="Canada" or row[spec["category"]]!=spec["value"] or row[spec["other"]]!=spec["selection"]:
                    continue
                if "vector" in spec and row.get("VECTOR")!=spec["vector"]:
                    continue
                if row["UOM"]!=spec["unit"] or row["SCALAR_FACTOR"]!=spec["scale"]:
                    raise ValueError("StatCan selected unit/scale mismatch: "+row["UOM"]+"/"+row["SCALAR_FACTOR"])
                p=row["REF_DATE"]
                if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])",p):
                    raise ValueError("StatCan selected month code invalid")
                if period_end(p)>now:continue
                raw_value=row["VALUE"]
                if raw_value in ("", "..", "."):continue
                v=float(raw_value)
                if not math.isfinite(v) or v<=0 or v>1e12:
                    raise ValueError("StatCan selected value implausible")
                if p in values:raise ValueError("StatCan selected duplicate month "+p+" current="+row.get("COORDINATE","?")+" vector="+row.get("VECTOR","?")+" prior="+references.get(p,"?"))
                values[p]=v;references[p]=row.get("COORDINATE","?")+"/"+row.get("VECTOR","?")
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
            if label!=target and not (target=="Business" and label.replace(" ","") in {"Businessa"}):continue
            try: first=float(row[1].replace(",",""));second=float(row[2].replace(",",""))
            except ValueError:continue
            if not all(math.isfinite(x) and -15<=x<=15 for x in (first,second)):
                raise ValueError("RBA growth rate impossible")
            values.append((first,second))
    if len(values)!=1:raise ValueError("RBA credit subcategory ambiguous/missing")
    return [(prev,values[0][0]),(current,values[0][1])]


RBA_D1_CSV="https://www.rba.gov.au/statistics/tables/csv/d1-data.csv"

def parse_rba_d1(raw,now,which,reference):
    """Accept only an unambiguous official monthly growth column matching the release.
    No stitching of separate vintages or growth computed from credit stocks.
    """
    sector={"RBA_HOUSING_CREDIT_GROWTH_MM":"housing",
            "RBA_BUSINESS_CREDIT_GROWTH_MM":"business"}.get(which)
    if sector is None or len(reference)!=2:raise ValueError("RBA D1 identity/reference")
    rows=list(csv.reader(StringIO(raw.decode("utf-8-sig"))))
    meta={}
    for row in rows[:30]:
        if row:
            label=row[0].strip().lower()
            if label in {"title","description","units","frequency","series id"}:
                if label in meta:raise ValueError("RBA D1 duplicate metadata")
                meta[label]=row
    titles=meta.get("title",meta.get("description",[]))
    def field(label,i):
        row=meta.get(label,[])
        return row[i].strip().lower() if i<len(row) else ""
    def norm(s):
        return re.sub(r"[^a-z0-9]+"," ",s.lower()).strip()
    matches=[]
    for i,t in enumerate(titles[1:],1):
        title=norm(t)
        if sector=="business":
            # RBA release footnote (a): lending to non-financial businesses.
            # The former generic business series is discontinued; never substitute
            # the broader series including select financial institutions.
            if field("series id",i)!="dgfacbnfm" or title not in {
                    "credit non financial business monthly growth",
                    "credit non financial business monthly growth sa"}:
                continue
        elif title not in {f"credit {sector} monthly growth",f"{sector} credit monthly growth",
                           f"credit {sector} monthly percentage change",f"{sector} credit monthly percentage change"}:
            continue
        if field("frequency",i)!="monthly" or field("units",i) not in {"%","per cent","percent","percentage"} or not field("series id",i):
            continue
        obs={}
        for row in rows:
            if not row or i>=len(row):continue
            stamp=row[0].strip()
            p=None
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}",stamp):
                p=date.fromisoformat(stamp).strftime("%Y-%m")
            else:
                for fmt in ("%d-%b-%Y","%b-%Y","%d/%m/%Y","%d %b %Y"):
                    try:p=datetime.strptime(stamp,fmt).strftime("%Y-%m");break
                    except ValueError:pass
            if p is None or period_end(p)>now or not row[i].strip():continue
            try:v=float(row[i])
            except ValueError:raise ValueError("RBA D1 nonnumeric observation")
            if not math.isfinite(v) or not -15<=v<=15 or p in obs:raise ValueError("RBA D1 invalid observation")
            obs[p]=v
        ordered=sorted(obs.items())
        if len(ordered)<12:continue
        if [p for p,v in ordered[-2:]]!=[p for p,v in reference]:continue
        if any(abs(v-r)>0.05000001 for (_,v),(_,r) in zip(ordered[-2:],reference)):continue
        # Keep the exact source values; the live release is only an identity cross-check.
        history=contiguous_history(ordered,"M",now)
        if history["observations"]>=12:matches.append(ordered)
    if len(matches)!=1:raise ValueError("RBA D1 exact current growth column unavailable/ambiguous")
    return matches[0]

def fetch_rba_d1(now,which,reference):
    req=Request(RBA_D1_CSV,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":"text/csv"})
    with urlopen(req,timeout=16) as response:
        if response.geturl()!=RBA_D1_CSV:raise ValueError("RBA D1 unexpected redirect")
        raw=response.read(3_000_001)
        if not raw or len(raw)>3_000_000:raise ValueError("RBA D1 size")
    return parse_rba_d1(raw,now,which,reference)


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

ONS_WAGE_URL="https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kac3/lms"

def parse_ons_wage(raw,now):
    """ONS KAC3: whole economy, nominal total pay, SA rolling 3m YoY."""
    txt=raw.decode("utf-8","replace")
    p=_PlainText();p.feed(txt)
    plain=" ".join(" ".join(p.parts).split())
    if not re.search(r"Series ID:\s*KAC3\b",plain) or not re.search(
        r"Whole Economy Year on Year Three Month Average Growth \(%\): Seasonally Adjusted Total Pay Excluding Arrears",plain,re.I):
        raise ValueError("ONS KAC3 identity changed")
    table=_ReportTables();table.feed(txt)
    out={}
    for rows in table.tables:
        for row in rows:
            if len(row)!=2:continue
            mm=re.fullmatch(r"(\d{4}) (JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)",row[0],re.I)
            if not mm:continue
            month=["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"].index(mm[2].upper())+1
            period=f"{int(mm[1]):04d}-{month:02d}"
            if period_end(period)>now:continue
            if row[1] in ("","..",":","-"):continue
            v=float(row[1])
            if not math.isfinite(v) or abs(v)>50 or period in out:raise ValueError("ONS KAC3 invalid/duplicate value")
            out[period]=v
    if len(out)<12:raise ValueError("ONS KAC3 history unavailable")
    return sorted(out.items())

CAN_WAGE_PID=14100063
CAN_WAGE_PAGE="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301"
CAN_WAGE_MEMBERS={
 "Geography":"Canada","Wages":"Average hourly wage rate",
 "Type of work":"Both full- and part-time employees","Gender":"Total - Gender",
 "Age group":"15 years and over",
 "North American Industry Classification System (NAICS)":"Total employees, all industries"}
def statcan_wage_wds(method,payload):
    if method not in {"getCubeMetadata","getDataFromCubePidCoordAndLatestNPeriods"}:
        raise ValueError("unregistered wage WDS method")
    url="https://www150.statcan.gc.ca/t1/wds/rest/"+method
    req=Request(url,data=json.dumps([payload]).encode(),headers={"Content-Type":"application/json","Accept":"application/json","User-Agent":"GMFQ-Economic-Research/1.0"})
    with urlopen(req,timeout=25) as r:
        if r.geturl()!=url:raise ValueError("WDS redirect")
        raw=r.read(4_000_001)
        if not raw or len(raw)>4_000_000:raise ValueError("WDS response size")
    result=json.loads(raw)
    if not isinstance(result,list) or len(result)!=1 or result[0].get("status")!="SUCCESS":raise ValueError("WDS query failed")
    obj=result[0]["object"]
    if int(obj.get("productId",0))!=CAN_WAGE_PID or obj.get("responseStatusCode")!=0:
        raise ValueError("WDS product identity")
    return obj

def can_wage_coordinate(meta):
    if int(meta.get("productId",0))!=CAN_WAGE_PID or "Employee wages by industry, monthly" not in meta.get("cubeTitleEn",""):
        raise ValueError("Canada wage cube identity")
    dimensions=meta["dimension"]
    if len(dimensions)!=len(CAN_WAGE_MEMBERS):raise ValueError("Canada wage dimension count")
    coord=[0]*10;seen=set()
    for dim in dimensions:
        name=dim["dimensionNameEn"]
        if name not in CAN_WAGE_MEMBERS or name in seen:raise ValueError("Canada wage dimension identity")
        seen.add(name)
        match=[m for m in dim["member"] if m["memberNameEn"]==CAN_WAGE_MEMBERS[name]]
        pos=int(dim["dimensionPositionId"])-1
        if len(match)!=1 or not 0<=pos<6 or coord[pos]:raise ValueError("Canada wage dimension ambiguity")
        coord[pos]=int(match[0]["memberId"])
        if coord[pos]<=0:raise ValueError("Canada wage member invalid")
    if not all(coord[:6]):raise ValueError("Canada wage missing coordinate")
    return ".".join(map(str,coord))

def parse_can_wage_wds(obj,coordinate,now):
    if int(obj.get("productId",0))!=CAN_WAGE_PID or obj.get("coordinate")!=coordinate:
        raise ValueError("Canada wage response coordinate mismatch")
    obs={}
    for row in obj["vectorDataPoint"]:
        p=period(row["refPer"],"M")
        if period_end(p)>now:continue
        v=row.get("value")
        if v is None:continue
        if row.get("scalarFactorCode")!=0 or not isinstance(v,(float,int)) or isinstance(v,bool) or not math.isfinite(v) or not 5<=v<=150 or p in obs:
            raise ValueError("Canada wage level/scale/period invalid")
        obs[p]=v
    # Same calendar month of the preceding year; no interpolation or splicing.
    rates=[]
    for p,v in sorted(obs.items()):
        prior=str(int(p[:4])-1)+p[4:]
        if prior in obs:rates.append((p,100*(v/obs[prior]-1)))
    if len(rates)<12:raise ValueError("Canada wage annual history insufficient")
    return rates

NZ_WAGE_KEY="STATSNZ_LCI_ALL_RATES_YOY"
NZ_WAGE_RELEASE="https://www.stats.govt.nz/information-releases/labour-market-statistics-"
NZ_WAGE_FALLBACK="https://www.stats.govt.nz/news/unemployment-rate-at-5-7-percent-in-the-september-2026-quarter/"

def parse_nz_wage_release(raw,now):
    """Use the full historical LCI table in one official release, not a stitched series."""
    parser=_ReportTables();parser.feed(raw.decode("utf-8","replace"))
    candidates=[]
    months={"mar":1,"jun":2,"sept":3,"sep":3,"dec":4}
    for table in parser.tables:
        if not table:continue
        header=table[0]
        if len(header)!=3 or header[0].lower()!="quarter":continue
        if not re.fullmatch(r"LCI\s*[-–—]\s*all salary and wage rates",header[1],re.I):continue
        if not re.fullmatch(r"(?:QES\s*[-–—]\s*ordinary time hourly earnings|CPI\s*[-–—]\s*all groups)",header[2],re.I):continue
        values={}
        for row in table[1:]:
            if len(row)!=3:raise ValueError("LCI table width")
            hit=re.fullmatch(r"(Mar|Jun|Sept|Sep|Dec)[- ](\d{2}|\d{4})",row[0],re.I)
            if not hit:raise ValueError("LCI period invalid")
            y=int(hit[2]);y=y+2000 if y<100 else y
            p=f"{y}-Q{months[hit[1].lower()]}"
            if period_end(p)>now:continue
            value=float(row[1])
            if p in values or not math.isfinite(value) or abs(value)>20:raise ValueError("LCI value invalid")
            values[p]=value
        if len(values)<12:raise ValueError("LCI insufficient history")
        candidates.append(sorted(values.items()))
    if len(candidates)!=1:raise ValueError("LCI exact table missing or ambiguous")
    return candidates[0]

def fetch_nz_wage_release(now):
    from urllib.parse import urljoin
    def get(url):
        req=Request(url,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":"text/html"})
        with urlopen(req,timeout=25) as r:
            final=urlsplit(r.geturl())
            if final.scheme!="https" or final.hostname not in {"www.stats.govt.nz","stats.govt.nz"}:
                raise ValueError("LCI untrusted redirect")
            raw=r.read(5_000_001)
            if not raw or len(raw)>5_000_000:raise ValueError("LCI response size")
        return raw
    urls=[]
    for back in (1,2):
        q=now.year*4+(now.month-1)//3-back
        y,n=divmod(q,4)
        month=date(y,(n+1)*3,1).strftime("%B").lower()
        page=NZ_WAGE_RELEASE+f"{month}-{y}-quarter/"
        try:
            raw=get(page)
            try:return parse_nz_wage_release(raw,now),page
            except ValueError:pass
            for link in re.findall(r'href=["\']([^"\']+)',raw.decode("utf-8","replace"),re.I):
                url=urljoin(page,unescape(link))
                p=urlsplit(url)
                if p.scheme=="https" and p.hostname in {"www.stats.govt.nz","stats.govt.nz"} and p.path.startswith("/news/unemployment-rate-") and f"{month}-{y}-quarter" in p.path and url not in urls:
                    urls.append(url)
        except (ValueError,OSError,TimeoutError):pass
    if NZ_WAGE_FALLBACK not in urls:urls.append(NZ_WAGE_FALLBACK)
    for url in urls[:5]:
        try:return parse_nz_wage_release(get(url),now),url
        except (ValueError,OSError,TimeoutError):pass
    raise ValueError("No accessible official LCI historical table")


def curated_nz_wage(now):
    """Manual transcription from ONE official 4 November 2026 release.
    Not an automated source download. Expire by next expected release.
    """
    released=date(2026,11,4)
    checked=date(2026,11,25)
    if not released<=checked<=now or now>=date(2027,2,4):
        raise ValueError("Manual NZ LCI snapshot expired or future")
    dates=["2023-Q4","2024-Q1","2024-Q2","2024-Q3","2024-Q4","2025-Q1",
           "2025-Q2","2025-Q3","2025-Q4","2026-Q1","2026-Q2","2026-Q3"]
    values=[4.3,4.1,4.3,3.8,3.3,2.9,2.4,2.1,2.0,2.0,2.0,2.1]
    return list(zip(dates,values)),NZ_WAGE_RELEASE+"september-2026-quarter/"


CH_WAGE_ANNUAL_PAGE="https://statistik.admin.ch/en/asset/36503589"
CH_WAGE_ESTIMATE_CSV="https://dam-api.bfs.admin.ch/hub/api/dam/assets/36791145/master"

def ch_wage_annual_context(now):
    """Published actual annual rates, not quarterly observations or estimates.
    Single FSO release, 21 April 2026; manual verification, expiry at next annual release."""
    checked=date(2026,11,25)
    if now<checked or now>=date(2027,4,30):
        raise ValueError("Swiss annual wage snapshot expired or future")
    return {"ccy":"CHF","area":"wages","source_series_id":"FSO_SWI_NOMINAL_ANNUAL",
       "label":"Swiss Wage Index nominale (dato annuale definitivo)",
       "frequency":"A","unit":"% a/a","dates":["2023","2024","2025"],"values":[1.7,1.8,1.8],
       "source_page":CH_WAGE_ANNUAL_PAGE,"source_file":"FSO / Swiss Wage Index · verifica manuale",
       "quality":"SOURCE_VERIFIED_MANUAL_NONPIT","manual_verified_on":checked.isoformat(),
       "official_release_date":"2026-04-21","manual_expires_on":"2027-04-30",
       "observation_as_of":"2025","scope":"ANNUAL_ACTUAL_NOT_QUARTERLY"}

def probe_ch_wage_estimate():
    """Bounded source inspection. Never publish unvalidated estimate values."""
    req=Request(CH_WAGE_ESTIMATE_CSV,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":"text/csv"})
    with urlopen(req,timeout=15) as r:
        if r.geturl()!=CH_WAGE_ESTIMATE_CSV:raise ValueError("Swiss wage CSV redirected")
        raw=r.read(65537)
    if not raw or len(raw)>65536:raise ValueError("Swiss wage CSV size")
    lines=raw.decode("utf-8-sig").splitlines()
    if len(lines)<2:raise ValueError("Swiss wage CSV missing rows")
    return {"status":"SCHEMA_INSPECTION_ONLY","source_page":"https://statistik.admin.ch/en/asset/36791145",
      "header":lines[0][:500],"sample":lines[1][:500],"last_rows":lines[-3:],"rows":len(lines)}

# Real exports of goods and services, quarterly YoY, seasonally adjusted.
# Explicit OECD identities; no obsolete EA19 or nominal trade balance proxy.
EXPORT_KEYS={"USD":"NAEXKP06USQ659S","GBP":"NAEXKP06GBQ659S","JPY":"NAEXKP06JPQ659S",
 "CHF":"NAEXKP06CHQ659S","CAD":"NAEXKP06CAQ659S","AUD":"NAEXKP06AUQ659S",
 "NZD":"NAEXKP06NZQ659S","EUR":"EUROSTAT_EA21_P6_REAL_EXPORTS_YOY"}

ONS_CORE_URL="https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/dko8/mm23"
CORE_RECOVERY={
 "USD":dict(key="CPILFESL",method="fred",name="CPI core USA (indice SA)",unit="Index 1982-1984=100",origin="BLS tramite FRED / CPILFESL",source_page="https://fred.stlouisfed.org/series/CPILFESL"),
 "GBP":dict(key="DKO8",method="ons_core",name="CPI core UK (esclusi energia, alimentari, alcol e tabacco)",unit="% a/a",origin="ONS / DKO8",source_page=ONS_CORE_URL)
}
def parse_ons_core(raw,now):
    txt=raw.decode("utf-8","replace")
    p=_PlainText();p.feed(txt)
    plain=" ".join(" ".join(p.parts).split())
    if not re.search(r"Series ID:\s*DKO8\b",plain) or not re.search(r"CPI 12mth:\s*Excluding Energy,\s*food,\s*alcoholic beverages\s*&\s*tobacco",plain,re.I):
        raise ValueError("ONS DKO8 identity changed")
    table=_ReportTables();table.feed(txt)
    out={}
    for rows in table.tables:
        for row in rows:
            if len(row)!=2:continue
            mm=re.fullmatch(r"(\d{4}) (JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)",row[0],re.I)
            if not mm:continue
            month=["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"].index(mm[2].upper())+1
            p=f"{int(mm[1]):04d}-{month:02d}"
            if period_end(p)>now or row[1] in ("","..",":","-"):continue
            v=float(row[1])
            if not math.isfinite(v) or abs(v)>50 or p in out:raise ValueError("ONS DKO8 invalid/duplicate value")
            out[p]=v
    if len(out)<12:raise ValueError("ONS DKO8 history unavailable")
    return sorted(out.items())

def collect_inflation_context(now,fred_fetcher=fetch,ons_fetcher=None):
    result={"schema":"GMFQ_G8_INFLATION_CONTEXT_V1","series":[],"audit":{}}
    for ccy,definition in CORE_RECOVERY.items():
        try:
            key=definition["key"]
            obs=(parse_fred(fred_fetcher(FRED+key),key,"M",now) if ccy=="USD"
                 else parse_ons_core((ons_fetcher or fetch_issuer)(ONS_CORE_URL),now))
            if ccy=="USD" and any(v<=0 for _,v in obs):raise ValueError("non-positive CPI index")
            spec=dict(**definition,ccy=ccy,area="core",frequency="M",kind="points",max_age_days=85)
            item,status=candidate(spec,obs,now)
            if item:
                if ccy=="USD":
                    # Exact annual comparisons need their own base, not a
                    # contiguous 14-month run. Never impute a missing index.
                    latest=obs[-1][0]
                    def ix(p):return int(p[:4])*12+int(p[5:])
                    records={ix(p):v for p,v in obs}
                    recent=[(p,v) for p,v in obs if ix(latest)-ix(p)<36]
                    valid=[p for p,v in recent if ix(p)-12 in records]
                    if not valid:raise ValueError("US core index has no exact annual comparison")
                    item["exact_lag_history"]={"schema":"GMFQ_US_CORE_EXACT_LAG_V1",
                        "source_series_id":key,"dates":[p for p,v in recent],
                        "values":[v for p,v in recent]}
                    status={**status,"latest_index_period":latest,
                            "latest_yoy_period":valid[-1],
                            "annual_status":"EXACT_LAG_AVAILABLE" if valid[-1]==latest else "SOURCE_BASE_PERIOD_MISSING"}
                result["series"].append(item)
            result["audit"][ccy]=status
        except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError) as exc:
            result["audit"][ccy]={"status":"WITHHELD_FETCH_OR_VALIDATION","reason":str(exc)[:180]}
    return result

def collect_external_context(now,fetcher=fetch):
    result={"schema":"GMFQ_G8_EXTERNAL_CONTEXT_V1","series":[],"audit":{}}
    for ccy,key in EXPORT_KEYS.items():
        euro=ccy=="EUR"
        method="eurostat_exports_real" if euro else "fred"
        page="https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table?lang=en" if euro else "https://fred.stlouisfed.org/series/"+key
        try:
            obs=(parse_euro_extra(fetcher(euro_extra_url(method)),now,method) if euro
                else parse_fred(fetcher(FRED+key),key,"Q",now))
            spec=dict(ccy=ccy,area="external",key=key,method=method,
                name="Esportazioni reali di beni e servizi (crescita annua, SA)",
                unit="% a/a reale",frequency="Q",kind="points",max_age_days=175,
                origin="Eurostat / namq_10_gdp" if euro else "OECD tramite FRED / "+key,
                source_page=page)
            item,status=candidate(spec,obs,now)
            if item:result["series"].append(item)
            result["audit"][ccy]={**status,"source_page":page}
        except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError) as exc:
            result["audit"][ccy]={"status":"WITHHELD_FETCH_OR_VALIDATION","reason":str(exc)[:180],"source_page":page}
    return result

def collect_wage_context(now):
    """Independent context feed, not counted as an activity indicator."""
    result={"schema":"GMFQ_G8_WAGE_CONTEXT_V1","series":[],"audit":{}}
    try:
        obs=parse_ons_wage(fetch_issuer(ONS_WAGE_URL),now)
        spec=dict(ccy="GBP",area="wages",key="KAC3",method="ons_wage",
            name="Retribuzioni medie settimanali nominali (totale, media 3 mesi a/a, SA)",
            unit="% a/a",frequency="M",kind="points",max_age_days=85,
            origin="ONS / KAC3",source_page=ONS_WAGE_URL)
        item,status=candidate(spec,obs,now)
        if item:
            result["series"].append(item)
        result["audit"]["GBP"]=status
    except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError) as exc:
        result["audit"]["GBP"]={"status":"WITHHELD_FETCH_OR_VALIDATION","reason":str(exc)[:180]}
    try:
        meta=statcan_wage_wds("getCubeMetadata",{"productId":CAN_WAGE_PID})
        coord=can_wage_coordinate(meta)
        obj=statcan_wage_wds("getDataFromCubePidCoordAndLatestNPeriods",{"productId":CAN_WAGE_PID,"coordinate":coord,"latestN":49})
        obs=parse_can_wage_wds(obj,coord,now)
        spec=dict(ccy="CAD",area="wages",key="STATCAN_14100063_HOURLY_WAGE_YOY",method="statcan_wage",
            name="Salari orari medi nominali LFS (tutti i dipendenti, NSA, crescita annua)",
            unit="% a/a",frequency="M",kind="points",max_age_days=85,
            origin="Statistics Canada / 14-10-0063-01",source_page=CAN_WAGE_PAGE)
        item,status=candidate(spec,obs,now)
        if item:result["series"].append(item)
        result["audit"]["CAD"]={**status,"coordinate":coord}
    except (ValueError,KeyError,TypeError,IndexError,UnicodeError,TimeoutError,OSError) as exc:
        result["audit"]["CAD"]={"status":"WITHHELD_FETCH_OR_VALIDATION","reason":str(exc)[:180]}
    try:
        key="LCEAMN01JPQ659S"
        obs=parse_fred(fetch(FRED+key),key,"Q",now)
        spec=dict(ccy="JPY",area="wages",key=key,method="fred",
            name="Retribuzioni orarie manifatturiere nominali (proxy settoriale OECD, SA)",
            unit="% a/a",frequency="Q",kind="points",max_age_days=175,
            origin="OECD tramite FRED / LCEAMN01JPQ659S",
            source_page="https://fred.stlouisfed.org/series/LCEAMN01JPQ659S")
        item,status=candidate(spec,obs,now)
        if item:result["series"].append(item)
        result["audit"]["JPY"]={**status,"proxy_scope":"manufacturing hourly earnings only"}
    except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError) as exc:
        result["audit"]["JPY"]={"status":"WITHHELD_FETCH_OR_VALIDATION","reason":str(exc)[:180]}
    try:
        manual=False
        try:
            obs,page=fetch_nz_wage_release(now)
        except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError):
            obs,page=curated_nz_wage(now)
            manual=True
        spec=dict(ccy="NZD",area="wages",key=NZ_WAGE_KEY,method="statsnz_lci",
            name="Labour Cost Index nominale (tutti i settori, inclusi straordinari)",
            unit="% a/a",frequency="Q",kind="points",max_age_days=175,
            origin="Stats NZ / tabella LCI annual percentage change",source_page=page)
        item,status=candidate(spec,obs,now)
        if item:
            if manual:
                item.update(quality="SOURCE_VERIFIED_MANUAL_NONPIT",manual_verified_on="2026-11-25",
                    official_release_date="2026-11-04",manual_expires_on="2027-02-04")
                item["source_file"]+=" · verificato manualmente, non acquisito automaticamente"
                item["history"]["quality"]="MANUALLY_VERIFIED_SNAPSHOT_NOT_PIT"
                status={**status,"status":"READY_MANUAL_VERIFIED_NOT_AUTOMATIC","automatic_fetch":"FAILED"}
            result["series"].append(item)
        result["audit"]["NZD"]=status
    except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError) as exc:
        result["audit"]["NZD"]={"status":"WITHHELD_FETCH_OR_VALIDATION","reason":str(exc)[:180]}
    try:
        item=ch_wage_annual_context(now)
        result["series"].append(item)
        result["audit"]["CHF"]={"status":"READY_MANUAL_ANNUAL_CONTEXT_ONLY","last_observation":"2025",
            "history_observations":3,"scope":"ANNUAL_ACTUAL_NOT_QUARTERLY"}
    except (ValueError,KeyError) as exc:
        result["audit"]["CHF"]={"status":"WITHHELD_STALE","reason":str(exc)}
    try:
        result["audit"]["CHF_estimate"]=probe_ch_wage_estimate()
    except (ValueError,UnicodeError,TimeoutError,OSError) as exc:
        result["audit"]["CHF_estimate"]={"status":"WITHHELD_FETCH_OR_VALIDATION","reason":str(exc)[:180]}
    return result

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

def statsnz_house_zip_url(now,back):
    n=now.year*12+now.month-1-back
    y,m=n//12,n%12+1
    name=date(y,m,1).strftime("%B")
    return ("https://www.stats.govt.nz/assets/Uploads/Building-consents-issued/"
       f"Building-consents-issued-{name}-{y}/Download-data/building-consents-issued-{name.lower()}-{y}.zip")

def parse_statsnz_house_zip(raw,now):
    """Stats NZ official series BLDM.SFTZ1100A1S, national SA dwelling counts."""
    values={}
    with ZipFile(io.BytesIO(raw)) as z:
        members=[x for x in z.infolist() if x.filename.lower().endswith(".csv") and not x.is_dir()]
        if not members or sum(x.file_size for x in members)>350_000_000:
            raise ValueError("Stats NZ CSV archive missing or oversized")
        for member in members:
            with z.open(member) as stream:
                reader=csv.DictReader(io.TextIOWrapper(stream,encoding="utf-8-sig"))
                if not {"Series_reference","Period","Data_value","UNITS","MAGNTUDE"}.issubset(reader.fieldnames or []):
                    if not {"Series_reference","Period","Data_value","UNITS","MAGNITUDE"}.issubset(reader.fieldnames or []):continue
                for row in reader:
                    if row.get("Series_reference")!="BLDM.SFTZ1100A1S":continue
                    if row.get("UNITS","").lower() not in {"number","units"} or row.get("MAGNTUDE",row.get("MAGNITUDE"))!="0":
                        raise ValueError("Stats NZ SA dwelling series unit or scale changed")
                    if row.get("Suppressed","").strip():continue
                    match=re.fullmatch(r"(\d{4})[.\-](\d{2})",row["Period"])
                    if not match:raise ValueError("Stats NZ monthly period invalid")
                    p=f"{match[1]}-{match[2]}"
                    if period_end(p)>now or not row["Data_value"].strip():continue
                    val=float(row["Data_value"])
                    if p in values or not math.isfinite(val) or not 100<val<100000:
                        raise ValueError("Stats NZ duplicate or implausible dwelling count")
                    values[p]=val
    if len(values)<2:raise ValueError("Stats NZ exact BLDM.SFTZ1100A1S absent")
    return sorted(values.items())

def statsnz_fetch_zip(now):
    for back in range(1,4):
        url=statsnz_house_zip_url(now,back)
        try:
            req=Request(url,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":"application/zip,application/octet-stream"})
            with urlopen(req,timeout=25) as r:
                if urlsplit(r.geturl()).hostname!="www.stats.govt.nz":raise ValueError("Stats NZ archive off official host")
                raw=r.read(32_000_001)
                if len(raw)>32_000_000:raise ValueError("Stats NZ archive above budget")
            observations=parse_statsnz_house_zip(raw,now)
            latest=statsnz_house_url(now,back)
            return observations,latest
        except (OSError,ValueError,KeyError,UnicodeError,TimeoutError,__import__("zipfile").BadZipFile):continue
    raise ValueError("No verified Stats NZ dwelling archive")

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
BNZ_PSI_INDEX="https://www.bnz.co.nz/institutional-banking/research/publications"
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

class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in {"script","style"}:self.skip+=1
    def handle_endtag(self,tag):
        if tag in {"script","style"}:self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)


ANZ_OUTLOOK_URL="https://www.anz.co.nz/about-us/economic-markets-research/business-outlook/"

def parse_anz_outlook(raw,now):
    """Rounded own-activity net balances in the issuer's dated release summaries.
    Use only adjacent monthly releases; do not present as a single revised vintage.
    """
    p=_PlainText();p.feed(raw.decode("utf-8","replace"))
    txt=" ".join(" ".join(p.parts).split())
    if "ANZ Business Outlook" not in txt or "Expected own activity" not in txt:
        raise ValueError("ANZ survey identity absent")
    months={date(2000,m,1).strftime("%B"):m for m in range(1,13)}
    heading=re.compile(r"(?<![\w-])("+"|".join(months)+r")\s+(20\d{2})\s+(?=Business confidence\b)",re.I)
    values={}
    for hit in heading.finditer(txt):
        year=int(hit[2]);month=months[hit[1].title()]
        period=f"{year}-{month:02d}"
        if date(year,month,1)>now:continue
        body=txt[hit.end():hit.end()+550]
        # Only the first sentence on forward own activity, never past activity,
        # headline confidence or a change expressed in points.
        m=re.search(r"\bExpected own activity\b[^.]{0,130}?\b(?:to|at)\s+([+\-−]?\d{1,3}(?:\.\d+)?)\b",body,re.I)
        if not m:continue
        value=float(m[1].replace("−","-"))
        if not -100<=value<=100:raise ValueError("ANZ net balance range")
        if period in values and values[period]!=value:raise ValueError("ANZ conflicting release summaries")
        values[period]=value
    obs=sorted(values.items())
    # Reject stale headings, skipped months and ambiguous/partial source extraction.
    if len(obs)<2:raise ValueError("ANZ adjacent release summaries missing")
    latest=obs[-2:]
    contiguous_last_two(latest,"M")
    if period_end(latest[-1][0])>now:raise ValueError("ANZ observation month not closed")
    if (now-period_end(latest[-1][0])).days>65:raise ValueError("ANZ release summaries stale")
    return latest

def collect_anz_outlook(spec,now):
    req=Request(ANZ_OUTLOOK_URL,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":"text/html"})
    with urlopen(req,timeout=18) as r:
        if r.geturl().rstrip("/")!=ANZ_OUTLOOK_URL.rstrip("/"):raise ValueError("ANZ unexpected redirect")
        raw=r.read(3_000_001)
        if not raw or len(raw)>3_000_000:raise ValueError("ANZ source size")
    alt={**spec,"key":"ANZ_NZD_OWN_ACTIVITY_OUTLOOK_ROUNDED",
         "name":"ANZ attese attività propria (proxy anticipatore; saldi arrotondati da comunicati)",
         "unit":"saldo netto %","kind":"points","origin":"ANZ Business Outlook / release summaries",
         "source_page":ANZ_OUTLOOK_URL,"max_age_days":65}
    item,status=candidate(alt,parse_anz_outlook(raw,now),now)
    if item:
        item["history"]["quality"]="ROUNDED_RELEASE_SUMMARIES_NOT_SINGLE_VINTAGE"
        status["history_quality"]=item["history"]["quality"]
    return item,status


def parse_bnz_psi(raw,now):
    """Co-publisher's dated press release, taking the latest vintage's revised prior."""
    p=_PlainText();p.feed(raw.decode("utf-8","replace"))
    txt=" ".join(" ".join(p.parts).split())
    months={date(2000,m,1).strftime("%B").lower():m for m in range(1,13)}
    monthpat="|".join(months)
    found={}
    for hit in re.finditer(r"\b(?:BNZ|NZ) Research\s*[-–]\s*BusinessNZ\s*[-–]\s*(\d{2}\.\d{2}\.20\d{2})",txt):
        release=datetime.strptime(hit[1],"%d.%m.%Y").date()
        if release>now:continue
        body=txt[hit.end():hit.end()+1000]
        if not re.search(r"Performance of Services Index\s*\(PSI\)",body[:350],re.I):continue
        current=re.search(r"The PSI for ("+monthpat+r") was\s+(\d{2}\.\d)",body,re.I)
        if not current:continue
        prior=re.search(r"\bfrom\s+(\d{2}\.\d)\s+in\s+("+monthpat+r")\b",body[current.end():current.end()+500],re.I)
        if not prior:continue
        m=months[current[1].lower()];pm=months[prior[2].lower()]
        year=release.year if m<=release.month else release.year-1
        period=f"{year}-{m:02d}"
        py=year-1 if m==1 else year
        if pm!=(m-2)%12+1:continue
        previous=f"{py}-{pm:02d}"
        if period_end(period)>release or (release-period_end(period)).days>45:continue
        x,y=float(current[2]),float(prior[1])
        if not (20<=x<=80 and 20<=y<=80):raise ValueError("BNZ PSI outside valid scale")
        pair=[(previous,y),(period,x)]
        if release in found and found[release]!=pair:raise ValueError("BNZ conflicting releases")
        found[release]=pair
    if not found:raise ValueError("BNZ dated national PSI pair missing")
    return found[max(found)]

def fetch_bnz_psi(now):
    req=Request(BNZ_PSI_INDEX,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":"text/html"})
    with urlopen(req,timeout=20) as r:
        if r.geturl().rstrip("/")!=BNZ_PSI_INDEX:raise ValueError("BNZ unexpected redirect")
        raw=r.read(5_000_001)
        if not raw or len(raw)>5_000_000:raise ValueError("BNZ page invalid size")
    return parse_bnz_psi(raw,now)

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

def parse_boj_credit(raw,now):
    parser=_ReportTables();parser.feed(raw.decode("utf-8","replace"))
    results=[]
    for tab in parser.tables:
        header=next((r for r in tab if any("MD13'FAAPOBAL1@" in c for c in r)),None)
        if not header:continue
        cols=[i for i,c in enumerate(header) if "MD13'FAAPOBAL1@" in c]
        if len(cols)!=1:raise ValueError("BOJ credit code ambiguous")
        col=cols[0]
        name=next((r for r in tab if len(r)==len(header) and
                  "percent changes in average amounts outstanding from previous year" in r[col]),None)
        unit=next((r for r in tab if len(r)==len(header) and r[0]=="Unit" and r[col]=="%"),None)
        if not name or not unit:raise ValueError("BOJ credit identity/units changed")
        out={}
        for row in tab:
            if len(row)!=len(header) or not re.fullmatch(r"\d{4}/(?:0[1-9]|1[0-2])",row[0]):continue
            p=row[0].replace("/","-")
            if period_end(p)>now or row[col] in {"ND","-",""}:continue
            v=float(row[col])
            if not math.isfinite(v) or abs(v)>50 or p in out:raise ValueError("BOJ invalid/duplicate rate")
            out[p]=v
        if len(out)>=12:results.append(sorted(out.items()))
    if len(results)!=1:raise ValueError("BOJ exact credit table missing/ambiguous")
    return results[0]

def parse_rbnz_credit(raw,now):
    html=raw.decode("utf-8","replace")
    if not all(x in html for x in ("Sector lending (C5)","Annual growth rate","break-adjusted")):
        raise ValueError("RBNZ C5 identity or break adjustment missing")
    parser=_ReportTables();parser.feed(html)
    results=[]
    months={m:i+1 for i,m in enumerate(("jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"))}
    for tab in parser.tables:
        header=None;in_growth=False
        for row in tab:
            found=[re.fullmatch(r"([A-Za-z]{3,9}) (20\d{2})",c) for c in row]
            if sum(bool(x) for x in found)>=5:
                header=[(i,f"{m[2]}-{months[m[1][:3].lower()]:02d}") for i,m in enumerate(found)
                        if m and m[1][:3].lower() in months]
            if row and row[0].startswith("Annual growth rate (%)"):in_growth=True;continue
            if not in_growth or not header or not row:continue
            if not re.fullmatch(r"Business(?:\s*[\[\]{}()^0-9]+)*",row[0]):continue
            out={}
            for i,p in header:
                if i>=len(row):raise ValueError("RBNZ C5 header alignment changed")
                if period_end(p)>now:continue
                v=float(row[i].replace(",",""))
                if not math.isfinite(v) or abs(v)>100 or p in out:raise ValueError("RBNZ invalid/duplicate rate")
                out[p]=v
            if len(out)>=5:results.append(sorted(out.items()))
    if len(results)!=1:raise ValueError("RBNZ C5 exact annual growth row absent/ambiguous")
    return results[0]

def validate_snb_credit_metadata(raw):
    d=json.loads(raw.decode("utf-8-sig"))
    if d.get("cubeId")!="bakredinausbm":raise ValueError("SNB cube mismatch")
    expected={"D0":("AV1","Banks in Switzerland"),"D1":("I","Domestic"),
              "D2":("T1","Total loans"),"D3":("F","Utilisation")}
    dims={x["id"]:x for x in d["dimensions"]}
    if set(dims)!=set(expected):raise ValueError("SNB dimensions changed")
    for k,(code,name) in expected.items():
        choices=[x for x in dims[k]["dimensionItems"] if x["id"]==code and x["name"]==name]
        if len(choices)!=1:raise ValueError("SNB credit dimension identity changed: "+k)

def parse_snb_credit(raw,now):
    rows=list(csv.reader(StringIO(raw.decode("utf-8-sig")),delimiter=";"))
    if len(rows)<16 or rows[0]!=["CubeId","bakredinausbm"] or rows[1][0]!="PublishingDate":
        raise ValueError("SNB CSV identity changed")
    if date.fromisoformat(rows[1][1][:10])>now:raise ValueError("SNB future publishing date")
    start=next((i for i,row in enumerate(rows) if row==["Date","D0","D1","D2","D3","Value"]),None)
    if start is None:raise ValueError("SNB CSV dimensions changed")
    out={}
    for row in rows[start+1:]:
        if not row:continue
        if len(row)!=6:raise ValueError("SNB CSV width changed")
        p,*coords,v=row
        if coords!=["AV1","I","T1","F"]:continue
        if not re.fullmatch(r"\d{4}-\d{2}",p):raise ValueError("SNB invalid monthly period")
        if period_end(p)>now or v in {"","-","."}:continue
        value=float(v)
        if p in out or not math.isfinite(value) or not 10000<value<10000000:
            raise ValueError("SNB invalid or duplicate domestic loan stock")
        out[p]=value
    if len(out)<12:raise ValueError("SNB domestic credit history missing")
    return sorted(out.items())

def fetch_issuer(url):
    if url not in {ONS_URL,ONS_INDUSTRY,ONS_WAGE_URL,ONS_CORE_URL,STATCAN_GDP_ZIP,BOJ_CREDIT_URL,RBNZ_CREDIT_URL,SNB_CREDIT_URL,SNB_CREDIT_META}:raise ValueError("unregistered official services URL")
    accept=("application/json" if url==SNB_CREDIT_META else "text/csv" if url==SNB_CREDIT_URL else "text/html,application/zip")
    req=Request(url,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":accept})
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
 "geo=EA21&s_adj=SA&indic=BS-SCI-BAL&freq=M&sinceTimePeriod=2023-01"
)
EUROSTAT_EXTRA={
 "eurostat_exports_real":("namq_10_gdp",{"freq":"Q","geo":"EA21","na_item":"P6","s_adj":"SCA","unit":"CLV_PCH_SM"}),
 "eurostat_house_price":("prc_hpi_q",{"freq":"Q","geo":"EA21","purchase":"TOTAL","unit":"RCH_A"}),
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
      **filters,"sinceTimePeriod":"2020-Q1" if filters["freq"]=="Q" else "2023-01"})

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
        if not re.fullmatch(r"\d{4}-Q[1-4]" if selected["freq"]=="Q" else r"\d{4}-(?:0[1-9]|1[0-2])",p): continue
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

def contiguous_history(observations,frequency,now):
    """Retain at most 36 months / 12 quarters from a single revised source vintage.
    Never bridge a gap, mix different release vintages or fill missing points."""
    if frequency not in {"M","Q"}:raise ValueError("unsupported history frequency")
    if len(observations)<2:raise ValueError("insufficient observations")
    limit=36 if frequency=="M" else 12
    def index(p):
        if not re.fullmatch(r"\d{4}-\d{2}" if frequency=="M" else r"\d{4}-Q[1-4]",p):
            raise ValueError("history frequency mismatch")
        period_end(p)
        return int(p[:4])*(12 if frequency=="M" else 4)+int(p[5:] if frequency=="M" else p[-1])
    ordered=[]
    previous=None
    for p,v in observations:
        ix=index(p)
        if previous is not None and ix<=previous:raise ValueError("history not strictly ascending")
        if period_end(p)>now or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
            raise ValueError("invalid history observation")
        ordered.append((ix,p,v));previous=ix
    tail=[ordered[-1]]
    for row in reversed(ordered[:-1]):
        if len(tail)>=limit or tail[-1][0]-row[0]!=1:break
        tail.append(row)
    if len(tail)<2:raise ValueError("latest history gap")
    tail.reverse()
    return {"schema":"GMFQ_SEMAPHORE_CONTIGUOUS_HISTORY_V1",
            "frequency":frequency,"dates":[x[1] for x in tail],"values":[x[2] for x in tail],
            "observations":len(tail),"max_observations":limit,
            "quality":"SINGLE_SOURCE_REVISED_VINTAGE_NOT_PIT"}


def candidate(spec,observations,now):
    newest=observations[-1][0]
    age=(now-period_end(newest)).days
    if age>spec["max_age_days"]:
        return None,{"status":"WITHHELD_STALE","last_observation":newest,"days_since_period_end":age}
    if age<0:raise ValueError("future period")
    points=contiguous_last_two(observations,spec["frequency"])
    history=contiguous_history(observations,spec["frequency"],now)
    payload={"ccy":spec["ccy"],"area":spec["area"],
      "id":"SEM_G8_"+spec["ccy"]+"_"+spec["area"].upper(),
      "label":spec["name"],"frequency":spec["frequency"],"unit":spec["unit"],
      "dates":[x[0] for x in points],"values":[x[1] for x in points],
      "category":"Semaforo supplementare","source_file":spec["origin"],
      "source_page":spec["source_page"],"source_series_id":spec["key"],
      "metric_kind":spec["kind"],"observation_as_of":newest,
      "diffusion_threshold":50 if spec["method"]=="biznz" else None,
      "up_good":spec.get("up_good",True),
      "quality":"SOURCE_REVISED_RESEARCH_NOT_PIT",
      "history":{**history,"source_series_id":spec["key"]}}
    return payload,{"status":"READY_DESCRIPTIVE_REVISED","last_observation":newest,"days_since_period_end":age,
                    "history_observations":history["observations"]}

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
    item["history"]["quality"]="MANUALLY_VERIFIED_SNAPSHOT_NOT_PIT"
    item.update({"quality":"SOURCE_VERIFIED_MANUAL_NONPIT",
        "source_file":"BusinessNZ · verifica manuale "+doc["verified_on"]+" (accesso automatico bloccato)",
        "source_page":uri,
        "manual_verified_on":doc["verified_on"],
        "official_release_date":doc["official_release_date"]})
    return item,{"status":"READY_MANUAL_VERIFIED_NOT_AUTOMATIC",
      "last_observation":item["observation_as_of"],
      "verified_on":doc["verified_on"],
      "source_page":uri}



def prefer_current_psi(spec,now,item,status):
    """An older automatically fetched release must not displace a newer verified one.
    Compare observation periods, never fetch timestamps. Keep automatic on equal periods.
    """
    try:
        manual,manual_status=curated_official_businessnz(spec,now)
    except (ValueError,KeyError,IndexError,UnicodeError,OSError):
        return item,status
    if manual and (item is None or manual["observation_as_of"]>item["observation_as_of"]):
        return manual,{**manual_status,"automatic_last_observation":item["observation_as_of"] if item else None,
                       "automatic_fetch":"OLDER_OR_UNAVAILABLE"}
    return item,status


def collect_nzd_bis_housing(spec,now,fetcher=fetch):
    """Quarterly real house-price YoY proxy, not dwelling consents.
    Only used if the automatic Stats NZ sources failed; never splice histories.
    """
    if (spec["ccy"],spec["area"])!=("NZD","house"):raise ValueError("NZD housing proxy identity")
    key="QNZR368BIS"
    alt={**spec,"key":key,"name":"Prezzi immobiliari residenziali reali NZ (proxy immobiliare BIS, variazione annua)",
         "unit":"% a/a reale","frequency":"Q","kind":"points","max_age_days":175,
         "origin":"Fonti nazionali / BIS Residential Property Price database tramite FRED",
         "source_page":"https://fred.stlouisfed.org/series/"+key}
    obs=parse_fred(fetcher(FRED+key),key,"Q",now)
    if any(abs(v)>100 for _,v in obs):raise ValueError("BIS property price annual growth range")
    if contiguous_history(obs,"Q",now)["observations"]<12:raise ValueError("BIS housing insufficient contiguous history")
    return candidate(alt,obs,now)


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
    item["history"]["quality"]="MANUALLY_VERIFIED_SNAPSHOT_NOT_PIT"
    item.update({"quality":"SOURCE_VERIFIED_MANUAL_NONPIT","source_page":page,
        "source_file":"Stats NZ · verifica manuale "+d["verified_on"]+" (accesso automatico bloccato)",
        "manual_verified_on":d["verified_on"],"official_release_date":d["official_release_date"]})
    return item,{"status":"READY_MANUAL_VERIFIED_NOT_AUTOMATIC",
      "last_observation":item["observation_as_of"],
      "verified_on":d["verified_on"],"source_page":page}

NZD_CREDIT_PROXY_URL="https://tradingeconomics.com/new-zealand/private-sector-credit"

def parse_nzd_credit_proxy(raw,now):
    """Publicly reported RBNZ private credit stock, NOT C5 business growth."""
    p=_PlainText();p.feed(raw.decode("utf-8","replace"))
    txt=" ".join(" ".join(p.parts).split())
    months={date(2000,m,1).strftime("%B").lower():m for m in range(1,13)}
    pat="|".join(months)
    m=re.search(r"Private Sector Credit in New Zealand (?:increased|decreased|rose|fell) to ([\d,.]+) NZD Million in ("+pat+r") from ([\d,.]+) NZD Million in ("+pat+r") of (20\d{2})\.",txt,re.I)
    if not m:raise ValueError("NZD private credit exact published pair missing")
    if not re.search(r"source:\s*Reserve Bank of New Zealand",txt,re.I):
        raise ValueError("NZD credit issuer attribution missing")
    cur,prev=months[m[2].lower()],months[m[4].lower()]
    if prev!=(cur-2)%12+1:raise ValueError("NZD credit nonadjacent months")
    year=int(m[5])+(cur==1)
    period=f"{year}-{cur:02d}";prior=f"{int(m[5])}-{prev:02d}"
    if period_end(period)>now:raise ValueError("NZD credit future period")
    current=float(m[1].replace(",",""));previous=float(m[3].replace(",",""))
    if not all(math.isfinite(x) and 10000<x<2000000 for x in (current,previous)):
        raise ValueError("NZD credit stock invalid")
    return [(prior,previous),(period,current)]

def collect_nzd_credit_proxy(spec,now):
    req=Request(NZD_CREDIT_PROXY_URL,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":"text/html"})
    with urlopen(req,timeout=20) as r:
        if r.geturl().rstrip("/")!=NZD_CREDIT_PROXY_URL:raise ValueError("NZD credit proxy redirect")
        raw=r.read(2_000_001)
        if not raw or len(raw)>2_000_000:raise ValueError("NZD credit proxy size")
    obs=parse_nzd_credit_proxy(raw,now)
    # Never replace newer verified C5 data with older proxy observations.
    manual=json.loads(MANUAL_NZ_CREDIT.read_text(encoding="utf-8"))
    if obs[-1][0]<manual["dates"][-1]:raise ValueError("NZD credit proxy older than C5")
    alt={**spec,"key":"RBNZ_PRIVATE_CREDIT_STOCK_TE","name":"Credito privato totale, stock nominale (proxy del credito; RBNZ via Trading Economics)",
         "unit":"mln NZD nominali","kind":"percent","origin":"RBNZ / Trading Economics","source_page":NZD_CREDIT_PROXY_URL}
    return candidate(alt,obs,now)

def curated_rbnz_credit(spec,now):
    if spec["key"]!="RBNZ_C5_BUSINESS_YOY":raise ValueError("RBNZ snapshot identity")
    d=json.loads(MANUAL_NZ_CREDIT.read_text(encoding="utf-8"))
    expected={"schema":"GMFQ_RBNZ_C5_OFFICIAL_SNAPSHOT_V1","series_id":spec["key"],
      "source_url":"https://www.rbnz.govt.nz/statistics/series/lending-and-monetary/registered-banks-and-non-bank-lending-institutions-sector-lending",
      "unit":"% a/a","adjustment":"Break-adjusted",
      "scope":"Registered banks and non-bank lending institutions; business loans excluding agriculture"}
    if any(d.get(k)!=v for k,v in expected.items()):raise ValueError("RBNZ snapshot provenance mismatch")
    release=date.fromisoformat(d["official_release_date"]);verified=date.fromisoformat(d["verified_on"])
    if not release<=verified<=now:raise ValueError("RBNZ snapshot verification date invalid")
    periods=d["dates"];values=d["values"]
    if len(periods)!=2 or len(values)!=2 or period_end(periods[-1])>release:
        raise ValueError("RBNZ snapshot periods invalid")
    if any(not isinstance(x,(int,float)) or not math.isfinite(x) or abs(x)>100 for x in values):
        raise ValueError("RBNZ snapshot rate invalid")
    # Never present an old manual observation as current after the next monthly release + grace.
    if (now-release).days>38:return None,{"status":"WITHHELD_STALE","reason":"RBNZ verified release expired"}
    item,status=candidate(spec,list(zip(periods,values)),now)
    if item is None:return None,status
    item["history"]["quality"]="MANUALLY_VERIFIED_SNAPSHOT_NOT_PIT"
    item.update({"quality":"SOURCE_VERIFIED_MANUAL_NONPIT","source_page":d["source_url"],
        "source_file":"RBNZ C5 · verifica manuale "+d["verified_on"]+" (download automatico bloccato)",
        "manual_verified_on":d["verified_on"],"official_release_date":d["official_release_date"]})
    return item,{"status":"READY_MANUAL_VERIFIED_NOT_AUTOMATIC",
        "last_observation":item["observation_as_of"],"verified_on":d["verified_on"]}

def collect(now=None,fetcher=fetch):
    now=now or datetime.now(timezone.utc).date()
    out={"schema":SCHEMA,"as_of":now.isoformat(),"source_count":len(REGISTRY),
      "series":[],"audit":{},"notes":"Latest revised observations, not PIT, no FX score."}
    for spec in REGISTRY:
        code=spec["ccy"]+"_"+spec["area"]
        url=FRED+spec["key"] if spec["method"]=="fred" else (
          SNB_CREDIT_URL if spec["method"]=="snb_credit" else
          BOJ_CREDIT_URL if spec["method"]=="boj_credit" else
          RBNZ_CREDIT_URL if spec["method"]=="rbnz_credit" else
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
            if spec["method"]=="snb_credit" and fetcher is fetch:
                validate_snb_credit_metadata(fetch_issuer(SNB_CREDIT_META))
            fetched=(statsnz_fetch(url,now) if spec["method"]=="statsnz_house" and fetcher is fetch else
                fetch_rba_aggregate(now) if spec["method"]=="rba_credit" and fetcher is fetch else None)
            raw=(fetched[0] if fetched is not None else
                 fetch_boe(url) if spec["method"]=="boe_mortgage" and fetcher is fetch else
                 biznz_fetch(url) if spec["method"]=="biznz" else
                 fetch_statcan_detail(url) if spec["method"]=="statcan_detail" else
                 abs_services_fetch(url) if spec["method"] in {"abs_services","abs_demand"} else
                 fetch_statcan(url) if spec["method"]=="statcan" else
                 fetch_issuer(url)) if spec["method"] in {"snb_credit","boj_credit","rbnz_credit","biznz","abs_services","abs_demand","rba_credit","statcan_detail","statcan","ons","ons_industry","statcan_services","boe_mortgage","statsnz_house"} and fetcher is fetch else fetcher(url)
            observations=(parse_snb_credit(raw,now) if spec["method"]=="snb_credit" else
                          parse_boj_credit(raw,now) if spec["method"]=="boj_credit" else
                          parse_rbnz_credit(raw,now) if spec["method"]=="rbnz_credit" else
                          parse_statcan_detail(raw,now,spec["key"]) if spec["method"]=="statcan_detail" else
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
            history_page=None
            if spec["method"]=="rba_credit" and fetcher is fetch:
                try:
                    extended=fetch_rba_d1(now,spec["key"],observations)
                    extended_item,_=candidate(spec,extended,now)
                    if extended_item and extended_item["history"]["observations"]>2:
                        observations=extended
                        history_page=RBA_D1_CSV
                except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError):
                    pass # retain verified latest release if archive is not validated
            item,status=candidate(spec,observations,now)
            if item is None and spec["key"]=="NZLLOLITOAASTSAM" and fetcher is fetch:
                try:
                    proxy,proxy_status=collect_anz_outlook(spec,now)
                    if proxy:
                        out["series"].append(proxy)
                        out["audit"][code]={**proxy_status,"proxy":True,"source_page":proxy["source_page"],
                            "origin":proxy["source_file"],"primary_status":status["status"],
                            "primary_last_observation":status.get("last_observation")}
                        continue
                except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError) as proxy_exc:
                    status["proxy_error"]=str(proxy_exc)[:180]
            if spec["method"]=="biznz" and fetcher is fetch:
                item,status=prefer_current_psi(spec,now,item,status)
                if item and status["status"]=="READY_MANUAL_VERIFIED_NOT_AUTOMATIC":
                    out["series"].append(item)
                    out["audit"][code]={**status,"source_page":item["source_page"],"origin":item["source_file"]}
                    continue
            if item is not None:
                if fetched is not None:item["source_page"]=fetched[1]
                if history_page:
                    item["source_page"]=history_page
                    item["source_file"]="RBA D1 / Monthly growth (cross-checked against latest release)"
                out["series"].append(item)
            out["audit"][code]={"...":None,**status,"source_page":spec["source_page"],
                                 "origin":spec["origin"]}
            out["audit"][code].pop("...")
        except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError) as exc:
            if spec["key"]=="NZLLOLITOAASTSAM" and fetcher is fetch:
                try:
                    proxy,proxy_status=collect_anz_outlook(spec,now)
                    if proxy:
                        out["series"].append(proxy)
                        out["audit"][code]={**proxy_status,"proxy":True,"source_page":proxy["source_page"],
                            "origin":proxy["source_file"],"primary_error":str(exc)[:160]}
                        continue
                except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError) as proxy_exc:
                    exc=ValueError(str(exc)[:80]+"; ANZ: "+str(proxy_exc)[:90])
            if spec["method"]=="rbnz_credit":
                if fetcher is fetch:
                    try:
                        item,status=collect_nzd_credit_proxy(spec,now)
                        if item:
                            out["series"].append(item)
                            out["audit"][code]={**status,"source_page":item["source_page"],"origin":item["source_file"],"primary_error":str(exc)[:160],"proxy":True}
                            continue
                    except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError):
                        pass
                try:
                    item,status=curated_rbnz_credit(spec,now)
                    if item:out["series"].append(item)
                    out["audit"][code]={**status,"automatic_fetch":"BLOCKED_OR_UNVALIDATED","automatic_error":str(exc)[:180]}
                    continue
                except (ValueError,KeyError,IndexError,UnicodeError,OSError):
                    pass
            if spec["method"]=="statsnz_house":
                if fetcher is fetch:
                    try:
                        observations,page=statsnz_fetch_zip(now)
                        item,status=candidate(spec,observations,now)
                        if item:
                            item.update({"source_page":page,"source_file":"Stats NZ / CSV BLDM.SFTZ1100A1S"})
                            out["series"].append(item)
                            out["audit"][code]={**status,"source_page":page,"origin":"Stats NZ / BLDM.SFTZ1100A1S","primary_error":str(exc)[:160]}
                            continue
                    except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError):
                        pass
                if fetcher is fetch:
                    try:
                        item,status=collect_nzd_bis_housing(spec,now)
                        if item:
                            out["series"].append(item)
                            out["audit"][code]={**status,"source_page":item["source_page"],
                                "origin":item["source_file"],"primary_error":str(exc)[:160],
                                "proxy":True,"proxy_scope":"real residential prices, not permits"}
                            continue
                    except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError) as bis_exc:
                        exc=ValueError(str(exc)[:90]+"; BIS proxy: "+str(bis_exc)[:90])
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
                if fetcher is fetch:
                    try:
                        item,status=candidate(spec,fetch_bnz_psi(now),now)
                        item,status=prefer_current_psi(spec,now,item,status)
                        if item:
                            if status["status"]!="READY_MANUAL_VERIFIED_NOT_AUTOMATIC":
                                item.update({"source_page":BNZ_PSI_INDEX,"source_file":"BNZ / BusinessNZ · pubblicazione ufficiale coautore"})
                            out["series"].append(item)
                            out["audit"][code]={**status,"source_page":item["source_page"],"origin":item["source_file"],"primary_error":str(exc)[:160]}
                            continue
                    except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError):
                        pass
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
    if fetcher is fetch:
        out["wage_context"]=collect_wage_context(now)
        out["external_context"]=collect_external_context(now)
        out["inflation_context"]=collect_inflation_context(now)
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
      "wage_context":out.get("wage_context",{}).get("audit",{}),
      "external_context":out.get("external_context",{}).get("audit",{}),
      "inflation_context":out.get("inflation_context",{}).get("audit",{}),
      "history_observations":{s["ccy"]+"_"+s["area"]:s.get("history",{}).get("observations",0) for s in out["series"]},
      "audit":{k:v["status"] for k,v in out["audit"].items()},
      "withheld_reasons":{k:v.get("reason","") for k,v in out["audit"].items() if v["status"]=="WITHHELD_FETCH_OR_VALIDATION"}},ensure_ascii=False))
if __name__=="__main__":main()
