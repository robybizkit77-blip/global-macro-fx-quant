# CHF.labour — SECO/SNB first-release temporal provenance review (22 October 2026)

**Scope:** Evidence-only audit of the September 2026 registered unemployment rate, seasonally adjusted. No production-data, score, pair, trading signal, user-interface, scheduler, or historical-vintage promotion is authorized by this note.

## Canonical identity and unresolved claim

- Canonical runtime key: `CHF.labour`; series `CH_UNEMP_RATE` / `CH_UNEMP_RATE_history_value`.
- Upstream: SECO via SNB data portal cube `amarbma`, series label **Jobless rate - Seasonally adjusted**; reference period **2026-09**; monthly percentage level.
- Current canonical exact observation at the audit: **3.1249882357461%** (as also documented in PR #516). It is the value in the canonical SNB-transported dataset, **not** a proven October 6 first-publication vintage.
- The original SECO September release publishes the **rounded** seasonally adjusted jobless rate **3.1%**. Its numerical agreement when rounded does not independently certify the exact 3.1249882357461% or its availability at publication.
- SECO's publication date: **2026-10-06**. Its official publication calendar listed **09:00 Europe/Zurich** for that report (a **scheduled** time, not independently attested first availability of SNB's exact machine-readable value). Do not write an actual release instant to the PIT ledger from schedule alone.

**Decision:** `WITHHELD_EXACT_PERIOD_EVIDENCE` remains correct for the September 2026 exact observation. Keep `first_release_date=null` and `first_release_timestamp_utc=null` in the **exact-value-certified** release ledger. Separately documented publisher date/scheduled clock do not mean the exact value was published then.

## Publisher records inspected

1. SECO, **Die Lage auf dem Arbeitsmarkt, September 2026**, dated **6 October 2026**, p. 6 (PDF page index 5), table 1:
   - September SA unemployed persons: **147,411**;
   - September SA unemployment rate: **3.1%**;
   - August SA unemployed persons (revised within the September release): **147,886**;
   - footnote: unemployment rates rounded to **one decimal place**.
   - Original publisher PDF: https://www.arbeit.swiss/api/media/fileservice/sdweb-docs-prod-arbeitswiss-files/files/2026/10/05/0cad6bef-5a75-4044-8b59-5e83c29f6681.pdf
   - Press announcement: https://www.seco.admin.ch/it/newnsb/Cdju9-o8WGML
2. SECO, **Die Lage auf dem Arbeitsmarkt, August 2026**, dated **7 September 2026**, p. 6 (PDF page index 5), table 1:
   - August SA unemployed persons in the August release: **147,970**;
   - August SA unemployment rate: **3.1%**.
   - Original publisher PDF: https://www.arbeit.swiss/api/media/fileservice/sdweb-docs-prod-arbeitswiss-files/files/2026/09/04/f72d8d9d-0117-47cb-89b0-16bbefe6d78a.pdf
3. SECO official labour statistics page:
   - Archive links to the separate August and September PDFs; published dates September 7 and October 6, respectively.
   - Definitions explicitly say seasonal adjustment uses **X-13-ARIMA-SEATS** and *recalculates the time series with each additional observation*, so earlier SA estimates may change.
   - The Swiss labour force denominator applicable from 2023 is stated as **4,717,177** persons; dividing the rounded/whole-person **147,411** SA count by that denominator gives about **3.12498344%**, not exactly the current series **3.1249882357461%**. This near-match is **not** a first-release exact-value attestation.
   - https://www.arbeit.swiss/en/information-centre/labour-market-statistics-switzerland
4. SNB official data-portal API documentation explains `lastUpdate` as **most recent table/chart update**, with ETag support. A present-day lastUpdate/ETag alone does **not** expose an October 6 first-release vintage or its original bytes.
   - https://data.snb.ch/en/help_api
   - Runtime transport: https://data.snb.ch/api/cube/amarbma/data/json/en
   - Latest-update endpoint: https://data.snb.ch/api/cube/amarbma/lastUpdate

## Demonstrated cross-release revision

For reference period **2026-08**, seasonally adjusted **count** was **147,970** in the September 7 August report and **147,886** in the October 6 September report: **−84 persons**. Both releases round the SA unemployment **rate** to **3.1%**. Thus, identical rounded rates can conceal real changes to the underlying adjusted series.

This is **directly observed evidence** of a vintage-revision hazard in SECO's SA labour series. It does **not** prove that the September 2026 rate has itself been revised.

## Access / reproducibility boundary

The source PDF tables and their text/visual tables were reviewed. Attempts to fetch the SNB cube `data/json/en` and `lastUpdate` endpoint directly during this audit were unsuccessful in the research environment; no live API response/October 6 byte-level SNB snapshot was captured. Current repository fixtures/source metadata identify the canonical transport, but do not create evidence of what the API returned on October 6. PDF URL upload-directory dates do not establish when the files became publicly accessible. No hashes purporting to attest the historical first release are claimed.

## Conditions for upgrading CHF.labour

A **candidate** first-release exact-value record would need ALL of:

1. Original official SECO or SNB machine-readable artifact identifying the **2026-09 seasonally adjusted rate** with the precise value, and proof it was the vintage distributed on **2026-10-06** (e.g., timestamped official archive, authenticated publisher vintage export, trustworthy contemporaneous capture, publisher confirmation).
2. Same series and transformation: SECO registered unemployment, **seasonally adjusted percentage**, not the **unadjusted 3.0%** or survey-based ILO unemployment.
3. A separate, documented distinction between the SECO headline announcement time and the exact SNB-cube update time; calendar time is only the scheduled release.
4. For historical backtests, per-period first-release versions throughout the required lookback, not just September 2026.
5. Regression tests retaining `safe_to_publish_new_D=false`, no changes to 24 historical Macro scores / 28 pairs, and no intraday release-time assumptions until independently verified.

**Next-source priority:** request/read an official SECO AMSTAT first-publication export or SNB archive for `amarbma` as of 6 October 2026, ideally including data timestamp, numeric precision, and immutable version ID. Failing this, preserve the withheld exact-vintage status and start storing time-stamped SNB API snapshots prospectively without retroactively backfilling unsupported release instants.

## Non-impact contract

- **Shared data / evidence:** this document only; no changes to `live_data`, PIT status codes, or canonical numeric data.
- **Active Control Room Preview:** unchanged; no visible site change claimed.
- **Legacy UI:** unchanged.
- **Automations:** none added or modified.
