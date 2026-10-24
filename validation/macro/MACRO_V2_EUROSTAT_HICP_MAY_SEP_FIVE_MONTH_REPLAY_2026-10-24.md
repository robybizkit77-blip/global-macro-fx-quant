# Macro V2 — Eurostat EA21 HICP May–September 2026: publication-vintage research

**24 October 2026 · read-only shadow, NOT a certified historical PIT archive.**

## What the five-month replay actually contains

Eurostat **five monthly economic reference periods**, each with two official publication stages (flash and detailed). Ten release events; six comparable annual-rate indicators in each stage (headline, core excluding energy/food/alcohol/tobacco, energy, food/alcohol/tobacco, non-energy industrial goods, services); **60 per-metric report values**. These are not 60 independent first releases.

| Reference month | Flash date | Headline flash (% YoY) | Detailed date | Headline detailed | Change |
| --- | --- | ---: | --- | ---: | ---: |
| May | 2 Jun 2026 | 3.2 | 17 Jun 2026 | 3.2 | 0.0 pp |
| June | 1 Jul 2026 | 2.8 | 17 Jul 2026 | 2.8 | 0.0 pp |
| July | 31 Jul 2026 | 2.9 | 19 Aug 2026 | 2.9 | 0.0 pp |
| August | 1 Sep 2026 | 3.3 | 17 Sep 2026 | **3.2** | **−0.1 pp** |
| September | 2 Oct 2026 | 3.8 | 16 Oct 2026 | 3.8 | 0.0 pp |

The two additional months are sourced from [May flash](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-02062026-ap), [May detailed](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-17062026-ap), [June flash](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-01072026-ap), [June detailed](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-17072026-ap). July–September original three-month validator and archive paths from PR #584 remain intact and get invoked by composition.

## Material inflation component revisions

- **May:** core (excluding energy and food/alcohol/tobacco) **2.5→2.6%**, energy **10.9→10.8%**, food/alcohol/tobacco **2.0→1.9%**; headline remains 3.2%.
- **June:** energy **8.7→8.5%**, food/alcohol/tobacco **1.6→1.5%**, non-energy goods **0.9→0.7%**; headline remains 2.8%.
- Prior July–September: 5 additional nonzero comparable component changes, including August headline 3.3→3.2%.

Thus **11 nonzero comparable flash-to-detailed component comparisons** across five reference months, versus only **one headline revision**. Value changes in components are not additive without the correct HICP component weights/methodology; do not infer headline changes from the displayed one-decimal rates.

## An older reference month changing in a later bulletin

The [May detailed bulletin, 17 June](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-17062026-ap) shows **March 2026 Services YoY at 3.3%** in its retrospective column. The [June flash bulletin, 1 July](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-01072026-ap) shows **March Services 3.2% with the explicit `r` revised marker**. The source reports a later change in the historical reading (−0.1pp). This is **not** the same as the June flash estimate for June Services 3.2%; the two measurements have different reference periods.

The research replay stores that separate March retrospective line with two conservative publication gates: 18 June 00:00 UTC for the first quoted value, and 2 July 00:00 UTC for the later `3.2r`. It **does not know March's original first-release value**, the earliest time of the actual revision, or the full set of intermediate vintages. Do not backdate the revised 3.2 into March.

## Critical limitations

1. Eurostat's public release pages establish official **dates**. The audit cannot independently certify an exact intraday release clock: availability in the *research simulation* is conservatively set to **00:00 UTC on the day following the published calendar date**, not represented as actual trading-time publication.
2. Period-specific original publisher webpages are available, but original **release-day immutable page bytes** were not captured/certified, so the evidence is **web-attested**, not a fully preserved PIT archive.
3. The compiled full-five-month evidence does not certify the older 2025 EA20 to 2026 EA21 geographic transition for historical model normalization.
4. Five reference months are **20 monthly first releases short** of the 25-month research training+OOS minimum, and still lack a complete revision history and externally certified source bytes.
5. No inference of ECB OIS repricing, 2Y reaction, EUR/USD move, economic score, backtest suitability, or live trade.

## Validation

```bash
python -m unittest validation.macro.test_v2_eurostat_hicp_five_month_replay_v1 -v
python -m validation.macro.v2_eurostat_hicp_five_month_replay_v1 \
  --asof 2026-07-01T23:59:59Z --out /tmp/macro-v2-shadow/eurostat-before-june-flash-gate.json
python -m validation.macro.v2_eurostat_hicp_five_month_replay_v1 \
  --asof 2026-10-24T00:00:00Z --out /tmp/macro-v2-shadow/eurostat-may-sep-five-month-replay.json
```

All tests/receipts are read-only. No `live_data/`, `site/`, `payload/`, `dashboard/`, `D.json`, 28-pair ranking, recurring schedule, or scoring changes.
