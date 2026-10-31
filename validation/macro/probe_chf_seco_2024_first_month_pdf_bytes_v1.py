#!/usr/bin/env python3
"""Bounded issuer-host PDF-byte recheck of four SECO 2024 first-month documents.

Recovery today != publisher-day PIT capture; a PDF header alone does not prove
that its table/first column is the original monthly issue. No automatic source
ledger promotion, no source-day clock invention, no Macro FX/Forward writes.
The two candidate issuer URLs for each month were previously identified by
the existing SECO first-month source dossier.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from validation.macro.v2_chf_seco_first_month_rounded_alternative_v1 import (
    EARLY_INDEX_ONLY, INDEXED_OFFICIAL_PDF_TEXT_ONLY,
)

SCHEMA = "GMFQ_CHF_SECO_2024_FOUR_ISSUER_PDF_BYTE_RECHECK_V1"
MAX_BYTES = 12 * 1024 * 1024
ALLOWED_HOSTS = {"www.seco.admin.ch", "seco.admin.ch",
                 "www.arbeit.swiss", "arbeit.swiss"}
TARGETS = ("2024-09", "2024-10", "2024-11", "2024-12")


def require(value, message):
    if not value:
        raise ValueError("CH_SECO_PDF_BYTE_PROBE_REJECTED: " + message)


def allowed_url(url, month):
    parsed = urlsplit(url)
    require(parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS
            and parsed.port in (None, 443)
            and not parsed.username and not parsed.password
            and parsed.path.endswith("/" + month + "_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf"),
            "not a pinned official issuer PDF URL")
    return url


def candidates():
    raw = {period: original for period, _, _, original in EARLY_INDEX_ONLY}
    require(set(raw) == set(INDEXED_OFFICIAL_PDF_TEXT_ONLY) == set(TARGETS),
            "exact four original-report months")
    result = {}
    for month in TARGETS:
        indexed = INDEXED_OFFICIAL_PDF_TEXT_ONLY[month][0]
        result[month] = tuple(dict.fromkeys(
            (allowed_url(raw[month], month), allowed_url(indexed, month))))
    return result


def pdf_candidate(raw, reported_type, final_url, month):
    allowed_url(final_url, month)
    require(isinstance(raw, bytes) and 15000 <= len(raw) <= MAX_BYTES
            and raw.startswith(b"%PDF-") and b"%%EOF" in raw[-4096:],
            "no complete nontrivial PDF bytes received")
    require("pdf" in (reported_type or "").lower() or
            (reported_type or "").lower() == "application/octet-stream",
            "non-PDF server media type")
    return {"sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
            "source_pdf_header_and_eof_only": True,
            "monthly_table_first_column_authenticated": False,
            "publisher_day_original_HTTP_bytes_certified": False,
            "exact_SNB_first_publication_vintage_proven": False}


def fetch(url, month, timeout=12):
    req = urllib.request.Request(url, headers={
        "User-Agent": "GMFQ-CHF-SECO-first-reports-provenance/1.0",
        "Accept": "application/pdf",
    })
    with urllib.request.urlopen(req, timeout=timeout) as res:
        require(res.status == 200, "HTTP response not 200")
        final = res.geturl()
        allowed_url(final, month)
        content = res.read(MAX_BYTES + 1)
        meta = pdf_candidate(content, res.headers.get("Content-Type"), final, month)
        return content, meta, final


def run(*, output_dir, attempt=fetch):
    output_dir = Path(output_dir)
    require(output_dir.resolve().is_relative_to(Path("/tmp")),
            "use a temporary research artifact directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    all_results = {}
    downloaded = 0
    for month, urls in candidates().items():
        trials = []
        selected = None
        for url in urls:
            try:
                body, detail, final_url = attempt(url, month)
                # Validate results independently, including any fake transport.
                checked = pdf_candidate(body, "application/pdf", final_url, month)
                require(checked["sha256"] == detail["sha256"],
                        "transport claimed different bytes")
                filename = "CH_SECO_2024_" + month + "_CANDIDATE_DOWNLOADED_TODAY.pdf"
                (output_dir / filename).write_bytes(body)
                selected = {"url": url, "final_url": final_url, "file": filename,
                            "candidate": checked}
                trials.append({"url":url, "status":"PDF_BINARY_CANDIDATE_CAPTURABLE"})
                downloaded += 1
                break
            except (ValueError, urllib.error.HTTPError,
                    urllib.error.URLError, TimeoutError, OSError) as error:
                trials.append({"url":url,"status":"FETCH_OR_PDF_VALIDATION_FAILED",
                               "error_type":type(error).__name__,
                               "http_status":getattr(error, "code", None)})
        all_results[month] = {
            "attempted_issuer_urls": trials,
            "captured_candidate_today": selected,
            "original_2024_publisher_day_vintage_verified": False,
            "old_2024_first_source_SNB_exact_value_proven": False,
        }
    report = {
        "schema": SCHEMA, "retrieved_at_utc": now,
        "source_months": all_results,
        "summary": {
            "first_month_periods_checked": 4,
            "candidate_PDF_bytes_retrieved_today": downloaded,
            "still_no_candidate_original_PDF_bytes": 4 - downloaded,
            "exact_historical_SNB_release_vintages_certified": 0,
            "publisher_day_original_HTTP_vintages_certified": 0,
        },
        "source_day_replay_certified": False,
        "source_table_first_column_authenticated": False,
        "can_upgrade_2024_SECO_fixture_automatically": False,
        "can_promote_CHF_labour_to_24_months_PIT": False,
        "can_update_D_or_28_pairs": False,
        "can_update_Forward_or_Beta": False,
        "writes_live_data": False,
    }
    (output_dir / "probe_manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args()
    r = run(output_dir=args.output_dir)
    print(json.dumps({"schema": SCHEMA, "summary": r["summary"],
                      "no_source_promotion": True}, sort_keys=True))


if __name__ == "__main__":
    main()
