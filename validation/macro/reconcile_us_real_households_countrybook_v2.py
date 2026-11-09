#!/usr/bin/env python3
"""US revised real consumption and income: issuer-checked Country Book overlay.

Uses the existing daily source intake receipt, the CURRENT official BEA news
release and the frozen canonical historical series. Does not splice revised
observations into the old vintage, alter D/28-pair scores, or claim a first
release or historical point-in-time backtest.

This research overlay is built inside existing Macro Persistent Daily, is
retained as an artifact, and replaces no canonical source.
"""
from __future__ import annotations

import argparse
import copy
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re

from bs4 import BeautifulSoup

from validation.macro import build_g8_causal_evidence_bridge_v2 as bridge
from validation.macro.collect_us_nz_household_firm_sources_v1 import (
    FRED_IDS, LIVE, ROOT, fetch,
)

SCHEMA="GMFQ_US_HOUSEHOLDS_REVISED_BEACHECK_COUNTRYBOOK_RESEARCH_V2"
BEA_MONTHS=(
    "january","february","march","april","may","june",
    "july","august","september","october","november","december",
)
RESULT=Path("/tmp/macro-persistent/us-households-revised-countrybook-v2.json")
NOTE=Path("/tmp/macro-persistent/us-households-revised-countrybook-v2.md")
SAAR_UNIT="Billions of Chained 2017 Dollars SAAR"


def gate(value,reason):
    if not value:
        raise ValueError("US_HOUSEHOLDS_REVISED_RESEARCH_WITHHELD: "+reason)


def bea_table(raw, url, period):
    """Read issuer's real DPI/PCE and nominal PCE monthly change table."""
    from urllib.parse import urlparse
    u=urlparse(url)
    gate(u.scheme=="https" and u.hostname in {"www.bea.gov","bea.gov"},
         "BEA issuer URL not approved")
    label=BEA_MONTHS[int(period[5:7])-1]
    gate(u.path==f"/news/{period[:4]}/personal-income-and-outlays-{label}-{period[:4]}",
         "BEA release URL not the correct month")
    soup=BeautifulSoup(raw,"html.parser")
    title=" ".join((h.get_text(" ",strip=True) for h in soup.find_all(["h1","h2"])))
    gate(bool(re.search(
        r"Personal Income and Outlays,\s*"+label+r"\s+"+period[:4],
        title,re.I)), "BEA HTML title not for the expected month")
    rows={}
    labels={"Real DPI":"real_dpi_mom_pct",
            "Real PCE":"real_pce_mom_pct",
            "Current-dollar PCE":"nominal_pce_mom_pct"}
    for tr in soup.find_all("tr"):
        cells=[" ".join(c.get_text(" ",strip=True).split())
               for c in tr.find_all(["th","td"],recursive=False)]
        if len(cells)<3 or cells[0] not in labels:
            continue
        key=labels[cells[0]]
        gate(key not in rows,"duplicate BEA exact table metric "+key)
        try:
            a=float(cells[-2].replace(",",""))
            b=float(cells[-1].replace(",",""))
        except ValueError as e:
            raise ValueError("BEA percentage table is not numeric") from e
        gate(all(math.isfinite(x) and abs(x)<20 for x in (a,b)),
             "invalid BEA monthly percentage")
        rows[key]={"prior_month_pct":a,"current_month_pct":b}
    # BEA sometimes renders the rows with non-table list markup; accept
    # only an exact label followed by two percentage columns in the
    # independently scoped "Personal Income and Related Measures" section.
    if set(rows)!=set(labels.values()):
        text=" ".join(soup.stripped_strings)
        m=re.search(r"Personal Income and Related Measures\s*"
                    r"\[Percent change from preceding month\]\s*"
                    r"(.*?)(?:For definitions|Next release:)",text,re.I)
        if m:
            scoped=m.group(1)
            for label_name,key in labels.items():
                if key in rows:
                    continue
                pattern=(r"(?<![A-Za-z])"+re.escape(label_name)+
                         r"\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\b")
                match=re.search(pattern,scoped,re.I)
                if match:
                    rows[key]={"prior_month_pct":float(match[1]),
                               "current_month_pct":float(match[2])}
    gate(set(rows)==set(labels.values()),
         "exact BEA table real PCE/real DPI/nominal PCE not found")
    return {"period":period,"url":url,"issuer_html_sha256":sha256(raw).hexdigest(),
            "values":rows,"issuer_release_first_seen_PIT":False}


