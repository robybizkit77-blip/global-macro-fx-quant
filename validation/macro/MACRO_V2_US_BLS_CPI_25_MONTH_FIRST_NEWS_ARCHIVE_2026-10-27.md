# Macro V2 — BLS original CPI news-release issuer audit, 25 calendar months

**Evidence researched 27 October 2026. Research-only, no live model changes.**

## What was actually acquired as evidence

We located the official [BLS archive index](https://www.bls.gov/bls/news-release/cpi.htm)
for all 25 calendar economic months September 2024–September 2026.
**24** all-items CPI release links exist. All **24** archived BLS HTML
release pages are now accessible via the official BLS publisher pages
indexed in web search. Their contemporary all-items **seasonally adjusted,
one-decimal percentage changes** were read. The three initially unresolved
economic periods were recovered on 27 October 2026:
November 2024 **+0.3%** ([11 Dec 2024](https://www.bls.gov/news.release/archives/cpi_12112024.htm));
December 2024 **+0.4%** ([15 Jan 2025](https://www.bls.gov/news.release/archives/cpi_01152025.htm));
July 2025 **+0.2%** ([12 Aug 2025](https://www.bls.gov/news.release/archives/cpi_08122025.htm)). The original
HTML raw bytes were **not downloaded and SHA-256-archived**; therefore the
HTML-opened records are NOT byte-captured first-release primary artifacts.

October 2025 has **no BLS all-items CPI release or full original all-items
SA index**. That is a structural source gap, not a connectivity error;
see [BLS shutdown FAQ](https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm)
and [BLS revised schedule](https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm).
November 2025's original report explicitly quotes **+0.2% across TWO
months (September to November)**, *not* +0.2% November month-over-month:
[December 18, 2025 original report](https://www.bls.gov/news.release/archives/cpi_12182025.htm).
The December 2025 first reported 1-month SA change is separately +0.3%
([January 13, 2026](https://www.bls.gov/news.release/archives/cpi_01132026.htm)).

Independently cross-checked anchors:

| Economic month | Original issuer HTML | SA all-items change in that release | Unlike NSA YoY |
| --- | --- | --- | --- |
| 2024-09 | [10 Oct 2024](https://www.bls.gov/news.release/archives/cpi_10102024.htm) | +0.2% over 1 month | 2.4% NSA YoY |
| 2025-09 | [24 Oct 2025](https://www.bls.gov/news.release/archives/cpi_10242025.htm) | +0.3% over 1 month | 3.0% NSA YoY |
| 2025-10 | No all-items publication | Missing, **not zero** | Missing |
| 2025-11 | [18 Dec 2025](https://www.bls.gov/news.release/archives/cpi_12182025.htm) | +0.2% over **2 months** | 2.7% NSA YoY |
| 2026-09 | [14 Oct 2026](https://www.bls.gov/news.release/archives/cpi_10142026.htm) | +0.6% over 1 month | 3.7% NSA YoY |

## Critical identity and first-vintage limitation

**Core canonical inflation metric:** `CPIAUCSL`, seasonally adjusted *index*
level and annual index transformation. BLS issuer series equivalent:
`CUSR0000SA0` (BLS identifies the third character S as seasonally
adjusted). The **NSA** all-items series `CUUR0000SA0` and the popular
12-month *unadjusted* news headline are **not** substitutable.
See [BLS series IDs](https://www.bls.gov/cpi/factsheets/cpi-series-ids.htm).

Rounded contemporaneous SA monthly changes are useful primary-publisher
context, but cannot reconstruct exact three-decimal SA index levels or
precise 12-month SA growth rates. The BLS revises seasonally adjusted
history annually, typically across five preceding years. The [ALFRED
CPIAUCSL release-day pilot](v2_us_cpi_alfred_release_day_pilot_v1.py)
is **a separate Fed mirror**, not BLS first-published raw bytes.

Even with all 24 links verified, only **23 of the 24 preceding calendar
months** to September 2026 have original first-release reports because
October 2025 does not exist. One of those 23, November 2025, reports a
two-month change, while three other reports are index-only in this audit.
Neither 24 consecutive canonical issuer first-vintages nor a precise
replayable 24-month PIT normalization has been established.

## Reproducible deliverables / invariants

- `fixtures/v2_bls_us_cpi_25_month_first_news_release_ledger_2026_10_27.json`: per-month issuer archive URL, publication day, strength of evidence, 1- vs 2-month percentage-change horizon, null source hash and null exact SA index.
- `v2_us_bls_cpi_first_news_archive_v1.py`: isolated, deterministic validation and source-quality receipt; rejects imputed October, unverified index-only numbers, 2025-11 duration substitution, NSA/SA ID swaps, duplicate dates and fabricated hashes.
- `test_v2_us_bls_cpi_first_news_archive_v1.py`: adversarial tests.
- `v2_g8_24_axis_training_history_gap_audit_v1.py`: nests the receipt **separately**, with zero promotion of a first-released `CPIAUCSL` level.

The existing **22/24 numerical initial-web G8 audit remains unchanged**,
and the historic PIT-certified model score count remains **0**. No
`D.json`, pair scoring, source-registration identity, Beta, Forward,
website, daily schedule, OIS or Rates fields are modified.

**Next research:** acquire and checksum original contemporaneous
`CUSR0000SA0` index vintages for months with actual publication, check
first-release day, initial historical seasonal revisions, and carry the
unpublished Oct-2025 gap as a structural missing period. No automatic
upgrade to 24-month consecutive training permitted.

## Original CPI-U supplementary vintages — feasibility assessed 27 October 2026

BLS explicitly maintains [archived supplemental CPI files](https://www.bls.gov/cpi/tables/supplemental-files/home.htm)
with individual **2025/2026 issue-month XLSX** files (CPI-U and Historical CPI-U)
and a consolidated **2024 archive ZIP**. It also preserves annual
[seasonal-adjustment revisions](https://www.bls.gov/cpi/tables/seasonal-adjustment/)
(e.g., the February 2026 replacement of 2021–2025 adjusted values). These
are the appropriate original-publisher candidates for testing precise
issue-time `CUSR0000SA0` index histories.

**No official original XLSX/ZIP bytes were successfully acquired or
checksummed in this recovery.** The 2026-09 issuer XLSX could be identified
by URL, but the research fetch environment could not download the binary.
ALFRED `CPIAUCSL` historical-vintage exports remain an independently
maintained Fed mirror and were also not acquired in this recovery. No
backtest, intraday vintage assertion, or canonical issuer first-vintage
approval follows from the mere existence of archive URLs.

A follow-up byte-level recovery must parse the exact all-items **SA**
index levels (not the unadjusted CPI-U table index), match each document's
reference/issue month, retain raw bytes + SHA-256, and compare issuer
vintage versus any ALFRED snapshot at the same publisher release date.
The archived publisher warns that supplemental files can include
subsequent revisions, so a contemporary issue-month file must be
independently checked for accidental 2026 backfill. The 2025-10
all-items data remain structurally unpublished: never invent or
interpolate them, and do not call the research 24/24 PIT-ready.
