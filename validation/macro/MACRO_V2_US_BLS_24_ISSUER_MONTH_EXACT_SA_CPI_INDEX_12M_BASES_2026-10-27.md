# Macro V2 — BLS exact SA CPI-U index, issuer-month XLSX study (27 Oct 2026)

## Result / quantitative identity

Retrieved **all 24 publisher CPI-U issue-month XLSX files corresponding to the
24 months actually released** within the 25 reference months September
2024–September 2026. The BLS all-items **seasonally adjusted index**
(\`CUSR0000SA0\`, FRED \`CPIAUCSL\` counterpart) was read from the explicitly
labelled *"Seasonally adjusted indexes"* column of the US *All items* row,
not the separate **unadjusted indexes** column. The same workbook contains
the SA index level of the reference month 12 months earlier; both values
were extracted at three decimals and the 12-month SA index change was
computed from that **same issuer-month document**.

**2025-10 is deliberately absent:** no original all-items CPI release,
despite the BLS's separate internal October imputation used in the seasonal
adjustment process. See [BLS shutdown FAQ](https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm).

## Evidence strength

- **24/24 released months:** publisher-hosted named \`cpi-u-YYYYMM.xlsx\`
  XLSX successfully downloaded with HTTP 200 and ZIP/workbook magic checked,
  2026-10-27 SHA-256 and byte count recorded per file.
- **24/24:** same-workbook SA current index AND SA 12-month base available.
- **7/7:** independent original release-date **ALFRED** index page observations
  match the corresponding BLS source-month *current SA* index.
- **0/24:** historic *day-of-publication downloaded BLS raw bytes*
  independently available. BLS itself warns that archived supplemental
  spreadsheets can incorporate subsequent edition revisions.
- **0/24:** certified model-ready PIT scoring windows. This result does not
  change the 22/24 previous *numeric* G8 first-web source-window count,
  which is a separate and weaker claim than PIT backtest certification.
- **No original October 2025 data** and no 24 consecutive **calendar**
  months available. The prior 24-month calendar window for September 2026
  includes one unpublished 2025-10 source month.

## Distinguishing a first-issue candidate and a revised historic value

| Economic month | Publisher issue-month source | Current exact SA index | 12-month SA base in same workbook | SA 12-month index change |
|---|---|---:|---:|---:|
| 2024-09 | [2024-09 XLSX](https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-202409.xlsx) | 314.686 | 307.288 | +2.407513% |
| 2025-09 | [2025-09 XLSX](https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-202509.xlsx) | 324.368 | 314.851 | +3.022700% |
| 2025-10 | **not published** | — | — | — |
| 2025-11 | [2025-11 XLSX](https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-202511.xlsx) | 325.031 | 316.449 | +2.711969% |
| 2025-12 | [2025-12 XLSX](https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-202512.xlsx) | 326.030 | 317.603 | +2.653312% |
| 2026-09 | [2026-09 XLSX](https://www.bls.gov/cpi/tables/supplemental-files/cpi-u-202609.xlsx) | 336.298 | 324.245 | +3.717251% |

In the **2025-11 issue** the current index is **325.031**; the later
**January 2026 edition** lists its historical November-2025 adjusted
index as **325.063**, a +0.032 index-point difference. In the September
2026 workbook the 2025-09 SA index is **324.245**, compared with
**324.368** in the original September 2025 issue-month workbook (a
-0.123 point difference). These are direct evidence of why current revised
history is unsuitable for a historical information-set backtest.

The six-decimal percentage changes in the table above are **calculations
from three-decimal SA index levels in the same publisher workbook**.
They are NOT the headline 12-month NSA inflation figures published in
press releases, and their printed precision does not imply index
precision beyond 3 decimals.

## What the initial evidence does NOT prove

A workbook whose filename corresponds to its economic month, downloaded
on 27 October 2026, is a strong **publisher issue-month source candidate**,
but this alone does not prove that the very same **binary** was served at
8:30am ET on the historical release date; the publisher's warning about
revisions applies. ALFRED cross-matches 7 index levels at dated web pages,
which strengthens that subset but does not timestamp the original XLSX byte
delivery or prove the complete historical vintage vector.

Acquisition with SHA-256 **occurred on 2026-10-27**, not in 2024/2025.
No vintage is declared PIT model-certified. Do not promote into
\`D.json\`, ranking of 28 FX pairs, Beta, Forward or production websites.

## Data and reproduction

- \`validation/macro/fixtures/v2_us_cpi_24_issue_sa_index_sha_2026_10_27.json\`:
  all 24 source URL, date, index, 12-month base, derived YoY, SHA-256
  and one explicit missing 2025-10 row.
- \`validation/macro/v2_us_blscpi_24_issue_sa_index_sha_evidence_v1.py\`:
  deterministic provenance and semantic validation, plus 7 ALFRED checks.
- \`validation/macro/test_v2_us_blscpi_24_issue_sa_index_sha_evidence_v1.py\`:
  adversarial tests for lookahead, wrong series, false missing values,
  altered numbers, hashes, issue-month timestamps and no Core writes.
- \`validation/macro/one_shot_us_cpi_bls_alfred_byte_probe_v1.py\`:
  opt-in downloader for official issuer source bytes with host/mime size
  guards, writes only under /tmp.
- \`validation/macro/one_shot_us_cpi_issue_xlsx_sa_index_extract_v1.py\`:
  extract exact index levels and same-issue base from locally captured
  official XLSX. Research artifacts available from [one-off GitHub
  Actions run](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40587426321)
  with short-term artifact retention. No new scheduled workflows.

**Next decisive control:** immutable original issue-day byte snapshots
or provider first-vintage ALFRED index vectors, plus policy decision for
the structurally unpublished 2025-10 month. Only thereafter can we
claim model-ready PIT training or quantify a trading edge.
