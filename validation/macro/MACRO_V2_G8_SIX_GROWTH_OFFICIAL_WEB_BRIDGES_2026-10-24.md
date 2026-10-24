# Macro V2 — Six outstanding G8 Growth research publisher bridges

**24 October 2026. Scope: publisher web evidence with verified rates/levels and explicit mismatches; NOT six newly selected canonical Growth model inputs.**

## What the shared G8 evidence adapter gained

The common 24-slot G8 evidence controller now has **a bounded, source-attested research candidate** for all 8 Growth currency slots. Previous Growth sources AUD GDP (+0.4% QoQ in 2026Q2) and NZ GDP (+2.6% same-quarter YoY in 2026Q2) remain untouched. The six new streams are intentionally **not declared canonical Growth definitions**:

| Currency | Existing observed Growth *raw* metric (not original PIT) | Verified publisher web metric | Original published source date | Same unit/period? |
| --- | --- | --- | --- | --- |
| 🇺🇸 USD | **Industrial production index 103.0682**, Aug 2026, 2017=100 | Federal Reserve **103.1**, Aug 2026 industrial production, **rounded to one decimal**, SA 2017=100 | **18 September 2026**, 09:15 EDT (13:15Z) | Same underlying index concept, but **not same numerical precision**; do not rewrite 103.0682 |
| 🇪🇺 EUR | **Industrial production index 98.3**, July 2026, 2021=100 | Eurostat July **−0.1% MoM** first estimate, **revised to −0.3% MoM** in subsequent August publication | **16 September** (first), **15 October** (retrospective revision) | **No**: monthly growth rate is not the index level, cannot substitute −0.3 for 98.3 |
| 🇬🇧 GBP | **Production index 98.5**, July 2026 | ONS July bulletin **−0.5% three-month-on-three-month** total production change | **11 September 2026**, 07:00 London BST (06:00Z) | **No**: rolling 3m/3m rate and monthly production index are different measurements |
| 🇯🇵 JPY | **Industrial production index 104.4**, July 2026, 2020=100 | METI industrial production SA index **103.0** for **May 2026** in a 30 June publisher page | **30 June 2026**, no independently certified original-day UTC clock | Same base and general series family but **different economic reference month** and publisher page is mutable; first-day original HTML not captured |
| 🇨🇭 CHF | **Industrial production index 122**, June 2026, 2021=100 | SECO **+1.5% QoQ** GDP **adjusted for sporting events**, Q2 2026 | **3 September 2026**, day-only | **No**: industrial output monthly index vs quarterly sporting-adjusted GDP growth |
| 🇨🇦 CAD | **Monthly real GDP industry level 2,369,309** million chained 2017 CAD SAAR, June 2026 | Statistics Canada industry GDP table: **2,369,309** in same units, June 2026 | **28 August 2026**, day-only | Source metric/value aligns numerically, but exact **canonical source ID/method/vintage still not approved** |

### Official dated source links

