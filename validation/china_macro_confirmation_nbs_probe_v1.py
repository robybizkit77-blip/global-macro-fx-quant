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
    replacements = {
        "&nbsp;": " ", "&amp;": "&", "&#39;": "'", "&quot;": '"',
        "&rsquo;": "’", "&ldquo;": "“", "&rdquo;": "”",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def parse_activity(text: str, spec: ReleaseSpec, failures: list[str]) -> tuple[float | None, float | None]:
    current = re.search(r"manufacturing industry was\s*([0-9]+(?:\.[0-9]+)?)%", text, flags=re.I)
    delta = re.search(r"increase of\s*([0-9]+(?:\.[0-9]+)?)\s*percentage points from the previous month", text, flags=re.I)

    if not current:
        failures.append("current_value_not_found")
        value = None
    else:
        value = float(current.group(1))
        if value != spec.expected_value:
            failures.append(f"current_value_mismatch:{value}")

    if not delta:
        failures.append("activity_delta_not_found")
        prior = None
    elif value is None:
        prior = None
    else:
        prior = round(value - float(delta.group(1)), 10)
        if prior != spec.expected_prior:
            failures.append(f"prior_value_mismatch:{prior}")

    return value, prior


def parse_demand(text: str, spec: ReleaseSpec, failures: list[str]) -> tuple[float | None, float]:
    matches = [
        float(x)
        for x in re.findall(
            r"total retail sales of consumer goods(?:\s+reached)?[^%]{0,220}?"
            r"(?:up by|increased by|grew by)\s*([0-9]+(?:\.[0-9]+)?)%\s*year on year",
            text,
            flags=re.I,
        )
    ]
    if spec.expected_value not in matches:
        failures.append(f"current_value_not_found_or_mismatch:candidates={matches[:8]}")
        value = None
    else:
        value = spec.expected_value

    prior = spec.expected_prior
    return value, prior


def build_receipt(spec: ReleaseSpec) -> dict:
    raw = fetch(spec.url)
    text = html_to_text(raw)
    failures: list[str] = []

    if spec.expected_title not in text:
        failures.append("title_mismatch")
    if spec.expected_release_timestamp not in text:
        failures.append("release_timestamp_mismatch")

    if spec.lane == "activity":
        value, prior = parse_activity(text, spec, failures)
    else:
        value, prior = parse_demand(text, spec, failures)

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


def direction(receipt: dict) -> str:
    value = receipt.get("value")
    prior = receipt.get("prior_value")
    if not receipt.get("strict_checks_green") or value is None or prior is None:
        return "WITHHELD"
    if value > prior:
        return "IMPROVING"
    if value < prior:
        return "WEAKENING"
    return "STABLE"


def evaluate() -> dict:
    receipts = {spec.lane: build_receipt(spec) for spec in SPECS}
    failures = [f"{lane}:{failure}" for lane, receipt in receipts.items() for failure in receipt["failures"]]
    activity_direction = direction(receipts["activity"])
    demand_direction = direction(receipts["demand"])
    if "WITHHELD" in (activity_direction, demand_direction):
        combined = "WITHHELD"
    elif activity_direction == demand_direction:
        combined = activity_direction
    else:
        combined = "MIXED"

    return {
        "schema": "GMFQ_CHINA_NBS_DUAL_PIT_PROBE_V1",
        "status": "CANDIDATE_RECEIPTS_READY" if not failures else "FAIL",
        "validator_green": not failures,
        "receipts": receipts,
        "direction_snapshot": {
            "activity": activity_direction,
            "demand": demand_direction,
            "combined": combined,
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