def _months(a,b):
    x=date.fromisoformat(a);y=date.fromisoformat(b)
    return (y.year-x.year)*12+(y.month-x.month)


def reconcile(receipt, original, official_html, official_url, *, at):
    gate(at.tzinfo is not None and at.utcoffset() is not None,
         "aware UTC clock required")
    gate(receipt.get("schema")==
         "GMFQ_HOUSEHOLD_FIRMS_ISSUER_INTAKE_RESEARCH_V1",
         "unrecognized daily source receipt")
    observed=datetime.fromisoformat(receipt["observed_at_utc"].replace("Z","+00:00"))
    gate(observed<=at, "source observed after research read")
    feed=receipt.get("sources",{})
    release=feed.get("BEA_CURRENT_RELEASE_DISCOVERY",{})
    gate(release.get("status")=="VERIFIED_RESEARCH_ONLY",
         "BEA issuer release not discovered")
    latest=release["value"]
    gate(latest.get("status")=="ISSUER_RELEASE_DISCOVERED_NOT_ACTUAL_PARSED",
         "BEA discovery identity mismatch")
    period=latest["release_reference_period"]
    gate(re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])",period),
         "invalid BEA reference period")
    gate(_months(period+"-01",at.date().replace(day=1).isoformat())>=1,
         "no future or same-month BEA reference")
    gate(latest["release_url"]==official_url,
         "BEA content URL differs from discovered official release")
    bea=bea_table(official_html,official_url,period)
    gate("USD" in original and isinstance(original["USD"],list),
         "canonical USD source unreadable")
    idx={r["id"]:r for r in original["USD"]}
    snapshots={}
    for fred,canonical_id in FRED_IDS.items():
        src=feed.get("FRED_BEAMIRROR_"+fred,{})
        gate(src.get("status")=="VERIFIED_RESEARCH_ONLY",
             fred+" source unavailable")
        candidate=src["value"]
        gate(candidate.get("series_id")==fred and
             candidate.get("source_lineage")==
             "FRED_FEDERAL_RESERVE_MIRROR_OF_BEA_REVISED_NOT_ISSUER_PIT" and
             candidate.get("metric_kind")==
             "MONTHLY_SA_CHAINED_DOLLAR_REAL_LEVEL_NOT_MOM_PCT",
             fred+" incompatible source dimension or quality")
        gate(candidate.get("last_date")==period+"-01",
             fred+" FRED vintage not synchronized with BEA release month")
        values=candidate["revised_vintage_monthly_history"]
        gate(24<=len(values)<=200 and values[-1]["date"]==period+"-01",
             fred+" revised window missing latest month")
        data={x["date"]:x["value"] for x in values}
        gate(len(data)==len(values),"duplicate FRED month in revised window")
        gate(all(re.fullmatch(r"\d{4}-\d{2}-01",x) for x in data),
             fred+" invalid monthly precision")
        gate(all(type(v) in (float,int) and math.isfinite(v) and v>0
                 for v in data.values()),fred+" missing/nonpositive real level")
        keys=list(data)
        gate(all(_months(a,b)==1 for a,b in zip(keys,keys[1:])),
             fred+" monthly revised vintage not contiguous")
        row=idx.get(canonical_id)
        gate(row is not None and row.get("last_date")==row["dates"][-1] and
             row.get("last_value")==row["values"][-1] and
             len(row["dates"])==len(row["values"]),
             fred+" invalid canonical provenance")
        # Both series have exactly this locked identity/definition at FRED.
        # DSPIC96's canonical row lacks a unit; do not falsely certify it.
        canonical_unit_confirmed=(row.get("unit")==SAAR_UNIT)
        gate(row["source_file"]=="US_"+fred+"_history.csv",
             fred+" unexpected canonical history origin")
        gate(all(date_str in data for date_str in row["dates"]),
             fred+" FRED revised window cannot replace all canonical dates")
        old={d:v for d,v in zip(row["dates"],row["values"])}
        revisions=[{"date":d,"old":v,"revised":data[d],
                    "delta":round(data[d]-v,6)}
                   for d,v in old.items()
                   if not math.isclose(v,data[d],rel_tol=0,abs_tol=1e-7)]
        prior=keys[-2]
        mom=100*(data[keys[-1]]/data[prior]-1)
        bea_key={"PCEC96":"real_pce_mom_pct",
                 "DSPIC96":"real_dpi_mom_pct"}[fred]
        publisher=bea["values"][bea_key]["current_month_pct"]
        # BEA publishes one decimal place. FRED level-derived monthly changes
        # must lie inside half a one-decimal reporting step (+ small tolerance).
        gate(abs(mom-publisher)<=0.051,
             fred+" level change disagrees with published BEA m/m percentage")
        snapshots[fred]={
            "id":canonical_id,
            "source_fred_id":fred,
            "source_fred_url":"https://fred.stlouisfed.org/series/"+fred,
            "source_csv_sha256":src["sha256"],
            "expected_unit":SAAR_UNIT,
            "canonical_unit_metadata_present_and_matching":canonical_unit_confirmed,
            "source_revised_vintage_not_point_in_time":True,
            "latest_month":period,
            "latest_level":data[keys[-1]],
            "previous_month_level":data[prior],
            "latest_mom_pct_from_revised_levels":round(mom,5),
            "latest_mom_pct_BEA_published":publisher,
            "historical_original_months":len(old),
            "historical_revised_months":len(values),
            "overlap_revised_observation_count":len(revisions),
            "original_last_month":row["last_date"],
            "old_last_level":row["last_value"],
            "revised_old_last_month_level":data[row["last_date"]],
            "revisions":revisions,
            "complete_revised_history":values,
            "canonical_series_overwritten":False,
        }
    pce=snapshots["PCEC96"];dpi=snapshots["DSPIC96"]
    pcev=pce["latest_mom_pct_BEA_published"]
    dpiv=dpi["latest_mom_pct_BEA_published"]
    nominal=bea["values"]["nominal_pce_mom_pct"]["current_month_pct"]
    story=(
        f"USA, {period}: consumi reali {pcev:+.1f}% m/m, reddito "
        f"disponibile reale {dpiv:+.1f}% m/m; spesa nominale "
        f"{nominal:+.1f}% m/m. La differenza tra crescita nominale e reale "
        "segnala che il valore della spesa non equivale ai volumi acquistati. "
        "Questa è una fotografia revisionata del BEA, non il primo valore "
        "disponibile storicamente; nessun repricing Fed o segnale USD è dimostrato."
    )
    return {
        "schema":SCHEMA,
        "status":"TWO_REVISED_REAL_SERIES_RECONCILED_WITH_BEA_ISSUER_RESEARCH_ONLY",
        "source_observed_at_utc":receipt["observed_at_utc"],
        "research_processed_at_utc":at.astimezone(timezone.utc).isoformat(),
        "latest_release_month":period,
        "bea_issuer":bea,
        "revised_series":snapshots,
        "countrybook_us_households_narrative_it":story,
        "alternative_it":(
            "Il risultato mensile può essere revisionato. Consumi reali "
            "invariati non implicano automaticamente recessione né tagli Fed: "
            "verificare persistenza, servizi e redditi nei prossimi rilasci."
        ),
        "series_pit_certified":False,
        "revised_full_history_separate_from_prior_vintage":True,
        "replaces_live_macro_series":False,
        "published_to_site":False,
        "affects_28_pair_core":False,
        "fx_signal":None,
    }


