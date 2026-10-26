# EUR daily source-history safeguard — 26 Oct 2026

**Purpose:** the daily official EUR 2Y/10Y publisher can advance new ECB spot yield observations, but the existing early historical EUR curve is formally **LEGACY_NOT_SAME_BASIS_WITH_VALIDATED_25SEP**. PR #642 found 260 mismatching historic EUR 2Y values and 260 for 10Y, even though latest 22 Oct ECB values agree with the official source. It would be false to relabel all 271 legacy history observations as one historical official series. The complete 282-point original ECB replacement remains staged only until visual and downstream CHF proxy review.

## Scheduled task behavior

The modified `validation/build_rates_candidate_from_audit.py` adds `eur_daily_append_source_gate()` **only when EUR is one of the official advancing updates**. It accepts a daily append solely if:

- Current source is ECB AAA Svensson official 2Y and 10Y, with `FULL_CURRENT_OFFICIAL` quality.
- Both histories have aligned, strictly increasing original ISO observation dates without duplicate or missing values.
- The eight **independently original-ECB-source checked Oct 13–22 date/value pairs for BOTH tenors** remain equal within a 0.000005 percentage-point comparison. Neither 2Y nor 10Y may silently be swapped for another curve.
- The current official rate levels agree with last original dated observations.
- A new publisher date advances normally, no more than 12 calendar days after the previous observation, and the preceding 7-calendar-day weekly reference lies **inside the publisher-verified clean suffix**, not in the heterogeneous legacy period.
- The legacy non-equivalent-history labels are preserved. An unpromoted original-publisher *research candidate* must NOT be mistaken for an officially approved new production rate basis.

When an advancing EUR snapshot fails the guard, the builder **quarantines ONLY EUR**, records the reason in the job's GitHub summary, preserves its original live snapshot, and allows other independently valid G8 countries to refresh (for example CAD). If EUR is the only attempted update, the candidate becomes `NO_UPDATES`, enabling ordinary existing date-only Rates metadata refresh. There is no fake value, source switch, 2Y/10Y average or fallback curve. Before any active EUR history promotion, this protection requires a separately reviewed source-version transition.

## Test coverage

`validation/test_eur_daily_rates_history_source_guard_v1.py` checks:
- Real current 8-date official clean tail and original non-equivalent history provenance;
- daily fresh ECB Oct23 2Y/10Y append **without pretending legacy history fixed**;
- all officially verified tail values unchanged and tampering with either tenor rejected;
- 2Y/10Y source calendars consistent and duplicate dates rejected;
- no future fabricated stale weekly reference or non-advancing official date;
- an EUR source quarantine still allows the **CAD update** to go through;
- an EUR-only blocked update leaves G8 source unchanged and permits metadata age refresh;
- no-update identity.

The scheduled workflow `.github/workflows/rates-persistent-daily-v1.yml` runs these tests as part of its preflight and writes an explicit quarantine entry to `GITHUB_STEP_SUMMARY`. Its **original cron windows and push/lease/currency publication mechanics remain unchanged**.

**Important limitations:** this is **not** an implementation or publication of the complete historical EUR source repair; the 260+260 mismatched legacy values remain labeled heterogeneous. This gate does not resolve source first-publication PIT timestamps, enable core score updates, or certify CHF 10Y reference-beta estimates. The larger v10 candidate Chromium QA remains a separate PR (#644) and must pass before any controlled published historic source change.

A passing job means the scheduled builder cannot quietly reclassify historical EUR rates, not that it restored the entire ECB history.
