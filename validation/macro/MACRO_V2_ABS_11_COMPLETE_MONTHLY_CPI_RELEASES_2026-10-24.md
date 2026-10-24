# Macro V2 — ABS complete monthly CPI: 11 period-specific official web releases

**24 ottobre 2026 · Shadow research, not production**

## Scope

This release-event ledger covers the first **11 regularly published complete Monthly CPI reference periods**, October 2025 through August 2026. They correspond to **11 different ABS release events** and **22 metric-value observations** (headline and monthly trimmed mean).

The first **complete Monthly CPI** for October 2025 was published on **26 November 2025**. The original series also includes *retrospective* historical observations from April 2024, which were made available only later and **must not be re-labelled as separate contemporaneous 2024 monthly publications**. ABS explains the transition in the [July 2025 announcement](https://www.abs.gov.au/media-centre/media-statements/abs-announces-monthly-cpi-start-november-2025); the RBA independently explains the historical backcast and discontinued partial Monthly CPI Indicator in its [technical note](https://www.rba.gov.au/publications/technical-notes/2025/the-transition-to-a-complete-monthly-cpi.html).

## First web-reported release ledger

| Reference period | Release (Australia/Sydney, 11:30) | Headline YoY | Trimmed YoY | Original period-specific official URL |
| --- | --- | ---: | ---: | --- |
| 2025-10 | 2025-11-26 AEDT | 3.8 | 3.3 | [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/oct-2025) |
| 2025-11 | 2026-01-07 AEDT | 3.4 | 3.2 | [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/nov-2025) |
| 2025-12 | 2026-01-28 AEDT | 3.8 | 3.3 | [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/dec-2025) |
| 2026-01 | 2026-02-25 AEDT | 3.8 | 3.4 | [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/jan-2026) |
| 2026-02 | 2026-03-25 AEDT | 3.7 | 3.3 | [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/feb-2026) |
| 2026-03 | 2026-04-29 AEST | 4.6 | 3.3 | [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/mar-2026) |
| 2026-04 | 2026-05-27 AEST | 4.2 | 3.4 | [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/apr-2026) |
| 2026-05 | 2026-06-24 AEST | 4.0 | 3.6 | [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/may-2026) |
| 2026-06 | 2026-07-29 AEST | 3.8 | 3.6 | [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/jun-2026) |
| 2026-07 | 2026-08-26 AEST | 3.5 | 3.6 | [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/jul-2026) |
| 2026-08 | 2026-09-30 AEST | 4.0 | 3.6 | [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/aug-2026) |

AEST is UTC+10, AEDT is UTC+11. The code uses the actual supplied official Australia/Sydney publication clock and verifies daylight-saving offsets against the Python `zoneinfo` database, so a value published at 11:30 is not visible in a simulated cutoff at 11:29:59.

## Source discrepancy: January trimmed mean

The January **own-period** ABS source reports **3.4%** on 25 February, but the 25 March **February** release describes January as **3.3%**. This creates a documented discrepancy of 0.1 percentage points across the two separate release pages. It **may** be a seasonal-adjustment revision or another reporting inconsistency, but this ledger **does not claim a certified revision**. The earliest reported 3.4 is left intact; after 25 March the later 3.3 reference becomes visible *only as a separate flagged evidence item*. Do not rewrite January's first release on the basis of an unverified revised-vintage explanation.

The January 2026 page also notes supporting tables republished on 27 February with headline / trimmed measures *unaffected*. This does not explain the March cross-publication discrepancy and reinforces the need for a direct vintage comparison before concluding what changed.

## Limits and next phase

- **11 of 25** first regular monthly reference periods are documented as period-specific official web headlines; the fixed 25 monthly FIRST releases training+OOS minimum has a **14-release shortfall** as of 24 October 2026.
- This is **web-attributed** evidence, not a complete immutable PIT archive: no original release-day HTML or data bytes were captured, and original pages may have changed later.
- The 2024–2025 *backcast* and the prior partial Monthly CPI Indicator belong to **different availability and measurement regimes**. Neither can be silently counted as older complete-monthly first releases to fill the shortfall.
- Rates/OIS, event-time pre-release consensus, actual publication-day archived snapshots, historical data revisions, and intraday FX responses remain outside the validation scope.
- No score, trading signal, backtest, runtime feed, Control Room or 28 FX pair update.

## Read-only commands

```bash
python -m unittest validation.macro.test_v2_abs_complete_monthly_cpi_11_release_replay_v1 -v
python -m validation.macro.v2_abs_complete_monthly_cpi_11_release_replay_v1 \
  --asof 2026-02-25T00:30:00Z \
  --out /tmp/macro-v2-shadow/abs-jan-original-release.json
python -m validation.macro.v2_abs_complete_monthly_cpi_11_release_replay_v1 \
  --asof 2026-10-24T00:00:00Z \
  --out /tmp/macro-v2-shadow/abs-11-releases-audit.json
```
