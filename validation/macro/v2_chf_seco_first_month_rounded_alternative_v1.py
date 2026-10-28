#!/usr/bin/env python3
"""CHF labour ALTERNATIVE: 25 dated official SECO 0.1%-rounded FIRST reports.

21 current downloadable official original issue PDFs, SHA256 captured on
2026-10-27, plus four older issue PDFs (404 now) with their published first
monthly SA rates attested by official SECO search-index excerpts. Separate
the four weaker source-index cases from the 21 present byte-level captures.

This alternative is NOT original precision SNB amarbma CH_UNEMP_RATE vintage.
Never auto-upgrade original CHF.labour first-web status or trading PIT model.
"""
from __future__ import annotations

import argparse, copy, hashlib, json, math, re, statistics
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_eur_ea_regime_chf_precision_guard_v1 import swiss_quality

SCHEMA = "GMFQ_MACRO_V2_CHF_25_MONTH_FIRST_SECO_ROUNDED_ISSUER_ALTERNATIVE_V1"
FIXTURE = ROOT / "validation/macro/fixtures/seco_chf_sa_registered_unemployment_25_first_monthly_reports_2024_09_2026_09.json"
ASOF = "2026-10-26T23:59:59Z"
SOURCE_INDEX = "https://www.seco.admin.ch/de/arbeitsmarktstatistik-berichte-rechtsgrundlagen"
# These four 2024 official publisher PDFs still have search-engine-indexed
# original contents / table 1, but their old direct PDF links now return HTTP
# 404 to the archive materializer. NO raw-byte source SHA or archived object!
EARLY_INDEX_ONLY = (
    ("2024-09",2.6,"2024-10-04",
     "https://www.seco.admin.ch/dam/seco/de/dokumente/Publikationen_Dienstleistungen/Publikationen_Formulare/Arbeit/Arbeitslosenversicherung/Die%20Lage%20auf%20dem%20Arbeitsmarkt/arbeitsmarkt_2024/lage_arbeitsmarkt_september_2024.pdf.download.pdf/2024-09_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf"),
    ("2024-10",2.6,"2024-11-05",
     "https://www.seco.admin.ch/dam/seco/de/dokumente/Publikationen_Dienstleistungen/Publikationen_Formulare/Arbeit/Arbeitslosenversicherung/Die%20Lage%20auf%20dem%20Arbeitsmarkt/arbeitsmarkt_2024/large_arbeitsmarkt_oktober_2024.pdf.download.pdf/2024-10_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf"),
    ("2024-11",2.6,"2024-12-05",
     "https://www.seco.admin.ch/dam/seco/de/dokumente/Publikationen_Dienstleistungen/Publikationen_Formulare/Arbeit/Arbeitslosenversicherung/Die%20Lage%20auf%20dem%20Arbeitsmarkt/arbeitsmarkt_2024/large_arbeitsmarkt_november_2024.pdf.download.pdf/2024-11_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf"),
    ("2024-12",2.6,"2025-01-10",
     "https://www.seco.admin.ch/dam/seco/de/dokumente/Publikationen_Dienstleistungen/Publikationen_Formulare/Arbeit/Arbeitslosenversicherung/Die%20Lage%20auf%20dem%20Arbeitsmarkt/arbeitsmarkt_2024/lage_arbeitsmarkt_dezember_2024.pdf.download.pdf/2024-12_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf"),
)


