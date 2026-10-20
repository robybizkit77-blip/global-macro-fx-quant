# Macro Scoring Engine V2 — phase 1: point-in-time shadow features (2026-10-20)

## Status and scope
**RESEARCH / SHADOW ONLY; NO ECONOMIC SCORES.** The original Growth/Labour/Inflation scalar generator was not recovered. Legacy `D.json` remains fixed at 2026-09-25 under PR #454. This work is not a replacement, calibration, or replay of the 24 old scalar values. It has no route to production publishing or 28-pair selection.

This phase establishes a *pure function* `build_features(manifest)` that transforms an explicitly timestamped, versioned series into raw economic dynamics **as they were knowable at one exact cutoff time**. The live source inventory is read-only and is never automatically upgraded into these PIT manifests.

## Data reality in the current repo
- `MACRO_SERIES.json`: observed Growth series in all 8 currencies; the script counts these without claiming their first-release vintages are certified.
- `MACRO_SOURCE_REGISTRY_2026-10-08.json`: 16 registered Inflation/Labour source adapters with historical replay attestations. These attestations do **not** automatically prove that every historic month/quarter has an observation-specific, timestamped, source-backed first release and revision chain suitable for backtesting.
- The input manifest must **explicitly** supply source identity, frequency, measurement unit, each observation period, exact timezone-aware `released_at`, `kind` (`FIRST`/`REVISION`), numeric value and `evidence_ref`. Merely providing `observation_period` is insufficient.
- Transport labels are verified **structurally**, not fact-checked from an external authority in this prototype. Even `OFFICIAL_DIRECT` claims leave `source_evidence_is_independently_certified = false`. `SECONDARY_MIRROR` is rejected; `SYNTHETIC_FIXTURE` is permitted only to exercise deterministic tests.

## Contract (illustrative data only)
```json
{
  "schema": "GMFQ_MACRO_V2_PIT_FEATURE_INPUT_V1",
  "as_of": "2026-05-05T12:00:00Z",
  "currency": "USD",
  "pillar": "growth",
  "series_id": "SYNTHETIC_GROWTH_TEST",
  "frequency": "M",
  "unit": "index",
  "max_lag_periods": 1,
  "source": {
    "authority": "TEST_ONLY",
    "source_id": "TEST_V1",
    "transport": "SYNTHETIC_FIXTURE"
  },
  "vintages": [
    {"observation_period": "2026-01", "released_at": "2026-02-02T09:00:00Z", "value": 1.0, "kind": "FIRST", "evidence_ref": "FIXTURE_JAN"},
    {"observation_period": "2026-02", "released_at": "2026-03-02T09:00:00Z", "value": 2.0, "kind": "FIRST", "evidence_ref": "FIXTURE_FEB"},
    {"observation_period": "2026-03", "released_at": "2026-04-02T09:00:00Z", "value": 4.0, "kind": "FIRST", "evidence_ref": "FIXTURE_MAR"},
    {"observation_period": "2026-04", "released_at": "2026-05-02T09:00:00Z", "value": 3.0, "kind": "FIRST", "evidence_ref": "FIXTURE_APR"}
  ]
}
```

An actual source manifest must have externally verifiable authority evidence and a versioned source-specific transformation, before its output can be considered even *eligible* for a certified PIT score model.

## Feature definitions (not FX signs)
Given the latest four **contiguous observed and released** periods at as-of time:
- **Level:** latest raw measurement (`x[t]`), in source units.
- **Direction:** sign of `x[t] - x[t-1]`. Not the same as economic desirability.
- **Velocity:** `x[t] - x[t-1]`, per month **or** per quarter (not per day). One series/frequency only.
- **Acceleration:** `(x[t] - x[t-1]) - (x[t-1] - x[t-2])`, per period squared.
- **Turning point:** sign reversal of consecutive velocities (strict up→down / down→up). Zero values do not automatically signal a turning point.
- **Freshness:** last selected observation period cannot exceed explicit `max_lag_periods` relative to the as-of period.
- **Vintages:** for each period, accept exactly one earliest `FIRST`, ordered `REVISION` timestamps, and select only the latest value published **on or before** the cutoff. A revision after cutoff must not contaminate historical features.
- **Fail closed:** missing releases/evidence, ambiguous timezone, non-finite data, duplicate releases, missing recent periods, unsupported transport or overdue series produce an error, not an imputed signal.

These are *unit-specific raw features*, not normalized cross-country scores. A higher unemployment rate or a higher inflation rate must **not** automatically be encoded as positive FX strength.

## Design decisions still pending (NOT implemented)
1. **Source/feature selection per country:** Growth (real GDP, real spending, production, surveys), Labour (unemployment, employment, wage growth), Inflation (headline/core/services/persistence). Avoid treating annual growth rates and index levels as comparable raw quantities. Avoid changing mix based on observed FX outcomes.
2. **Transformations:** specify per series level vs YoY vs QoQ vs surprise, units, release calendar, directions and vintage-aware baseline history. Quarterly observations stay quarterly; monthly forward-fill must carry an explicit stale status.
3. **Normalization:** use training-window-only expanding/rolling robust Z or percentile where economically defensible, avoid post-cutoff revisions and near-zero variance. Document sample minimum and winsorization beforehand.
4. **Pillar aggregation:** pre-register candidate weights/fallback rules, distinguish inflation-pressure from beneficial-for-currency *policy response*. No fitting to the 24 legacy numbers. Do not equate higher CPI with a favorable FX signal.
5. **Cycle rules and validation:** version a separate macro regime taxonomy and thresholds, use strictly vintage-correct walk-forward, OOS, sensitivity to weights, stress regimes, FX confirmation via OIS/rates and price. Control transaction costs, multiple testing and overlap; record adverse evidence.
6. **Certification and governance:** independent official PIT receipts, observed-source verification, replay across multiple cutoffs, deterministic negative tests, review/approval of score specification, and separate gate before any new baseline is published.

## Run safely
```bash
python -m unittest validation.macro.test_v2_shadow_features_v1 -v
python -m validation.macro.v2_shadow_features_v1
```
Optional `--out /tmp/macro-v2-shadow/inventory.json` exports the **inventory receipt** into a CI artifact path, not under `live_data`.

## No-impact contract
New files reside under `validation/macro/` plus **one PR/manual-only, unscheduled** QA workflow. No edits to `D.json`, `MACRO_SERIES.json`, Macro Thermometer, rates, OIS, FX pairs, active Control Room Preview or old UI; no updates to existing production/scheduled workflows; no new ChatGPT scheduled task. Outputs always include `ready_for_scoring=false`, `safe_to_publish_new_D=false`, `safe_to_update_pair_theses=false`, `writes_live_data=false`.
