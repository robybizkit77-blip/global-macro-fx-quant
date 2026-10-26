#!/usr/bin/env python3
"""Audit Japan MoF JGB 2Y source chronology; stage no production replacement.

Use the original (date, yield) tuples without guessing. Optionally certify each
tuple against the independent MoF jgbcme_all.csv + jgbcme.csv original bytes.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import hashlib
import io
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "live_data/sections/NATIVE_RATES_DATA.json"
HIST_URL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
CURR_URL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"
LEGACY = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
MOF_DATE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
MOF_ERA = re.compile(r"^([RHS])(\d{1,2})\.(\d{1,2})\.(\d{1,2})$")


def day(value):
    m = LEGACY.fullmatch(value) if isinstance(value, str) else None
    if not m:
        raise ValueError("unexpected legacy date")
    return date(*(int(x) for x in m.groups()))


def publisher_day(raw):
    raw = raw.strip()
    m = MOF_DATE.fullmatch(raw)
    if m:
        return date(*(int(x) for x in m.groups()))
    # Japanese publisher may use era-labelled dates in its newer files.
    m = MOF_ERA.fullmatch(raw)
    if m:
        era, y, month, dom = m.groups()
        origin = {"R":2018,"H":1988,"S":1925}[era]
        return date(origin+int(y),int(month),int(dom))
    raise ValueError("unrecognized official MoF date "+raw[:40])


def normalize_source(data):
    if not isinstance(data, dict) or not isinstance(data.get("JPY"), dict):
        raise ValueError("JPY 2Y source absent")
    j = data["JPY"]
    if ("Japan Ministry of Finance" not in str(j.get("source"))
            or j.get("quality") != "FULL_CURRENT_OFFICIAL"):
        raise ValueError("unexpected JPY rate provenance")
    h = j.get("history2")
    if not isinstance(h, dict):
        raise ValueError("JPY 2Y history absent")
    dates, vals = h.get("dates"), h.get("values")
    if (not isinstance(dates, list) or not isinstance(vals, list)
            or not dates or len(dates) != len(vals)):
        raise ValueError("unbalanced JPY 2Y history")
    indexed, n_unpadded = [], 0
    for i,(raw,v) in enumerate(zip(dates,vals)):
        d = day(raw)
        if d.isoformat() != raw:
            n_unpadded += 1
        if type(v) not in (float,int) or not math.isfinite(v):
            raise ValueError("invalid JPY historical 2Y observation")
        if d.weekday() >= 5:
            raise ValueError("weekend date in JGB business-day 2Y history")
        indexed.append((d,float(v),i))
    by_date = sorted(indexed, key=lambda x:x[0])
    if len({x[0] for x in by_date}) != len(by_date):
        raise ValueError("duplicated 2Y observation day after normalization")
    if by_date[-1][0].isoformat() != j.get("date"):
        raise ValueError("2Y last dated observation disagrees with source as-of")
    reversals = sum(indexed[i][0] < indexed[i-1][0]
                    for i in range(1,len(indexed)))
    mapping = [{"date":d.isoformat(),"yield_pct":v,"original_row_index":i}
               for d,v,i in by_date]
    # Current source order is suspected string sort; preserve its original
    # original date/value pairing and provenance in the candidate.
    return {
        "schema":"GMFQ_JPY_2Y_CHRONOLOGY_STAGE_V1",
        "status":"NORMALIZED_PAIRS_PUBLISHER_ATTESTATION_PENDING",
        "original_row_count":len(indexed),
        "normalized_row_count":len(mapping),
        "noncanonical_date_strings":n_unpadded,
        "chronological_reversals":reversals,
        "first_day":mapping[0]["date"],
        "last_day":mapping[-1]["date"],
        "source_current_quality":j.get("quality"),
        "source_text":j.get("source"),
        "raw_jpy_history_original_sha256":hashlib.sha256(
            json.dumps(h,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
        "date_value_pairs_preserved":True,
        "yield_values_modified":False,
        "missing_dates_imputed":False,
        "historical_first_publication_pit_certified":False,
        "promoted_into_live_rates":False,
        "promoted_into_beta":False,
        "candidate_rows":mapping,
    }


def parse_mof_csv(raw_bytes, *, source):
    if not isinstance(raw_bytes, bytes) or not raw_bytes:
        raise ValueError("MoF original CSV bytes required")
    try:
        text = raw_bytes.decode("cp932")
    except UnicodeDecodeError as exc:
        raise ValueError("cannot decode original MoF CSV as CP932") from exc
    lines = csv.reader(io.StringIO(text))
    columns = None
    out = {}
    for row in lines:
        if not row or not row[0].strip():
            continue
        header = [x.strip().lstrip("\ufeff") for x in row]
        if columns is None:
            if header[0] == "Date":
                if "2Y" not in header or header.count("2Y") != 1:
                    raise ValueError("MoF 2Y tenor missing/ambiguous")
                columns = header.index("2Y")
            continue
        # CSV footer/text may follow the data; stop at first unrecognized
        # date only after at least one bona fide observation.
        try:
            d = publisher_day(header[0])
        except ValueError:
            if out:
                break
            raise ValueError("no MoF published dated observations")
        if columns >= len(row):
            raise ValueError("MoF source row shorter than tenor header")
        value = row[columns].strip()
        if value == "-":
            continue
        try:
            v = float(value)
        except ValueError as exc:
            raise ValueError("invalid MoF 2Y source number") from exc
        if not math.isfinite(v):
            raise ValueError("nonfinite MoF 2Y source number")
        if d in out:
            raise ValueError("duplicated MoF 2Y source date")
        out[d] = v
    if not out or columns is None:
        raise ValueError("no MoF 2Y series parsed")
    return out


def verify_official(candidate, historical, current):
    if candidate.get("status") != "NORMALIZED_PAIRS_PUBLISHER_ATTESTATION_PENDING":
        raise ValueError("untrusted normalization receipt")
    older = parse_mof_csv(historical,source=HIST_URL)
    newer = parse_mof_csv(current,source=CURR_URL)
    overlap = set(older).intersection(newer)
    conflicting = sorted(d.isoformat() for d in overlap if older[d]!=newer[d])
    if conflicting:
        raise ValueError("historical/current MoF overlapping figures conflict")
    official = {**older, **newer}
    matched = []
    mismatches = []
    missing = []
    for row in candidate["candidate_rows"]:
        d = date.fromisoformat(row["date"])
        if d not in official:
            missing.append(d.isoformat())
        elif abs(row["yield_pct"]-official[d]) > 0.0005000001:
            mismatches.append({"date":d.isoformat(),
                               "candidate":row["yield_pct"],
                               "official":official[d]})
        else:
            matched.append(d.isoformat())
    success=(not mismatches and not missing and
             len(matched)==candidate["normalized_row_count"])
    return {
        "schema":"GMFQ_JPY_2Y_OFFICIAL_MOF_ATTESTATION_V1",
        "state":"ALL_2Y_POINTS_AGREE_WITH_MOF" if success else "NOT_CERTIFIED_OFFICIAL_COMPARISON_FAILED",
        "matched":len(matched),
        "missing":missing,
        "mismatches":mismatches,
        "historical_source_sha256":hashlib.sha256(historical).hexdigest(),
        "current_source_sha256":hashlib.sha256(current).hexdigest(),
        "source_urls":[HIST_URL,CURR_URL],
        "historical_first_publication_pit_certified":False,
        "candidate_promoted_into_live_rates":False,
    }


# Explicitly reviewed discrepancy from official 26 Oct 2026 MoF CSV
# comparison. A third discrepancy is a new source incident, not an
# automatically acceptable revision.
REVIEWED_CONFLICT_DATES = frozenset(("2026-09-25","2026-09-28"))


def propose_verified_latest_publisher_candidate(candidate, historical, current):
    """Use independently downloaded MoF values for precisely reviewed dates.

    Never infer missing observations. Re-validate 273/273 after the replacements.
    Returns research candidate only; historical first-release PIT still absent.
    """
    first = verify_official(candidate, historical, current)
    if first["missing"]:
        raise ValueError("publisher missing original 2Y dates: no correction")
    differences = first["mismatches"]
    if {m["date"] for m in differences} != REVIEWED_CONFLICT_DATES:
        raise ValueError("unreviewed MoF source differences; independent audit needed")
    patches = {m["date"]:m for m in differences}
    repaired = json.loads(json.dumps(candidate))
    for row in repaired["candidate_rows"]:
        d=row["date"]
        if d in patches:
            row["yield_pct"]=patches[d]["official"]
    repaired["yield_values_modified"]=True
    repaired["original_values_retained_in_patch_audit"]=True
    repaired["latest_publisher_value_replacements"]=differences
    # Rerun independent full-row cross-check after the changes. Temporarily
    # retain the first-stage status accepted by verify_official.
    second=verify_official(repaired,historical,current)
    if second["state"]!="ALL_2Y_POINTS_AGREE_WITH_MOF" or second["matched"]!=273:
        raise ValueError("publisher reconciliation did not match all 273 original dates")
    repaired["status"]="PUBLISHER_RECONCILED_273_OF_273_LATEST_RELEASE_RESEARCH_ONLY"
    repaired["source_comparison"]=second
    repaired["source_initial_271_of_273_audit"]=first
    repaired["historical_first_publication_pit_certified"]=False
    repaired["promoted_into_live_rates"]=False
    repaired["promoted_into_beta"]=False
    return repaired


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--historical-csv",type=Path)
    ap.add_argument("--current-csv",type=Path)
    ap.add_argument("--reconcile-reviewed-two",action="store_true",
                    help="Replace only official-audited Sep25/Sep28 values in /tmp candidate")
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    if not args.out.resolve().is_relative_to(Path("/tmp")):
        ap.error("audit receipt must stay in /tmp")
    if bool(args.historical_csv) != bool(args.current_csv):
        ap.error("both publisher CSV sources must be available together")
    candidate=normalize_source(json.loads(SOURCE.read_text(encoding="utf-8")))
    if args.reconcile_reviewed_two and not args.historical_csv:
        ap.error("publisher reconciliation requires both original MoF CSV files")
    if args.historical_csv:
        historical=args.historical_csv.read_bytes()
        current=args.current_csv.read_bytes()
        if args.reconcile_reviewed_two:
            candidate=propose_verified_latest_publisher_candidate(
                candidate,historical,current)
        else:
            candidate["source_comparison"]=verify_official(
                candidate,historical,current)
            candidate["status"]="PUBLISHER_VERIFIED_OFFLINE_CANDIDATE" if (
                candidate["source_comparison"]["state"]=="ALL_2Y_POINTS_AGREE_WITH_MOF"
            ) else "PUBLISHER_COMPARISON_FAILED"
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(candidate,indent=2,ensure_ascii=False)+"\n",
                        encoding="utf-8")
    print(json.dumps({k:v for k,v in candidate.items() if k!="candidate_rows"},
                     ensure_ascii=False,sort_keys=True))
    if candidate["status"]=="PUBLISHER_COMPARISON_FAILED":
        raise SystemExit(2)


if __name__=="__main__":
    main()
