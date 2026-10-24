# Macro V2 — First real USD industrial-production publisher-vintage replay

**Reviewed 24 October 2026 · Federal Reserve G.17, 2026 March–September**  
**Shadow research only. Source webpages reviewed today are *not* independently preserved publisher files collected on their actual release days.**

## Material advance

The common eight-currency Growth normalization contract in [PR #594](https://github.com/robybizkit77-blip/global-macro-fx-quant/pull/594) was still mathematically tested on **synthetic source-vintage events**. This dossier adds **actual publisher-reported headline industrial production index readings**, from **seven separately dated Federal Reserve G.17 editions**, including original preliminary values and **subsequent revisions to the *same* reference months**. Unlike current revised `INDPRO` histories, all values belong to explicitly dated press-edition tables.

This **does not yet yield a 25-month training chain, cryptographically archived original-day HTML bytes, validated unrounded INDPRO precision, or any operational currency rank**.

### Official release calendar and exact source-reported indexes

The Fed publishes monthly G.17 at **09:15 US Eastern**. Every selected date April–October 2026 was in daylight-saving time, **09:15 EDT = 13:15 UTC**. The index is seasonally adjusted, 2017=100, **rounded to one decimal place in each historical summary table**. In every dated table the most recent month is tagged **[p] preliminary**; older month columns may be tagged **[r] revised**.

| Dated Fed G.17 web summary | First preliminary economic reference month | First preliminary Total IP index |
| --- | --- | ---: |
| [16 April 2026](https://www.federalreserve.gov/releases/g17/20260416/table0.htm) | March 2026 | **101.8** |
| [15 May 2026](https://www.federalreserve.gov/releases/g17/20260515/table0.htm) | April 2026 | **102.5** |
| [15 June 2026](https://www.federalreserve.gov/releases/g17/20260615/table0.htm) | May 2026 | **102.6** |
| [17 July 2026](https://www.federalreserve.gov/releases/g17/20260717/table0.htm) | June 2026 | **102.6** |
| [18 August 2026](https://www.federalreserve.gov/releases/g17/20260818/table0.htm) | July 2026 | **103.0** |
| [18 September 2026](https://www.federalreserve.gov/releases/g17/20260918/table0.htm) | August 2026 | **103.1** |
| [16 October 2026](https://www.federalreserve.gov/releases/g17/20261016/table0.htm) | September 2026 | **104.0** |

Each edition's actual summary `Total index` row for all shown March–September reference months is stored in the fixture, not just the last new-month cell. A later edition can omit an older column: the October table starts in April, so the latest earlier March observation is kept from September rather than fabricated or deleted.

### What the revision history demonstrates

The seven tables contain **7 distinct first preliminary months**, plus **13 value-changing, later-edition statements** for months already reported. For example:

- **March 2026 index** first **101.8** (16 April); later **101.6** (15 June), **101.8** (18 August), **101.7** (18 September). These are not four separate March first releases.
- **July 2026 index** first **103.0** (18 August), later **103.2** (16 October).
- **August 2026 index** first **103.1** (18 September), later **103.3** (16 October). This publisher rounded August preliminary 103.1 is **not proof** that the now-observed four-decimal `US_INDPRO_history_value = 103.0682` was available to the model exactly at 09:15 on 18 September.

The replay uses source edition dates, index levels and release times as explicit facts in a pinned independently checked contract; nonmatching metrics, dates, clocks, publisher hosts or rounded totals fail closed. Its input first-edition source URLs are **publisher-dated pages as served on 24 October**, not verified hashes of HTML **captured at the actual historical publication time**. Hashing a fixture today does not magically establish its historical provenance.

### A real, descriptive 3m/3m calculation

The existing `shadow_math` function from PR #593 computes an unannualized **3-month versus prior 3-month change** from six monthly levels **only when those publication events are already visible**. Two methods illustrate why revision timing matters:

| Information as of | 3m/3m from each month's original one-decimal preliminary | 3m/3m from the latest publisher values **available as of that date** |
| --- | ---: | ---: |
| 18 September 2026, **before 13:15 UTC** | Unavailable (August not published) | Unavailable |
| 18 September 2026, **at 13:15 UTC** (March–August) | **+0.5865%** | **+0.6517%** |
| 16 October 2026, **before 13:15 UTC** | Replays earlier August-ended feature | Replays earlier August-ended feature |
| 16 October 2026, **at 13:15 UTC** (April–September) | **+0.7800%** | **+0.7136%** |

This is **calculation on the published rounded Total index values**, *not* exact source `INDPRO` values and not a retrospectively recomputed model score. The prior-value changes are information available only at the **later** publisher release time. A training feature frozen at its previous publication cutoff would retain its earlier vintage, as required by PR #594.

### Explicit missing pieces

1. **18 additional original monthly preliminary releases** required to reach the *minimum 25 distinct economic months* in the research target. A rolling normalizer additionally needs **25 earlier frozen feature observations plus a current feature**, after the initial six monthly source levels needed for the first 3m/3m feature.
2. All needed **source-period revisions across an extended window**, including Fed annual benchmark and seasonal-adjustment changes, with year-specific original publisher versions.
3. **Immutable original publication-day source bytes/metadata** or an independently verifiable old archival copy, and a decision on using the **rounded 0.1 Fed Total index** versus the original exact/official time-vintage machine series.
4. Approved source-to-canonical USD Growth metric mapping; economy-wide GDP and narrower industrial production are not interchangeable. Real-economy comparability for EUR/GBP/JPY/CHF/CAD/AUD/NZD remains unresolved.
5. Independent weights, positioning/price interaction, FX model and 28-pair ranking audits before any deployment.

**Deliberately unchanged:** the G8 source inventory, **24/24 connected candidate streams**, original `live_data`, `D.json`, macro Growth score, 28 pairs, Control Room, backtests, scheduled alerts/workflows, and source-readiness certification. The new material lives exclusively under `validation/macro/` and only writes receipts into `/tmp`.

## Reproduce in existing unscheduled Macro V2 shadow CI

```bash
python -m unittest validation.macro.test_v2_us_fed_g17_seven_release_growth_replay_v1 -v
python -m validation.macro.v2_us_fed_g17_seven_release_growth_replay_v1 \
  --asof 2026-09-18T13:14:59Z \
  --out /tmp/macro-v2-shadow/us-g17-before-aug-release.json
python -m validation.macro.v2_us_fed_g17_seven_release_growth_replay_v1 \
  --asof 2026-09-18T13:15:00Z \
  --out /tmp/macro-v2-shadow/us-g17-at-aug-release.json
python -m validation.macro.v2_us_fed_g17_seven_release_growth_replay_v1 \
  --asof 2026-10-16T13:15:00Z \
  --out /tmp/macro-v2-shadow/us-g17-at-sep-release.json
```
