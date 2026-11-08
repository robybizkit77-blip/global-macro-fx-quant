#!/usr/bin/env python3
"""Daily AUD 2Y/10Y F2 source history, V2 research only (never Core/OIS/signals).

RBA F2 is a weekly CSV RELEASE of individually dated DAILY observations.
Never reinterpret its weekly publication date as the market observation date.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path

from refresh_fxv2_aud_rba_f2_context import (
    CANONICAL, SERIES_2Y, SERIES_10Y, URL, demand, fetch, parse_f2
)

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "site/fx-quant-v2/aud-rba-f2-history-research.json"
SOURCE_SNAPSHOT = ROOT / "site/fx-quant-v2/aud-rba-f2-research.json"
SCHEMA = "GMFQ_AUD_RBA_F2_DAILY_HISTORY_RESEARCH_V1"


def parse_daily(raw: bytes, today: dt.date) -> dict:
    """Reuse official F2 header/units checks and independently preserve every day."""
    latest = parse_f2(raw, today)
    table = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    ids = table[10]
    two, ten = ids.index(SERIES_2Y), ids.index(SERIES_10Y)
    obs = []
    for row in table[11:]:
        if len(row) <= max(two, ten):
            continue
        if not all((row[0].strip(), row[two].strip(), row[ten].strip())):
            continue
        try:
            day = dt.datetime.strptime(row[0].strip(), "%d-%b-%Y").date()
            y2, y10 = float(row[two]), float(row[ten])
        except ValueError:
            continue
        demand(all(math.isfinite(x) and -5 < x < 25 for x in (y2, y10)),
               "implausible daily RBA government 2Y/10Y")
        demand(day <= dt.date.fromisoformat(latest["publication_date"])
               and day <= today, "future daily observation")
        obs.append({"date": day.isoformat(), "2Y": y2, "10Y": y10})
    obs.sort(key=lambda x: x["date"])
    demand(len(obs) >= 30, "minimum 30 source-dated daily observations")
    demand(len({r["date"] for r in obs}) == len(obs), "duplicate source date")
    demand(obs[-1]["date"] == latest["as_of"]
           and abs(obs[-1]["2Y"] - latest["2Y"]) < 1e-10
           and abs(obs[-1]["10Y"] - latest["10Y"]) < 1e-10,
           "daily history does not reconcile to published latest snapshot")
    return {
        "schema": SCHEMA,
        "status": "OFFICIAL_F2_DAILY_RESEARCH_ONLY_NOT_POINT_IN_TIME",
        "source": "Reserve Bank of Australia F2, daily government bond assessments",
        "source_url": URL,
        "series_2Y": SERIES_2Y,
        "series_10Y": SERIES_10Y,
        "publication_date": latest["publication_date"],
        "last_observation_date": latest["as_of"],
        "source_response_sha256": hashlib.sha256(raw).hexdigest(),
        "observations": obs[-150:],
        "research_only": True,
        "source_latest_vintage_not_first_release_pit": True,
        "no_interpolation": True,
        "same_date_same_source": True,
        "data_cadence": "DAILY_OBSERVATIONS_PUBLISHED_WEEKLY",
        "eligible_for_core": False,
        "eligible_for_fx_pair_engine": False,
        "eligible_for_backtests": False,
        "eligible_for_automatic_promotion": False,
        "canonical_government_rates_untouched": True,
        "note": "Official RBA F2 yields are research-grade assessments, not financial benchmarks. No OIS or live execution price; official release is weekly."
    }


def validate_and_merge(candidate: dict, canonical: dict, source_snapshot: dict,
                       previous: dict | None, today: dt.date) -> dict:
    demand(candidate.get("schema") == SCHEMA and candidate.get("research_only") is True,
           "unapproved research schema")
    end = candidate["last_observation_date"]
    demand(end == source_snapshot["as_of"]
           and candidate["publication_date"] == source_snapshot["publication_date"],
           "history latest observation/release must match independently stored F2 snapshot")
    demand(abs(candidate["observations"][-1]["2Y"] - source_snapshot["2Y"]) < 1e-8
           and abs(candidate["observations"][-1]["10Y"] - source_snapshot["10Y"]) < 1e-8,
           "latest F2 2Y/10Y does not match research snapshot")
    demand(end >= canonical["AUD"]["date"], "RBA source older than current canonical observation")
    demand((today - dt.date.fromisoformat(end)).days <= 14,
           "official F2 observation is stale for weekly release")
    if previous and previous.get("status") != "AWAITING_OFFICIAL_F2_DAILY_HISTORY":
        demand(previous.get("schema") == SCHEMA and previous.get("research_only") is True
               and previous.get("eligible_for_core") is False
               and previous.get("eligible_for_fx_pair_engine") is False,
               "previous historical release was not isolated research")
        old = {x["date"]: x for x in previous.get("observations", [])}
        fresh = {x["date"]: x for x in candidate["observations"]}
        demand(not old or any(d in fresh for d in old), "source history has no shared dates")
        for d, row in old.items():
            if d in fresh:
                demand(row == fresh[d],
                       "RBA revised prior official observation: quarantine for independent review")
        demand(end >= previous["last_observation_date"], "official daily history rollback")
        if end == previous["last_observation_date"]:
            demand(candidate["source_response_sha256"] == previous["source_response_sha256"],
                   "RBA source changed without a newer observation: review needed")
    return candidate


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", type=dt.date.fromisoformat,
                   default=dt.datetime.now(dt.timezone.utc).date())
    p.add_argument("--input", type=Path, help="offline test CSV only")
    p.add_argument("--output", type=Path, default=TARGET)
    args = p.parse_args()
    raw = args.input.read_bytes() if args.input else fetch()
    candidate = parse_daily(raw, args.as_of)
    canon = json.loads(CANONICAL.read_text("utf-8"))
    snapshot = json.loads(SOURCE_SNAPSHOT.read_text("utf-8"))
    previous = json.loads(args.output.read_text("utf-8")) if args.output.exists() else None
    result = validate_and_merge(candidate, canon, snapshot, previous, args.as_of)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if not args.output.exists() or args.output.read_text("utf-8") != text:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, "utf-8")
    print("AUD_F2_DAILY_RESEARCH_PASS", json.dumps({
        "last_date": result["last_observation_date"],
        "publication_date": result["publication_date"],
        "observations": len(result["observations"]), "core_written": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
