# Macro V2 — G8 Growth comparability cohorts and frozen-as-of rolling normalization

**24 October 2026 · Research methods only · NOT a score, PIT source certification or model activation**

## Aim

The prior [eight-currency Growth transform contract](./MACRO_V2_G8_GROWTH_TRANSFORM_CONTRACT_2026-10-24.md) defined six monthly `3m/3m` candidates, one AUD GDP quarterly QoQ candidate, and one NZD GDP quarterly same-quarter YoY candidate. Merely applying the same mathematical formula or country-specific standardization **does not make industrial production economically equivalent to GDP**, nor does it turn a later-revised historical series into a valid as-of trading signal.

This additional gate makes those distinctions machine-testable and introduces **pure, source-snapshot-supplied rolling normalization**, with no live-data factor calculation.

### Four distinguishable statistical/economic cohorts

| Cohort | FX members | Numeric interpretation | Limitation |
| --- | --- | --- | --- |
| Industrial production | 🇺🇸 USD, 🇪🇺 EUR, 🇬🇧 GBP, 🇯🇵 JPY, 🇨🇭 CHF | Monthly SA production level, proposed trailing 3-month mean versus prior 3-month mean | This is **industry**, not total GDP or domestic demand; national weights/sector composition and original-release sources still differ |
| Real GDP by industry | 🇨🇦 CAD | Official monthly GDP-by-industry level, expressed as chained-dollar annual-rate level; same 3m/3m calculation | National accounts, broader economic coverage; not identical to industry-only output |
| Quarterly real GDP QoQ | 🇦🇺 AUD | Released QoQ percent quarterly real GDP | Distinct report frequency and horizon; never treat as monthly IP |
| Quarterly real GDP YoY | 🇳🇿 NZD | Released year-on-year percent for same quarter of previous year | **Different horizon** from AUD QoQ and the overlapping monthly rolling 3m/3m |

Two currencies can share a **cohort** as a mathematical definition while still lacking an approved **cross-country economic or model ranking**. Equal z-scores can mean equally unusual conditions *relative to each country's own past*, not equal GDP growth or currency attractiveness.

An overlapping monthly `3m/3m` rate is especially **not the same as official quarterly GDP QoQ** at arbitrary calendar-month endpoints. Even at a quarter end, an IP index is not GDP. Converting NZD YoY GDP into QoQ requires valid **same-vintage quarterly level observations** or a separately audited compatible bridge. No division of YoY by four, annualization shortcut, or mixing current historical levels is permitted.

### Frozen-as-of normalization math

For a source-consistent published **descriptive feature** (f_t) at time (T), use **only (N) strictly earlier** first-release/as-of feature snapshots (f_{t-N},...,f_{t-1}), each frozen at **its own historical cutoff**. Do **not** refit their vintage using today's revised source data.

[
mu_{t-1} = rac{1}{N}sum_{i=1}^{N}f_{t-i},
qquad
sigma_{t-1}=sqrt{rac{1}{N}sum_{i=1}^{N}(f_{t-i}-mu_{t-1})^2},
qquad
z^{research}_t=rac{f_t-mu_{t-1}}{sigma_{t-1}}.
]

- Prototype requirement: **(N=25) earlier frozen monthly *feature observations*** or **(N=13) earlier quarterly *feature observations***, with **no gaps** in the corresponding period grid and positive historical dispersion. This is deliberately more conservative than the prior source-readiness minimum of 25 monthly / 13 quarterly **first-release raw observations**: a monthly 3m/3m feature needs six source levels before the *first* feature, then **25 previous feature periods plus one current** for the proposed rolling normalization. A genuine contiguous first-release calendar plus complete revision lineage remains necessary.
- The **current feature is excluded from its own mean/standard deviation**. No future release, future revision, duplicate period, cross-metric family, mixed USD/GBP first-release record, unqualified same-quarter YoY in QoQ samples, or retrospective recomputation is accepted.
- If historical periods are missing, the variance is zero/nearly zero, timestamps are inconsistent, or economic definitions differ, the normalization stays **unavailable** rather than producing a misleading z-score or defaulting to some revised dataset.
- The synthetic test produces a reported z-score from **hypothetical frozen features** only. It independently enforces `source_original_day_archive_verified=false`, `certified_for_macro_scoring=false`, `recomputed_using_later_vintages=false`. A boolean self-declaration in a record is **not proof** of actual source archive authentication.

### Historical revisions: the key PIT rule

Suppose the 2026-04 period was initially known as one industrial-production reading. A later revision published in July may update the value *from July onward*. A historical `f_{April}` frozen at its April publication remains the **April-era feature vintage** when normalizing a June event. Replacing that old training observation with a new present-day replay would create an artificial historical signal.

The source-specific `shadow_math` calculation in PR #593 handles **current as-of visible monthly level revisions**. This PR adds the **separate frozen feature history** to prevent a rolling historical z-score from re-fitting earlier feature inputs with future knowledge. True publisher first-release data and independent recorded snapshots must ultimately back both steps.

### Official methodological context

- [ONS guidance on rolling 3m/3m versus quarterly GDP](https://www.ons.gov.uk/economy/grossdomesticproductgdp/methodologies/aguidetointerpretingmonthlygrossdomesticproduct) distinguishes rolling and calendar-quarter changes and notes the difference in volatility.
- [Eurostat quarterly national accounts metadata](https://ec.europa.eu/eurostat/cache/metadata/en/ei_qna_esms.htm) distinguishes q/q-1 and q/q-4 and annualized rates; chain-linked levels have specific aggregation properties.
- [OECD composite leading indicators FAQs](https://www.oecd.org/en/data/insights/data-explainers/2024/04/composite-leading-indicators-frequently-asked-questions.html) explain that seasonal filtering, smoothing, de-trending and normalization can revise historical feature signals.
- [European Commission's normalization guidance](https://knowledge-for-policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en/step-5-normalisation_en) warns that common statistical units do not remove all comparability problems.

This implementation is explicitly **not** a new OECD CLI, nowcast, factor weight model or GDP contribution score. Consumption or credit may become a separate economic driver only after original publisher, weights, compatible data semantics and historical PIT sources are added; **no consumption series was invented here**.

## CI and intended use

```bash
python -m unittest validation.macro.test_v2_g8_growth_rolling_pit_normalization_v1 -v
python -m validation.macro.v2_g8_growth_rolling_pit_normalization_v1 \
  --out /tmp/macro-v2-shadow/g8-growth-frozen-normalization-comparability.json
```

Unit tests cover 25 prior monthly feature periods, 13 prior quarters, current exclusion, synthetic future revisions, same-series and same-family constraints, missing periods, zero variance, invalid timestamps, duplicated periods, frozen-as-of chronology and immutable inputs. No real-world z-scores are generated.

The proposed research data system has **24/24 official-event candidate adapters**, but still **0/8 canonical Growth selections certified**, **0 new G8 FX Growth z-scores ready for use**, and **0 new 28-pair ranks or backtests**.

The new workflow is the existing **unscheduled** PR Macro V2 shadow CI. No site, payload, dashboard, D.json, production `live_data`, scheduler or alerts are changed. Output receipts may only be written under `/tmp`.
