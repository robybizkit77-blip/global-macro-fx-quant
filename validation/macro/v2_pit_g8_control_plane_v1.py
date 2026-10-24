#!/usr/bin/env python3
"""G8 Macro V2 shared PIT evidence control plane: 24 slots, read-only.

Ingest independently pinned Eurostat/ABS/BLS/ONS research evidence using the
SAME schema, while retaining the canonical 16 registry source identities and
eight unselected Growth slots. Never upgrade a candidate to a production
source just because it has numerous official-web first releases.

There is NO downloader or auto-scheduler here; it is a unified, testable
audit/replay interface on verified source dossiers. Release-day immutable
bytes, source-to-canonical identity, complete historical revisions, exact
publisher time and independent model approval remain separate future gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from validation.macro.v2_shadow_features_v1 import ROOT, FX, PILLARS, period_index, period_start, require, timestamp
from validation.macro.v2_pit_coverage_readiness_v1 import run as readiness_run
from validation.macro.v2_pit_g8_evidence_adapters_v1 import collect, PROVENANCE

SCHEMA = "GMFQ_MACRO_V2_G8_SHARED_PIT_CONTROL_PLANE_V1"
CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
PILLAR_ORDER = ("growth", "labour", "inflation")
PUBLISHER_HOSTS = {
    "Eurostat": {"ec.europa.eu"},
    "Australian Bureau of Statistics": {"www.abs.gov.au"},
    "U.S. Bureau of Labor Statistics": {"www.bls.gov"},
    "UK Office for National Statistics": {"www.ons.gov.uk"},
    "Statistics Canada": {"www150.statcan.gc.ca"},
    "Statistics Bureau of Japan": {"www.stat.go.jp"},
    "Stats NZ": {"www.stats.govt.nz"},
    "Swiss Federal Statistical Office": {"dam-api.bfs.admin.ch"},
    "Swiss State Secretariat for Economic Affairs": {"www.seco.admin.ch"},
    "Federal Reserve Board": {"www.federalreserve.gov"},
    "Ministry of Economy, Trade and Industry Japan": {"www.meti.go.jp"},
}
SOURCE_KINDS = {"FIRST_WEB", "DETAILED_WEB", "REVISION_WEB"}
RESEARCH_REVIEW_ASOF = date(2026, 10, 24)


def numeric(x):
    return type(x) in (int, float) and math.isfinite(x)


def normalize(source):
    """Validate one independently attested source stream, no promotion.

    Adding a new country/metric requires an adapter/manifest with actual
    publisher facts and then this same validation. No scoring special cases.
    """
    require(isinstance(source, dict), "source event stream must be a dict")
    ccy, pillar, sid, freq = (source.get("currency"), source.get("pillar"),
                              source.get("source_series_id"), source.get("frequency"))
    require(ccy in FX and pillar in PILLARS and freq in ("M", "Q"),
            "candidate G8 pillar and monthly/quarterly frequency required")
    require(isinstance(sid, str) and bool(sid.strip())
            and isinstance(source.get("metric_unit"), str)
            and bool(source["metric_unit"].strip())
            and isinstance(source.get("period_semantics"), str)
            and bool(source["period_semantics"].strip()),
            "exact series, metric unit and reference-period interpretation needed")
    require(source.get("provenance") == PROVENANCE
            and source.get("original_release_day_immutable_bytes_verified") is False
            and source.get("complete_revision_history_verified") is False
            and source.get("canonical_series_mapping_independently_certified") is False,
            "source web evidence cannot silently become independently certified")
    publisher = source.get("publisher")
    require(publisher in PUBLISHER_HOSTS
            and isinstance(source.get("evidence_contract"), str)
            and bool(source["evidence_contract"].strip())
            and isinstance(source.get("limitations"), list)
            and len(source["limitations"]) > 0,
            "attested publisher and explicit evidence limitations required")
    events = source.get("events")
    require(isinstance(events, list) and len(events) > 0,
            "nonempty source event evidence required")
    first = {}
    group = defaultdict(list)
    prepared = []
    seen = set()
    for e in events:
        require(isinstance(e, dict) and e.get("kind") in SOURCE_KINDS,
                "only official first/revised web rate events in standardized metric replay")
        period = e.get("observation_period")
        idx = period_index(period, freq)
        when = timestamp(e.get("visible_from_utc"))
        require(when.date() >= period_start(period, freq),
                "reported publication before observation period")
        require(numeric(e.get("reported_value")), "finite metric value required")
        url = e.get("source_url")
        require(isinstance(url, str), "documented official publisher URL required")
        parsed = urlsplit(url)
        require(parsed.scheme == "https"
                and parsed.hostname in PUBLISHER_HOSTS[publisher]
                and parsed.path and not parsed.username
                and not parsed.password and not parsed.fragment,
                "URL must be publisher-specific official HTTPS source")
        marker = (period, e["kind"])
        require(marker not in seen, "duplicated source period/publication kind")
        seen.add(marker)
        group[period].append((when, e))
        if e["kind"] == "FIRST_WEB":
            require(period not in first, "two first-web releases for same reference period")
            first[period] = when
        prepared.append({
            "reference_period": period, "reference_period_index": idx,
            "stage": e["kind"], "visible_from_utc": when.isoformat(),
            "reported_value": e["reported_value"], "source_url": url,
        })
    require(len(first) > 0 and len(first) == len(group),
            "every source period must have exactly one initial publisher record")
    for period, records in group.items():
        ordered = sorted(records, key=lambda x: x[0])
        require(ordered[0][1]["kind"] == "FIRST_WEB",
                "detailed value arrived before first documented publication")
        require(all(ordered[i][0] < ordered[i+1][0]
                    for i in range(len(ordered)-1)),
                "duplicate or nonincreasing same-period publication clock")
    order = sorted(first, key=lambda x: period_index(x, freq))
    require(len({period_index(x, freq) for x in order}) == len(order),
            "duplicate economic period after normalization")
    # IMPORTANT: do NOT reject genuine discontinuities (e.g. BLS shutdown).
    # Count them explicitly so they cannot accidentally enter a 25-month window.
    gaps = sum(period_index(b, freq)-period_index(a, freq)-1
               for a,b in zip(order,order[1:]))
    require(gaps >= 0, "initial release periods out of order")
    return {
        **{k: source[k] for k in (
            "currency", "pillar", "source_series_id", "frequency",
            "metric_unit", "publisher", "period_semantics", "provenance",
            "evidence_contract", "limitations")},
        "first_reference_months_total": len(first),
        "missing_reference_periods_inside_candidate_range": gaps,
        "candidate_history_periods_contiguous": gaps == 0,
        "all_documented_publication_events": sorted(
            prepared, key=lambda x: (timestamp(x["visible_from_utc"]),
                                     x["reference_period"], x["stage"])),
        "original_release_day_immutable_bytes_verified": False,
        "complete_revision_history_verified": False,
        "canonical_series_mapping_independently_certified": False,
    }


def build(readiness, sources, *, as_of):
    cutoff = timestamp(as_of)
    require(isinstance(readiness, dict) and readiness.get("schema") ==
            "GMFQ_MACRO_V2_G8_PIT_COVERAGE_READINESS_V1",
            "G8 canonical source registry readiness input required")
    require(readiness.get("scores_computed") is False
            and readiness.get("safe_to_publish_new_D") is False
            and readiness.get("safe_to_update_pair_theses") is False
            and readiness.get("writes_live_data") is False,
            "input source-readiness evidence cannot be promoted")
    require(readiness["summary"]["observed_pillar_slots"] == 24
            and readiness["summary"]["registered_core_series"] == 16
            and readiness["summary"]["certified_full_first_release_histories"] == 0,
            "underlying observed G8/readiness inventory unexpectedly changed")
    inventory = readiness["rows"]
    require(isinstance(inventory, list) and len(inventory) == 24,
            "all 24 currency/pillar registry slots required")
    expected = {(c,p) for c in CURRENCIES for p in PILLAR_ORDER}
    index = {(x["currency"], x["pillar"]): x for x in inventory}
    require(set(index) == expected and len(index) == len(inventory),
            "missing, duplicate or unknown G8 source slots")
    require(isinstance(sources, list), "candidate source streams must be an array")
    coverage = {}
    for raw in sources:
        audited = normalize(raw)
        slot_key = (audited["currency"], audited["pillar"])
        require(slot_key in expected and slot_key not in coverage,
                "duplicate or foreign source candidate assigned to G8 pillar")
        coverage[slot_key] = audited
    rows = []
    for currency in CURRENCIES:
        for pillar in PILLAR_ORDER:
            core = index[(currency, pillar)]
            candidate = coverage.get((currency, pillar))
            registry_id = core["source_id"]
            registry_freq = core["frequency"]
            events = candidate["all_documented_publication_events"] if candidate else []
            visible = [e for e in events
                       if timestamp(e["visible_from_utc"]) <= cutoff]
            first = [e for e in visible if e["stage"] == "FIRST_WEB"]
            detail = [e for e in visible if e["stage"] == "DETAILED_WEB"]
            historical_revision = [e for e in visible if e["stage"] == "REVISION_WEB"]
            latest = max(first, key=lambda e: e["reference_period_index"]) if first else None
            # A publisher stage may be later than the first event for the same
            # reference period. Select last visible per metric/period without
            # retroactively revising any older as-of timestamp.
            revised = next((
                e for e in reversed(visible) if latest is not None
                and e["reference_period"] == latest["reference_period"]
            ), None)
            series_exact = bool(candidate and candidate["source_series_id"] == registry_id
                                and registry_id is not None)
            frequency_exact = bool(candidate and candidate["frequency"] == registry_freq
                                   and registry_freq is not None)
            certified_source_mapping = bool(candidate and
                                             candidate["canonical_series_mapping_independently_certified"])
            require(not certified_source_mapping,
                    "unreviewed research data cannot be certified as canonical")
            # Continuous release count is descriptive only; no score promotion.
            missing = (candidate["missing_reference_periods_inside_candidate_range"]
                       if candidate else None)
            target = core["training_first_release_minimum"]
            first_count = len(first)
            same_series_frequency = series_exact and frequency_exact
            status = (
                "NO_ATTESTED_HISTORICAL_FIRST_RELEASE_STREAM" if not candidate else
                "SOURCE_EVENT_NOT_YET_VISIBLE_AT_CUTOFF" if first_count == 0 else
                "CANDIDATE_PERIOD_OR_FREQUENCY_MISMATCH_REVIEW" if not same_series_frequency else
                "MATCHING_SERIES_ID_BUT_PERIOD_OR_SOURCE_VINTAGE_REVIEW" if not certified_source_mapping else
                "CANDIDATE_FIRST_RELEASES_UNCERTIFIED"
            )
            rows.append({
                "currency": currency, "pillar": pillar,
                "canonical_series_id": registry_id,
                "canonical_frequency": registry_freq,
                "candidate_evidence_source_id": candidate["source_series_id"] if candidate else None,
                "candidate_frequency": candidate["frequency"] if candidate else None,
                "candidate_metric_unit": candidate["metric_unit"] if candidate else None,
                "candidate_period_semantics": candidate["period_semantics"] if candidate else None,
                "candidate_source_publisher": candidate["publisher"] if candidate else None,
                "candidate_source_contract": candidate["evidence_contract"] if candidate else None,
                "canonical_series_id_matches_candidate": series_exact,
                "canonical_frequency_matches_candidate": frequency_exact,
                "candidate_series_periods_in_full_dossier":
                    candidate["first_reference_months_total"] if candidate else 0,
                "candidate_stage_events_in_full_dossier": len(events),
                "candidate_documented_first_periods_visible": first_count,
                "candidate_detailed_events_visible": len(detail),
                "candidate_revision_events_visible": len(historical_revision),
                "candidate_revised_reference_periods_visible":
                    len({e["reference_period"] for e in historical_revision}),
                "candidate_reference_range_gaps_in_dossier": missing,
                "candidate_first_periods_are_contiguous_in_dossier":
                    candidate["candidate_history_periods_contiguous"] if candidate else None,
                "latest_candidate_period_visible": latest["reference_period"] if latest else None,
                "latest_candidate_initial_web_value": latest["reported_value"] if latest else None,
                "latest_candidate_visible_stage": revised["stage"] if revised else None,
                "latest_candidate_value_at_cutoff": revised["reported_value"] if revised else None,
                "latest_candidate_publisher_gate_utc": revised["visible_from_utc"] if revised else None,
                "minimum_training_first_releases_per_canonical_frequency": target,
                # Not meaningful to subtract a monthly candidate from a
                # quarterly registry's requirement, or a Growth unselected series.
                "missing_canonical_training_periods_unconditionally": None,
                "has_enough_candidate_web_periods_for_target":
                    (first_count >= target if target is not None and
                     same_series_frequency else None),
                "source_status": status,
                "evidence_limitations": candidate["limitations"] if candidate else [
                    "Historical published first-release source not onboarded in shared G8 adapter",
                    "Observed historical values in source registry do not equal vintage archive",
                ],
                "original_release_day_immutable_bytes_verified": False,
                "canonical_first_release_chain_certified": False,
                "complete_revision_history_certified": False,
                "release_event_is_current_live_feed": False,
                "eligible_for_macro_score": False,
                "eligible_for_backtest": False,
                "safe_to_publish_new_D": False,
                "safe_to_update_pair_theses": False,
            })
    with_candidates = sum(r["candidate_evidence_source_id"] is not None for r in rows)
    summary = {
        "currencies": 8, "pillar_slots": 24,
        "core_registry_slots": 16, "growth_source_selection_unresolved": 8,
        "candidate_source_streams_loaded": with_candidates,
        "slots_without_shared_candidate_stream": 24-with_candidates,
        "candidate_first_release_reference_periods_visible": sum(
            r["candidate_documented_first_periods_visible"] for r in rows),
        "candidate_web_publication_stage_events_visible": sum(
            r["candidate_documented_first_periods_visible"]+
            r["candidate_detailed_events_visible"]+
            r["candidate_revision_events_visible"] for r in rows),
        "slots_with_full_canonical_first_release_pit_training_certified": 0,
        "slots_eligible_for_new_live_scores": 0,
    }
    require(summary["candidate_source_streams_loaded"] <= 24,
            "candidate source stream cardinality invalid")
    digest = hashlib.sha256(json.dumps({
        "as_of": cutoff.isoformat(), "source_inputs": sources,
        "readiness_as_of": readiness["as_of"]
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema": SCHEMA,
        "status": "G8_24_SLOT_SOURCE_CONTROL_PLANE_READ_ONLY_NOT_PIT_CERTIFIED",
        "as_of_utc": cutoff.isoformat(),
        "canonical_inventory_review_snapshot_date": readiness["as_of"],
        "inventory_snapshot_is_not_historical_asof_reconstruction": True,
        "candidate_source_events_obey_asof_cutoff": True,
        "all_publisher_evidence_is_past_web_attestation_not_original_day_archives": True,
        "candidate_first_event_count_is_not_model_training_certification": True,
        "rows": rows, "summary": summary,
        "next_onboarding_priority": [
            "Canonical series exact identity, measurement units and period semantics",
            "Original historical first release source artifacts and all revisions",
            "Independent GMT release timestamp or explicit conservative day-only policy",
            ">=25 monthly or >=13 quarterly source-consistent first-release records",
            "Full historical PIT score methodology approval before FX model inclusion",
        ],
        "source_review_fingerprint_sha256": digest,
        "scores_computed": False, "model_parameters_fitted": False,
        "ready_for_backtest": False, "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False, "writes_live_data": False,
    }


def run(*, as_of="2026-10-24T00:00:00Z"):
    # The 24-slot registry and latest observations were reviewed on 24 October.
    # Explicitly do NOT pass a past replay cutoff as a historic inventory date:
    # that would misrepresent today's source registry as a past PIT snapshot.
    base = readiness_run(as_of=RESEARCH_REVIEW_ASOF)
    return build(base, collect(), as_of=as_of)


def markdown(receipt):
    sm = receipt["summary"]
    lines = [
        "# Macro V2 G8 | PIT evidence control plane",
        "**Research snapshot only** · Cutoff: "+receipt["as_of_utc"],
        "",
        f"Slots: **{sm['pillar_slots']}/24**; candidate evidence streams: "
        f"**{sm['candidate_source_streams_loaded']}**; other slots awaiting "
        f"standard source adapters: **{sm['slots_without_shared_candidate_stream']}**.",
        f"Documented web first-release periods visible in these pilot streams: "
        f"**{sm['candidate_first_release_reference_periods_visible']}**; "
        f"stage events: **{sm['candidate_web_publication_stage_events_visible']}**. "
        "**These are NOT PIT-certified model training rows.**",
        "",
        "| Currency | Pillar | Canonical | Candidate | Web-first at cutoff | PIT score ready |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for r in receipt["rows"]:
        lines.append(f"| {r['currency']} | {r['pillar']} | "
                     f"{r['canonical_series_id'] or 'Not selected'} | "
                     f"{r['candidate_evidence_source_id'] or 'Not onboarded'} | "
                     f"{r['candidate_documented_first_periods_visible']} | **No** |")
    lines += [
        "", "## Non-negotiable scientific gates",
        "- Release web page count is not an independently archived original-day vintage history.",
        "- A candidate source cannot overwrite a canonical series with different frequency or identity.",
        "- The 2025/2026 Eurostat EA20/EA21/ECOICOP transition and ABS CPI regime are explicit breaks.",
        "- GBP MGSX uses three-month LFS window end, not the ONS center month.",
        "- BLS LNS14000000 web-release series is a pilot, not an authorized replacement for UNRATE.",
        "- The baseline 24-slot observed inventory is not reconstructed retroactively for older cutoffs.",
        "- No scores, backtests, FX pair rankings, site/Control Room feeds or schedules were updated.",
    ]
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--asof", default="2026-10-24T00:00:00Z")
    p.add_argument("--json-out",type=Path)
    p.add_argument("--markdown-out",type=Path)
    args=p.parse_args()
    result=run(as_of=args.asof)
    for path,content in (
        (args.json_out,json.dumps(result,indent=2,ensure_ascii=False)+"\n"),
        (args.markdown_out,markdown(result)),
    ):
        if path is not None:
            require(path.resolve().is_relative_to(Path("/tmp")),
                    "shared G8 audit receipts may only be written under /tmp")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content,encoding="utf-8")
    print(json.dumps({"schema": result["schema"],**result["summary"],
                      "safe_to_publish_new_D":False}))


if __name__=="__main__":
    main()
