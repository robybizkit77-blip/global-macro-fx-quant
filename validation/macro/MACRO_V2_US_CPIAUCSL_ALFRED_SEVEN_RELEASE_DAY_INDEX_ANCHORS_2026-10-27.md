# Macro V2 — US CPIAUCSL: seven release-day exact SA-index anchors from ALFRED

**27 October 2026 · read-only research.** Supersedes no BLS primary issuer archive.

## Why this is a separate evidence type

The 24/24 BLS contemporary CPI original **HTML news releases** in
`v2_us_bls_cpi_first_news_archive_v1.py` establish rounded, seasonally
adjusted **percentage changes**, not the precise historical release-day
**SA all-items index**. The model's `CPIAUCSL` transformation depends on
SA index levels, and yearly BLS seasonal reestimation revises the previous
five years. See [BLS seasonal adjustment policy](https://www.bls.gov/cpi/seasonal-adjustment/)
and [BLS archived CPI supplemental files](https://www.bls.gov/cpi/tables/supplemental-files/home.htm).

The Federal Reserve Bank of St. Louis **ALFRED** has a web-facing original
*release-date* selector. At each specific historical date it displays
`CPIAUCSL`, "Monthly, Seasonally Adjusted", the last newly reported
economic observation and its exact 3-decimal SA index. These observations
were manually checked on the release-day ALFRED HTML page on 27 October
2026, **not** captured by contemporaneous HTTP 2024/25/26 snapshots.

## Seven independently checked Fed release-page anchors

| Economic month | Release date | ALFRED last observation CPIAUCSL SA INDEX |
|---|---|---:|
| 2024-10 | [13 Nov 2024](https://alfred.stlouisfed.org/release?rd=2024-11-13&rid=10) | 315.454 |
| 2024-12 | [15 Jan 2025](https://alfred.stlouisfed.org/release?rd=2025-01-15&rid=10) | 317.685 |
| 2025-07 | [12 Aug 2025](https://alfred.stlouisfed.org/release?rd=2025-08-12&rid=10) | 322.132 |
| 2025-09 | [24 Oct 2025](https://alfred.stlouisfed.org/release?rd=2025-10-24&rid=10) | 324.368 |
| 2025-11 | [18 Dec 2025](https://alfred.stlouisfed.org/release?rd=2025-12-18&rid=10) | 325.031 |
| 2025-12 | [13 Jan 2026](https://alfred.stlouisfed.org/release?rd=2026-01-13&rid=10) | 326.030 |
| 2026-08 | [11 Sep 2026](https://alfred.stlouisfed.org/release?rd=2026-09-11&rid=10) | 334.131 |

Values were extracted from the `CPIAUCSL` **seasonally-adjusted monthly
index** entry, not the adjacent CPIAUCNS unadjusted index, the annual
headline, or the Core CPI excluding food and energy. The `2025-11`
mirror issue-day value **325.031** must NOT be replaced with a later
seasonally revised value as if it had already been known that day.
Similarly `2025-12` first date **326.030** is a separate vintage.

**Crucial limit:** these are **seven standalone last economic observations
only**, not the 12-month *matched vintage base index* needed to compute
exact SA year-over-year growth at each release date. They are Federal
Reserve ALFRED mirror display values, not original publisher BLS
XLSX/ZIP bytes or archived full ALFRED historical vintage CSV files.
No original SHA-256s have been acquired. Release-day index levels might
also reflect Fed ingestion timing; the exact intraday issuer availability
is not established. They are valuable evidence but **not PIT trading
certification**.

## Structural October 2025 source gap

The [BLS archived supplemental-file index](https://www.bls.gov/cpi/tables/supplemental-files/home.htm)
says October 2025 tables were not published owing to the funding lapse.
ALFRED's Nov-2025 report shows two new/revised observations on the
18 December 2025 release date and **cannot be reverse-engineered into
a valid original October 2025 all-items figure**. No October value,
historical SA index or one-month rate is imputed anywhere.

## Verified restrictions and next useful work

- `fixtures/v2_us_cpiau_alfred_seven_release_day_html_index_2026_10_27.json`:
  exact source-link and issue-date anchors with all issuer-byte hashes null
  and all original BLS certification flags false.
- `v2_us_cpiau_alfred_seven_release_day_index_v1.py`: checks against 24
  archived BLS issue dates, values, metric ID, publisher mismatch, missing
  2025-10 and strict no-score / no-live-output gates.
- `test_v2_us_cpiau_alfred_seven_release_day_index_v1.py`: adversarial
  falsification of future leakage, revised vintage overwrites, NSA switch,
  forged BLS raw-byte attestations and fabricated 2025-10.
- Attached to existing `v2_g8_24_axis_training_history_gap_audit_v1.py`
  **separately**, with no promotion of any canonical original BLS
  source-day index history.

The next decisive objective is acquiring and hashing each original BLS
issue-month companion XLSX/ZIP, extracting **CUSR0000SA0** SA index and
12-month SA base, and independently checking the ALFRED release-day
mirror values. If full binaries are unavailable, explicitly label
the mirror as an independent estimate/source of limited provenance,
rather than mark it as complete training data.

**Invariant:** research `22/24` G8 first-web numeric windows remain
`22/24`, research `0/24` first-vintage PIT-complete model training
windows and `0` FX scores authorised. No `D.json`, 28-pair
ranking, Beta/Forward, website, Rates, schedules or live data modified.
