#!/usr/bin/env python3
"""One-off *read-only* download diagnostic: historic BLS CPI source bytes and ALFRED.

Never executed by standard pipeline. Explicit opt-in via one-shot PR workflow.
This script does NOT certify PIT vintage, alter live data, infer October 2025,
or interpret a downloaded XLSX as a known original first-release vintage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from zipfile import ZipFile, BadZipFile
from io import BytesIO

ALLOW = {"www.bls.gov", "alfred.stlouisfed.org"}
MAX = 5 * 1024 * 1024
TARGETS = [
 ("bls_cpi_u_202609", "https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-202609.xlsx", "xlsx"),
 ("bls_historical_cpi_u_202609", "https://www.bls.gov/cpi/tables/supplemental-files/historical-cpi-u-202609.xlsx", "xlsx"),
 ("bls_cpi_u_202601", "https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-202601.xlsx", "xlsx"),
 ("bls_cpi_u_202512", "https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-202512.xlsx", "xlsx"),
 ("bls_cpi_u_202511", "https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-202511.xlsx", "xlsx"),
 ("bls_supplemental_archive_index", "https://www.bls.gov/cpi/tables/supplemental-files/", "html"),
 ("alfred_2025_12_18_cpiaucsl_vintage",
  "https://alfred.stlouisfed.org/graph/alfredgraph.csv?" +
  urlencode({"id":"CPIAUCSL","vintage_date":"2025-12-18","cosd":"2024-09-01","coed":"2025-11-01"}),
  "csv"),
]

def target_probe(name, url, expected, out):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOW:
        raise ValueError("unapproved download source host")
    result = {"target": name, "url": url, "expected_format": expected,
              "http_status": None, "downloaded_bytes": 0,
              "download_sha256": None, "contains_requested_original_release_day_pit_proof": False,
              "source_quality": "UNVERIFIED_UNTIL_BYTES_CHECKED",
              "error_kind": None, "zip_sample_members": []}
    try:
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; MacroV2Research/1.0)",
            "Accept": "*/*"})
        with urlopen(req, timeout=12) as response:
            actual = urlparse(response.geturl())
            if actual.hostname not in ALLOW or actual.scheme != "https":
                raise ValueError("blocked external redirect")
            result["http_status"] = response.status
            data = response.read(MAX + 1)
        if len(data) > MAX:
            raise ValueError("oversized response blocked")
        if expected == "xlsx":
            if not data.startswith(b"PK\x03\x04"):
                raise ValueError("not XLSX archive magic")
            try:
                with ZipFile(BytesIO(data)) as z:
                    members = z.namelist()
                    if "[Content_Types].xml" not in members or not any(
                        x.startswith("xl/worksheets/") for x in members
                    ):
                        raise ValueError("ZIP not spreadsheet")
                    result["zip_sample_members"] = members[:10]
            except BadZipFile as exc:
                raise ValueError("bad XLSX ZIP") from exc
        elif expected == "html":
            if b"Archived Consumer Price Index" not in data:
                raise ValueError("not BLS CPI index page")
        elif expected == "csv":
            head = data[:300].decode("utf-8-sig", "replace")
            if "CPIAUCSL_" not in head or ("observation_date" not in head and "DATE" not in head):
                raise ValueError("not expected dated ALFRED CPIAUCSL data")
        result["downloaded_bytes"] = len(data)
        result["download_sha256"] = hashlib.sha256(data).hexdigest()
        result["source_quality"] = "BYTES_CAPTURED_TODAY_NOT_HISTORIC_ISSUER_PIT"
        folder = out / "raw_research_sources"
        folder.mkdir(exist_ok=True, parents=True)
        (folder / (name + "." + expected)).write_bytes(data)
    except HTTPError as exc:
        result["http_status"] = exc.code
        result["error_kind"] = "HTTP_ERROR_NO_BYTES"
    except (URLError, TimeoutError, OSError) as exc:
        result["error_kind"] = type(exc).__name__
    except ValueError as exc:
        result["error_kind"] = "VALIDATION_ERROR_" + str(exc)[:64].replace(" ", "_")
    return result

def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--out", type=Path, default=Path("/tmp/bls_cpi_research_probe"))
    args = cli.parse_args()
    root = args.out.resolve()
    if not root.is_relative_to(Path("/tmp")):
        raise ValueError("no writes outside /tmp")
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, url, kind in TARGETS:
        item = target_probe(name, url, kind, root)
        rows.append(item)
        print("PROBE_RECEIPT: " + json.dumps(item, sort_keys=True), flush=True)
    receipt = {
      "schema":"GMFQ_MACRO_V2_US_CPI_BLS_ALFRED_BYTES_ONE_SHOT_PROBE_V1",
      "acquired_on_utc":datetime.now(timezone.utc).isoformat(),
      "status":"RESEARCH_TRANSPORT_DIAGNOSTIC_NOT_VINTAGE_CERTIFICATION",
      "results":rows,
      "successfully_captured_source_byte_files":sum(x["download_sha256"] is not None for x in rows),
      "original_BLS_first_issuer_vintages_PIT_certified":0,
      "missing_2025_10_all_items_CPI_observation_filled":False,
      "current_revised_source_never_substituted_for_original":True,
      "safe_to_publish_new_D":False,
      "safe_to_change_28_pairs":False,
      "safe_for_beta":False,
      "safe_for_forward":False,
      "writes_live_data":False,
    }
    (root / "receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print("SUMMARY_RECEIPT: " + json.dumps({
       "attempted":len(rows),
       "captured":receipt["successfully_captured_source_byte_files"],
       "first_vintages_certified":0,
       "blocked":sum(x["download_sha256"] is None for x in rows)
    }),flush=True)

if __name__ == "__main__":
    main()
