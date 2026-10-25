#!/usr/bin/env python3
"""Offline, fail-closed source and event-clock audit for Event → Market research.

This code checks a manually inspected evidence registry; it NEVER establishes
licensing rights, first-market dissemination time, or observed intraday prices.
No network, trades, reports, published feeds or model scores are affected.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

SCHEMA = "GMFQ_EVENT_MARKET_EVIDENCE_REGISTRY_V1"
REQUIRED = frozenset({
    "DUKASCOPY_BI5_EURUSD", "CME_DATAMINE_SR3_TNS",
    "CME_BROKERTEC_UST2Y", "CME_EBS_SPOTFX",
})
AUTHORIZED_DOMAINS = frozenset({
    "www.dukascopy.com", "datamine.new.cmegroup.com",
    "cmegroupclientsite.atlassian.net", "www.cmegroup.com",
})
BLS_URL = "https://www.bls.gov/news.release/archives/empsit_10022026.htm"
CLOCK = datetime(2026, 10, 2, 12, 30, tzinfo=timezone.utc)
BASE = Path(__file__).resolve().parents[1]
REGISTRY = BASE / "validation/event_market_evidence_registry_v1.json"


def _valid_url(url, hosts):
    if not isinstance(url, str):
        return False
    p = urlparse(url)
    return (p.scheme == "https" and p.hostname in hosts and not p.username
            and not p.password and p.port in (None, 443) and not p.fragment)


def _scheduled_in_utc(e):
    if e.get("official_archived_release_url") != BLS_URL:
        raise ValueError("not the audited BLS archived release")
    if e.get("official_release_id") != "USDL-26-1549":
        raise ValueError("release accession not verified")
    if e.get("timezone") != "America/New_York":
        raise ValueError("publisher event timezone must be explicit")
    if e.get("embargo_calendar_date") != "2026-10-02" or e.get("embargo_wall_clock") != "08:30:00":
        raise ValueError("embargo clock inconsistent with archived publisher release")
    if e.get("timing_evidence") != "PUBLISHER_ARCHIVED_EMBARGO_LABEL_NOT_DELIVERY_RECEIPT":
        raise ValueError("embargo cannot be represented as actual delivery")
    local = datetime.fromisoformat(e["embargo_calendar_date"] + "T" + e["embargo_wall_clock"])
    ny = local.replace(tzinfo=ZoneInfo("America/New_York"))
    if ny.astimezone(timezone.utc).astimezone(ny.tzinfo).replace(tzinfo=None) != local:
        raise ValueError("nonexistent/ambiguous local publisher clock")
    scheduled = ny.astimezone(timezone.utc)
    if scheduled != CLOCK or e.get("expected_scheduled_utc") != "2026-10-02T12:30:00Z":
        raise ValueError("scheduled UTC does not match official publisher clock")
    # The official embargo/schedule does not independently timestamp dissemination.
    if (e.get("independently_verified_first_public_delivery_utc") is not None
            or e.get("first_public_delivery_receipt") is not None):
        raise ValueError("uncertified delivery evidence must not be promoted")
    return scheduled


def audit(registry):
    if not isinstance(registry, dict) or registry.get("schema") != SCHEMA:
        raise ValueError("unknown evidence registry schema")
    if registry.get("scope") != "RESEARCH_ONLY_NOT_PRODUCTION_ENTITLEMENT_OR_CAUSAL_PROOF":
        raise ValueError("registry scope would promote unverified data")
    event = registry.get("event")
    if not isinstance(event, dict):
        raise ValueError("missing event")
    scheduled = _scheduled_in_utc(event)
    sources = registry.get("providers")
    if not isinstance(sources, list):
        raise ValueError("missing market source inventory")
    ids = [x.get("id") if isinstance(x, dict) else None for x in sources]
    if len(ids) != len(REQUIRED) or len(set(ids)) != len(ids) or set(ids) != REQUIRED:
        raise ValueError("missing, duplicate, or unauthorized market source")
    for source in sources:
        if not _valid_url(source.get("source_url"), AUTHORIZED_DOMAINS):
            raise ValueError("unapproved market-data catalogue source URL")
        if source.get("acquisition_state") not in {
            "TRANSPORT_PROBED_RESEARCH_ONLY", "CATALOG_ONLY_NOT_ACQUIRED"
        }:
            raise ValueError("unverified source acquisition promotion")
        for status_field in ("commercial_use_rights", "publication_rights"):
            if source.get(status_field) != "NOT_ESTABLISHED":
                raise ValueError("entitlement cannot be asserted via unverified registry")
        if source.get("raw_ticks_authorized_retained") is not False:
            raise ValueError("unverified source bytes cannot be marked approved")
        if source.get("cross_event_quote_receipt_independently_verified") is not False:
            raise ValueError("independent event-window receipt has not been audited")
    lookup = {source["id"]: source for source in sources}
    if lookup["DUKASCOPY_BI5_EURUSD"]["acquisition_state"] != "TRANSPORT_PROBED_RESEARCH_ONLY":
        raise ValueError("incorrect probe history")
    if any(lookup[s]["acquisition_state"] != "CATALOG_ONLY_NOT_ACQUIRED"
           for s in REQUIRED - {"DUKASCOPY_BI5_EURUSD"}):
        raise ValueError("catalogue is not evidence of actual market-data delivery")
    return {
        "schema": "GMFQ_EVENT_MARKET_SOURCE_READINESS_RECEIPT_V1",
        "state": "BLOCKED_NOT_CERTIFIED",
        "event": event["event_id"],
        "scheduled_embargo_utc": scheduled.isoformat().replace("+00:00", "Z"),
        "scheduled_embargo_source": BLS_URL,
        "scheduled_embargo_verified_against_official_archive": True,
        "actual_first_public_delivery_verified": False,
        "publisher_wall_clock_is_actual_delivery_proof": False,
        "fx_source_transport_previously_probed": True,
        "fx_source_usage_rights_verified": False,
        "fx_price_window_independently_rehashed": False,
        "short_rate_futures_intraday_acquired": False,
        "sofr_futures_is_not_direct_ois": True,
        "treasury_2y_intraday_acquired": False,
        "benchmark_security_and_yield_conversion_certified": False,
        "simultaneous_competing_headline_audit_done": False,
        "research_only": True,
        "causal_attribution": "NOT_ESTABLISHED",
        "market_reaction": "NOT_CERTIFIED",
        "eligible_for_live_data": False,
        "eligible_for_score": False,
        "eligible_for_backtest": False,
        "safe_to_update_pair_theses": False,
        "blocked_by": [
            "NO_INDEPENDENT_ACTUAL_PUBLIC_DELIVERY_TIMESTAMP",
            "NO_ATTESTED_MARKET_DATA_LICENSE_OR_PUBLIC_DISTRIBUTION_RIGHTS",
            "NO_AUTHORIZED_INDEPENDENTLY_REHASHED_FX_EVENT_WINDOW",
            "NO_TIMESTAMPED_MATCHED_CONTRACT_SHORT_RATE_FUTURES_WINDOW",
            "NO_TIMESTAMPED_COMPARABLE_2Y_TREASURY_WINDOW",
            "NO_COMPETING_EVENT_AND_EXPECTED_REACTION_AUDIT",
        ],
        "market_source_count": len(sources),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.out and not args.out.resolve().is_relative_to(Path("/tmp")):
        ap.error("research receipt output must remain under /tmp")
    result = audit(json.loads(args.registry.read_text(encoding="utf-8")))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
