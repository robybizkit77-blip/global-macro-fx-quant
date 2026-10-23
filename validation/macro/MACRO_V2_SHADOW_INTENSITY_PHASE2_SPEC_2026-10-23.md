# Macro V2 — Phase 2: preregistered PIT dimension intensities

**Status (23 October 2026): Research/SHADOW only. Not a live Macro score, FX signal, classification, backtest or replacement for the 24 frozen values in `D.json`.**

## Economic problem

The earlier shadow pipeline reconstructs level, direction, speed, acceleration and turning point without look-ahead when a release-dated manifest is supplied. This phase adds a **univariate, within-series normalized intensity**: how exceptional is today's value relative to an *older* point-in-time first-release window?

It does **not** compare unemployment percentages directly with production-growth percentages, infer monetary policy from CPI, or use the 24 historic September scores to fit parameters. A number shown here must not appear in the Control Room's live ranking.

## Fixed methodological contract, version 1

| Variable type | Pillar | Cadence / unit | Previous first releases | Economic positive direction | Meaning of higher index |
| --- | --- | --- | ---: | ---: | --- |
| `real_gdp_qoq` | Growth | Q / qoq_pct | 12 | +1 | More real activity |
| `industrial_production_yoy` | Growth | M / yoy_pct | 24 | +1 | More industrial activity |
| `unemployment_rate` | Labour | M / percent | 24 | -1 | Tighter labour market |
| `unemployment_rate_quarterly` | Labour | Q / percent | 12 | -1 | Tighter labour market |
| `headline_cpi_yoy` | Inflation | M / yoy_pct | 24 | +1 | More price pressure |
| `headline_cpi_yoy_quarterly` | Inflation | Q / yoy_pct | 12 | +1 | More price pressure |

These are **hypotheses fixed in code, not optimised trading weights**. Frequency mismatches, unexpected units, missing observations, unverified transport declarations, and zero training dispersion reject the computation.

At cutoff `T`, take the latest `n+1` consecutive FIRST releases published on or before `T`, with `n=24` (monthly) or `n=12` (quarterly). Earlier revisions and releases in the future do **not** enter this first-release comparison. The **latest value is excluded from training**.

```text
median_train = median(x[t-n], ..., x[t-1])
MAD_train    = median(abs(x_train - median_train))
raw_z        = (x[t] - median_train) / (1.4826 * MAD_train)
display_z    = clamp(raw_z, -3, 3)
intensity    = predefined_economic_polarity * display_z
```

The 1.4826 factor is a conventional robust-scale normalisation, **not a claim that observations are Gaussian**. `MAD <= 1e-9` is rejected; no variance is invented. The raw z, clipping, ranking within training values, first-release momentum and acceleration, training cutoff, data lineage, SHA-256 method fingerprint and all safety gates are retained in the receipt. Clipping is a display guard, not a risk signal.

### Why no overall Macro or FX score?

A low unemployment rate can be supportive for domestic rates, but the FX impact depends on the **relative** data, OIS expectations, surprise, growth and currency pricing. Elevated CPI might lead to tighter policy, or signal harmful stagflation. No policy-response map or regime classifier has been validated. Therefore the output contains only a named dimension-specific intensity, with `currency_strength_score=null`, `economic_cycle=null`, no aggregate across pillars and no pair preference.

## Point-in-time and limitations

The existing `build_features` function validates release order, time zones, source/event claims, latest-four continuity, staleness and revision chronology. Phase 2 then builds the full first-release training window. The **source provenance fields are declarations**, not independently hashed official archives. No certified full-history PIT dataset for 8×3 pillars is claimed.

The five archived BLS unemployment releases from December 2023 to April 2024 are useful to demonstrate release dates, but **fail the 24-month minimum**. That is the correct outcome: an insufficient window cannot be padded or treated as a published score. Tests also use **synthetic** monthly and quarterly vintages, not market observations.

Selection of additional official source series, archival release-chain verification, multi-cutoff vintage replay, cross-source coverage, growth/labour/inflation aggregation, regime mapping, model sensitivity and out-of-sample FX/rates validation remain open research.

## Run and governance

```bash
python -m unittest validation.macro.test_v2_shadow_features_v1 validation.macro.test_v2_shadow_intensity_v1 -v
python -m unittest validation.macro.test_v2_bls_unrate_first_release_pilot_v1 -v
python -m validation.macro.v2_shadow_intensity_v1 --manifest /tmp/my_verified_manifest.json --out /tmp/shadow-intensity.json
```

The CLI output is restricted to `/tmp`. CI is **pull-request/manual only, not scheduled**, produces an illustrative synthetic receipt under `/tmp`, and audits zero changes to `live_data`, `site`, `dashboard` or `payload`.

Permanent publication restrictions: `ready_for_macro_scoring=false`; `usable_for_backtest=false`; `safe_to_publish_new_D=false`; `safe_to_update_pair_theses=false`; `writes_live_data=false`.

The legacy 25 September 2026 baseline, all 24 historical scalar scores and 28 pair selections remain untouched.
