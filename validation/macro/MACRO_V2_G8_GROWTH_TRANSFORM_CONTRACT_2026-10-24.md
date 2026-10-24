# Macro V2 — G8 Growth feature-definition and point-in-time transformation gate

**24 October 2026 · Shadow research only. No model score/FX update.**

## What PR #592 accomplished, and what is different now

PR #592 connected official publisher **candidate event streams for all 24/24 G8 currency–pillar slots**, but it did not select the canonical Growth factor. This research package now defines a **proposed algebraic interpretation for every one of the eight Growth inputs** and tests its ability to run on a properly dated first-release/revision ledger, without pretending that the currently available revised `MACRO_SERIES.json` history was historically observable.

**Crucial separation:** “24/24 official evidence streams connected” is NOT “24/24 series with a certified PIT model”. The shared source controller provides **one initially web-attested Growth period for each FX currency**; that is insufficient to estimate a historical time-normalised macro factor.

## Eight bounded observed candidates, three distinct economic horizons

| Currency | Existing observed Growth series | Published data type | Proposed *descriptive* research transform | Current-history rows (**revised, not vintage**) |
| --- | --- | --- | --- | ---: |
| 🇺🇸 USD | `US_INDPRO_history_value` | SA industrial output index, 2017=100 | **3-month mean / preceding 3-month mean −1** | 82 |
| 🇪🇺 EUR | `EA_IP_history_value` | SA industrial production index, 2021=100 | Same index **3m/3m** concept; *not* July publisher −0.1/−0.3% MoM | 82 |
| 🇬🇧 GBP | `UK_PRODUCTION_history_value` | Industrial production index | Same index **3m/3m** concept, publisher 3m/3m percentage kept separate | 82 |
| 🇯🇵 JPY | `JP_IIP_history_value` | SA industrial production index, 2020=100 | Same **3m/3m** concept, without treating May's 103.0 publisher figure as July's 104.4 vintage | 82 |
| 🇨🇭 CHF | `CH_PRODUCTION_history_value` | Industrial production index, 2021=100 | Same **3m/3m** index feature, *not* SECO sports-adjusted quarterly GDP +1.5% | 82 |
| 🇨🇦 CAD | `CA_REAL_GDP_M_history_value` | Chained-2017-dollar **monthly GDP level (SAAR)** | **3m/3m** from compatible monthly real GDP levels; not substitute the +0.3% MoM headline | 82 |
| 🇦🇺 AUD | `AU_REAL_GDP_QOQ_ABS_history_value` | SA real GDP quarterly **QoQ percentage**, June quarter | Preserve **QoQ rate** as reported; cannot invent monthly GDP first releases | 33 |
| 🇳🇿 NZD | `NZ_REAL_GDP_Q_history_value` | SA real GDP **same-quarter YoY percentage**, June quarter | Preserve **YoY rate** as reported; cannot directly compare with AUD QoQ | 42 |

Total original observed-series history lengths = **567 current/revised datapoints**, not 567 independently archived first-release vintages. Those source histories are used here **only to validate names, frequencies, periods, values, contiguity and units**; they do **not** feed a Growth score or its standardisation.

This is a **proposed research proxy mapping, not a definitive preference for industrial production over GDP**. Industrial production is a narrower measure than GDP and can lead or lag its services-heavy broader economy. Canada already uses monthly GDP, whereas AUD/NZD currently have quarterly GDP; full G8 economic equivalence is **unresolved** even with a comparable mathematical formula.

## Pure formula verification (source-vintage input only)

For a monthly, strictly-positive seasonally-adjusted output level stream, the proposed *quarter-equivalent* real-activity rate is:

[
g_{3m/3m,t} = 100 left( rac{x_t + x_{t-1} + x_{t-2}}{x_{t-3} + x_{t-4} + x_{t-5}} - 1 ight).
]

This is **not** MoM, not compounded annualized growth, and not a weighted GDP contribution. The reference-month sample must be **six strictly consecutive** monthly periods from the **same metric/source vintage known as of the particular cutoff**. Missing or future source values are rejected; no interpolation, extrapolation or fallback to contemporary revised observations.

