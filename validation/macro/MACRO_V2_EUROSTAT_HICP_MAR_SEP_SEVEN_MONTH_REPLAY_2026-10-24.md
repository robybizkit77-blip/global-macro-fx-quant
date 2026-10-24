# Macro V2 — Eurostat HICP March–September 2026: seven-month web-release vintage audit

**24 October 2026 · shadow-only research; original release-day archive and full PIT revision chain NOT certified.**

## Official first-stage versus detailed publications

| Reference month | Flash date | First headline (% YoY) | Detailed date | Detailed headline | Revision, pp |
| --- | --- | ---: | --- | ---: | ---: |
| March 2026 | 31 Mar | **2.5** | 16 Apr | **2.6** | **+0.1** |
| April 2026 | 30 Apr | 3.0 | 20 May | 3.0 | 0.0 |
| May 2026 | 2 Jun | 3.2 | 17 Jun | 3.2 | 0.0 |
| June 2026 | 1 Jul | 2.8 | 17 Jul | 2.8 | 0.0 |
| July 2026 | 31 Jul | 2.9 | 19 Aug | 2.9 | 0.0 |
| August 2026 | 1 Sep | **3.3** | 17 Sep | **3.2** | **−0.1** |
| September 2026 | 2 Oct | 3.8 | 16 Oct | 3.8 | 0.0 |

New original publisher pages (period-specific EUR **EA21** annual-rate selected aggregates):
- [March flash, 31 March](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-31032026-ap).
- [March detailed, 16 April](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16042026-ap).
- [April flash, 30 April](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-30042026-ap).
- [April detailed, 20 May](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-20052026-ap).

Later May–September original 10 dated events and values are **reused unchanged** from PR #585. All 14 events contain six comparable annual-rate values: headline, core ex energy/food/alcohol/tobacco, energy, food/alcohol/tobacco, non-energy industrial goods, services. These **84 metric-stage values** are NOT 84 distinct monthly first releases: there are only **seven** reference months.

New changes:
- March headline 2.5 → 2.6 (+0.1 percentage points); energy 4.9 → 5.1 (+0.2 pp). Other five-yearly-rate categories used in this reduced set unchanged.
- April headline unchanged 3.0; energy 10.9 → 10.8 (−0.1pp), food/alcohol/tobacco 2.5 → 2.4 (−0.1pp).
- Combined source contract: 15 nonzero annual-rate component flash/detail comparisons over seven reference months, including **two nonzero headline revisions** (March, August).

## A newly documented historical revision trajectory: March services

**A March reference period can appear with different reported values in later Eurostat bulletins, even after the own-month detailed release.**

| Source report | Official publication date | March 2026 services rate |
| --- | --- | ---: |
| March detailed | 16 April | 3.2% |
| April detailed | 20 May | **3.3%** |
| May detailed | 17 June | 3.3% |
| June flash | 1 July | **3.2%** (publisher shows revised marker in table) |

All four records explicitly refer to the **same March 2026 reference period, Services YoY metric**, not the then-current reference month of each later bulletin. Each historical statement is visible only from the next UTC day after its dated publisher report, because this dossier **does not verify the actual Eurostat intraday release clock**.

The four web-reported values describe 3.2→3.3→3.3→3.2 across inspected sources, **not** a fully certified time series of true release-day vintage bytes. A change between later reports can have occurred on an intermediate release or involve a publisher page altered since release; this audit cannot independently date the statistical revision event itself. No current/revised March 3.2 or 3.3 is retroactively substituted into an earlier cutoff.

## Controls and limitations

- Publisher-page-specific dates, URLs, annual-rate metrics, and exact values independently pinned in code; negative tests just before/after conservative gates. No fabricated intraday publication time.
- Prior May–Sept 5-month code is re-executed intact and its research-only score/backtest flags checked.
- The reported 2026 series uses **EA21**, not pre-2026 EA20; naive historical splice forbidden.
- The annual-rate components are **not** headline contributions or HICP index levels. No estimate of ECB rates, 2Y repricing, FX surprise, trading reaction or causal market signal.
- No source byte archives from the original publication day, no full 25-first-release training evidence, no complete revision lineage; **7/25 monthly periods**, 18-month shortfall before even discussing research normalization.
- Hard no-write `live_data`, `site`, `payload`, `dashboard`; `D.json`, pair rankings, scoring, backtest, scheduler unchanged.

## Reproduce (CI receipts only under /tmp)

```bash
python -m unittest validation.macro.test_v2_eurostat_hicp_seven_month_replay_v1 -v
python -m validation.macro.v2_eurostat_hicp_seven_month_replay_v1 \
  --asof 2026-05-20T23:59:59Z \
  --out /tmp/macro-v2-shadow/eurostat-before-april-final-gate.json
python -m validation.macro.v2_eurostat_hicp_seven_month_replay_v1 \
  --asof 2026-10-24T00:00:00Z \
  --out /tmp/macro-v2-shadow/eurostat-march-september-seven-month-replay.json
```
