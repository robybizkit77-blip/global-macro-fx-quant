# Japan MoF 2Y — lossless date/value reconciliation (26 October 2026)

## The actual defect

The existing `live_data/sections/NATIVE_RATES_DATA.json` JPY 2Y observation history has **273** `(date,yield)` entries. Of these, **246** use noncanonical unpadded strings (for example `2025-6-2` rather than `2025-06-02`), and **30** positions go chronologically backward after normalizing the date text. The pattern indicates **lexicographic string sorting**, not necessarily an erroneous original JGB yield value. The producer/collector root cause still requires identification.

**Example:** `2025-6-2` sits after `2025-6-19` in the source's original list. Simply sorting dates and leaving the yield array in its old order would **corrupt every linked interest-rate observation**.

## Conservative, data-preserving resolution

The new tool `validation/rates/audit_jpy_2y_mof_chronology_v1.py` creates only a **candidate research receipt** under `/tmp`. It reads every original `(date, yield)` tuple, validates numeric values and calendar dates, normalizes each date to `YYYY-MM-DD` and sorts the intact tuple as a unit. It refuses duplicate normalized dates, weekends, unbalanced arrays, nonfinite yields or source-as-of conflicts. No values are smoothed, interpolated, overwritten or backfilled. The candidate carries the original source JSON history SHA-256, original row indices and unchanged yield values for traceability.

The candidate is deliberately **NOT promoted** to the active `live_data/` JPY history, Beta OOS, the 28 pairs, Core or public dashboard until independent publisher reconciliation.

## Independent official source audit

Official original Ministry of Finance, Japan CSV datasets:

- [Full historical archive](https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv) — historical `Date,1Y,2Y,...` source.
- [Current-month archive](https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv) — current-month `Date,1Y,2Y,...` source.
- [MoF interest rate methodology](https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/qa.htm) — official daily JGB constant-maturity curve construction based on transaction reference yields.

An independent CSV comparator reads original **CP932** publication bytes and selects the explicitly labelled `2Y` column, interpreting day strings `YYYY/M/D` or Japanese era `R8.10.21` when present. It demands all **273** original candidate date-value points agree with official independently downloaded data (0.0005 percentage-point tolerance for 3-decimal printed yields). Any official missing date, difference, missing source, inconsistent overlap, duplicate or unparseable file **blocks certification**.

The PR CI has an independent network step for these official original URLs. If the Ministry site cannot be reached or even a single row disagrees, the publisher state is **NOT VERIFIED** and the candidate remains quarantined; the offline unit tests may still pass, but **that is not certification of the JPY source**. Downloaded publisher bytes remain under `/tmp`; the workflow does not publish or redistribute their contents.

## Actual independent original-source CI attestation — 26 October 2026

The [official JGB archive](https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv) and [current file](https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv) were both retrieved independently in GitHub Actions; source SHA-256s were captured in the CI receipt. The **first** historical mirror comparison returned **271 / 273** source matches, not 273 / 273. The two official-source conflicts were:

| Historical date | Stored initial 2Y % | Official MoF latest release 2Y % | Difference |
|---|---:|---:|---:|
| 2026-09-25 | 1.925 | 1.948 | +2.3 bp |
| 2026-09-28 | 1.950 | 1.981 | +3.1 bp |

The repaired **research-only** candidate then replaced exactly these two source values with the independently downloaded official publisher data, without changing any other 271 observations. Its full **second** publisher comparison passed **273 / 273**. **Original site data, original Core, existing Beta run and 28 pair ranking remain unchanged.**

This is a validated agreement **against the MoF files retrieved in the CI run**, not independent certification of first-release vintage as actually known in September (the publisher may revise historical values). No original publisher bytes are redistributed. An added third mismatch or missing publisher date is a hard blocker, not silently patched.

Run with publisher original files:
```bash
python -m validation.rates.audit_jpy_2y_mof_chronology_v1 \
  --historical-csv /tmp/jgbcme_all_official.csv \
  --current-csv /tmp/jgbcme_current_official.csv \
  --reconcile-reviewed-two \
  --out /tmp/jpy-2y-official-reconciled.json
```

## Research Beta status

`validation/beta/weekly_fx_2y_shadow_oos_v1.py` currently quarantines JPY 2Y when its source chronology violates strict ISO. The seven affected cross pairs remain excluded until the original official CSV comparisons pass *and* the source builder can fix the actual daily chronology without ever pairing a yield with another day. Independent historical first-release PIT timestamps, rate basis comparability and true predictive performance **remain unverified** even if all 273 observations agree.

## Reproduce

```bash
python -m unittest validation.rates.test_audit_jpy_2y_mof_chronology_v1 -v
python -m validation.rates.audit_jpy_2y_mof_chronology_v1 \
  --out /tmp/jpy-2y-normalized-candidate.json

# Independently acquired original official publisher bytes only:
python -m validation.rates.audit_jpy_2y_mof_chronology_v1 \
  --historical-csv /tmp/jgbcme_all_official.csv \
  --current-csv /tmp/jgbcme_current_official.csv \
  --out /tmp/jpy-2y-mof-verified.json
```

No GitHub schedules are created; no live 2Y history, scoring, forward or dashboard artifacts are changed. A future PR may promote the verified, immutable (date,yield) candidate and add regression protection to the source importer after independently resolving the producer root cause.
