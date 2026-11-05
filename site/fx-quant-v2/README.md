# FX Quant V2 — new independent website

Public preview: https://robybizkit77-blip.github.io/global-macro-fx-quant/site/fx-quant-v2/

This is an additive unified 12-page site. It does **not** change the current Control Room V10, Design Studio, Core, weights, price/rates datasets, alert jobs, or automation triggers.

Shared navigation assets: `assets/site-nav.css` and `assets/site-nav.js`.

Eleven of the 12 pages are carried over from the approved Design Studio with internal links remapped to the V2 paths. Each page retains its own approved analytical visuals, charts and source logic. Where the approved page embeds research snapshots, those remain snapshots with their original per-series as-of; six accompanying JSON data files are copied as reference assets. Pages using `raw.githubusercontent.com/.../main/live_data/sections/` read ongoing canonical feeds. No Core source has been duplicated or modified.

Site navigation and data lineage are distinct: an available link does not guarantee freshness of every underlying series. Source-level dates and classifications still apply. FX thesis is not a trade-entry signal.

**No promotion to primary site until end-to-end QA (all pages, on-device/browser, data freshness, mobile navigation, report URLs, chart interactions) and owner approval.**

## Dedicated OIS & Market Pricing (2026-11-04)

The additional `ois.html` is a standalone research section, linked in the shared 12-page navigation. It displays 8 currencies × 3 pricing horizons with per-tenor source dates and explicit instrument types (GBP BoE OIS; other official futures; secondary futures/proxy where unavailable). It reads `OIS_OPERATIONAL_VIEW`, `CB_PRICING_ESTIMATED`, and `NZD_CB_PRICING_DIRECTIONAL_PROXY`, falling back to a dated `ois-pricing-snapshot.json` without overwriting the canonical data. Quoted futures are *not* OIS; maturity spreads across them are illustrative, not policy repricing. Core FX signals, backtests and V10 are untouched.

## NZD B2 — Authorized API fallback (2026-11-04)

The source order for V2 CHF/NZD research is: (1) official RBNZ B2 public
HTML (same-row 2Y/10Y and benchmark-roll guards); (2) optional authorized
eolas API redistribution (one weekday slot or explicit workflow dispatch);
(3) previous dated V2 research reading, never relabelled as fresh. The
RBNZ endpoint returned HTTP 403 to GitHub-hosted runners. No attempt is
made to bypass that access control.

The vendor API requires EOLAS_API_KEY configured by the repository owner
as a GitHub Actions secret and a valid service plan. No key is stored in
source code, HTML, repository artifacts or logs. When unavailable, the
optional vendor call is not made and the GitHub workflow summary states
NZD_SOURCE=UNAVAILABLE. A free 10-requests/month plan cannot sustain daily
requests. Choosing a plan or purchasing access is entirely a user decision.

The eolas adapter insists on the RBNZ B2 daily dataset and same-row
government 2Y/10Y series plus matching April 2029/April 2037 instrument
columns after the 2026-10-30 benchmark roll. It rejects missing, future,
stale and contradictory rows and labels approved data as third-party
redistribution, NOT direct RBNZ observations or an official publication
timestamp. No write to Core, OIS, macro scoring, FX engine or backtests.

## RBNZ source access rights + Nov 5 manual public-page reading

On November 5, 2026, the public RBNZ B2 release page displayed **November 4
closing yields** (2Y April 2029: **3.83%**, 10Y April 2037: **4.81%**). These
were entered into the V2 **research-only** CHF/NZD feed as a dated reviewed
public-page observation. This was **not** an automated runner download and was
**not** independently XLSX-reconciled. The Oct 30 benchmark transition is
still kept separate and no FX Core, official OIS or backtest is changed.

Source: https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates
and the official benchmark rollover note dated Nov 2, 2026.

**Automated access:** Under RBNZ's Terms of Use, prior written permission is
required for automated website access (the index of published XLSX files does
not waive that requirement). The scheduled GitHub HTML reader is now
**disabled by default**. It can only run when the repository owner has
received the written authorization and explicitly sets
`RBNZ_AUTOMATED_ACCESS_AUTHORIZED=true` as a GitHub Actions secret.
Do not set this flag merely because the webpage is public. Do not bypass HTTP
403 controls. Official policy and allow-list request:
- https://www.rbnz.govt.nz/about-our-site/terms-of-use
- https://www.rbnz.govt.nz/about-our-site/terms-of-use/allow-list-request

The optional `EOLAS_API_KEY` source is separate: it needs its own valid
license/subscription and is only used in the daily quota-protected slot or
explicit dispatch. Without one of those authorized paths, the research feed
retains the **last dated** observation without claiming a fresh close.

The V2 UI displays dated estimates/observations for informational purposes;
Core, certified rates, pair signals, OIS_DATA and backtests are unchanged.
