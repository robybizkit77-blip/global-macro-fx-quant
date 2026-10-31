#!/usr/bin/env python3
"""Adversarial regression for immutable, conflicting secondary daily-bar quotes."""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from build_cb_pricing_estimated_v1 import build_currency
from ois_same_contract_history_v1 import (
    SOURCE, HISTORY, append_verified, candidates, load_history, record_key,
)
from reconcile_ois_secondary_conflicts_v1 import (
    STATUS, apply, read_conflicts,
)

# Use original immutable October source bars, not the moving latest-live quotes.
original = load_history(HISTORY)
anchor = next(r for r in original if (
    r["currency"], r["contract"], r["observation_date"]
) == ("USD", "ZQZ2026", "2026-10-30"))
template = json.loads(SOURCE.read_text(encoding="utf-8"))
fixture = copy.deepcopy(template)
fixture["generated_at_utc"] = "2026-10-31T12:01:00Z"
for c in ("USD", "EUR", "CHF"):
    row = fixture["currencies"][c]
    row["status"] = "LIVE_SECONDARY_READY"
    row["source_quality"] = "SECONDARY_PUBLIC_LIVE_PROXY"
    for h, days in (("3m", 90), ("6m", 180), ("12m", 365)):
        historical = [r for r in original
                      if r["currency"] == c and r["observed_under_horizon"] == h
                      and r["observation_date"] <= "2026-10-30"]
        assert historical, (c, h)
        a = max(historical, key=lambda v: (v["observation_date"], v["contract"]))
        q = row["horizons"][h]
        q.update({
            "contract": a["contract"], "symbol": a["symbol"],
            "expiration": a["expiration"], "quote_as_of": a["observation_date"],
            "futures_price": a["futures_price"], "rate": a["implied_rate"],
            "quote_timestamp_verified": True,
            "quote_timestamp_source": "SSR_DAILY_BAR_DATA_UPDATE_TIME",
            "mapping": "nearest dated listed contract expiry to today+"
                       + str(days) + "d; no interpolation",
        })

changed = fixture["currencies"]["USD"]["horizons"]["3m"]
assert changed["contract"] == "ZQZ2026"
assert changed["quote_as_of"] == "2026-10-30"
assert changed["rate"] == 4.015
changed["futures_price"] = 95.99
changed["rate"] = 4.01

