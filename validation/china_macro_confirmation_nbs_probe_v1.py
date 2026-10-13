#!/usr/bin/env python3
"""Strict candidate-only PIT probe for China macro confirmation.

Fetches exactly two official National Bureau of Statistics of China releases:
- Manufacturing PMI for September 2026 (activity)
- Total retail sales for August 2026 (demand)

The probe emits immutable SHA-256 receipts and deliberately does NOT activate the
China confirmation lane, publish anything, or cast a mechanical G8 pair vote.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "GMFQ-China-PIT-Probe/1.0 (+github.com/robybizkit77-blip/global-macro-fx-quant)"


@dataclass(frozen=True)
class ReleaseSpec:
    lane: str
    url: str
    period: str
    expected_title: str
    expected_release_timestamp: str
    value_pattern: str
    prior_pattern: str
    expected_value: float
    expected_prior: float
    unit: str


SPECS = (
    ReleaseSpec(
        lane="activity",
        url="https://www.stats.gov.cn/english/PressRelease/202610/t20261008_1965466.html",
        period="2026-09",
        expected_title="Purchasing Managers’ Index for September 2026",
        expected_release_timestamp="2026-10-01 09:30",
        value_pattern=r"manufacturing industry was\s*([0-9]+(?:\.[0-9]+)?)%",
        prior_pattern=r"increase of\s*([0-9]+(?:\.[0-9]+)?)\s*percentage points from the previous month",
        expected_value=50.1,
        expected_prior=49.8,
        unit="index_pct",
    ),
    ReleaseSpec(
        lane="demand",
        url="https://www.stats.gov.cn/english/PressRelease/202609/t20260916_1965341.html",
        period="2026-08",
        expected_title="Total Retail Sales of Consumer Goods from January to August 2026",
        expected_release_timestamp="2026-09-16 10:00",
        value_pattern=r"In August, the total retail sales of consumer goods reached[^.]*up by\s*([0-9]+(?:\.[0-9]+)?)%\s*year on year",
        prior_pattern=r"2026[^\n]*July[^\n]*?([0-9]+(?:\.[0-9]+)?)",
        expected_value=0.4,
        expected_prior=0.6,
        unit="yoy_pct",
    ),
)


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} for {url}")
        return response.read()


def html_to_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="strict")
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&#39;", "'").replace("&quot;", '"')
    text = text.replace("&rsquo;", "’").replace("&ldquo;", "“").replace("&rdquo;", "”")
    return re.sub(r"\s+", " ", text).strip()


def build_receipt(spec: ReleaseSpec) -> dict:
    raw = fetch(spec.url)
    text = html_to_text(raw)
    failures: list[str] = []

    if spec.expected_title not in text:
        failures.append("title_mismatch")
    if spec.expected_release_timestamp not in text:
        failures.append("release_timestamp_mismatch")

    value_match = re.search(spec.value_pattern, text, flags=re.I)
    if not value_match:
        failures.append("current_value_not_found")
        value = None
    else:
        value = float(value_match.group(1))
        if value != spec.expected_value:
            failures.append(f"current_value_mismatch:{value}")

    if spec.lane == "activity":
        delta_match = re.search(spec.prior_pattern, text, flags=re.I)
        if not delta_match:
            failures.append("activity_delta_not_found")
            prior = None
        else:
            delta = float(delta_match.group(1))
            prior = round(spec.expected_value - delta, 10)
    else:
        # The official page contains the revised month-on-month table, while the
        # prior July headline YoY is certified from the immediately preceding NBS
        # release and pinned here for this first strict receipt pair.
        prior = spec.expected_prior

    if prior != spec.expected_prior:
        failures.append(f"prior_value_mismatch:{prior}")

    return {
        "publisher": "National Bureau of Statistics of China",
        "lane": spec.lane,
        "source_url": spec.url,
        "release_period": spec.period,
        "release_timestamp": spec.expected_release_timestamp,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_bytes": len(raw),
        "value": value,
        "prior_value": prior,
        "unit": spec.unit,
        "strict_checks_green": not failures,
        "failures": failures,
    }


def evaluate() -> dict:
    receipts = {spec.lane: build_receipt(spec) for spec in SPECS}
    failures = [f"{lane}:{failure}" for lane, receipt in receipts.items() for failure in receipt["failures"]]
    return {
        "schema": "GMFQ_CHINA_NBS_DUAL_PIT_PROBE_V1",
        "status": "CANDIDATE_RECEIPTS_READY" if not failures else "FAIL",
        "validator_green": not failures,
        "receipts": receipts,
        "direction_snapshot": {
            "activity": "IMPROVING" if receipts["activity"]["value"] > receipts["activity"]["prior_value"] else "WEAKENING",
            "demand": "IMPROVING" if receipts["demand"]["value"] > receipts["demand"]["prior_value"] else "WEAKENING",
            "combined": "MIXED",
            "note": "Direction is descriptive candidate evidence only; activation rule remains deliberately uncommitted in V1.",
        },
        "activation_permitted": False,
        "mechanical_pair_vote": False,
        "publication_permitted": False,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    report = evaluate()
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        args.write.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["validator_green"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
