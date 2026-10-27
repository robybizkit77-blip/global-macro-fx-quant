#!/usr/bin/env python3
"""One-shot capture of 25 issuer first-month SECO published SA unemployment rates.

Access official SECO release reports from Sep 2024 to Sep 2026 and extract
the 1-decimal registered unemployment seasonally adjusted (%) from p.6 table1.
This is NOT historically exact first-release SNB 'amarbma' cube vintage.
Do not use values from columns for previous/current year or future editions.
"""
from __future__ import annotations
import hashlib, io, json, re, time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import fitz
import requests

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/"validation/macro/fixtures/seco_chf_sa_registered_unemployment_25_first_monthly_reports_2024_09_2026_09.json"
LIST="https://www.seco.admin.ch/de/arbeitsmarktstatistik-berichte-rechtsgrundlagen"
MONTHS=("Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember")
OLD={
"2024-09":"https://www.seco.admin.ch/dam/seco/de/dokumente/Publikationen_Dienstleistungen/Publikationen_Formulare/Arbeit/Arbeitslosenversicherung/Die%20Lage%20auf%20dem%20Arbeitsmarkt/arbeitsmarkt_2024/lage_arbeitsmarkt_september_2024.pdf.download.pdf/2024-09_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf",
"2024-10":"https://www.seco.admin.ch/dam/seco/de/dokumente/Publikationen_Dienstleistungen/Publikationen_Formulare/Arbeit/Arbeitslosenversicherung/Die%20Lage%20auf%20dem%20Arbeitsmarkt/arbeitsmarkt_2024/large_arbeitsmarkt_oktober_2024.pdf.download.pdf/2024-10_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf",
"2024-11":"https://www.seco.admin.ch/dam/seco/de/dokumente/Publikationen_Dienstleistungen/Publikationen_Formulare/Arbeit/Arbeitslosenversicherung/Die%20Lage%20auf%20dem%20Arbeitsmarkt/arbeitsmarkt_2024/large_arbeitsmarkt_november_2024.pdf.download.pdf/2024-11_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf",
"2024-12":"https://www.seco.admin.ch/dam/seco/de/dokumente/Publikationen_Dienstleistungen/Publikationen_Formulare/Arbeit/Arbeitslosenversicherung/Die%20Lage%20auf%20dem%20Arbeitsmarkt/arbeitsmarkt_2024/lage_arbeitsmarkt_dezember_2024.pdf.download.pdf/2024-12_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf",
}
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; gmfq-open-source-issuer-audit/1.0)"}
EXPECTED=[f"{y:04d}-{m:02d}" for y in (2024,2025,2026) for m in range(1,13)
          if "2024-09"<=f"{y:04d}-{m:02d}"<="2026-09"]

def require(ok,why):
    if not ok:raise ValueError("SECO_25_OFFICIAL_ORIGINALS_REJECTED: "+why)

def retrieve(url,pdf=False):
    host=urlparse(url).hostname
    require(host in {"www.seco.admin.ch","seco.admin.ch"},
            "issuer domain outside SECO official")
    response=requests.get(url,headers=HEADERS,timeout=45,allow_redirects=True)
    response.raise_for_status()
    require(urlparse(response.url).hostname in {"www.seco.admin.ch","seco.admin.ch"},
            "issuer redirect outside official host")
    data=response.content
    require(len(data)>1000 and len(data)<4_000_000,"missing or oversized SECO source")
    if pdf:require(data.startswith(b"%PDF-"),"publisher source is not PDF")
    return data,response.url

def discover():
    h,_=retrieve(LIST)
    page=BeautifulSoup(h,"html.parser")
    docs=dict(OLD)
    for a in page.find_all("a",href=True):
        label=a.get_text(" ",strip=True)
        match=re.search(r"Die Lage auf dem Arbeitsmarkt im\s+("+"|".join(MONTHS)+r")\s+(202[56])\b",label,re.I)
        if not match:continue
        month=next(i+1 for i,n in enumerate(MONTHS) if n.lower()==match[1].lower())
        key=f"{match[2]}-{month:02d}"
        url=requests.compat.urljoin(LIST,a["href"])
        require(urlparse(url).hostname in {"www.seco.admin.ch","seco.admin.ch"} and
                url.lower().endswith(".pdf"),"publisher document is not official PDF")
        require(key not in docs,"duplicate official SECO report "+key)
        docs[key]=url
    require(set(docs)==set(EXPECTED),
            f"25 SECO monthly original report URLs required, got {sorted(docs)}")
    return docs,hashlib.sha256(h).hexdigest()

