#!/usr/bin/env python3
"""Permanent, source-hash-pinned EUR HICP and AUD quarterly CPI release archive.

The archival CSVs were recovered from historic GitHub Actions artifacts and
committed as LZMA+base64 ASCII fixture copies. This read-only loader verifies
both the exact original CSV bytes AND the independently attested semantic
rowset SHA-256 before exposing 105 Eurostat initial web flashes and 34 ABS
quarterly observations to an as-of research timeline.

This does NOT re-fetch or independently re-certify each historic source byte.
It never labels an archival receipt as a new production PIT authorization.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import lzma
import math
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from validation.macro.v2_shadow_features_v1 import ROOT

SCHEMA = "GMFQ_MACRO_V2_EUR_AUD_139_FIRST_WEB_SOURCE_ROW_OVERLAY_V1"
ENTRIES = {
    "EUR.inflation": {
        "fixture": "EUR_HICP_FLASH_STRICT_FIRST_RELEASE_2018_2026_09.csv.xz.b64",
        "original_csv_sha256": "78b876f9eec93d6a77696373a93e0444aed0e72e97a1dc71e4f74ae61eed541f",
        "artifact_id": 11674452706, "artifact_workflow_run": 38063873303,
        "count": 105, "start": "2018-01", "end": "2026-09",
        "frequency": "M", "canonical_series_id": "EA_HICP_HEADLINE_YOY",
        "authority": "Eurostat",
        "evidence": "eur_inflation_strict_pit_evidence_v1_2026-10-10.json",
        "expected_semantic_hash": "fd19fea3a286b327019b9727a79ade5e51550cfc073538139ac3f600d81c68b1",
        "keys": ["reference_month", "headline_hicp_yoy_pct", "release_date",
                 "source_route", "pit_status"],
        "csv_columns": ["reference_month", "headline_hicp_yoy_pct", "release_date",
                        "source_url", "page_sha256", "source_route", "pit_status"],
        "allowed_hosts": {"ec.europa.eu"},
    },
    "AUD.inflation": {
        "fixture": "AUD_CPI_Q_YOY_STRICT_FIRST_RELEASE_2018_2026Q2.csv.xz.b64",
        "original_csv_sha256": "03271a29146afa1ab88837b84ee437e01c1617bac9a361e4cc1d3c9a8908ac7e",
        "artifact_id": 11627499603, "artifact_workflow_run": 37956927900,
        "count": 34, "start": "2018-03", "end": "2026-06",
        "frequency": "Q", "canonical_series_id": "AU_CPI_HEADLINE_Q_YOY",
        "authority": "Australian Bureau of Statistics",
        "evidence": "aud_inflation_strict_pit_evidence_v1_2026-10-09.json",
        "expected_semantic_hash": "d448f8717ab8a7ae73a93e0444aed0e72e97a1dc71e4f74ae61eed541f",  # overwritten by pinned rowset check below
        "keys": ["reference_quarter", "cpi_yoy", "release_date",
                 "release_time", "timezone", "pit_status"],
        "csv_columns": ["reference_quarter", "cpi_yoy", "release_date",
                        "release_time", "timezone", "source_url",
                        "source_sha256", "route", "pit_status"],
        "allowed_hosts": {"www.abs.gov.au"},
    },
}
# Explicit separate AUD SHA in archival evidence. Keep adjacent to EUR pin;
# a wrong/poisoned row cannot be accepted by either semantic or original bytes.
ENTRIES["AUD.inflation"]["expected_semantic_hash"] = (
    "d448f8717ab8a7ae73af7d591fd1114512e578c6ef3821f3afe96ae9b789a31f"
)


def require(ok, msg):
    if not ok:
        raise ValueError("GMFQ_139_ARCHIVED_RELEASES_REJECTED: " + msg)


def _period_index(raw, frequency):
    require(isinstance(raw, str) and
            re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])", raw),
            "invalid economic observation period")
    y, m = map(int, raw.split("-"))
    if frequency == "Q":
        require(m in (3, 6, 9, 12), "ABS only quarterly CPI observations")
        return 4 * y + (m - 1)//3
    return 12 * y + m - 1


def _utc_gate(row, key):
    if key == "EUR.inflation":
        day = date.fromisoformat(row["release_date"])
        # Date-only historical Eurostat web attestation -> next UTC day.
        return datetime.combine(day + timedelta(days=1), time.min,
                                timezone.utc), "CONSERVATIVE_NEXT_UTC_DAY"
    day = datetime.strptime(row["release_date"], "%d/%m/%Y").date()
    stamp = row["release_time"].lower().replace(" ", "")
    require(re.fullmatch(r"(?:0?[1-9]|1[0-2]):[0-5]\d(?:am|pm)", stamp),
            "ABS published release-time format changed")
    hour, minute = map(int, stamp[:-2].split(":"))
    hour = (hour % 12) + (12 if stamp[-2:] == "pm" else 0)
    zone = ZoneInfo("Australia/Sydney")  # Same IANA civil time as Canberra.
    local = datetime.combine(day, time(hour, minute), zone)
    abbreviation = local.tzname()
    require(row["timezone"] in ("CANBERRA_TIME", "AEST", "AEDT"),
            "unknown ABS publisher time zone")
    if row["timezone"] != "CANBERRA_TIME":
        require(row["timezone"] == abbreviation,
                "ABS release DST designation disagrees with Australia/Sydney tzdb")
    return local.astimezone(timezone.utc), (
        "ABS_PUBLISHED_LOCAL_TIME_IANA_SYDNEY_CANBERRA_CONVERTED_TO_UTC"
    )


def rows_and_events(key, *, root=ROOT):
    require(key in ENTRIES, "only EUR and AUD published first-release streams")
    spec = ENTRIES[key]
    path = root / "validation/macro/fixtures" / spec["fixture"]
    # LZMA supports a fixed upper bound on uncompressed CSV size.
    zipped = base64.b64decode("".join(path.read_text(encoding="ascii").split()),
                              validate=True)
    decompressor = lzma.LZMADecompressor()
    raw = decompressor.decompress(zipped, max_length=50000)
    require(decompressor.eof and len(raw) < 50000,
            "archived source compressed fixture truncated/oversized")
    require(hashlib.sha256(raw).hexdigest() == spec["original_csv_sha256"],
            "archived ORIGINAL CSV bytes do not match downloaded artifact")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    require(reader.fieldnames == spec["csv_columns"],
            "source original CSV header schema drift")
    rows = list(reader)
    require(len(rows) == spec["count"] and
            rows[0][spec["keys"][0]] == spec["start"] and
            rows[-1][spec["keys"][0]] == spec["end"],
            "archival CSV source count/coverage drift")
    event_rows, seen, sha_seen, periods = [], set(), set(), []
    for row in rows:
        economic_period = row[spec["keys"][0]]
        idx = _period_index(economic_period, spec["frequency"])
        require(idx not in seen, "duplicate archived first-release economic period")
        seen.add(idx)
        periods.append(idx)
        raw_value = row["headline_hicp_yoy_pct" if key == "EUR.inflation"
                        else "cpi_yoy"]
        value = float(raw_value)
        require(math.isfinite(value) and -30 < value < 50,
                "nonfinite or implausible archived CPI rate")
        row["headline_hicp_yoy_pct" if key == "EUR.inflation"
            else "cpi_yoy"] = value
        url = row["source_url"]
        u = urlsplit(url)
        require(u.scheme == "https" and u.hostname in spec["allowed_hosts"]
                and u.path and not u.username and not u.password
                and not u.fragment, "nonofficial source URL in archive")
        source_hash = row["page_sha256" if key == "EUR.inflation"
                          else "source_sha256"]
        require(re.fullmatch(r"[0-9a-f]{64}", source_hash) is not None and
                source_hash not in sha_seen, "invalid or reused official source hash")
        sha_seen.add(source_hash)
        require(row["pit_status"] == (
            "STRICT_FIRST_RELEASE_FLASH" if key == "EUR.inflation"
            else "STRICT_FIRST_RELEASE"),
            "not archived FIRST-release record")
        gate, clock_quality = _utc_gate(row, key)
        require(gate.date() >= date(idx // (12 if key == "EUR.inflation" else 4),
                                  1, 1), "release date predates reference year")
        event_rows.append({
            "currency": key[:3], "pillar": "inflation",
            "canonical_series_id": spec["canonical_series_id"],
            "frequency": spec["frequency"],
            "reference_period": economic_period,
            "stage": "FIRST_WEB",
            "reported_value": value,
            "visible_from_utc": gate.isoformat(),
            "publisher_clock_quality": clock_quality,
            "source_url": url,
            "archived_source_sha256": source_hash,
            "archived_source_route": row.get("source_route", row.get("route")),
            "source_receipt_artifact_id": spec["artifact_id"],
            "original_day_immutable_bytes_independently_reverified_now": False,
            "PIT_history_replay_for_trading_authorized": False,
        })
    require(periods == list(range(periods[0], periods[-1] + 1)),
            "archived CPI economic periods not contiguous")

    semantic = hashlib.sha256(json.dumps(
        [{k: row[k] for k in spec["keys"]} for row in rows],
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    require(semantic == spec["expected_semantic_hash"],
            "archived first-release semantic SHA mismatch")
    evidence = json.loads((root / "validation/macro" / spec["evidence"])
                          .read_text(encoding="utf-8"))
    coverage = evidence["coverage"]
    require(evidence["status"] == "PASS" and
            evidence["target"] == key and
            evidence["series_contract"]["series_id"] == spec["canonical_series_id"]
            and evidence["series_contract"]["frequency"] == spec["frequency"]
            and evidence["semantic_rowset_sha256"] == semantic
            and coverage["start"] == spec["start"] and
            coverage["end"] == spec["end"] and
            coverage["materialized_months" if key == "EUR.inflation"
                     else "materialized_quarters"] == spec["count"]
            and not evidence.get("missing") and not evidence.get("errors"),
            "separate archival issuer materializer receipt not identical")
    return {
        "currency": key[:3], "pillar": "inflation",
        "source_id": spec["canonical_series_id"],
        "frequency": spec["frequency"],
        "reference_periods": len(event_rows),
        "source_observation_first": spec["start"],
        "source_observation_last": spec["end"],
        "source_csv_sha256": spec["original_csv_sha256"],
        "source_semantic_sha256": semantic,
        "archived_github_artifact_id": spec["artifact_id"],
        "archived_github_run_id": spec["artifact_workflow_run"],
        "events": event_rows,
        "first_publisher_source_bytes_pinned_by_artifact_source_sha_not_revalidated_now": True,
        "historical_full_revision_chain_certified": False,
        "canonical_source_research_history_loaded_but_not_model_approved": True,
        "safe_to_publish_new_D": False,
        "safe_for_beta": False, "safe_for_forward": False,
    }


def archived_overlay(*, root=ROOT, as_of="2026-10-27T00:00:00Z"):
    cutoff = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    require(cutoff.tzinfo is not None and cutoff.utcoffset() == timedelta(0),
            "UTC historical replay cutoff required")
    out = {}
    for key in ENTRIES:
        item = rows_and_events(key, root=root)
        visible = [e for e in item["events"]
                   if datetime.fromisoformat(e["visible_from_utc"]) <= cutoff]
        newest = visible[-1] if visible else None
        out[key] = {**item,
                    "as_of_utc": cutoff.isoformat(),
                    "visible_initial_web_periods": len(visible),
                    "most_recent_first_web_at_cutoff": newest}
    return {
        "schema": SCHEMA, "status": "EUR_105M_AUD_34Q_SOURCE_ARCHIVE_LOADED_RESEARCH",
        "as_of_utc": cutoff.isoformat(),
        "histories": out,
        "summary": {
            "pinned_original_first_web_rows": 139,
            "eur_inflation_monthly": 105, "aud_inflation_quarterly": 34,
            "official_source_csvs_permanently_committed_in_repo": 2,
            "source_archival_receipts_reconciled": 2,
            "live_core_pillar_scores_updated": 0,
            "fx_pair_rankings_changed": 0,
        },
        "no_rewriting_old_flash_from_later_Eurostat_detail": True,
        "no_substituting_monthly_ABS_for_quarterly_ABS": True,
        "no_reconstruction_of_original_day_publisher_source_bytes": True,
        "historical_aggregate_score_pit_certified": False,
        "safe_to_publish_new_D": False, "safe_to_change_28_pairs": False,
        "safe_for_beta": False, "safe_for_forward": False,
        "writes_live_data": False,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default="2026-10-27T00:00:00Z")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        require(args.output.resolve().is_relative_to(Path("/tmp")),
                "research artifact must stay under /tmp")
    x = archived_overlay(as_of=args.as_of)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(x, indent=2) + "\n",
                               encoding="utf-8")
    print(json.dumps({"status": x["status"], **x["summary"],
                      "safe_to_publish_new_D": False}, sort_keys=True))
