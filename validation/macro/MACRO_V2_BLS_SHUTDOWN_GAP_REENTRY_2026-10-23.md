# Macro V2 — BLS shutdown 2025: missing observation vs delayed publication

**23 October 2026. Historical research only. Does not update D.json or 28 FX pairs.**

## Source-verified fact

BLS's [shutdown CPS methodology](https://www.bls.gov/cps/methods/2025-federal-government-shutdown-impact-cps.htm) states that **no household survey for October 2025 was collected**, and no October unemployment rate will be retroactively estimated. BLS [revised release calendar](https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm) confirms **no October Employment Situation was published**. September 2025 was collected normally but first released late on 20 November 2025 (4.4%, as shown in the existing 25-release pilot).

Two official original [Employment Situation](https://www.bls.gov/bls/news-release/empsit.htm) releases restart the story:

| Reference month | As actually first released (08:30 New York) | U-3 headline SA | Archived official BLS source |
| --- | --- | ---: | --- |
| 2025-09 | 2025-11-20 | 4.4% | [Employment Situation September](https://www.bls.gov/news.release/archives/empsit_11202025.htm) |
| **2025-10** | **Never released; household survey not conducted** | **None** | [BLS CPS shutdown FAQ](https://www.bls.gov/cps/methods/2025-federal-government-shutdown-impact-cps.htm) |
| 2025-11 | 2025-12-16 | 4.6% | [Employment Situation November](https://www.bls.gov/news.release/archives/empsit_12162025.htm) |
| 2025-12 | 2026-01-09 | 4.4% | [Employment Situation December](https://www.bls.gov/news.release/archives/empsit_01092026.htm) |

**Important:** the household (unemployment) survey had no October observation; **payroll establishment survey** treatment differs (October payroll estimates published with November). This exception must be scoped to the CPS U-3 rate, *not blanket-applied to all US labour datasets*. The December 2025 release also applied new seasonal factors to previously reported CPS figures: we retain **original first-release headlines** in the research window rather than overwriting them with later revisions.

## Two non-equivalent analyses

The original `build_features` / `build_shadow_intensity` functions require consecutive monthly reference periods and continue to **reject** the Sep-to-Nov missing-October interval; their per-month velocity, acceleration and turning point cannot be computed across it.

A separate experimental `v2_bls_shutdown_sparse_reentry_v1.py` can make a **sparse-event descriptive level comparison**:

- **November 2025 cutoff 16 December 13:30 UTC:** 4.6% compared with 24 actually released earlier FIRST observations, excluding 4.6% itself from training.
- **December 2025 cutoff 9 January 13:30 UTC:** 4.4% compared with 24 previously released observations, including November's original 4.6%.
- The rolling window uses 24 **released observations**, *not 24 consecutive calendar months*. This creates a different estimator and must be labelled `SPARSE_OBSERVATION_GAP_EVENT_RESEARCH_ONLY`. Its output cannot be compared uncritically with the regular consecutive-month z score or trained for trading.
- `velocity_per_month`, `acceleration_per_month_squared` and `turning_point_per_month` are always **null**; no artificial October value, fake one-month difference or mechanical USD thesis is permitted.

## Risk controls and validation

The explicit absence and original two release/value pairs are pinned to specific BLS archived HTML pages, with observed Eastern time and DST offsets. Negative tests cover November/December cutoffs to the **second**, fake October releases, revised/incorrect source values, altered evidence host, release-calendar classification, stale 2026 replays, mutated pre-gap history and unexpected calls to live-score plumbing.

The existing 25-release window ends with September 2025's late first publication. No claim is made that the source bytes have been independently hashed or that a fully revised PIT vintage chain exists. Source pages may be checked directly; this research receipt is not a certified backtest dataset.

```bash
python -m unittest validation.macro.test_v2_bls_shutdown_sparse_reentry_v1 -v
python -m validation.macro.v2_bls_shutdown_sparse_reentry_v1 \
  --asof 2026-01-09T13:30:00Z \
  --out /tmp/macro-v2-shadow/bls-shutdown-gap.json
```

The workflow is manual/pull-request-only and writes a receipt to `/tmp`. No edits to `live_data/`, `site/`, `payload/`, `dashboard/`, `D.json`, pair signals or current macro scoring.

**Next:** before attempting a present-day Macro V2 score, extend release-verified first observations through 2026 **and validate how all observation gaps should be handled**, then perform out-of-sample sensitivity and rates/FX contribution tests with distinct historical and live gates.
