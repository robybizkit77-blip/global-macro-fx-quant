# EURJPY Beta 2Y source audit — 26 October 2026

## Root cause proven against both original publishers

- Existing ECB FX reference history, ECB EUR AAA Svensson 2Y mirror and independently downloaded Japan MoF JGB 2Y had **58 business-week periods** (Sep 2025–Oct 2026), but only **57** with at least one common exact FX/EUR2Y/JPY2Y observation date.
- The sole missing common week was **ending 25 September 2026**:
  - ECB EUR 2Y mirror: **21 and 22 September** only.
  - MoF JPY 2Y: **24 and 25 September** only.
  - ECB FX: 21, 22, 23, 24, 25 September.
- Thus the longest continuous triple-date run was **53 weeks** rather than the **54 weekly fixing anchors** required to fit 52 previous weekly returns and test one subsequent week.

## More serious source discrepancy (full independent ECB audit)

The official, unchanged series identifier is **YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y** (ECB AAA euro area Svensson 2Y spot yield), retrieved as original CSV from the ECB data API on 26 Oct 2026:

`https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y?startPeriod=2025-09-16&endPeriod=2026-10-22&format=csvdata`

Independent payload SHA256: `2d5b0e884b0d3728c29d935e0982e761896102bd401f4ae406a17680f6079bab`.

| Comparison | Result |
|---|---:|
| Official 2Y observations | 282 |
| Current repo EUR 2Y history observations | 271 |
| Same-day overlaps | 271 |
| Same-day mismatches | **260** |
| Dates missing in mirror, present at ECB | **11** |
| Largest absolute same-day difference | 15.52485 basis points |
| Median absolute difference among mismatches | 8.6055 basis points |
| 21 Sept repo vs ECB official | 3.2598888904% vs **3.1476088412%** |
| 22 Sept repo vs ECB official | 3.2487042718% vs **3.1355631320%** |
| 22 October last stored/current official observation | 3.0074951382% (equal) |

The 11 missing dates are **2026-09-23/24/25/28/29/30** and **2026-10-05/07/08/09/12**. Existing 2Y history cannot be labelled as numerically equivalent to the exact ECB series without source producer and transformation remediation. These mismatches may reflect a different fitted-curve definition, earlier source vintage, wrong transport or processing; **none of those explanations is proven yet**.

A proposed patch that would add only three missing September dates was correctly **rejected**, because even the two overlapping existing September dates disagreed by over 11bp with the independently obtained original ECB series. No silent backfilling or acceptance of misidentified rates is permitted.

## Proven read-only shadow recovery

The module `validation/beta/audit_ecb_eur2y_official_mirror_parity_v1.py` first performs the source-comparison audit, then can substitute the **full set of 282 original official ECB 2Y observations in memory only**, independently accompanied by the **original MoF full JPY 2Y official source files** already reconciled 273/273 in PR #639. The unchanged Beta estimator uses 52 previous complete, consecutive weeks for each held-out observation.

Actual independent GitHub Actions results on 26 Oct 2026:

- **EURJPY: 5 historical held-out weeks**.
- **28/28 FX G8 pairs** now have at least one historical pseudo-OOS observation.
- **15/28 pairs** have at least four held-out weeks for a descriptive (not statistically validated) variance comparison.
- All changes are **research-memory only**: zero `live_data/` changes, zero site publication, zero pair score/weight effects, zero new Core signals, zero actual trading return or backtest certification.
- This is **pseudo-OOS** on current publisher historical values. Historical first-availability PIT timestamps are not established, neither is like-for-like economic benchmark comparability of ECB Svensson, US Treasury par yields, Japan MoF reference JGB curve, etc.

**Critical remaining launch-blocking data-quality task:** locate and repair the source producer of the persisted EUR 2Y historical mirror, determine why the 260 historical values differ from the exact official ECB series, and revalidate the complete affected 2Y / 10Y snapshots and any active published calculations before declaring market-data quality certified. The primary site stays unchanged while a complete impact audit is pending. Do not suppress this finding to report 28/28 research coverage as a finished validated Beta.

## Repeat the independent official audit

```bash
python -m unittest validation.beta.test_eurjpy_weekly_calendar_forensics_v1 -v
python -m unittest validation.beta.test_eurjpy_ecb_2y_official_bridge_v1 -v
python -m unittest validation.beta.test_audit_ecb_eur2y_official_mirror_parity_v1 -v
```

For the real publisher, run the PR CI `EURJPY Official Weekly 2Y Alignment Audit`, which downloads the precise original ECB CSV and the two original MoF JGB 2Y CSVs, checks their series/date/value provenance and performs full read-only shadow recalculation. Its 28/28 read-only result is **not** automatically applied to the published site or trading model.
