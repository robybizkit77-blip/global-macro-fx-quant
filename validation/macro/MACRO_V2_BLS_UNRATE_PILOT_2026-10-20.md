# Macro V2 — US Labour (BLS UNRATE): first official-web historical replay pilot

Date of manual source review: 2026-10-20. **Shadow research only.** Never used for economic score, pair selection, new baseline, or trading. Model Legacy remains 2026-09-25.

## Purpose
Establish the first *real* consecutive historical point-in-time case with five original official BLS archived Employment Situation releases (NOT a latest-revised UNRATE history). Month of observation is **not** the publication date. The manifest records actual official release-date, the 08:30 America/New_York press embargo lift time and seasonal UTC offset. It pins period-specific headline national unemployment rates (seasonally adjusted), as publicly reported in the individual first releases.

| Observation period | First-release unemployment rate | Release day (08:30 ET) | Official archived source |
|---|---:|---|---|
| 2023-12 | 3.7% | 2024-01-05 (EST) | https://www.bls.gov/news.release/archives/empsit_01052024.htm |
| 2024-01 | 3.7% | 2024-02-02 (EST) | https://www.bls.gov/news.release/archives/empsit_02022024.htm |
| 2024-02 | 3.9% | 2024-03-08 (EST) | https://www.bls.gov/news.release/archives/empsit_03082024.htm |
| 2024-03 | 3.8% | 2024-04-05 (EDT) | https://www.bls.gov/news.release/archives/empsit_04052024.htm |
| 2024-04 | 3.9% | 2024-05-03 (EDT) | https://www.bls.gov/news.release/archives/empsit_05032024.htm |

Release identifier is separately pinned (USDL-24-0006, USDL-24-0148, USDL-24-0451, USDL-24-0629, USDL-24-0796), and URL host, archival filename, observed series ID LNS14000000, reading, precise ET clock / daylight-saving offset all fail closed on changes. Evidence is archived official *web-page content crosschecked at review*, **not** immutable archived bytes. CI does not fetch and re-hash BLS pages. No independent authoritative source checksum or all-vintage series is claimed.

## Worked shadow replay

| As-of UTC | Eligible observations | Latest period and raw level | Velocity | Acceleration | Train-only Z |
|---|---:|---|---:|---:|---|
| 2024-04-05 12:29:59 | 3 | Feature withheld (<4) | — | — | — |
| 2024-04-05 12:30:00 | 4 | 2024-03 · 3.8% | -0.1 pp/month | -0.3 pp/month² | WITHHELD (only 3 prior levels) |
| 2024-05-03 12:29:59 | 4 | 2024-03 · 3.8% | -0.1 pp/month | -0.3 pp/month² | WITHHELD |
| 2024-05-03 12:30:00 | 5 | 2024-04 · 3.9% | +0.1 pp/month | +0.2 pp/month² | Computed from prior 4 ONLY |

At May 3 as-of, the prior-only historical training set is December 2023 through March 2024 (3.7, 3.7, 3.9, 3.8). Mean 3.775 percentage points and population standard deviation ≈0.082916 pp. The new 3.9% reading yields a *descriptive* Z-score of ≈+1.5076. This is **not** an FX strength score. A rising unemployment rate can signal labour market softening, not currency appreciation.

## Methodological boundaries
- This uses each month's **FIRST** published unemployment value. Later revisions to earlier months are intentionally excluded; therefore it does not represent the complete revised-vintage information set or certify a strategy's historical point-in-time replay across all months.
- Four observations are necessary for raw dynamics under the existing V2 interface. Four *prior* released observations are required for training-only normalization (i.e. five observed first releases). Neither the current observation nor future releases may enter its mean or variance.
- The population standard deviation is used solely for a reproducible demonstration; four training values are **too few for an economically robust Z-score**. The displayed normalisation status is `PILOT_PRIOR_ONLY_Z_COMPUTED_NOT_ECONOMICALLY_VALIDATED`.
- No inflation/FX polarity, cross-indicator weights, composite Labour score, trading thesis, model regime or predictive effect is calculated. No FX/out-of-sample evidence has been tested.
- The reader is pinned to five rows to reject a silently injected revision or a fabricated extra datapoint. A later upgraded revision-aware dataset would need a separate versioned contract, source proof, and tests.

## Execution, isolation and follow-up
```bash
python -m unittest validation.macro.test_v2_bls_unrate_first_release_pilot_v1 -v
python -m validation.macro.v2_bls_unrate_first_release_pilot_v1 --asof 2024-05-03T12:30:00Z
```
The optional `--out` produces an ephemeral read-only receipt; there are no writes to production. The existing unscheduled Macro V2 PR/manual-only QA workflow is extended to exercise these cases; no cron or existing production/scheduled workflow is added or modified.

For a **strict first-release archive certification**, secure immutable publisher release artifacts and hashes for each period, an externally auditable timestamp, complete revision history or a documented first-release-only inference contract, and independent PIT-source assertions beyond local pinned fixtures. For a predictive model, additionally define feature transforms, research-split/walk-forward and multiple-testing controls before designing composite scores.

All emitted receipts must continue to have `ready_for_macro_scoring=false`, `safe_to_publish_new_D=false`, `safe_to_update_pair_theses=false` and `writes_live_data=false`.