def research_countrybook_snapshot(result, *,today,root=ROOT):
    book=bridge.build(today=today,root=root)
    gate(book["countries"]["USD"]["safe_for_site"] is False and
         book["countries"]["USD"]["safe_for_reports"] is False,
         "Country Book publication gates changed")
    row=book["countries"]["USD"]
    row["countrybook_revised_household_context"]={
        "research_as_of_utc":result["research_processed_at_utc"],
        "latest_published_reference_period":result["latest_release_month"],
        "narrative_it":result["countrybook_us_households_narrative_it"],
        "revised_series_ids":[result["revised_series"][k]["id"]
                              for k in ("PCEC96","DSPIC96")],
        "historical_series_replaced":False,
        "PIT_certified":False,
    }
    # Replace only the stale wording in the RESEARCH export. Keep the
    # original economic_transmission_observations and its period flags.
    row["economic_transmission_narrative_it"][4]=(
        "Famiglie e consumi: "+result["countrybook_us_households_narrative_it"]+
        " Fonte BEA, coerente con i livelli reali FRED. "
        "Le serie storiche del Country Book originale restano a luglio "
        "e non sono usate per inferire un'accelerazione recente."
    )
    return book


def render_md(result):
    lines=[
        "# Country Book USA — consumi e reddito reali, fonte verificata",
        "",
        "**Ricerca, non segnale e non snapshot point-in-time per backtest.**",
        f"As-of: {result['research_processed_at_utc']} | "
        f"Periodo BEA: {result['latest_release_month']}",
        "",
        result["countrybook_us_households_narrative_it"],
        "",
        "## Qualità della revisione storica",
    ]
    for fred in ("PCEC96","DSPIC96"):
        r=result["revised_series"][fred]
        lines.append(
            f"- {fred}: {r['historical_original_months']} mesi storici da "
            f"riconciliare; {r['overlap_revised_observation_count']} livelli "
            "differiscono dallo storico precedente. "
            f"Ultimo livello: {r['latest_level']} ({r['latest_month']}); "
            f"variazione mensile calcolata {r['latest_mom_pct_from_revised_levels']:+.3f}%, "
            f"BEA {r['latest_mom_pct_BEA_published']:+.1f}%. "
            f"Unità canonica certificata: {r['canonical_unit_metadata_present_and_matching']}."
        )
    lines += [
        "",
        "**Lettura alternativa:** "+result["alternative_it"],
        "",
        "La cronologia revisionata è conservata integralmente nel JSON di ricerca, "
        "non innestata sul vecchio storico. Nessuna pubblicazione live, "
        "modifica dei 28 segnali o nuova automazione.",
    ]
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--intake",type=Path,
                   default=Path("/tmp/macro-persistent/household-firm-publisher-intake-v1.json"))
    p.add_argument("--json-out",type=Path,default=RESULT)
    p.add_argument("--md-out",type=Path,default=NOTE)
    args=p.parse_args()
    gate(all(q.resolve().is_relative_to(Path("/tmp"))
             for q in (args.intake,args.json_out,args.md_out)),
         "research intake/artifacts must be under /tmp")
    receipt=json.loads(args.intake.read_text(encoding="utf-8"))
    source=receipt.get("sources",{}).get("BEA_CURRENT_RELEASE_DISCOVERY",{})
    gate(source.get("status")=="VERIFIED_RESEARCH_ONLY",
         "no issuer-discovered BEA release")
    url=source["value"]["release_url"]
    raw,final=fetch(url)
    gate(final==url, "BEA release redirected away from exact issuer URL")
    original=json.loads(LIVE.read_text(encoding="utf-8"))
    at=datetime.now(timezone.utc)
    result=reconcile(receipt,original,raw,url,at=at)
    book=research_countrybook_snapshot(result,today=at.date())
    result["countrybook_research_overlay"]={
        "country":"USD",
        "household_narrative_it":book["countries"]["USD"]["economic_transmission_narrative_it"][4],
        "source_observation_periods_unchanged":True,
        "legacy_current_vintage_false_pit_guard":True,
    }
    args.json_out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",
                             encoding="utf-8")
    args.md_out.write_text(render_md(result),encoding="utf-8")
    print(json.dumps({"status":result["status"],
        "latest_release_month":result["latest_release_month"],
        "revised_pce":result["revised_series"]["PCEC96"]["latest_level"],
        "revised_dpi":result["revised_series"]["DSPIC96"]["latest_level"],
        "current_live_series_modified":False,
        "source_pit_certified":False},sort_keys=True))


if __name__=="__main__":
    main()
