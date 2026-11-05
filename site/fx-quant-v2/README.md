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

## Relative pricing research for all 28 FX pairs (2026-11-05)

`pricing-relative-28pairs-research.json` is a separately dated **research-only**
dataset built from `ois-pricing-snapshot.json` using the exact 28 pair
orientations published in the V2 Macro descriptive candidate. It provides
84 arithmetic level contrasts (28 pairs × 3 horizons), including estimates
and the NZD ASX bank-bill proxy. The OIS page displays the results under
"Ricerca relativa delle 28 coppie".

Calculation: `spread_bp = 100 × (base level in % − quote level in %)`.
Each leg retains its own observation date, instrument family, source quality
and specific contract when available. Same display horizon **does not**
guarantee the same maturity, underlying index, benchmark convention, or basis.
Mixed-date differences are not same-time market spreads. These values **are
not** investable FX carry, homogeneous OIS spreads, central-bank policy
repricing, inferred direction, expected return, pair signal, or backtest input.

`FX Quant V2 Relative Pricing 28-Pair Research` refreshes the data after
successful OIS / Macro V2 source producers (or changes to the relevant
files). A separate publication trigger carries the produced sidecar into
GitHub Pages, even when the data update was committed with GITHUB_TOKEN.
The workflow refuses missing dates, missing pairs and source classification
drift. Only the V2 research JSON is writable. Canonical FX Core and all 28
existing trading signals remain unchanged.

## FX-pair research triangulation (2026-11-05)

The existing V2 `coppie.html` research area now shows a separate
Macro / relative front-end levels / FX price evidence reading for each
of the 28 pairs. The independent
`assets/pair-relative-triangulation-v1.js` adapter consumes the
published `pricing-relative-28pairs-research.json` (28×3 observations),
observed Macro V3, and the canonically dated ECB FX fixing context.

- OIS / futures / indicative / NZD bank-bill proxy contrast levels retain
  the original quote date and instrument type. Different dates/bases are
  never treated as one synchronized change or policy-rate surprise.
- Macro V3 reports whether inflation, labour and GDP acceleration
  observations are comparable by period; revised observations are **not**
  point-in-time or a new structural FX score.
- FX price 1M return and the pre-existing price confirmation description
  are displayed with the actual fixing date and source validation status.
  An old snapshot is explicitly marked; it is **not** a newly observed price.
- This is narrative evidence **only**. No new weighting, macro score,
  FX recommendation, carry calculation, meeting probability or backtest.
  No Core, FX signals, alerts or previously approved styling changed.

## Quant temporal readiness, strict same-contract sample (2026-11-05)

`validation/quant/fxv2_rates_fx_temporal_readiness_v1.py` counts only
USD/EUR/CHF **listed futures** changes when the *same exact contract*
appears for each of two **consecutive ECB fixing sessions** and the
two currency legs share the same two market days. A roll, nonmatching
horizon, missing day or ambiguous contract is not interpreted as
policy repricing.

The source-availability timestamp is the latest first-seen UTC of
the four required leg quotes. Any future ECB reference price could be
admitted no earlier than the *first reference-fixing date strictly after
that UTC capture calendar date*. The audit does **not** produce
same-day reaction, FX expected returns, realized forward returns,
hit rate, significance, Sharpe or profit.

The research sidecar `quant-temporal-readiness-v1.json` includes
28/28 pair coverage (including explicit zero-history rows), the
underlying 561+ official ECB FX sessions, rate quote provenance and a
small descriptive futures variation sample. It is updated only when
its source history changes, via `FX Quant V2 Rates FX Temporal Research Audit`
after OIS G8, ECB FX price history or Macro candidate producer runs.
The isolated V2 publisher handles the bot-written report.

This is **NOT** a point-in-time macro backtest: the new Macro V3
history uses revised values, no preregistered directional FX rule
exists, and 28 cross pairs are not 28 statistically independent
assets. The original Core, strategy signals, website style and
backtests remain unchanged.
