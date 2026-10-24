# Macro V2 — Eurostat July–September 2026 HICP web release-event replay

**24 October 2026 · shadow research ONLY; no publication to operational scores, no backtests.**

## Official-source comparison, EA21, annual percentage change

| Reference month | Eurostat flash published | HICP headline flash | Detailed published | Headline detailed | Difference |
| --- | --- | ---: | --- | ---: | ---: |
| July 2026 | 31 July 2026 | 2.9% | 19 August 2026 | 2.9% | 0.0 pp |
| August 2026 | 1 September 2026 | **3.3%** | 17 September 2026 | **3.2%** | **−0.1 pp** |
| September 2026 | 2 October 2026 | 3.8% | 16 October 2026 | 3.8% | 0.0 pp |

Read directly from the **six period-specific Eurostat Euro-indicator publisher pages**:

1. [July flash](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-31072026-ap)
2. [July detailed](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-19082026-ap)
3. [August flash](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-01092026-ap)
4. [August detailed](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-17092026-ap)
5. [September flash](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-02102026-ap)
6. [September detailed](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16102026-ap)

## Six strictly comparable annual-rate components

| Month | Metric | Flash, % YoY | Detailed, % YoY | Revision, pp |
| --- | --- | ---: | ---: | ---: |
| July | Energy | 10.0 | 10.3 | +0.3 |
| August | All-items headline | 3.3 | 3.2 | −0.1 |
| August | Food, alcohol, tobacco | 1.2 | 1.1 | −0.1 |
| September | Energy | 18.8 | 18.9 | +0.1 |
| September | Food, alcohol, tobacco | 1.4 | 1.3 | −0.1 |

The other comparisons in the pinned set (headline, core excluding energy/food/alcohol/tobacco, energy, food/alcohol/tobacco, non-energy industrial goods, services) are unchanged **at one decimal point**. There are **18 independently paired annual-rate comparisons**, **5 nonzero component comparisons**, but just **three economic reference months and six distinct official release events**. The source ledger records **36 rate-value entries across stages**, not 36 independent monthly first releases.

## Anti-look-ahead and period/vintage separation

- July 2026 flash value becomes conservatively visible on **1 August 2026 00:00 UTC**; its detailed value only from **20 August 00:00 UTC**.
- August 2026 flash 3.3% becomes conservatively visible on **2 September 00:00 UTC**. The detailed **3.2%** is forbidden until **18 September 00:00 UTC**.
- September 2026 flash 3.8% becomes conservatively visible on **3 October 00:00 UTC**; detailed rates from **17 October 00:00 UTC**.
- These are **artificial next-UTC-day conservative visibility gates** because **the actual publisher intraday release timestamps have not been independently certified**. They must *not* be interpreted as the market's actual same-day knowledge time.
- The replay keeps each reference period and its then-known flash/detailed value separately; later detail for August must not leak into August's flash cutoff, even when September data are subsequently available.
- Original publisher pages were checked on 24 October, but not cryptographically captured on their initial publication dates. No archived first-release-day bytes, complete historical revision matrices, consensus surprise, OIS 2Y/FX event response are claimed.

## Research implications

The headline August revision −0.1 pp matters for vintage integrity: a backtest that uses only the final August 3.2% rate **as if known on 1 September** commits a future-data leakage error. The rate itself does *not* imply a verified ECB repricing or trade. Three consecutive reference periods are still **22 short** of a hypothetical 25 monthly first-release training+held-out rule, without source provenance certification.

The full G8 Macro V2 pipeline remains read-only: no D.json rebuilding, no 28 pair ranking change, no Control Room or any scheduled task modification. The existing September-only component study remains separately pinned and checked for consistency by the new code.

## Reproduction in CI

```bash
python -m unittest validation.macro.test_v2_eurostat_hicp_three_month_replay_v1 -v
python -m validation.macro.v2_eurostat_hicp_three_month_replay_v1 \
  --asof 2026-09-17T23:59:59Z --out /tmp/macro-v2-shadow/eur-aug-flash-before-detailed-gate.json
python -m validation.macro.v2_eurostat_hicp_three_month_replay_v1 \
  --asof 2026-10-24T00:00:00Z --out /tmp/macro-v2-shadow/eur-hicp-jul-sep-web-pit-replay.json
```