# Search-engine document indexes have preserved the publisher's FULL PDF TEXT
# (including Table 1); as of 2026-10-28 direct PDF HTTP/byte capture is NOT
# available. These are NOT alternate downloaded originals and their exact
# URL existence in the index must not promote a source-day PIT vintage.
INDEXED_OFFICIAL_PDF_TEXT_ONLY = {
    "2024-09": (
        "https://www.arbeit.swiss/dam/secoalv/de/dokumente/publikationen/amstat/2024/"
        "die_lage_auf_dem_arbeitsmarkt_im_september_2024.pdf.download.pdf/"
        "2024-09_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf", 26
    ),
    "2024-10": (
        "https://www.arbeit.swiss/dam/secoalv/de/dokumente/publikationen/amstat/2024/"
        "die_lage_auf_dem_arbeitsmarkt_202410_dfi.pdf.download.pdf/"
        "2024-10_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf", 27
    ),
    "2024-11": (
        "https://www.arbeit.swiss/dam/secoalv/de/dokumente/publikationen/amstat/2024/"
        "die_lage_auf_dem_arbeitsmarkt_202411.pdf.download.pdf/"
        "2024-11_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf", 27
    ),
    "2024-12": (
        "https://www.arbeit.swiss/dam/secoalv/de/dokumente/publikationen/amstat/2024/"
        "die_lage_auf_dem_arbeitsmarkt_202412.pdf.download.pdf/"
        "2024-12_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf", 28
    ),
}


def require(value, message):
    if not value:
        raise ValueError("MACRO_V2_CHF_SECO_25_ALTERNATIVE_REJECTED: " + message)


def period_index(period):
    require(isinstance(period,str) and re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])",period),
            "canonical monthly reporting period")
    y,m=map(int,period.split("-"))
    return y*12+m-1


def first_gate(day):
    return datetime.combine(date.fromisoformat(day)+timedelta(days=1),
                            time.min,timezone.utc).isoformat()


def from_index_only():
    require(set(INDEXED_OFFICIAL_PDF_TEXT_ONLY) ==
            {p for p, *_ in EARLY_INDEX_ONLY},
            "exact four historical issuer PDF cache locators")
    rows = []
    for p, rate, day, url in EARLY_INDEX_ONLY:
        indexed_url, indexed_pages = INDEXED_OFFICIAL_PDF_TEXT_ONLY[p]
        parsed = urlsplit(indexed_url)
        require(parsed.scheme == "https" and parsed.hostname == "www.arbeit.swiss"
                and parsed.path.endswith(".pdf")
                and p[:4] in parsed.path and p in parsed.path
                and not parsed.username and not parsed.password
                and indexed_pages >= 22,
                "cached publisher PDF locator cannot prove an issuer original")
        require(rate == 2.6, "indexed SECO Table 1 rounded SA rate drift")
        rows.append({"reference_month":p,
         "original_seco_rounded_sa_registered_unemployment_pct":rate,
         "published_report_date":day,
         "conservative_available_from_utc":first_gate(day),
         "official_month_report_url":url,
         "official_web_indexed_full_PDF_text_locator_NOT_downloadable_original":indexed_url,
         "indexed_document_pages_reported_NOT_verified_raw_PDF":indexed_pages,
         "indexed_pdf_first_table_SA_rate_one_decimal_confirmed":rate,
         "indexed_official_PDF_text_is_not_original_bytes_or_source_day_snapshot":True,
         "source_quality":"OFFICIAL_2024_INDEXED_ORIGINAL_PDF_TABLE_CACHED_404_NO_BYTES",
         "official_pdf_sha256_captured_now":None,
         "source_first_month_raw_document_bytes_downloaded":False,
         "document_original_release_day_HTTP_snapshot_verified":False,
         "publisher_first_original_exact_SNB_values_verified":False})
    return rows