- [Federal Reserve G.17: September 18, 2026, July/August industrial production summary](https://www.federalreserve.gov/RELEASES/g17/20260918/table0.htm). Publisher states release **09:15 EDT** in period-specific release. The **preliminary** August SA total output index is 103.1 (2017=100). This says nothing conclusive about exact subsequent `INDPRO` current-revised **103.0682** or the time it first appeared in any machine-readable stream.
- [Eurostat: industrial production July 2026, 16 September](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/4-16092026-ap), [Eurostat industrial production August release, 15 October](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/4-15102026-ap). The latter **explicitly revises July MoM from −0.1% to −0.3%**. In the normalized event stream the *first* event is gated at **17 September 00:00 UTC**, while the retrospective `REVISION_WEB` becomes visible **16 October 00:00 UTC**. These are **conservative source-day gates, not release timestamps for FX event studies**. A separate numerical Eurostat index level **98.3** is not derivable from either MoM rate alone.
- [ONS: Index of Production UK July 2026](https://www.ons.gov.uk/economy/economicoutputandproductivity/output/bulletins/indexofproduction/july2026), and [ONS release calendar, 11 September 07:00 UK local time](https://www.ons.gov.uk/releases/indexofproductionukjuly2026). ONS's quoted **−0.5%** is **3-month aggregate change**, not the monthly index 98.5.
- [METI: English index of industrial production page](https://www.meti.go.jp/english/statistics/tyo/iip/). The web-attested **May 2026** preliminary index was 103.0 (2020=100); the publisher page is mutable and the exact old original report/day clock is **NOT** archived in this new source dossier. This is **not** an attestation of the later **July 2026 104.4** index's original-vintage value.
- [SECO: quarterly GDP release for Q2 2026](https://www.seco.admin.ch/en/gross-domestic-product). SECO states the adjusted sporting-events GDP grew **1.5% QoQ**, incorporating annual-data revisions. This is an alternative GDP driver, **not** direct evidence for the observed Swiss monthly industrial index 122.
- [Statistics Canada: June 2026 monthly GDP-by-industry level table](https://www150.statcan.gc.ca/n1/daily-quotidien/260828/t001b-eng.htm) and [press narrative, 28 August](https://www150.statcan.gc.ca/n1/daily-quotidien/260828/dq260828b-eng.htm). **2,369,309** (millions of chained 2017 CAD at SAAR) is the index/level used; the distinct publisher headline **+0.3% MoM** must not replace it.

## Common shared PIT controller — updated scope

- **24/24** currency × pillar slots have at least one *candidate publisher web event record*, of which **16 Labour/Inflation** and **8 Growth**.
- Count of distinct first-report reference period rows across *different source metrics*: **75**, plus prior first/detailed/revision stages and one additional EUR July retrospective revision for **87 total publisher stage events**.
- Previously: 18 source streams with 69 first-web periods and 80 event rows. **Important:** these descriptive totals are not homogeneous economic training samples; every publisher stream has its own frequency, unit and event semantics.
- **8/8 Growth slots still have no selected canonical score input** in the official source registry. In particular, the new CHF quarterly GDP cannot be substituted for the existing monthly industrial output; the date-and-unit mismatch is now an explicit source candidate review blocker.
- **0 newly certifiable model PIT historical Growth series**, **0 new FX scores**, **0 changes to D.json** or live weights. Counts of web attestations, not complete immutable original-day source bytes or subsequent complete historical revisions.

### What the code enforces

1. Separate official publisher URL/hostname, observation reference period and calendar source release date/clock; invalid source substitutions are rejected.
2. Rate vs raw index and MoM vs 3m/3m vs QoQ vs SAAR level distinctions are pinned; no conversion is inferred.
3. One initial publisher statement per economic reference period, *separate subsequent reported revision* (July EUR −0.1→−0.3), conservative source-date-only visibility gates where publisher intraday is unavailable.
4. Each research candidate is crosschecked against **the current observed source ID, frequency, actual observed period/value/unit** without calling that current history first-publication-certified. A later revision cannot be backdated.
5. No automated acquisition/cron: this PR only connects six official source-event dossiers to the **existing unscheduled** G8 shadow CI. Research receipts are restricted to `/tmp`; production site, live_data, 28-pair rankings and scheduling remain unchanged.

### Next work

A source-selection and **economic feature-definition review** is needed before assigning any of the eight Growth slots one canonical feed. Recommendation: select explicitly whether each nation's Growth pillar is GDP or a nowcasting industrial/consumption composite; specify monthly/quarterly cadence, index-to-growth transforms, release revision policy and fitting windows. Further original-release document archiving must then establish **25 monthly or 13 quarterly** *comparable first-web source periods* per selected series and revisions, not cross-country counts.

### Reproduce

```bash
python -m unittest validation.macro.test_v2_pit_g8_growth_web_bridges_v1 -v
python -m unittest validation.macro.test_v2_pit_g8_control_plane_v1 -v
python -m validation.macro.v2_pit_g8_control_plane_v1 \
  --asof 2026-10-24T00:00:00Z \
  --json-out /tmp/macro-v2-shadow/g8-24-growth-candidates.json \
  --markdown-out /tmp/macro-v2-shadow/g8-24-growth-candidates.md
```
