# Macro V2 — ABS trimmed mean: cross-publication evidence, not certified revisions

**24 October 2026 — read-only shadow research**

## Findings supported by period-specific original publisher pages

| Reference period | Original-period release | First-published web headline | Subsequent-period release(s) | Later reported reference value | Difference |
| --- | --- | ---: | --- | ---: | ---: |
| January 2026 | 25 Feb 2026, 11:30 AEDT | 3.4% YoY | February bulletin, 25 Mar 2026 11:30 AEDT | 3.3% YoY for January | −0.1 pp |
| May 2026 | 24 Jun 2026, 11:30 AEST | 3.6% YoY | June bulletin, 29 Jul 2026 11:30 AEST | **3.6%** YoY for May | 0.0 pp |
| May 2026 | 24 Jun 2026, 11:30 AEST | 3.6% YoY | July bulletin, 26 Aug 2026 11:30 AEST | **3.5%** YoY for May | −0.1 pp |

These are *cross-publication differences in reported values* visible on period-specific ABS pages as inspected on 24 October 2026. The source URLs themselves are not independently frozen release-day artifacts; publication headings and dates do not prove page-body immutability.

- [ABS January 2026](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/jan-2026): first-period summary gives January trimmed mean 3.4%.
- [ABS February 2026](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/feb-2026): contemporaneous February bulletin refers to January trimmed mean 3.3%.
- [ABS May 2026](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/may-2026): own-period May trimmed mean 3.6%.
- [ABS June 2026](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/jun-2026): June trimmed mean 3.6%, unchanged versus reported May 3.6%.
- [ABS July 2026](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/jul-2026): retrospective historical chart shows May 3.5%, while July's own trimmed mean remains 3.6%.

## Mechanistic guardrail

The new `v2_abs_trimmed_cross_publication_v1.py` references the official 11-release base ledger (#581) for each source's exact **Australia/Sydney 11:30** publication timestamp. It independently pins 5 cross-publication observations (2 January, 3 May), retains both initial and later values and replays what is supported at requested cutoffs.

At the March 25 publication gate, January's later 3.3% first becomes **visible in this sampled evidence**; at the August 26 publication gate, May's retrospective 3.5% first becomes **visible in this sampled evidence**. Neither implies the exact time at which ABS performed a statistical revision. To establish that, locate the earliest official revised-release data file, its correction/revision notes, and archived original bytes.

**These observations do not add 5 extra independent economic periods:** two underlying reference months are represented by multiple publication-time statements.

## Remaining gaps

- No original **release-day immutable HTML/XLS/CSV payloads**; source webpages might have been updated.
- No complete revision-vintage matrix for all 11 reference periods (both archived first estimates and later revisions).
- No certified exact revision-change timestamp, independent consensus or OIS market event attribution.
- The 2024/25 backcast is still excluded as separate monthly first releases; **11/25** complete monthly reference periods documented, not a full training window.

**Hard gates:** `safe_to_publish_new_D=false`, `safe_to_update_pair_theses=false`, `eligible_for_backtest=false`, `writes_live_data=false`. Control Room, live prices and 28 pair rankings are untouched.

## CI

```bash
python -m unittest validation.macro.test_v2_abs_trimmed_cross_publication_v1 -v
python -m validation.macro.v2_abs_trimmed_cross_publication_v1 --asof 2026-03-25T00:29:59Z --out /tmp/macro-v2-shadow/abs-jan-before-retrospective.json
python -m validation.macro.v2_abs_trimmed_cross_publication_v1 --asof 2026-10-24T00:00:00Z --out /tmp/macro-v2-shadow/abs-trimmed-cross-report-2026.json
```