def extract_seasonal_first_rate(raw,key):
    document=fitz.open(stream=raw,filetype="pdf")
    require(22<=len(document)<=35,"expected official SECO month report")
    start=document[0].get_text("text",sort=True)
    name=MONTHS[int(key[5:])-1]
    require(name in start and key[:4] in start,"report cover economic month drift: "+key)
    # First report date appears on cover, formatted (e.g. "6. Oktober 2026"),
    # not a timestamp of first HTTP availability.
    releases=re.findall(r"\b(\d{1,2})\.\s*("+ "|".join(MONTHS)+r")\s+(202[4567])\b",start)
    require(len(releases)>=1,"official report calendar date missing: "+key)
    n,mon,year=releases[0]
    release_day=date(int(year),MONTHS.index(mon)+1,int(n))
    year_ref,month_ref=map(int,key.split("-"))
    require((release_day.year-year_ref)*12+release_day.month-month_ref in (1,2),
            "report date not following reported month")
    # Original report table on printed p.6, physical PDF index 5.
    table=document[5].get_text("text",sort=True).replace("\u00ad","")
    match=re.search(r"Arbeitslosenquote.{0,40}?(?:\n|$).*?Saisonbereinigt",table,re.S)
    require(match is not None and "Tabelle 1" in table,"official unemployment table missing")
    segment=table[match.end():match.end()+190]
    numbers=re.findall(r"(?<!\d)(\d{1,2},\d)(?!\d)",segment)
    # First number is first-report value in the economic month column;
    # second and third are in the previous-month/year comparison columns.
    require(len(numbers)>=3,"seasonally adjusted rate comparison columns missing")
    rate=float(numbers[0].replace(",","."))
    require(1.0<=rate<=8.0,"implausible Swiss registered SA rate")
    return rate,release_day,len(document),{
        "table_rate_current":numbers[0],"table_rate_previous":numbers[1],
        "table_rate_last_year":numbers[2]}

def run():
    urls,page_sha=discover()
    rows=[]
    for key in EXPECTED:
        raw,final=retrieve(urls[key],pdf=True)
        rate,day,pages,comparisons=extract_seasonal_first_rate(raw,key)
        item={
            "reference_month":key,"original_seco_rounded_sa_registered_unemployment_pct":rate,
            "published_report_date":day.isoformat(),
            "conservative_available_from_utc":(day+timedelta(days=1)).isoformat()+"T00:00:00+00:00",
            "release_time_quality":"DAY_AFTER_OFFICIAL_REPORT_DATE_NOT_PROVEN_INTRADAY_AVAILABLE",
            "official_month_report_url":final,
            "official_pdf_sha256_captured_now":hashlib.sha256(raw).hexdigest(),
            "original_month_pdf_pages":pages,
            "first_column_validated_against_comparison_columns":comparisons,
            "source_metric":"SECO_REGISTERED_UNEMPLOYMENT_SEASONALLY_ADJUSTED_ROUNDED_0P1PCT",
            "original_release_day_HTTP_bytes_preserved_at_its_own_date":False,
            "equivalent_to_exact_SNB_AMARBMA_first_vintage":False,
        }
        rows.append(item)
        print(key,day,rate,flush=True)
        time.sleep(.12)
    require(len(rows)==25 and [r["reference_month"] for r in rows]==EXPECTED,
            "all 24 prior original published headline months must be present")
    require(rows[-1]["original_seco_rounded_sa_registered_unemployment_pct"]==3.1,
            "September-2026 first headline conflicts with separately verified SECO")
    require(rows[-9]["reference_month"]=="2026-01" and
            rows[-9]["original_seco_rounded_sa_registered_unemployment_pct"]==2.9,
            "January 2026 independently reviewed SECO first headline differs")
    output={
        "schema":"GMFQ_MACRO_V2_CHF_25_OFFICIAL_SECO_MONTH_REPORT_FIRST_ROUNDED_SA_RATES_V1",
        "source_publisher":"Swiss State Secretariat for Economic Affairs (SECO)",
        "official_index_url":LIST,
        "index_capture_SHA256":page_sha,
        "source_recovery":"2026-10-27_DOWNLOAD_OF_OFFICIAL_ISSUER_REPORTS_NOT_CONTEMPORANEOUS_CAPTURE",
        "metric":"CH_SECO_REGISTRATION_SA_UNEMPLOYMENT_RATE_0P1_PERCENT_ALTERNATIVE",
        "frequency":"M","unit":"percent","precision_decimals":1,
        "archived_issuer_first_rounded_reports":rows,
        "first_reference_month":"2024-09","last_reference_month":"2026-09",
        "observations":25,"prior_training_observations":24,
        "source_day_first_HTTP_payloads_independently_archived":False,
        "complete_historical_SNB_exact_release_vintage_proven":False,
        "can_replace_canonical_CH_UNEMP_RATE_history_value":False,
        "safe_to_publish_new_D":False,"safe_for_beta":False,
        "safe_for_forward":False,"writes_live_data":False,
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

if __name__=="__main__":
    run()
