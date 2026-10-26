# Forward Test: prospective frozen-Core observations (26 October 2026)

**Purpose:** begin genuine prospective recordings on future market sessions, not reconstruct past decisions, and do not claim the Core recomputed a new Macro signal.

## Why the distinction matters
- `live_data/sections/D.json` is frozen at **2026-09-25**. Its 28 pair states may be observed going forward as a fixed baseline; they are **not** new recalculated model decisions.
- The earlier 28 `2026-10-14T21:01:45Z` snapshots are immutable smoke-test records, missing the `inputs` key specified by `CORE_FORWARD_DECISION_LOGGER_V1_SCHEMA.json`. Never overwrite or rehash them.
- New capture rows use `schema_version=GMFQ_CORE_FORWARD_DECISION_LOGGER_V1.1.0`, `capture_class=FROZEN_CORE_BASELINE_OBSERVATION`, `core_baseline_as_of=2026-09-25`, `core_recomputed_at_capture=false`, `current_macro_score_certified=false`, a separate `inputs` object and the unchanged legacy detail keys.
- Macro release/availability timestamps are not independently certified: the raw Macro thermometer observation **must remain WITHHELD in the new forward capture input contract**, rather than being dated with `D.json.asOf`.
- Rates, OIS, COT and price retain conservative observation-day availability heuristics or WITHHELD. No invented same-day release timestamps or assumed license.

## Admission and cadence
An *independent*, explicitly scheduled GitHub Actions workflow at **19:30 Rome weekdays** (both CET/CEST crons with a local DST gate) attempts prospective evidence capture only if all are true:
1. Active actual Rome weekday and at/after 19:00; no fake historical cutoff. Direct non-dry-run CLI also checks the decision cutoff is within 120 seconds of real UTC time.
2. Current-day **official ECB reference rate history** has `last_as_of == Rome today`. If unpublished due holiday/lag, record `BLOCKED_NO_CAPTURE`, not a fabricated return.
3. All **28 pair** current operational setup prices have `price_asof == Rome today`, with the 28 canonical Core structures present and a historical Core baseline date.
4. Every new snapshot has all v1 contract fields, canonical source sha digests, and a daily unique observational intent; runs twice on the same date cannot append 56 false decisions. A preexisting partial daily batch causes a hard failure.
5. Only `validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl` and the immutable receipt path may change. `git push` must be fast-forward; no force push, no rebasing a prior-time decision over later source updates.
6. A PR runs offline QA only; never writes any snapshot or creates an outcome. No site or model recalculation or live trade.

A scheduled run can be **blocked** by unavailable official feeds or delayed Cron. This is intentional and must not count as successful forward market observation. GitHub schedule does not guarantee execution at a precise time. A cancelled/late admission is **not backfilled** later.

## Oct 26 audit hardening before any first genuine 19:30 capture

The V1.1 future capture logger now validates the exact complete 28-unordered-G8-pair batch atomically before writing it. Checks the canonical V1 contract required fields, the frozen Sept 25 model provenance and no-PIT-promotion fields, deterministic snapshot identity and SHA256, layer-to-publisher digest parity, all nine input states, timestamp `available_at` strictly no later than the frozen decision cutoff, explicit `WITHHELD` null values, independent conservative daily ECB reference T0, and absence of future-return labels. Bad/partial/tampered batches fail without touching the append-only file; no source replay or corrections of old observations are authorized.

The 28 Oct 14 `V1.0.0` test snapshots are preserved byte-for-byte. V1.1 checks apply to genuine prospective additions only. A GREEN offline test does **not** certify that the 19:30 GitHub cron ran or that the official current-day ECB 28-pair price source existed at capture. Real capture remains subject to its separate admission gate and future observed outcomes.

## What remains unproven
- Price and instrument-specific later outcomes/costs are not attached, do not exist yet, and must be source and PIT audited.
- A frozen-core baseline observation does not constitute independent updated Macro score and cannot be presented as an active trade entry.
- The earlier historical pseudo-walkforward cannot replace forward observations.
- The 52W beta remains research-only pending canonical B1/B2 rules, real PIT 2Y panel and OOS hedge variance reduction.
- Control Room active Preview is not modified. Legacy Forward UI CI is not a QA certificate for active Preview.

After the first genuine scheduled capture appears on `main`, verify its job run, receipt, immutable snapshot hash and source provenance. Then design a separately auditable official-ECB future-fixing and realized-cost outcome observer; do not calculate fictitious P&L.
