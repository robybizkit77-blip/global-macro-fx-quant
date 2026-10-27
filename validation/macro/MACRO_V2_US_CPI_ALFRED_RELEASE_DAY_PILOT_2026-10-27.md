# Macro V2 — US CPI: ALFRED release-day SA-index vintage pilot (27 October 2026)

## Why this is different from the earlier revised-history CPI estimate

The registered Core series is **CPIAUCSL**, the **seasonally adjusted index** from BLS via the St. Louis Fed, transformed to index-based 12-month change. The headline annual CPI percentage in BLS news Table 1 is **not seasonally adjusted** and is *not* the same historical variable. BLS retrospectively updates seasonal factors for up to five years, so a current revised 2026 file does not represent the original 2025 information set.

Official archive: https://www.bls.gov/cpi/tables/supplemental-files/home.htm
BLS seasonal revision policy: https://www.bls.gov/cpi/seasonal-adjustment/
ALFRED historical-vintage tool: https://alfred.stlouisfed.org/series/downloaddata?seid=CPIAUCSL
ALFRED download guide: https://alfred.stlouisfed.org/help/downloaddata

## Narrow independently dated release-day pilot

- September 2025 was reported **October 24, 2025** in the original BLS news release https://www.bls.gov/news.release/archives/cpi_10242025.htm
- September 2026 was reported **October 14, 2026** in the BLS news release https://www.bls.gov/cpi/news.htm
- ALFRED graph CSV route: `/graph/alfredgraph.csv?id=CPIAUCSL&vintage_date=YYYY-MM-DD&cosd=...&coed=...`. The reader checks the exact series+date header, index-month presence, previous-year index, source bytes SHA256 and structural absences; it *does not* claim this mirror is a contemporaneously archived BLS original.
- **October 2025 CPI All Items does not exist** due to shutdown: https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm . Do not interpolate, copy NSA or infer a missing first release. Therefore the calendar-consecutive 24M prior window for September 2026 remains impossible even if all other months are acquired.
- ALFRED's date requested may sometimes represent the last preceding true vintage. Matching the CSV header is necessary but not sufficient: require the publication-day's newly available target-month observation plus external BLS evidence. The result is a *date-as-of Federal Reserve mirror*, not proof of a BLS-release intraday timestamp.
- **No source bytes or 24-series first releases are claimed recovered by this PR.** The previous 22/24 original-web research windows and 0/24 fully PIT-certified training windows remain unchanged. The bridge is intentionally limited to two source/date pairs until a full original release manifest is independently validated.

Reproducible opt-in retrieval (when external network access is available):
```sh
python -m validation.macro.v2_us_cpiaucl_alfred_release_day_pilot_v1 --month 2026-09 --download --output /tmp/us-cpi-alfred-sep2026.json
python -m validation.macro.v2_us_cpiaucl_alfred_release_day_pilot_v1 --month 2025-09 --download --output /tmp/us-cpi-alfred-sep2025.json
python -m unittest validation.macro.test_v2_us_cpiaucl_alfred_release_day_pilot_v1 -v
```

Nothing fetched at import or in offline tests, nothing written to live_data, **no cron**, no Core D.json, pair rankings, active Control Room, Rates, Beta or Forward changes. Next: retrieve actual publisher release-time files and ALFRED vintage bytes, verify whether the two source values match, then expand the dated archive; do not turn the pilot into a trading signal.
