# Macro V2 — first explicit domestic-score *candidate* (27 Oct 2026)

## What gets closed
The frozen `D.json` 8-country scalar scores were produced by an undocumented legacy generator and cannot be reconstructed just from one published output vector. We stop attempting to retrofit a formula to those numbers. This proposal gives a fully **versioned, predetermined** input/transform/math/output contract, with no fitted parameters or automatic publication.

For each country: `growth_z` = publisher-first-web GDP QoQ, trained against the **previous 12** GDP observations (US SAAR converted to QoQ). `labour_tightness_z` = negative standardized registered/unemployment-rate z against **previous 24 monthly or 12 quarterly** observations; unemployment improvements raise tightness. `inflation_pressure_z` = normalized underlying registered CPI measure; higher is **pressure**, not automatically FX-positive.

**Candidate activity**: `0.50 × growth_z + 0.50 × labour_tightness_z + 0.00 × inflation_pressure_z`. Classification thresholds are +-0.50 against own history. Domestic descriptive price pressure is *separate*. Indicative economic regimes are the four activity/price combinations, with an explicit mixed/turning state when a component is near zero. These are NOT the old `D.macro[].cycle` labels.

## Core limitation / falsification
The first-web GDP statement ledger has original issuer web reports without a complete attested contemporaneous-release-day source-byte panel; unemployment/inflation historical sources include retrospective revisions and two explicit BLS-shutdown estimates. Eurozone GDP membership and Swiss sports-adjustment measurement caveats remain flagged.

The output is **not** a cross-country Macro Strength ranking, FX valuation, expected return, OIS/CB policy repricing or a price signal. Country z units are heterogeneous. Test the activity classification with alternative growth weights 25/50/75%; sensitivity instability is displayed rather than hidden. Later, before any FX model promotion, require independent multi-vintage historical PIT replay, policy reaction and 2Y rate mapping, OOS FX performance, Beta PDF A-Z, Forward observations and negative-controls. Do not choose thresholds/weights by optimizing against the historical frozen `D`.

## Exact isolation
- Input: existing `v2_g8_three_axis_economic_shadow_v1` (one source of truth; do not rebuild old values)
- Output: a **dated /tmp-only research receipt** containing 8 countries × 3 economic axes, 3 weight scenarios, quality labels and legacy reference as noncomparable values
- No modification to `live_data`, `D.json`, published Control Room, 28 pair theses, scheduled workflows, Beta, or Forward
- Offline adversarial tests and a new unscheduled PR CI check; release/cutover requires separate evidence, not this successful CI alone.

Run:
```bash
python -m unittest validation.macro.test_v2_domestic_candidate_explicit_formula_v1 -v
python -m validation.macro.v2_domestic_candidate_explicit_formula_v1 --as-of 2026-10-27 --out /tmp/gmfq-domestic-macro-candidate.json
```