with tempfile.TemporaryDirectory() as td:
    directory = Path(td)
    feed = directory / "source.json"
    archive = directory / "archive.jsonl"
    quarantine = directory / "quarantine.jsonl"
    feed.write_text(json.dumps(fixture, sort_keys=True) + "\n")
    archive.write_text(json.dumps(anchor, sort_keys=True) + "\n")
    original_bytes = archive.read_bytes()

    initial_eligible, exclusions = candidates(fixture)
    assert len(initial_eligible) == 9 and not exclusions, (initial_eligible, exclusions)

    # Stage diagnostics only, no writes.
    candidate = apply(source=feed, history=archive, quarantine=quarantine, write=False)
    assert candidate["status"] == "PARTIAL_SOURCE_CONFLICT_QUARANTINED", candidate
    assert candidate["new_quarantine_events"] == 1, candidate
    assert candidate["unaffected_eligible_contracts"] == 8, candidate
    assert not quarantine.exists()
    assert archive.read_bytes() == original_bytes
    assert json.loads(feed.read_text()) == fixture

    # Real writer: the competing quote has an immutable evidence copy; it is
    # not an official OIS/bar correction, while the 8 other contracts remain.
    receipt = apply(source=feed, history=archive, quarantine=quarantine, write=True)
    assert receipt["written"] == 1 and receipt["conflict_currencies"] == ["USD"], receipt
    assert archive.read_bytes() == original_bytes
    events = read_conflicts(quarantine)
    assert len(events) == 1
    event = events[0]
    assert event["original_immutable_quote"]["implied_rate"] == 4.015
    assert event["conflicting_source_quote"]["implied_rate"] == 4.01
    assert event["status"] == STATUS and event["resolution"] is None
    assert event["eligible_for_ois_level"] is False
    assert event["eligible_for_repricing"] is False
    assert event["eligible_for_model_or_H1"] is False

    degraded = json.loads(feed.read_text())
    bad = degraded["currencies"]["USD"]
    assert bad["status"] == "LIVE_SECONDARY_CONFLICT_QUARANTINED"
    assert bad["source_conflict_status"] == STATUS
    assert bad["horizons"]["3m"]["quote_timestamp_verified"] is False
    assert bad["horizons"]["3m"]["quote_timestamp_source"] == "QUARANTINED_SAME_CONTRACT_SAME_DAY"
    adjusted, exclusions = candidates(degraded)
    assert len(adjusted) == 8 and exclusions, (adjusted, exclusions)
    result = append_verified(degraded, archive, write=True)
    assert result["written"] == 8 and result["eligible"] == 8, result
    persisted = load_history(archive)
    assert len(persisted) == 9
    assert next(x for x in persisted if record_key(x) == record_key(anchor)) == anchor
    assert len({record_key(x) for x in persisted}) == 9

    # Indicative 3M/6M/12M prices are still visible, but provenance is
    # explicitly conflicted: no native fallback, no CB delta, no OIS repricing,
    # no historic estimated-snapshot admission despite non-null display levels.
    usd = build_currency("USD", {"rate": 3.875, "market_pricing": {
        "h3m": 4.25, "h6m": 4.32, "h12m": 4.6, "as_of": "2026-10-30"
    }}, {"status": "WITHHELD"}, bad)
    assert usd["status"] == "ESTIMATED_ACTIVE", usd
    assert usd["input_mode"] == "LIVE_SECONDARY_CONFLICT_INDICATIVE", usd
    assert usd["source_quality"] == "SECONDARY_CONFLICTED_INDICATIVE_NOT_OIS", usd
    assert usd["source_conflict_status"] == STATUS
    assert all(v["rate"] is not None and v["policy_delta_bp"] is None
               for v in usd["horizons"].values())
    assert usd["direction_vs_policy"] == "WITHHELD"
    assert usd["change_1d_bp"] is None and usd["change_1w_bp"] is None
    from ois_estimated_snapshot_v1 import append_changed_snapshots
    scratch = directory / "estimated_snapshots.jsonl"
    prohibited = append_changed_snapshots({
        "currencies": {"USD": {"operational_status": "GREEN_ESTIMATED", **usd},
                       "EUR": {"operational_status": "WITHHELD"},
                       "CHF": {"operational_status": "WITHHELD"},
                       "NZD": {"operational_status": "WITHHELD"}}
    }, "2026-10-31T12:01:00Z", scratch)
    assert prohibited["appended"] == 0 and not scratch.exists(), prohibited

    frozen_archive, frozen_quarantine = archive.read_bytes(), quarantine.read_bytes()

    # Original raw quote independently reappears; record neither a second
    # conflict event nor an overwritten first observation.
    first_print = copy.deepcopy(fixture)
    first_print["currencies"]["USD"]["horizons"]["3m"]["futures_price"] = anchor["futures_price"]
    first_print["currencies"]["USD"]["horizons"]["3m"]["rate"] = anchor["implied_rate"]
    feed.write_text(json.dumps(first_print, sort_keys=True) + "\n")
    replay = apply(source=feed, history=archive, quarantine=quarantine, write=True)
    assert replay["written"] == 0 and replay["new_quarantine_events"] == 0, replay
    # Re-fetching the very first source print is NOT proof that the
    # disagreement has been independently resolved. It stays in quarantine.
    assert replay["conflict_currencies"] == ["USD"], replay
    replay_source = json.loads(feed.read_text(encoding="utf-8"))
    replay_h = replay_source["currencies"]["USD"]["horizons"]["3m"]
    assert replay_h["quote_timestamp_verified"] is False
    assert replay_h["quote_timestamp_source"] == "QUARANTINED_SAME_CONTRACT_SAME_DAY"
    assert replay_h["rate"] == 4.015  # Original print retained, NOT promoted
    assert replay_source["currencies"]["USD"]["source_conflict_keys"][0]["event_id"] == event["event_id"]
    from reconcile_ois_secondary_conflicts_v1 import validate_conflict_lineage
    reread = validate_conflict_lineage(replay_source, load_history(archive),
                                       read_conflicts(quarantine))
    assert reread["current_quarantine_horizons_verified"] == 1

    assert archive.read_bytes() == frozen_archive
    assert quarantine.read_bytes() == frozen_quarantine
    assert len(read_conflicts(quarantine)) == 1

    # Changing the source again is a separate unreconciled print, never a
    # same-day overwrite or an automatic choice of the "final" close.
    later = copy.deepcopy(fixture)
    later["currencies"]["USD"]["horizons"]["3m"]["futures_price"] = 95.985
    later["currencies"]["USD"]["horizons"]["3m"]["rate"] = 4.015
    # Returning to the original first print is a replayed, already-known
    # disagreement. It must not create another event or clear quarantine.
    feed.write_text(json.dumps(later) + "\n")
    same = apply(source=feed, history=archive, quarantine=quarantine, write=True)
    assert same["conflict_currencies"] == ["USD"], same
    assert same["new_quarantine_events"] == 0, same
    assert quarantine.read_bytes() == frozen_quarantine

    # A forged official quote is never accepted into the history or quarantine.
    forged = copy.deepcopy(fixture)
    forged["currencies"]["USD"]["horizons"]["3m"]["rate"] = "not-a-quote"
    forged["currencies"]["USD"]["horizons"]["3m"]["futures_price"] = "not-a-price"
    feed.write_text(json.dumps(forged) + "\n")
    ignored = apply(source=feed, history=archive, quarantine=quarantine, write=True)
    assert ignored["conflict_currencies"] == [] and ignored["written"] == 0
    assert archive.read_bytes() == frozen_archive
    assert quarantine.read_bytes() == frozen_quarantine

    # Tampering with either immutable side of the evidence fails closed.
    damaged = copy.deepcopy(event)
    damaged["original_immutable_quote"]["implied_rate"] = 4.0
    quarantine.write_text(json.dumps(damaged) + "\n")
    try:
        read_conflicts(quarantine)
        raise AssertionError("tampered source-evidence record was accepted")
    except ValueError:
        pass
    # No write when quarantine history has been altered.
    feed.write_text(json.dumps(fixture) + "\n")
    try:
        apply(source=feed, history=archive, quarantine=quarantine, write=True)
        raise AssertionError("corrupted quarantine history allowed new capture")
    except ValueError:
        pass
    assert archive.read_bytes() == frozen_archive

print("OIS_SECONDARY_CONFLICT_QUARANTINE_V1_PASS: immutable first quote, "
      "later source quarantined, 8 unaffected bars, no duplicate or repricing")
