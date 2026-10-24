# Macro V2 — December 2025 EA20 → January 2026 EA21 HICP release-vintage bridge

**24 October 2026 · Shadow research, NOT independent full historical PIT certification.**

## First release and detailed December data

The December 2025 **EA20** euro-area HICP was reported as **2.0% YoY** in Eurostat's [7 January 2026 flash estimate](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-07012026-ap), and revised to **1.9% YoY** in the [19 January 2026 detailed release](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-19012026-ap). The detailed release expressly states that the earlier flash was 2.0%. Both publisher news pages show specific official release *dates*, without independently certified source intraday clocks.

| Annual rate, Dec 2025 EA20 | Flash 7 January | Detailed 19 January | Difference |
| --- | ---: | ---: | ---: |
| All-items HICP | **2.0%** | **1.9%** | **−0.1 pp** |
| Core ex energy/food/alcohol/tobacco | 2.3% | 2.3% | 0.0 |
| Energy | −1.9% | −1.9% | 0.0 |
| Food, alcohol & tobacco | 2.6% | 2.5% | −0.1 pp |
| Non-energy industrial goods | 0.4% | 0.4% | 0.0 |
| Services | 3.4% | 3.4% | 0.0 |

**Important cross-publication discrepancy:** the later [January 2026 flash release, 4 February](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-04022026-ap) **and** [January 2026 detailed release, 25 February](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-25022026-ap) both cite **December 2025 at 2.0%** retrospectively, whereas its 19 January own-period detailed release had published **1.9%**. Later statements must remain separate vintage observations, **not automatically overwrite the original December 1.9% detailed value**. The exact source, method and effective revision time behind this discrepancy remain unknown; annual rate, geography, classification and source vintage need further investigation.

## Geographic and classification boundary — two separate issues

- [European Commission: Bulgaria adopted the euro on 1 January 2026](https://economy-finance.ec.europa.eu/euro/eu-countries-and-euro/bulgaria-and-euro_en). Eurostat's dated releases explicitly define **EA20 up to December 2025 and EA21 from January 2026**. Eurostat says rolling compositions use a **chain index**. The 2025 economic reference month must retain EA20 identity even when later statements occur after the membership expansion.
- Eurostat's [Q&A on HICP improvements effective January 2026](https://ec.europa.eu/eurostat/documents/272892/11336726/HICP%2Bimprovements%2B-%2BQuestions%2Band%2BAnswers-2026-EN.pdf/dff14a89-9f65-8371-e143-488231305710?t=1766052045691) explains **ECOICOP v2**, the new **2025=100** base, and recompiled component back-series. The **all-items historical HICP is required to remain unchanged through the ECOICOP conversion alone** at the relevant precision; categories/weights may have breaks. Therefore, do not ascribe the December 1.9→2.0 later reference solely to ECOICOP or solely to Bulgaria without a source-audited explanation.
- December 2025 as initially published: **old ECOICOP classification, 2015=100 index base**, **EA20**. January 2026: **ECOICOP v2**, **2025=100**, **EA21**. Annual rates are **% YoY** and not raw index levels.
- The replay *may display* each observed YoY rate but **cannot automatically infer a normalized cross-regime headline change, weighted component comparisons, inflation surprise, ECB OIS response, or FX trade**. Independent economic/model methodology review is required before treating old/new aggregate features as interchangeable.

## As-of availability and source confidence

The research code uses a **conservative 00:00 UTC on the calendar day after each official publisher event date**. That is a safe simulation cutoff and **not** an assertion of the actual intraday market-release timestamp.

| Information source | Official source date | Conservative visible from |
| --- | --- | --- |
| December flash 2.0% | 7 Jan 2026 | 8 Jan 00:00 UTC |
| December detailed 1.9% | 19 Jan 2026 | 20 Jan 00:00 UTC |
| January flash retrospective Dec 2.0% | 4 Feb 2026 | 5 Feb 00:00 UTC |
| January detailed retrospective Dec 2.0% | 25 Feb 2026 | 26 Feb 00:00 UTC |

January flash page itself was later corrected on 5 February on some non-headline components, as already documented in PR #587. **No unchanged original release-day webpage bytes or complete source-vintage snapshots are certified.** Those dates are *stated publisher release dates on currently served web pages*, not independently archived point-in-time source bytes.

## Cumulative research scope

Previous PR #587: 9 Jan–Sep 2026 reference months, 18 standard flash/detailed reports, 2 exceptional corrigenda. This new addendum yields **10 reference months (Dec 2025–Sep 2026)**, **20 regular release events**, **2 exceptional corrigenda**, **120 reported selected annual-rate value slots across stages**, plus 2 retrospective December reference statements (which do **not** count as independent new economic reference months).

At least **15 monthly first-release reference periods short** of 25 in the research target, on top of missing immutable original-day source archive, all revisions, and validated comparability. The headline flash→detail revisions now include **Dec 2025 −0.1 pp, Mar 2026 +0.1 pp, Aug 2026 −0.1 pp**. All other recorded monthly headline pairs are unchanged at the displayed 0.1pp precision.

**No production mutation:** the macro scores, D.json, 28 FX pair rankings, Control Room, live_data/site/payload/dashboard, backtests and schedulers are untouched. Research receipts are written only under `/tmp`.

## Reproduce

```bash
python -m unittest validation.macro.test_v2_eurostat_dec2025_regime_bridge_replay_v1 -v
python -m validation.macro.v2_eurostat_dec2025_regime_bridge_replay_v1 \
  --asof 2026-02-04T23:59:59Z --out /tmp/macro-v2-shadow/dec-before-later-retrospective.json
python -m validation.macro.v2_eurostat_dec2025_regime_bridge_replay_v1 \
  --asof 2026-10-24T00:00:00Z --out /tmp/macro-v2-shadow/dec2025-sep2026-boundary-web-replay.json
```
