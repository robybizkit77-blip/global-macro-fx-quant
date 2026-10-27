#!/usr/bin/env python3
"""One-time, exact-hash-pinned retention of 11 earlier STRICT issuer-release artifacts.

Runs only in the short-lived feature branch under an explicitly permissioned
one-shot GitHub Actions workflow. Source: immutable IDs of archived Actions ZIPs.
Rejects changed original bytes or unexpected record counts. Never fetches
current revised economic time series or writes to live_data.
"""
from __future__ import annotations
import base64
import csv
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
REPO = "robybizkit77-blip/global-macro-fx-quant"
PINNED = [
  [
    "NZD.inflation",
    11684277043,
    "a/evidence.json",
    "b8ce3150581aa0e5b18bd521a458838258a72465aad092c16d419d74d1a294b2",
    34,
    "Q"
  ],
  [
    "NZD.labour",
    11695734299,
    "a/evidence.json",
    "55ff014e485de5afa2f31e09add51c90dc8dd42a077c265267bce4dc75fed92f",
    34,
    "Q"
  ],
  [
    "AUD.labour",
    11624278864,
    "aud-labour-full-archive-probe.json",
    "fbccc3ba685a25ca0b90425459f56116c92ef0fe05381afbaf1816f4ddafc9a0",
    104,
    "M"
  ],
  [
    "CAD.inflation",
    11639347271,
    "CAD_CPI_STRICT_FIRST_RELEASE_2018_2026_08.csv",
    "8317ee57fa8c81a3d9610d818ccc53fd28209900590817a34b747d536f25c7ad",
    104,
    "M"
  ],
  [
    "CAD.labour",
    11632028728,
    "CAD_LABOUR_UNEMPLOYMENT_STRICT_FIRST_RELEASE_2018_2026_08.csv",
    "ef2e2e61157f51511203ce6be8649eb0b429472b56180b1777bb81f3dd1900b9",
    104,
    "M"
  ],
  [
    "EUR.labour",
    11678794954,
    "a/EUR_LABOUR_STRICT_FIRST_RELEASE_2018_2026_08.csv",
    "358a247324d64f5fada9014ecd042694e25849d3ffa1468842ee02baa20d3924",
    104,
    "M"
  ],
  [
    "GBP.inflation",
    11667538364,
    "a/GBP_INFLATION_STRICT_FIRST_RELEASE_2018_2026_08.csv",
    "0d0a1e3b5b2d8b4aae883e45bde8212d03a8378394fab9681e6c1eeb320bdad1",
    104,
    "M"
  ],
  [
    "GBP.labour",
    11665467830,
    "a/GBP_LABOUR_STRICT_FIRST_RELEASE_2018_2026_06.csv",
    "32c433b8fa8c1f39f9d766792821a29c0c99427a92ba6b1bc355b51f1f145dc2",
    102,
    "M"
  ],
  [
    "JPY.inflation",
    11680868760,
    "jpy_inflation_strict_pit_evidence_v1_runtime.json",
    "0d27eddf1ef981a4580b20a4fad28dce910dae2b58da091c6f4af04b5695422e",
    104,
    "M"
  ],
  [
    "JPY.labour",
    11620957412,
    "JPY_LABOUR_LFS_STRICT_FIRST_RELEASE_2018_2026_08.csv",
    "ee8cda9161cb8a6896be3c4a0a4bf2c78d16fdef21f5dbb01b3a7904722e9fe2",
    104,
    "M"
  ],
  [
    "CHF.inflation",
    11681952627,
    "a/evidence.json",
    "6d534298e0bd81261be04fafc6ec45899ce53ca8394c5c6d8a0cc77b8a48ff22",
    105,
    "M"
  ]
]


def get_artifact(artifact_id):
    token = os.environ["GITHUB_TOKEN"]
    endpoint = f"https://api.github.com/repos/{REPO}/actions/artifacts/{artifact_id}/zip"
    req = urllib.request.Request(endpoint, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "macro-v2-strict-archive-one-shot",
    })
    class SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, msg, headers, newurl):
            redirected = super().redirect_request(request, fp, code, msg, headers, newurl)
            if redirected is not None and not newurl.startswith("https://api.github.com/"):
                redirected.remove_header("Authorization")
                redirected.remove_unredirected_header("Authorization")
            return redirected
    return urllib.request.build_opener(SafeRedirect()).open(req, timeout=100).read()


def retain():
    folder = ROOT / "validation/macro/fixtures"
    folder.mkdir(parents=True, exist_ok=True)
    records = []
    for key, art, member, expected_sha, expected_count, frequency in PINNED:
        output = folder / f"{key.replace('.', '_')}_STRICT_WEB_FIRST_ROWS_2018_2026.archive.xz.b64"
        archive = get_artifact(art)
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            raw = z.read(member)
        got_sha = hashlib.sha256(raw).hexdigest()
        if got_sha != expected_sha:
            raise RuntimeError(f"Source artifact SHA drift: {key}: {got_sha}")
        decoded = json.loads(raw) if member.endswith(".json") else None
        if member.endswith(".csv"):
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        else:
            rows = decoded.get("rows") or decoded.get("records")
        if not isinstance(rows, list) or len(rows) != expected_count:
            raise RuntimeError(f"First-release row count drift: {key}")
        if decoded is not None and decoded.get("target") is not None:
            dtarget = decoded["target"]
            if isinstance(dtarget, dict):
                dtarget = dtarget.get("currency") + "." + dtarget.get("dimension")
            if dtarget != key:
                raise RuntimeError(f"Original issuer identity drift: {key}")
        if output.exists():
            current = lzma.decompress(base64.b64decode(output.read_text().strip()))
            if hashlib.sha256(current).hexdigest() != expected_sha:
                raise RuntimeError(f"Existing fixture digest drift: {key}")
        else:
            encoded = base64.b64encode(lzma.compress(raw, preset=6)).decode("ascii")
            output.write_text(encoded + "\n", encoding="ascii")
        records.append({"slot": key, "artifact_id": art, "archived_zip_member": member,
                        "original_source_materialization_sha256": expected_sha,
                        "first_release_periods": expected_count,
                        "frequency": frequency, "fixture": output.name,
                        "original_record_format": "json" if decoded is not None else "csv",
                        "source_origin": "EARLIER_GITHUB_ACTIONS_OFFICIAL_STRICT_PIT_MATERIALIZER",
                        "source_day_bytes_independently_refetched_today": False,
                        "eligible_to_modify_live_core": False})
        print(key, expected_count, expected_sha)
    (folder/"G8_STRICT_SOURCE_FIRST_RELEASE_11_ARCHIVES_MANIFEST.json").write_text(
        json.dumps({"schema": "GMFQ_G8_11_PERSISTED_FIRST_RELEASE_ARCHIVES_V1",
                    "sources": records,
                    "total_first_web_records": sum(a["first_release_periods"] for a in records),
                    "source_archives": len(records),
                    "live_core_changed": False,
                    "historic_web_originals_not_independently_refetched_now": True},
                   indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    retain()
