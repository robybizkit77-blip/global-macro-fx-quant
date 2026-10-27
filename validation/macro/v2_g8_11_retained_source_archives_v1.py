#!/usr/bin/env python3
"""Decode 11 fixed, archived official first-release research sources.

Historical CSV/JSON bytes are pinned to earlier independent materializer
receipts and were copied losslessly to tracked compressed ASCII fixtures.
Proof is that the rows match the earlier evidence archives byte-for-byte,
NOT proof of fresh independent issuer web re-fetch or a joint 24-axis PIT test.
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
from datetime import datetime, date, timedelta, time, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.one_shot_retain_g8_11_original_release_artifacts_v1 import PINNED

SCHEMA = "GMFQ_MACRO_V2_11_G8_OFFICIAL_2018_2026_FIRST_RELEASE_ARCHIVES_V1"
FOLDER = ROOT / "validation/macro/fixtures"
MANIFEST = FOLDER / "G8_STRICT_SOURCE_FIRST_RELEASE_11_ARCHIVES_MANIFEST.json"
METRICS = {
    "NZD.inflation": ("observation_date", "value", "source_sha256", "Q"),
    "NZD.labour": ("observation_date", "value", "source_sha256", "Q"),
    "AUD.labour": ("reference_month", "unemployment_rate_sa", "sha256", "M"),
    "CAD.inflation": ("reference_month", "headline_yoy_reported", "combined_sha256", "M"),
    "CAD.labour": ("reference_month", "unemployment_rate_sa", "sha256", "M"),
    "EUR.labour": ("reference_month", "unemployment_rate_pct", "page_sha256", "M"),
    "GBP.inflation": ("reference_month", "headline_cpi_yoy_pct", "page_sha256", "M"),
    "GBP.labour": ("reference_month", "headline_unemployment_rate_pct", "page_sha256", "M"),
    "JPY.inflation": ("observation_date", "value", "source_sha256", "M"),
    "JPY.labour": ("reference_month", "unemployment_rate_sa_pct", "sha256", "M"),
    "CHF.inflation": ("reference_month", "headline_cpi_yoy_pct", "source_sha256", "M"),
}
HOSTS = {
    "NZD": {"www.stats.govt.nz"},
    "AUD": {"www.abs.gov.au"},
    "CAD": {"www150.statcan.gc.ca"},
    "EUR": {"ec.europa.eu"},
    "GBP": {"www.ons.gov.uk"},
    "JPY": {"www.e-stat.go.jp", "www.stat.go.jp"},
    "CHF": {"dam-api.bfs.admin.ch"},
}


def require(ok, what):
    if not ok:
        raise ValueError("G8_RETAINED_FIRST_RELEASE_SOURCE_REJECTED: " + what)


def economic_index(ref, frequency):
    require(isinstance(ref, str) and re.fullmatch(r"20\d\d-\d\d", ref),
            "invalid published reference period")
    y, m = map(int, ref.split("-"))
    require(1 <= m <= 12, "invalid economic period month")
    if frequency == "Q":
        require(m in (3, 6, 9, 12), "quarterly original period cannot be monthly substitute")
        return 4*y+(m//3-1)
    return 12*y+m-1


def publisher_gate(row, currency):
    day = (datetime.strptime(row["release_date"], "%d/%m/%Y").date()
           if currency == "AUD" else date.fromisoformat(row["release_date"]))
    if row.get("availability_timestamp_jst"):
        return (datetime.fromisoformat(row["availability_timestamp_jst"])
                .astimezone(timezone.utc).isoformat()), "PUBLISHER_JST_0830"
    if currency == "CAD":
        local = datetime.combine(day, time.fromisoformat(row["release_time"]),
                                 tzinfo=ZoneInfo("America/Toronto"))
        return local.astimezone(timezone.utc).isoformat(), "STATCAN_EASTERN_0830_DST"
    if currency == "AUD":
        value = row["release_time"].strip().lower().replace(" ", "")
        match = re.fullmatch(r"(\d{1,2}):(\d\d)(am|pm)", value)
        require(match is not None, "invalid historical Canberra reporting time")
        h, m, ampm = match.groups()
        h = int(h)%12 + (12 if ampm == "pm" else 0)
        local = datetime.combine(day, time(h,int(m)), tzinfo=ZoneInfo("Australia/Sydney"))
        return local.astimezone(timezone.utc).isoformat(), "ABS_CANBERRA_LOCAL_TIME_DST"
    if currency == "CHF":
        local = datetime.combine(day, time.fromisoformat(row["release_time_utc"]),
                                 timezone.utc)
        return local.isoformat(), "SFSO_UTC_RELEASE_TIME"
    # No intraday first-release time proved: a conservative visibility gate,
    # not an assertion that the publisher actually released at midnight.
    return datetime.combine(day + timedelta(days=1), time.min,
                            timezone.utc).isoformat(), "CONSERVATIVE_NEXT_UTC_DAY"


def decode_slot(key, *, folder=FOLDER):
    meta = {p[0]: p for p in PINNED}
    require(key in meta and key in METRICS, "unknown issuer first-release slot")
    name, artifact_id, member, sha, count, freq = meta[key]
    manifest = json.loads((folder / MANIFEST.name).read_text(encoding="utf-8"))
    require(manifest["schema"] ==
            "GMFQ_G8_11_PERSISTED_FIRST_RELEASE_ARCHIVES_V1" and
            manifest["source_archives"] == 11 and
            len(manifest["sources"]) == 11,
            "retention provenance manifest not complete")
    m = next((x for x in manifest["sources"] if x["slot"] == key), None)
    require(m is not None and
            m["artifact_id"] == artifact_id and
            m["original_source_materialization_sha256"] == sha and
            m["first_release_periods"] == count and
            m["frequency"] == freq,
            "retained raw file differs from pinned archived artifact")
    raw_encoded = (folder / m["fixture"]).read_text(encoding="ascii").strip()
    encoded = base64.b64decode(raw_encoded, validate=True)
    decoder = lzma.LZMADecompressor()
    raw = decoder.decompress(encoded, max_length=250000)
    require(decoder.eof and len(raw) < 250000 and
            hashlib.sha256(raw).hexdigest() == sha,
            "ORIGINAL archived CSV/JSON bytes SHA256 not verified")
    document = json.loads(raw) if member.endswith(".json") else None
    rows = (document.get("rows") or document.get("records")
            if document is not None else
            list(csv.DictReader(io.StringIO(raw.decode("utf-8")))))
    require(isinstance(rows,list) and len(rows) == count,
            "archived publisher original release row count drift")
    field, rate, source_sha, metric_frequency = METRICS[key]
    require(metric_frequency == freq, "metric frequency mismatch")
    seen, points = set(), []
    for r in rows:
        require(r.get("pit_status", "STRICT_FIRST_RELEASE") == "STRICT_FIRST_RELEASE",
                "source row not first publication")
        ref = r[field]
        ix = economic_index(ref,freq)
        require(ix not in seen, "duplicate economic first-release period")
        seen.add(ix)
        amount = float(r[rate])
        require(math.isfinite(amount) and -40 < amount < 80,
                "nonfinite/unreasonable first-published percentage")
        url = urlsplit(r["source_url"])
        currency, pillar = key.split(".")
        require(url.scheme == "https" and url.hostname in HOSTS[currency] and
                url.path and not url.username and not url.password,
                "issuer web URL not on approved official domain")
        digest = r[source_sha]
        require(re.fullmatch(r"[a-f0-9]{64}", digest) is not None,
                "source original publisher file hash absent")
        clock, clock_quality = publisher_gate(r, currency)
        # Release clock must follow the period's economic start.
        require(datetime.fromisoformat(clock).year >= int(ref[:4]),
                "publisher release date before economic report period")
        points.append({
            "slot": key,
            "reference_period": ref,
            "first_web_value": amount,
            "first_web_publisher_gate_utc": clock,
            "first_web_publisher_gate_quality": clock_quality,
            "official_source_url": r["source_url"],
            "original_publisher_materialization_sha256": digest,
            "metric_frequency": freq,
            "value_as_original_reported": True,
            "first_publisher_day_http_bytes_independently_recaptured_now": False,
            "valid_source_for_PIT_FX_backtest": False,
        })
    require([economic_index(x["reference_period"],freq) for x in points] ==
            list(range(min(seen), max(seen)+1)),
            "historical original first release periods not continuous")
    return {
        "slot": key, "currency": key.split(".")[0], "pillar": key.split(".")[1],
        "frequency": freq, "issuer_original_artifact_id": artifact_id,
        "artifact_member": member,
        "original_materializer_bytes_sha256": sha,
        "first_web_release_count": count,
        "first_reference_period": points[0]["reference_period"],
        "last_reference_period": points[-1]["reference_period"],
        "records": points,
        "historical_issuer_source_bytes_attested_by_earlier_materializer": True,
        "all_original_day_source_bytes_independently_refetched_today": False,
        "full_revision_history_complete": False,
        "FX_scoring_approved": False,
    }


def run(*, folder=FOLDER):
    items={key:decode_slot(key,folder=folder) for key, *_ in PINNED}
    require(len(items) == 11 and
            all(x["FX_scoring_approved"] is False for x in items.values()),
            "eleven official originals required with hard no-scoring guarantee")
    return {
        "schema": SCHEMA,
        "status": "11_EXISTING_STRICT_FIRST_RELEASE_DATASETS_RETAINED_NOT_JOINT_MACRO_PIT",
        "histories": items,
        "summary": {
            "g8_histories_added": len(items),
            "archived_first_release_observations": sum(
                x["first_web_release_count"] for x in items.values()),
            "PIT_24_axis_historical_model_scores_approved": 0,
            "FX_rankings_updated": 0,
        },
        "source_bytes_equal_to_prior_independently_audited_archives": True,
        "source_timestamp_quality_per_event_retained": True,
        "not_all_24_sources_joint_original_day_certified": True,
        "safe_to_publish_new_D": False,
        "safe_to_change_28_pairs": False,
        "safe_for_beta": False, "safe_for_forward": False,
        "writes_live_data": False,
    }


if __name__ == "__main__":
    x=run()
    print(json.dumps(x["summary"], sort_keys=True))
