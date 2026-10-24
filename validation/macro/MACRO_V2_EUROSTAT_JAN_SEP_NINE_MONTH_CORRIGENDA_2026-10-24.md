# Macro V2 — Eurostat January–September 2026 HICP: nine months including corrigenda

**24 October 2026 · research-only web source attestation, NOT complete PIT vintage certification.**

## Why Jan/Feb cannot be treated like ordinary flash/final pairs

Eurostat publishes dated period-specific flash and detailed HICP releases. In **January and February 2026**, the flash pages also explicitly disclose technical corrections. Consequently, the currently served flash page is **not an immutable representation of all original release-day body bytes**.

| Reference month | Flash date | All-items flash | Official corrigendum | Detailed date | All-items detailed |
| --- | --- | ---: | --- | --- | ---: |
| January 2026 | 4 Feb 2026 | 1.7% YoY | **5 Feb**, 11:00 AM (wall-clock zone not independently certified) | 25 Feb | 1.7% |
| February 2026 | 3 Mar 2026 | 1.9% YoY | **4 Mar**, 6:00 PM (wall-clock zone not independently certified) | 18 Mar | 1.9% |

Primary source pages: [January flash, including correction](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-04022026-ap), [January detailed](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-25022026-ap), [February flash, including correction](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-03032026-ap), [February detailed](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-18032026-ap).

For the six selected comparable **annual YoY rates** used by the prior March–Sept research replay:

| Reference month | Component | Flash | Detailed | Reported change |
| --- | --- | ---: | ---: | ---: |
| January | Headline | 1.7 | 1.7 | 0.0 pp |
| January | Core ex energy/food/alcohol/tobacco | 2.2 | 2.2 | 0.0 pp |
| January | Energy | **−4.1** | **−4.0** | **+0.1 pp** |
| January | Food/alcohol/tobacco | **2.7** | **2.6** | **−0.1 pp** |
| February | Headline | 1.9 | 1.9 | 0.0 pp |
| February | Core | 2.4 | 2.4 | 0.0 pp |
| February | Energy | **−3.2** | **−3.1** | **+0.1 pp** |
| February | Food/alcohol/tobacco | **2.6** | **2.5** | **−0.1 pp** |

Non-energy industrial goods and services have no displayed YoY difference at one decimal in either month.

### Two distinct correction categories

- **5 February January flash corrigendum:** Eurostat reports correction of **four monthly rates by 0.1 pp and one annual rate by 0.2 pp** due to a processing error. The affected annual-rate figure (unprocessed food) is outside the selected six aggregates; the flash headline remained **1.7%**. The page now contains revised fields with `r` markers; its uncorrected original values cannot be independently recreated from this page.
- **4 March February flash corrigendum:** Eurostat reports an error in **component weights**, max absolute revision **1.4 parts per thousand** for Services. The corrected weights show `rr` markers. A weight correction is **not an observed change in the headline annual inflation rate**, which remained **1.9%**. The page now shows corrected weights and cannot be passed off as the original March 3 snapshot.

**All source times**: only day and source-described wall clock are known for these corrections; no independently certified time zone or original flash intraday market timestamp. For chronology-only shadow replay, flash becomes visible the **following UTC midnight** (Jan 4→Feb 5, Feb 3→Mar 4), corrigendum the following UTC midnight (Feb 5→Feb 6, Mar 4→Mar 5), detailed the following UTC midnight (Feb 25→Feb 26, Mar 18→Mar 19). These are **conservative simulation gates**, NOT the actual news release clock and should not be used for same-day EURUSD/OIS reactions.

## Major 2026 HICP measurement and geography changes

Eurostat's **4 February 2026 methodological update** introduced the new **ECOICOP v2** classification, added games of chance in recreation services, and changed the HICP **index reference period to 2025=100**. Meanwhile **Bulgaria joined the euro area on 1 January 2026**, changing the geographic aggregate from EA20 to EA21. Historical 2025 EA20 readings should not be naively spliced into 2026 EA21 cross-sectional feature models. Rate levels here are YoY percentages, **not** index points, rate contributions or reference weights.

## Reused prior ledger and quantitative scope

The existing PR #586 **March–September seven-month replay remains unchanged** and is called by the new module. Combined evidence covers:

- **9 reference months**, **18 ordinary publisher flash/detailed publication stages** and **2 separate corrigendum events**, not 20 independent first releases.
- **108 annual-rate metric/stage observations** from six selected aggregates, **19** nonzero flash/detailed component comparison rows (the old seven months supplied 15; Jan and Feb add two each).
- Across nine months the all-items headline changes in **March +0.1 pp and August −0.1 pp**; other seven month-headlines unchanged at reported precision.
- **16 additional monthly first releases short** of the 25-month research minimum, *before* attempting vintage/revision certification.
- Published pages are **web-attested, not archived original-day immutable bytes**. Corrections mean page-body origin ambiguity must stay explicit.

No quantified macro strength score, FX bias, ECB repricing, 2Y or EURUSD event effect is asserted. No backtest, D.json update, Control Room/site/payload/dashboard/live_data alteration or new scheduler. The added code and CI are research-only, with receipts under /tmp.

## Reproduce

```bash
python -m unittest validation.macro.test_v2_eurostat_hicp_nine_month_corrigendum_replay_v1 -v
python -m validation.macro.v2_eurostat_hicp_nine_month_corrigendum_replay_v1 \
 --asof 2026-03-04T23:59:59Z --out /tmp/macro-v2-shadow/feb-flash-before-corrigendum.json
python -m validation.macro.v2_eurostat_hicp_nine_month_corrigendum_replay_v1 \
 --asof 2026-10-24T00:00:00Z --out /tmp/macro-v2-shadow/eurostat-jan-sep-nine-month.json
```