def audit(*,cutoff=ASOF,raw=None):
    require(cutoff==ASOF,"current issuer archive is NOT historical cutoff replay")
    base=raw if raw is not None else json.loads(FIXTURE.read_text(encoding="utf-8"))
    require(base.get("schema")==
            "GMFQ_MACRO_V2_CHF_25_TARGET_ISSUER_MONTHS_PARTIAL_RECOVERY_V1"
            and base.get("target_observations")==25
            and base.get("verified_issuer_first_rounded_reports")==21
            and base.get("original_reports_currently_unavailable_periods")==
            ["2024-09","2024-10","2024-11","2024-12"]
            and base.get("can_replace_canonical_CH_UNEMP_RATE_history_value") is False
            and base.get("safe_to_publish_new_D") is False,
            "issuer source acquisition may not silently claim 25 downloaded PDFs")
    later=base["archived_issuer_first_rounded_reports"]
    require(isinstance(later,list) and len(later)==21,"must have 21 source PDF snapshots")
    rows=from_index_only()
    for item in later:
        require(isinstance(item,dict),"non-dictionary issuer source")
        ref=item["reference_month"]
        uri=item["official_month_report_url"]
        parsed=urlsplit(uri)
        require(parsed.scheme=="https" and parsed.hostname in
                ("www.seco.admin.ch","seco.admin.ch") and
                parsed.path.endswith(".pdf") and not parsed.username and
                not parsed.password,
                "latest downloaded month must have official original PDF link")
        sha=item["official_pdf_sha256_captured_now"]
        require(isinstance(sha,str) and
                re.fullmatch(r"[a-f0-9]{64}",sha) is not None and
                item["original_month_pdf_pages"]>=22,
                "21 source bytes must retain SHA256 and real original report page count")
        require(item["first_column_validated_against_comparison_columns"]
                ["summary_rate_pct_one_decimal"]==
                str(item["original_seco_rounded_sa_registered_unemployment_pct"])
                .replace(".",","),
                "official executive summary first SA rate disagrees with row")
        rows.append({
            "reference_month":ref,
            "original_seco_rounded_sa_registered_unemployment_pct":
                item["original_seco_rounded_sa_registered_unemployment_pct"],
            "published_report_date":item["published_report_date"],
            "conservative_available_from_utc":item["conservative_available_from_utc"],
            "official_month_report_url":uri,
            "source_quality":"OFFICIAL_MONTH_PDF_BYTES_RECOVERED_2026_10_27_NOT_SOURCE_DAY_HTTP_CAPTURE",
            "official_pdf_sha256_captured_now":sha,
            "source_first_month_raw_document_bytes_downloaded":True,
            "document_original_release_day_HTTP_snapshot_verified":False,
            "publisher_first_original_exact_SNB_values_verified":False,
        })
    months=[f"{y:04d}-{m:02d}" for y in (2024,2025,2026) for m in range(1,13)
            if "2024-09"<=f"{y:04d}-{m:02d}"<="2026-09"]
    require([x["reference_month"] for x in rows]==months,
            "exact 25 consecutive source months must be present")
    require(len({x["official_month_report_url"] for x in rows})==25,
            "25 different original publisher URLs required")
    for item in rows:
        ref=item["reference_month"]
        value=item["original_seco_rounded_sa_registered_unemployment_pct"]
        require(type(value) in (float,int) and math.isfinite(value)
                and 1.0<=value<=6.0 and abs(value*10-round(value*10))<1e-8,
                "SECO published rate must be one-decimal not SNB first exact")
        d=date.fromisoformat(item["published_report_date"])
        y,m=map(int,ref.split("-"))
        require((d.year-y)*12+d.month-m in (1,2) and
                item["conservative_available_from_utc"]==first_gate(d.isoformat()) and
                datetime.fromisoformat(item["conservative_available_from_utc"])<
                datetime.fromisoformat(cutoff.replace("Z","+00:00")),
                "report release dates are not economic observation dates")
    require(rows[0]["original_seco_rounded_sa_registered_unemployment_pct"]==2.6
            and rows[4]["original_seco_rounded_sa_registered_unemployment_pct"]==2.7
            and rows[16]["original_seco_rounded_sa_registered_unemployment_pct"]==2.9
            and rows[-1]["original_seco_rounded_sa_registered_unemployment_pct"]==3.1,
            "independently checked monthly SECO anchor release values differ")
    old_download=sum(x["source_first_month_raw_document_bytes_downloaded"] for x in rows)
    require(old_download==21,"21 genuine first-report downloaded PDFs required")
    require(sum(bool(x.get("official_web_indexed_full_PDF_text_locator_NOT_downloadable_original"))
                for x in rows)==4 and
            all(x["official_pdf_sha256_captured_now"] is None and
                x["source_first_month_raw_document_bytes_downloaded"] is False
                for x in rows[:4]),
            "index text of four 2024 originals must not become captured PDF bytes")
    swiss=swiss_quality(cutoff=cutoff)
    require(swiss["rounded_SECO_sa_rate_pct_visible"]==3.1
            and swiss["exact_SNB_release_timestamp_utc"] is None,
            "SECO rounded web rate must remain separate from SNB exact API")
    values=[x["original_seco_rounded_sa_registered_unemployment_pct"] for x in rows]
    prior=values[:-1]
    med=statistics.median(prior)
    mad=statistics.median(abs(x-med) for x in prior)
    z=None if mad<=1e-9 else max(-3.0,min(3.0,(values[-1]-med)/(1.4826*mad)))
    status=("ROUNDING_AND_SOURCE_HETEROGENEITY_DESCRIPTIVE_Z_AVAILABLE"
            if z is not None else "NO_Z_ZERO_VARIATION_IN_ROUNDED_SECO")
    return {
        "schema":SCHEMA,
        "as_of_utc":cutoff,
        "status":status,
        "canonical_metric":"CH_UNEMP_RATE (SNB precise SA registered percentage)",
        "alternative_metric":"SECO published SA registered unemployment rate rounded to 0.1 percentage points",
        "publisher_first_rounded_monthly_reports":rows,
        "statistical_research":{
            "current_reference_period":"2026-09",
            "latest_SECO_rate_rounded_one_decimal_pct":3.1,
            "24_prior_calendar_months_present_for_alternative_metric":True,
            "24_prior_observations_from_FIRST_MONTH_WEB_REPORTS":True,
            "total_previous_publisher_byte_recovered_PDF_months":20,
            "total_previous_web_index_only_first_report_months":4,
            "research_prior_median_pct":med,
            "research_prior_mad_pct":mad,
            "descriptive_robust_z_of_rounded_first_SECO_rates":z,
            "statistical_precision_caveat":
                "ONE_DECIMAL_ROUNDING_AND_4_CACHED_INDEX_ONLY_REPORTS",
            "not_equivalent_to_exact_SNB_first_release_z":True,
            "original_SNBSI_values_reconstructed":False,
        },
        "summary":{
            "alternative_SECO_first_rounded_web_coverage_months":25,
            "official_PDF_raw_bytes_SHA_captured_now":21,
            "official_2024_original_PDF_search_index_only_currently_404":4,
            "official_2024_original_full_PDF_text_index_locators_identified":4,
            "original_PDF_bytes_still_missing_despite_indexed_text":4,
            "retrospective_SNBSI_source_first_precision_verified":0,
            "separate_new_SNB_canonical_first_release_history_periods":0,
            "USD_CPI_first_release_windows_changed":0,
            "authorized_G8_macro_currency_scores":0,
            "FX_pair_rankings_changed":0,
        },
        "not_PIT_authorized_for_real_FX_backtest":True,
        "source_first_publication_intraday_timestamp_not_proven":True,
        "historical_24_SNB_exact_first_release_percentages_unavailable":True,
        "safe_to_publish_new_D":False,"safe_to_change_28_pairs":False,
        "safe_for_beta":False,"safe_for_forward":False,"writes_live_data":False,
        "receipt_sha256":hashlib.sha256(
            json.dumps(rows,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if args.output:require(args.output.resolve().is_relative_to(Path("/tmp")),
                           "research output under /tmp only")
    report=audit()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report["summary"],sort_keys=True))

if __name__=="__main__":
    main()
