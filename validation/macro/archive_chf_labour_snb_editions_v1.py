#!/usr/bin/env python3
"""Archive newly observed SNB CHF labour editions for prospective macro research."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from validation.macro.capture_chf_labour_snb_vintage_v1 import (
    fetch_source, parse_source, record_capture,
)

UPDATE_URL = "https://data.snb.ch/api/cube/amarbma/lastUpdate"
ARCHIVE = Path("research/chf-labour-snb-vintages")
EDITION_FIELDS = ("editionDate", "publicSinceDate")
SCHEMA = "GMFQ_CHF_LABOUR_SNB_OBSERVED_EDITION_V1"
MONTHS = 25


def edition_metadata(payload):
    if not isinstance(payload, dict):
        raise ValueError("Unexpected SNB edition metadata")
    edition = {key: payload.get(key) for key in EDITION_FIELDS}
    for value in edition.values():
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{8}_[0-9]{4}", value):
            raise ValueError("Invalid SNB edition clock")
        datetime.strptime(value, "%Y%m%d_%H%M")
    return edition


def fetch_edition():
    request = Request(UPDATE_URL, headers={
        "Accept": "application/json", "User-Agent": "global-macro-fx-quant-pit-research/1.0",
    })
    with urlopen(request, timeout=25) as response:
        if response.status != 200 or response.geturl() != UPDATE_URL:
            raise ValueError("Unexpected SNB edition response")
        return json.loads(response.read(16 * 1024))


def archive_edition(directory, *, read_metadata=fetch_edition, read_source=fetch_source):
    edition = edition_metadata(read_metadata())
    name = "--".join(edition.values()) + ".json"
    path = directory / name
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("schema") != SCHEMA or existing.get("snb_metadata_as_reported") != edition:
            raise ValueError("Invalid existing CHF labour edition")
        return "ALREADY_ARCHIVED", path

    raw, headers, started, ended, response_url = read_source()
    capture = record_capture(raw, headers, started, ended, response_url)
    if edition_metadata(read_metadata()) != edition:
        raise ValueError("SNB published a different edition during retrieval; retry on the new edition")

    # All values belong to this edition. They become eligible for a replay
    # from this capture instant, not from the dates of their reference months.
    window = parse_source(raw)["observations"][-MONTHS:]
    receipt = {
        "schema": SCHEMA,
        "snb_metadata_as_reported": edition,
        "available_to_research_from_utc": capture["retrieval_completed_utc"],
        "observations_in_this_edition": window,
        "source_capture": capture,
    }
    directory.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        output.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return "RECORDED", path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-dir", type=Path, default=ARCHIVE)
    args = parser.parse_args()
    status, path = archive_edition(args.archive_dir)
    print(f"CHF_LABOUR_SNB_EDITION {status} {path}")


if __name__ == "__main__":
    main()
