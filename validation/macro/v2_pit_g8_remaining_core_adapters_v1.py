#!/usr/bin/env python3
"""Five remaining Labour/Inflation G8 official-source research adapters.

Web/date attestations and prior archival *receipts* are distinct evidence
types. Retain only explicitly supported values: exact 2026 vintage source
snapshots for CHF CPI and Japanese CPI have separately attested hashes, but
the common gateway does NOT ingest their complete archival bytes/histories.
Swiss SECO rounded 3.1% is NOT the non-rounded SNB canonical unemployment
number. NZ March unemployment 5.3 -> 5.4 is a later period revision event.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp
from validation.macro.v2_pit_g8_evidence_adapters_v1 import event, source

BASE=ROOT/"validation/macro"
SOURCE_FILES={
    "EUR.labour":"eur_labour_historical_anchor_2026-08.json",
    "JPY.inflation":"jpy_inflation_historical_anchor_2026-08.json",
    "CHF.labour":"chf_labour_historical_anchor_2026-08.json",
    "NZD.labour":"nzd_labour_historical_anchor_2026-06.json",
    "CHF.inflation":"chf_inflation_strict_pit_evidence_v1_2026-10-10.json",
}
STRICT_FILES={
    "CHF.inflation": "chf_inflation_strict_pit_evidence_v1_2026-10-10.json",
    "JPY.inflation": "jpy_inflation_strict_pit_evidence_v1_2026-10-10.json",
    "EUR.labour": "eur_labour_strict_pit_evidence_v1_2026-10-10.json",
    "NZD.labour": "nzd_labour_strict_pit_evidence_v1_2026-10-11.json",
}

# Independent pins, crosschecked against existing original official-publisher
# bootstraps/strict attestations, not estimates fabricated from revised history.
BOOTSTRAP_PINS={
    "EUR.labour":(
        ("2026-07","2026-09-01",6.4,"https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/3-01092026-bp"),
        ("2026-08","2026-10-01",6.4,"https://ec.europa.eu/eurostat/web/products-euro-indicators/w/3-01102026-ap"),
    ),
    "JPY.inflation":(
        ("2026-07","2026-08-21",1.9,"https://www.stat.go.jp/data/cpi/sokuhou/tsuki/index-z.html"),
        ("2026-08","2026-09-18",1.9,"https://www.stat.go.jp/data/cpi/sokuhou/tsuki/index-z.html"),
    ),
    "NZD.labour":(
        ("2026-03","2026-05-06",5.3,"https://www.stats.govt.nz/information-releases/labour-market-statistics-march-2026-quarter/"),
        ("2026-06","2026-08-05",5.6,"https://www.stats.govt.nz/information-releases/labour-market-statistics-june-2026-quarter/"),
    ),
    "CHF.labour":(
        ("2026-07","2026-08-06",3.1,"https://www.seco.admin.ch/de/newnsb/niOazL9Cj1f0D5QgjBkD6"),
        ("2026-08","2026-09-07",3.1,"https://www.seco.admin.ch/it/newnsb/OfSdV0mM5gUa"),
        ("2026-09","2026-10-06",3.1,"https://www.seco.admin.ch/it/newnsb/Cdju9-o8WGML"),
    ),
}
STRICT_EXPECTED={
    "CHF.inflation": ("GMFQ_CHF_INFLATION_STRICT_PIT_EVIDENCE_V1","CH_CPI_HEADLINE_YOY","M",105),
    "JPY.inflation": ("GMFQ_JPY_INFLATION_STRICT_PIT_EVIDENCE_V1","JP_CPI_HEADLINE_YOY","M",104),
    "EUR.labour": ("GMFQ_EUR_LABOUR_STRICT_PIT_EVIDENCE_V1","EA_UNEMP","M",104),
    "NZD.labour": ("GMFQ_NZD_LABOUR_STRICT_PIT_EVIDENCE_V1","NZ_UNEMP_RATE","Q",34),
}
JAPAN_ARCHIVE_PINS={
    "2026-07":("000040491312","05408f53918795ce4ea79344cb735cf81a96ec2e3f15e9b48e640e331776dc2c","2025_BASE"),
    "2026-08":("000040501408","c16cac0b97c6a802b64d08ecabb50ef51520f9bde07295c0acdce1229ea06749","2025_BASE"),
}
SWISS_ARCHIVE_PINS={
    "2026-07":(0.4,"2026-08-03","06:30:00",36753719,"03c03189f2c7baf3551f977efd13598de03e8acd2983499207890af9afabccea"),
    "2026-09":(1.0,"2026-10-01","06:30:00",36870831,"2117d093c13a00f4f938b4943a68f6345537c3f5aef6385cd7c6f5e45f2a30eb"),
}
METADATA_NOTE={
    "EUR.labour":("EUR","labour","EA_UNEMP","M","percent unemployment SA",
                  "Eurostat","MONTHLY_EURO_AREA_2026_EA21_UNEMP"),
    "JPY.inflation":("JPY","inflation","JP_CPI_HEADLINE_YOY","M","percent YoY national all-items CPI",
                     "Statistics Bureau of Japan","MONTHLY_NATIONAL_CPI_2025_BASE"),
    "NZD.labour":("NZD","labour","NZ_UNEMP_RATE","Q","percent unemployment SA",
                 "Stats NZ","QUARTERLY_HLFS_WITH_MARCH_REVISED_ON_JUNE_RELEASE"),
    "CHF.labour":("CHF","labour","CH_SECO_SA_REGISTERED_UNEMP_RATE_ONE_DECIMAL","M",
                  "percent SA registered unemployment rate rounded ONE decimal",
                  "Swiss State Secretariat for Economic Affairs",
                  "ROUNDED_SECO_PRESS_RATE_NOT_EXACT_SNB_AMARBMA_VALUE"),
    "CHF.inflation":("CHF","inflation","CH_CPI_HEADLINE_YOY","M","percent YoY CPI",
                     "Swiss Federal Statistical Office","MONTHLY_PUBLISHER_PDF_EMBARGO_UTC"),
}


def load(name):
    return json.loads((BASE/name).read_text(encoding="utf-8"))


def conservative(day):
    return datetime.combine(date.fromisoformat(day)+timedelta(days=1),
                            datetime.min.time(),tzinfo=timezone.utc).isoformat()


def verified_strict(key):
    schema, series, freq, total=STRICT_EXPECTED[key]
    d=load(STRICT_FILES[key])
    require(d.get("schema")==schema and d.get("status")=="PASS"
            and d.get("target")==key and
            d.get("series_contract",{}).get("series_id")==series and
            d.get("series_contract",{}).get("frequency")==freq,
            "underlying independent official archival PIT receipt drift: "+key)
    count=d.get("coverage",{}).get("materialized_months",
                                d.get("coverage",{}).get("materialized_quarters"))
    require(count==total and d.get("revised_fallback_used", d.get("strict_rules",{}).get("revised_history_fallback_used")) is False
            and not d.get("missing") and not d.get("errors"),
            "archival source receipt no longer passing: "+key)
    return d


def bootstrap(key):
    d=load(SOURCE_FILES[key])
    require(d.get("schema")=="GMFQ_MACRO_HISTORICAL_BOOTSTRAP_ANCHOR_V1"
            and d.get("target",{}).get("currency")==key.split(".")[0]
            and d.get("target",{}).get("dimension")==key.split(".")[1]
            and d.get("provenance",{}).get("official_release_pair_verified") is True
            and d.get("frequency")==METADATA_NOTE[key][3],
            "historical two-release bootstrap contract changed: "+key)
    records=[d["previous"],d["current"]]
    expected=BOOTSTRAP_PINS[key]
    require(len(records)==2, "two historical publisher evidence anchors required")
    for rec,(period,day,value,url) in zip(records,expected):
        require(rec.get("observation_date")==period
                and rec.get("release_date")==day and
                rec.get("official_reference")==url,
                "source original period/date/official page changed: "+key)
        if key=="CHF.labour":
            # Source runtime values have many decimals from a current SNB cube,
            # NOT independently attested precise SECO first-release decimals.
            require(round(rec.get("value"),1)==value,
                    "Swiss exact SNB retrospective value no longer rounds to publisher headline")
        else:
            require(rec.get("value")==value, "web-published economic headline changed")
    return d


def euro_labour():
    bootstrap("EUR.labour")
    verified_strict("EUR.labour")
    cc,dimension,sid,freq,unit,publisher,sem=METADATA_NOTE["EUR.labour"]
    ev=[event(period,"FIRST_WEB",conservative(day),val,url)
        for period,day,val,url in BOOTSTRAP_PINS["EUR.labour"]]
    return source(cc,dimension,sid,freq,unit,publisher,
        period_semantics=sem,evidence="EUR_OFFICIAL_104_MONTH_STRICT_PIT_RECEIPT_PLUS_TWO_WEB_BOOTSTRAP_ANCHORS",
        notes=[
            "Two bounded published-date anchors onboarded; 104-month archival PASS receipt is not replicated or imported as 104 source events",
            "Euro area composition and re-releases/revisions require source-specific qualification",
            "Original UTC intraday release hour not attested for these web pages; next UTC day is a conservative research gate",
        ],events=ev)


def japan_inflation():
    bootstrap("JPY.inflation")
    d=verified_strict("JPY.inflation")
    for period,(statid,sha,route) in JAPAN_ARCHIVE_PINS.items():
        anchor=d["anchors"][period]
        require(anchor["stat_inf_id"]==statid and
                anchor["source_sha256"]==sha and
                anchor["route"]==route and
                anchor["release_time_jst"]=="08:30",
                "original e-Stat archive metadata SHA or exact Japanese release clock drift")
    cc,dimension,sid,freq,unit,publisher,sem=METADATA_NOTE["JPY.inflation"]
    ev=[]
    for period,day,val,url in BOOTSTRAP_PINS["JPY.inflation"]:
        anchor=d["anchors"][period]
        require(anchor["rate"]==val and anchor["release_date"]==day,
                "Japan original archived first publication figure/date altered")
        local=day+"T08:30:00+09:00"
        ev.append(event(period,"FIRST_WEB",local,val,url))
    return source(cc,dimension,sid,freq,unit,publisher,
        period_semantics=sem,evidence="JPY_104_MONTH_ESTAT_ARCHIVE_RECEIPT_TWO_LOCAL_TIME_WEB_HEADLINES",
        notes=[
            "Original e-Stat archived file IDs and SHA256 pinned in verified archival receipt, but shared gateway imports only two explicit headline events",
            "Stat Bureau official CPI index webpage is mutable, not an immutable report URL; e-Stat archive IDs remain in source receipt",
            "2018–2026 older 2015/2025 base period change needs historical scoring methodology review",
        ],events=ev)


def swiss_inflation():
    d=verified_strict("CHF.inflation")
    cc,dimension,sid,freq,unit,publisher,sem=METADATA_NOTE["CHF.inflation"]
    ev=[]
    for period,(val,day,utc_time,asset,sha) in SWISS_ARCHIVE_PINS.items():
        a=d["anchors"][period]
        require(a["rate"]==val and a["release_date"]==day
                and a["release_time_utc"]==utc_time and
                a["asset_id"]==asset and a["source_sha256"]==sha,
                "FSO original publisher asset metadata/hash or clock changed")
        # Official DAM asset pattern is corroborated by retrieved FSO September
        # 2026 press PDF; source source ID and SHA originally audited separately.
        url="https://dam-api.bfs.admin.ch/hub/api/dam/assets/"+str(asset)+"/master"
        ev.append(event(period,"FIRST_WEB",
                        day+"T"+utc_time+"Z",val,url))
    return source(cc,dimension,sid,freq,unit,publisher,
        period_semantics=sem,evidence="CHF_FSO_105_MONTH_OFFICIAL_ASSET_ARCHIVE_RECEIPT_TWO_EXPLICIT_EVENTS",
        notes=[
            "FSO strict receipt separately certifies 105 period-specific source asset hashes, but common gateway imports only the two pinned first-web observations",
            "2026 August has no separately pinned record in this bounded adapter: candidate range has one missing month; no interpolation",
            "Official UTC embargo time is source-reported. No repeated revisions/production score implied by two imported research events",
        ],events=ev)


def swiss_labour():
    # Crucial numerical distinction: first SECO press release has 1 decimal;
    # exact SNB seasonally adjusted cube has >10 decimals and no first-day
    # precise-value proof. Do not relabel exact prior/current as first web.
    bootstrap("CHF.labour")
    study=(BASE/"CHF_LABOUR_SECO_SNB_TEMPORAL_PROVENANCE_2026-10-22.md").read_text(encoding="utf-8")
    require("WITHHELD_EXACT_PERIOD_EVIDENCE" in study and
            "3.1249882357461%" in study and
            "147,970" in study and "147,886" in study,
            "source's unproven exact SNB chronology/SA revisions boundary removed")
    cc,dimension,sid,freq,unit,publisher,sem=METADATA_NOTE["CHF.labour"]
    # The September official SECO webpage is independently verified; the
    # earlier July/Aug dates and reported 3.1% are also in original bootstrap.
    e=[event(period,"FIRST_WEB",conservative(day),val,url)
       for period,day,val,url in BOOTSTRAP_PINS["CHF.labour"]]
    return source(cc,dimension,sid,freq,unit,publisher,
        period_semantics=sem,evidence="SECO_ROUNDED_REPORT_3_MONTHS_EXACT_SNB_CLOCK_UNPROVEN",
        notes=[
            "ALL these observations are SECO publisher-reported ONE-DECIMAL 3.1% rate, NOT the exact SNB amarbma machine number",
            "SECO August seasonally adjusted unemployed persons changed 147970→147886 in September release, without changing rounded 3.1% unemployment rate",
            "October 6 publication schedule 09:00 Zurich is NOT evidence of exact SNB-cube first availability",
            "No verified exact source vintage for registered canonical CH_UNEMP_RATE; keep separate candidate ID and mismatch",
        ],events=e)


def new_zealand_labour():
    d=bootstrap("NZD.labour")
    verified_strict("NZD.labour")
    prior=d.get("prior_revision",{})
    require(prior.get("observation_date")=="2026-03"
            and prior.get("before_value")==5.3 and prior.get("value")==5.4,
            "new Zealand March unemployment revision missing from official bounded ledger")
    cc,dimension,sid,freq,unit,publisher,sem=METADATA_NOTE["NZD.labour"]
    q1,q2=BOOTSTRAP_PINS["NZD.labour"]
    events=[
        event("2026Q1","FIRST_WEB",conservative(q1[1]),5.3,q1[3]),
        event("2026Q2","FIRST_WEB",conservative(q2[1]),5.6,q2[3]),
        event("2026Q1","REVISION_WEB",conservative(q2[1]),5.4,q2[3]),
    ]
    return source(cc,dimension,sid,freq,unit,publisher,
        period_semantics=sem,evidence="NZD_HLFS_34_QUARTER_ARCHIVAL_RECEIPT_TWO_FIRST_REPORTS_ONE_LATER_REVISION",
        notes=[
            "March quarter unemployment first reported 5.3%; in the June-quarter bulletin it is 5.4%, explicitly a later reported retrospective value",
            "June 2026 quarter unemployment 5.6% is distinct economic reference quarter and is not a revision of March",
            "Both new revised Q1 and new Q2 values are date-only gated at next UTC calendar day; not a verified NZ intraday release instant",
            "Existing strict PIT archival 34-quarter PASS is a separate checked research receipt, not imported as a full 34-quarter source time series",
        ],events=events)


def collect_remaining_core():
    return [euro_labour(),japan_inflation(),swiss_inflation(),
            swiss_labour(),new_zealand_labour()]
