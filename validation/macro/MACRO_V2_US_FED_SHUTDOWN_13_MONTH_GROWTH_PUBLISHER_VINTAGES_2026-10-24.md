# Macro V2 — Federal Reserve G.17 shutdown bridge, September 2025–September 2026

**Research review: 24 October 2026. Twelve distinct publisher editions, thirteen first-published economic months, 35 subsequent changed index readings. All source data come from publisher-*dated web pages consulted after the event*, NOT independent cryptographic captures of those pages made on their original release days. No new Macro scores.**

## Why 13 economic months but only 12 publisher release dates?

During the 2025 US government shutdown, the Federal Reserve **delayed** the normal industrial-production (G.17) release timetable. The source's own [G.17 information feed](https://www.federalreserve.gov/feeds/g17.html) states:

- The industrial production estimate **for September 2025**, originally scheduled for October 17, was actually released **Wednesday, December 3, 2025, at 09:15 EST** (14:15 UTC).
- The previously scheduled November 18 and December 16 releases were combined into **one official release December 23, 2025, at 09:15 EST** (14:15 UTC). Both **October and November 2025 preliminary** observations became available together. There were **two distinct economic reference months, but one publication clock**, never fictitious 2025-11-18/2025-12-16 first-release events.
- The source returned to single-month releases in January 2026. At the daylight-saving boundary the clock changed from **09:15 EST / 14:15 UTC** to **09:15 EDT / 13:15 UTC**.
- Distinguish this shutdown schedule change from the Fed's **November 24, 2025 annual revision** to IP/CU: a revision publication is *not itself* a first economic-month estimate. The pre-September first-release reference periods are deliberately not inferred from today's revised historic Fed/FRED table.

## Source-edition ledger

The original research PR #595 already attested [April–October 2026 releases](./MACRO_V2_US_FED_G17_SEVEN_OFFICIAL_RELEASE_VINTAGES_2026-10-24.md). The expanded ledger now stores all relevant date-specific `Total index` values (0.1 index precision, seasonally adjusted, 2017=100) from the following twelve publisher editions:

| Actual Fed release date | First preliminary economic month(s) | Publisher preliminary Total index |
| --- | --- | --- |
| [3 Dec 2025](https://www.federalreserve.gov/releases/g17/20251203/table0.htm) | Sep 2025 | **101.4** |
| [23 Dec 2025](https://www.federalreserve.gov/releases/g17/20251223/table0.htm) | Oct **and** Nov 2025 | **101.6**, **101.8** |
| [16 Jan 2026](https://www.federalreserve.gov/releases/g17/20260116/table0.htm) | Dec 2025 | **102.3** |
| [18 Feb 2026](https://www.federalreserve.gov/releases/g17/20260218/table0.htm) | Jan 2026 | **102.3** |
| [16 Mar 2026](https://www.federalreserve.gov/releases/g17/20260316/table0.htm) | Feb 2026 | **102.6** |
| [16 Apr 2026](https://www.federalreserve.gov/releases/g17/20260416/table0.htm) | Mar 2026 | **101.8** |
| [15 May 2026](https://www.federalreserve.gov/releases/g17/20260515/table0.htm) | Apr 2026 | **102.5** |
| [15 Jun 2026](https://www.federalreserve.gov/releases/g17/20260615/table0.htm) | May 2026 | **102.6** |
| [17 Jul 2026](https://www.federalreserve.gov/releases/g17/20260717/table0.htm) | Jun 2026 | **102.6** |
| [18 Aug 2026](https://www.federalreserve.gov/releases/g17/20260818/table0.htm) | Jul 2026 | **103.0** |
| [18 Sep 2026](https://www.federalreserve.gov/releases/g17/20260918/table0.htm) | Aug 2026 | **103.1** |
| [16 Oct 2026](https://www.federalreserve.gov/releases/g17/20261016/table0.htm) | Sep 2026 | **104.0** |

The 2025 shutdown pages and first five 2026 summary editions are each independently checked against their exact historical dated publisher URL, economic reference periods, reported indices and Eastern DST/standard-time clock. Existing seven-edition March–September source values from #595 are **reconciled without changing the original code or its tests**.

## Multiple index observations are revisions, NOT new source months

In **61 publisher Total-index month cells**, there are **13 genuinely new economic-month first estimates**, **35 numerical changes made at later publication events**, and **13 publisher cells repeating the prior value**. Repeats do not become fake revisions; a later-released October edition may stop showing older months entirely, which does not erase the previously visible value.

Concrete example: September 2025 first appears as **101.4** (December 3), then **101.7** (December 23), **101.8** (January 16) and **101.7** again (February 18). Those are **one first release + three subsequent revisions**, not four separate Septembers. The December 23 same-day two-preliminary event and the November 24 annual benchmark revision make naïve monthly resampling scientifically invalid.

The **3m/3m** research transformation from the earlier prototype now becomes arithmetically computable on the six first-published reference periods **September 2025–February 2026** at **16 March 2026, 13:15 UTC**. At that precise cutoff, based on all publisher one-decimal source levels **as known then**, it gives **+0.7887%**; calculating once using each month's earliest preliminary reading only yields **+0.7874%**. This difference is the actual effect of the intervening publisher revisions included in the dated-page evidence, **not proof of broader GDP growth or FX strength**.

The code freezes an illustrative 3m/3m research feature separately at **each original edition's cutoff** after enough observations are present. On October 24, there are **eight snapshots of descriptive features**, not 25 earlier *frozen monthly* values needed for rolling normalization. Even a correct initial sample length of six levels cannot support a country-calibrated historical z-score yet.

## What is—and is not—certified

- **Improved:** 7→**13 distinct first-report economic months** for the US total industrial-production one-decimal summary *candidate*; 12 publisher releases and 35 **changed** historic observations. This crosses 2025's interrupted schedule without inventing missing release times or months.
- **Still not certified:** immutable original HTML **captured at the time of release**, continuous official *exact-precision* machine-data originals (present four-decimal `US_INDPRO_history_value` must not replace one-decimal source cells), **complete** archive of historical revisions including benchmark methodology changes, final original publisher source-to-score mapping, the **25 distinct first month minimum**, 25 *previously frozen feature* historical values for rolling z, or economic comparability across the G8.
- **Still short:** **12 months** to reach 25 first-reported monthly data points; for a genuine 25-prior-period rolling z of a six-month-based 3m/3m feature, a longer contiguous first-release record is needed and its revisions preserved. The 13 months are **not** a certified normalized Growth score.
- **No mutation:** G8 24 candidate research source adapters remain as previously; `D.json`, `live_data/`, `site/`, `payload/`, `dashboard/`, 28-pair FX rankings, online Control Room, backtests, alerts, calendar tasks and schedulers are unchanged.

## Reproduce (read-only under `/tmp`)

```bash
python -m unittest validation.macro.test_v2_us_fed_g17_shutdown_13_month_replay_v1 -v
python -m validation.macro.v2_us_fed_g17_shutdown_13_month_replay_v1 \
  --asof 2025-12-23T14:14:59Z --out /tmp/macro-v2-shadow/us-ip-before-double-first.json
python -m validation.macro.v2_us_fed_g17_shutdown_13_month_replay_v1 \
  --asof 2025-12-23T14:15:00Z --out /tmp/macro-v2-shadow/us-ip-after-double-first.json
python -m validation.macro.v2_us_fed_g17_shutdown_13_month_replay_v1 \
  --asof 2026-03-16T13:15:00Z --out /tmp/macro-v2-shadow/us-ip-first-real-six-month-growth.json
python -m validation.macro.v2_us_fed_g17_shutdown_13_month_replay_v1 \
  --asof 2026-10-24T00:00:00Z --out /tmp/macro-v2-shadow/us-ip-thirteen-month-replay.json
```

Tests fail closed on a fabricated ordinary Nov/Dec 2025 publication, missing same-day October/November first data, wrong observed units, rounded index instead of false unrounded value, naive/wrong timezone, fake publisher URL, future release leakage, and changes to prior seven-month September/October 2026 growth calculations.
