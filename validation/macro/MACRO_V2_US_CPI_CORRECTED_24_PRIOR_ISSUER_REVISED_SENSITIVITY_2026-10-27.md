# Macro V2 · CPI USA: corrected 24 **preceding** published months and vintage stress-test
**27 October 2026** · Research-only, no model/Beta/Forward/FX/live deployment.

## Correction after PR #724/#725

The 24 official BLS `cpi-u-YYYYMM.xlsx` issuer-month spreadsheets covered
September 2024–September 2026, with October 2025 not published. This
is **24 published observations INCLUDING current September 2026**. It is
**only 23 preceding published observations**. It is wrong to use that
24th current observation as its own historic training value.

The official [August 2024 BLS release](https://www.bls.gov/news.release/archives/cpi_09112024.htm)
was **September 11, 2024**. We now downloaded and verified the publisher's
[August 2024 original-issue-month XLSX](https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-202408.xlsx)
in one-time research CI on **27 October 2026**:
[receipt and XLSX artifact](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40597149084).

- Economic month Aug 2024, SA All-items `CUSR0000SA0` index **314.121**.
- **Same issuer-month** 12-month SA index denominator **306.187**.
- Index-based SA YoY (NOT published NSA headline YoY): **2.591227%**.
- Raw XLSX SHA-256 `41f4de5b7035be83cec85fca05d2339bd929290683206846f9b43b46d84a3a4d`; **150,338 bytes**.
- Raw XLSX downloaded 27 Oct 2026, **NOT** in September 2024; cannot
  claim BLS's 2024 release-day original bytes were independently archived.

**Correct training:** from August 2024 through August 2026 there are
**25 calendar months**, one unpublished October 2025, and **24 actual
preceding published BLS observations**. Latest September 2026 is the
separate 25th *published* observation and must remain EXCLUDED from
the median/MAD training. This remains **24 in 25**, not **24 consecutive
calendar observations**; any strict completeness or PIT-original gate
remains unchanged.

## Quantified first-issue-month versus revised-history Z-score sensitivity

For every published prior month, calculated `100*(SA_index / same-edition
SA_index_12_months_prior-1)` from the corresponding issuer-month BLS XLSX
captured on Oct 27. Compared it with the analogous SA index-based YoY
recomputed from the *single current-revised* `US_CPIAUCSL_history_value`
snapshot in the existing repo at the Oct 26 cutoff (Git blob
`0110d62ab38f9d6eb195114bcd8e0deddcf04c99`).
Both use identical 24 previously published **economic months**; one
historical publication month (October 2025) remains missing; September
2026 is compared out-of-sample from these 24 training values.

Use median and `MAD = median(abs(x - median))`,
then `Z = (current YoY - median prior 24) / (1.4826*MAD)`, clipped to ±3.
These are **DESCRIPTIVE SHADOW Z** and not trading/model signals.

| CPI SA index-based statistic | Individual BLS issue-month candidate values | Current-revised CPIAUCSL |
|---|---:|---:|
| Latest Sep-2026 SA YoY | 3.717251% | 3.717251% |
| Training median | 2.732190% | 2.731045% |
| Training MAD | 0.294348 pp | 0.294284 pp |
| Research Z-score | **+2.257242** | **+2.260357** |
| Z-score difference (issue minus revised) | **−0.003115** | — |

The average ABS difference of the 24 historical index-based YoY readings
is **0.006904 percentage points**, maximum **0.025902 pp**;
**zero** prior months exceed 0.05 pp.
The *direction* of this single Sept 2026 research inflation descriptor
therefore agrees under both methods.

**But:** an issuer-month XLSX downloaded in 2026 does NOT certify that
its binary contents were exactly those available during the original
release hour. The first-issue-month records are candidate historical
issue-month evidence, **not a fully proven PIT vintage dataset**. More
important, the 2025-10 all-items CPI data never existed as a published
observation, and no method can manufacture original observations.

## Enforced quality gate and suggested project decision

- `fixtures/v2_us_cpi_24_prior_month_issuer_vs_revised_shadow_sensitivity_2026_10_27.json`:
  25 published-month evidence rows (24 prior + Sep-2026 current),
  exact first-issue source XLSX SHA, SA index/12-month bases, frozen
  current-revised counterparts and robust-Z receipt.
- `v2_us_cpi_prior24_issuer_revised_sensitivity_v1.py`:
  independent source/provenance and numerical verification, no writes.
- `test_v2_us_cpi_prior24_issuer_revised_sensitivity_v1.py`:
  adversarial missing-month, 24 previous vs latest leakage,
  manipulated BLS SHA, revised source backdating, wrong YoY index,
  score guards and production file immutability.
- `v2_g8_24_axis_training_history_gap_audit_v1.py`:
  label and attach separately; compare revised research Z to the
  **existing** US CPI shutdown-gap proxy (no duplicated model).
- `one_shot_us_blscpi_aug2024_prior24_source_v1.py`:
  optional manual source acquisition only; workflow removed after success.

This closes the **sample-count mistake and source-method sensitivity**
for the Sept 2026 US CPI comparison. It does **not** improve 22/24
first-web numeric G8 source-window coverage; there are still **zero**
fully historically PIT-certified complete training vectors. The
existing estimated USD inflation proxy can remain visibly available
for qualitative interpretation, with its quality flags.
**No Core `D.json`, 28 pairs, beta, forward, dashboards or scheduler changes.**

Remaining blocker for strict historical model training is not the
Sept 2026 direction of inflation; it is guaranteed prior-day source
availability/revision provenance and structurally unpublished Oct 2025.
Do not spend repeated iterations pretending a perfectly strict
24-consecutive first-release series can be reconstructed for this sample.
