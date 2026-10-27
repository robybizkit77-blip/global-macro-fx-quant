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
    # Read first-release SA REGISTERED unemployment from the independent
    # publisher's "Kurzübersicht" (physical PDF page 4), not the separate
    # seasonally adjusted JOBSEEKER rate in the later part of Table 1.
    summary=document[4].get_text("text",sort=True).replace("\u00ad","")
    clean=" ".join(summary.split())
    match=re.search(r"Die\s+saisonbereinigte\s+Arbeitslosenquote\b(.{0,260}?)\.",clean,re.I)
    require(match is not None,"SECO original SA unemployment sentence missing: "+key)
    quoted=re.findall(r"(?:auf|bei)\s+(\d{1,2},\d)\s*%",match.group(1),re.I)
    require(len(quoted)==1,"SECO SA unemployment quote not unique: "+key+" "+match.group(1))
    rate=float(quoted[0].replace(",","."))
    require(1.0<=rate<=6.0,"SA registered unemployment rate outside plausible 1–6%")
    table=document[5].get_text("text",sort=True).replace("\u00ad","")
    require("Tabelle 1" in table and "Langzeitarbeitslose" in table and
            "Arbeitslosenquote" in table,"SECO table1 not found")
    # Cross-check the *unemployment* row only, up to "Langzeitarbeitslose",
    # to avoid confusing it with the distinct jobseeker and vacancy rates.
    before_long=table.split("Langzeitarbeitslose",1)[0]
    require(quoted[0] in before_long,
            "SECO summary rate not confirmed in Table 1: "+key)
    return rate,release_day,len(document),{
        "summary_original_quote":"Die saisonbereinigte Arbeitslosenquote "+match.group(1),
        "summary_rate_pct_one_decimal":quoted[0],
        "table_one_unemployment_subsection_rate_crosscheck":True}

def run():
    urls,page_sha=discover()
    rows=[]
    missing_legacy=[]
    for key in EXPECTED:
        if key in OLD:
            try:
                raw,final=retrieve(urls[key],pdf=True)
            except requests.exceptions.HTTPError as exc:
                # Known broken pre-2025 issuer paths: never backfill from a
                # later PDF where first/previous-month values were revised.
                if exc.response is None or exc.response.status_code not in (404,410):
                    raise
                missing_legacy.append(key)
                print("SECO_LEGACY_SOURCE_UNAVAILABLE",key,flush=True)
                continue
        else:
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
    actual=[x["reference_month"] for x in rows]
    require([x for x in EXPECTED if x not in missing_legacy] == actual
            and len(rows)>=21
            and all(x.startswith("2024-") for x in missing_legacy),
            "2025–2026 actual issuer reports must be complete; 2024 failures exposed")
    require(rows[-1]["original_seco_rounded_sa_registered_unemployment_pct"]==3.1,
            "September-2026 first headline conflicts with separately verified SECO")
    require(rows[-9]["reference_month"]=="2026-01" and
            rows[-9]["original_seco_rounded_sa_registered_unemployment_pct"]==2.9,
            "January 2026 independently reviewed SECO first headline differs")
    jan25=next(x for x in rows if x["reference_month"]=="2025-01")
    require(jan25["original_seco_rounded_sa_registered_unemployment_pct"]==2.7,
            "January 2025 independently verified SECO first release is 2.7%, never 4.5% jobseekers")
    output={
        "schema":"GMFQ_MACRO_V2_CHF_25_TARGET_ISSUER_MONTHS_PARTIAL_RECOVERY_V1",
        "source_publisher":"Swiss State Secretariat for Economic Affairs (SECO)",
        "official_index_url":LIST,
        "index_capture_SHA256":page_sha,
        "source_recovery":"2026-10-27_DOWNLOAD_OF_OFFICIAL_ISSUER_REPORTS_NOT_CONTEMPORANEOUS_CAPTURE",
        "metric":"CH_SECO_REGISTRATION_SA_UNEMPLOYMENT_RATE_0P1_PERCENT_ALTERNATIVE",
        "frequency":"M","unit":"percent","precision_decimals":1,
        "archived_issuer_first_rounded_reports":rows,
        "target_first_month":"2024-09","last_reference_month":"2026-09",
        "target_observations":25,
        "verified_issuer_first_rounded_reports":len(rows),
        "original_reports_currently_unavailable_periods":missing_legacy,
        "prior_original_published_months":len(rows)-1,
        "prior_training_target":24,
        "current_report_window_complete":False,
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