For an already published quarterly QoQ or same-quarter YoY rate, the only permitted research transformation is **identity/pass-through of that exact statistical definition**, with a visibly different economic horizon. A YoY percentage cannot be substituted for a QoQ percentage, and neither can be treated as a monthly index level.

Example unit-test-only synthetic sequence: three months with published index 100, followed by three months at 110, yields **+10% 3m/3m** after the sixth first release. If that sixth index is subsequently revised from 110 to 121, the *same cutoff replay* continues to show +10% **until the dated revision is visible**; only after that does the descriptive value become **+13.6667%**. These are clearly labelled **synthetic values**, not reconstructed 2026 market history.

The optional pure calculator accepts explicitly supplied events (`FIRST_WEB` and `REVISION_WEB`, source timestamps including UTC offsets) and returns a **descriptive test result** with `eligible_for_macro_score=false`; caller-supplied observations are **not independently authenticated publisher archives**. The live history is **never passed** to this calculator by the CLI.

## Publisher methodology considerations

- [Federal Reserve G.17](https://www.federalreserve.gov/releases/G17/) has a **9:15 a.m.** monthly release, annual revisions, and dated historical releases. A web table publishing index 103.1 to one decimal does not attest to the original availability of a current transport reading **103.0682** with four decimals.
- [Eurostat production metadata](https://ec.europa.eu/eurostat/cache/metadata/EN/sts_ind_prod_esms_it.htm) describes seasonal/calendar adjustment and changing production index weights; the published **July MoM −0.1% → −0.3%** retrospective revision cannot be substituted for the numeric index level **98.3**. Source vintages and base breaks need independent auditing.
- [ONS Index of Production methodology](https://www.ons.gov.uk/economy/nationalaccounts/uksectoraccounts/methodologies/ukindexofproductionqmi) identifies chain volume statistics and reporting conventions. Its published July **−0.5% three-month-on-three-month** rate is not the *index* 98.5, even if it is a mathematically related concept.
- GDP levels in chained volume monetary units (CAD) and CPI/industrial production indexes must be transformed within **their original reference unit and rebasing regime**, not mixed or concatenated across indicators.

## Formal gates for any future scoring

1. **Economic concept:** decide GDP versus industrial production proxy for each economy and whether real activity growth, nowcast and GDP are separate factors.
2. **Comparable horizon:** resolve New Zealand quarterly **YoY vs Australia QoQ**, and ensure index-level 3m/3m measures are not silently pooled as identical to GDP QoQ.
3. **Publisher source map:** official source ID/units and *first-day publication precision* must match the chosen canonical series; the existing six Growth bridge mappings include multiple incompatible definitions.
4. **PIT windows:** minimum **25 actual monthly or 13 quarterly first-release periods per selected metric**; additionally retain the full *as-of release/revision chain*. The **82/33/42 revised point histories do not qualify**.
5. **Country-specific calibration:** only after source/vintage review consider levels, direction, acceleration, regime breaks and standardized percentiles, with independent validation of old regime versus post-rebase data.
6. **Model scoring:** new weights/polarity, 8-currency rankings, 28 FX pairs and backtests require an explicit separate design audit and approval.

**All 8 Growth canonical selections remain unresolved; all 8 Growth score gates remain BLOCKED.** The engine never updates `D.json`, `live_data/`, `site/`, `payload/`, `dashboard/` or the public Control Room and does not add scheduled tasks.

## Reproduce

```bash
python -m unittest validation.macro.test_v2_g8_growth_transform_proposal_gate_v1 -v
python -m validation.macro.v2_g8_growth_transform_proposal_gate_v1 \
 --json-out /tmp/macro-v2-shadow/g8-growth-feature-proposal.json \
 --markdown-out /tmp/macro-v2-shadow/g8-growth-feature-proposal.md
```

All receipts are **read-only research** and writeable **only under /tmp**. The CI executes this contract before the external Dukascopy availability probe to fail fast on wrong units, data revisions, pseudo-release timestamps, future-data leaks or source-to-series confusion.
