# Global Macro FX Quant — operational target (6 November 2026)

## One canonical website: FX Quant V2

**Approved public URL:** https://robybizkit77-blip.github.io/global-macro-fx-quant/site/fx-quant-v2/

**Approved source:** `site/fx-quant-v2/` with 12 pages. **Public validation:** `validation/qa_fx_quant_v2_browser.cjs`; scheduled QA `.github/workflows/fx-quant-v2-browser-daily-qa.yml`.

### Preserve

1. Do not restyle V2 without the owner's explicit request. Preserve its page structure and the 28-pair FX engine and Core.
2. Keep distinct official and estimated OIS/futures/proxy/historical observations, original as-of, contract and source dates; no proxy promotion or invented policy repricing.
3. Preserve `live_data/`, `validation/`, historical `payload/`, `dashboard/`, `site/website-v1/` and `site/control-room-preview/` until dependency analysis and staged deactivation verify they are unused. Legacy is **not** the default interface but may still supply shared feeds or audit contracts.
4. Publication `main` -> `gh-pages` must be checked for the requested path; do not confuse a successful workflow with fresh underlying source observations.
5. For V2 changes, check `publish-fx-quant-v2.yml`, `fx-quant-v2-browser-daily-qa.yml` and `fxv2-morning-public-proof.yml`. Quote exact outcomes and remaining gaps. Do not change FX signals in UI-only PRs.
6. Do not delete or disable a GitHub workflow without checking references by workflow name (workflow_run triggers), producer/consumer data paths, schedules, secrets, publication, tests and rollback.

### Legacy entrances

`index.html` and `site/website-v1/index.html` navigate to V2; they keep their legacy fallback payload for compatibility. Direct URLs to old dashboards may remain accessible but are no longer the reference for new UI work.

For the staged cleanup boundary, see `MAINTENANCE_V2.md`.
## Research-first delivery protocol (8 November 2026)

These rules supplement the preservation and maintenance rules above. Apply the
most specific approved instruction to the task; do not treat every research
request as permission for redesign, Core changes, or publication.

### Operational V2 vs Next editorial preview

- **Production reference remains** \`site/fx-quant-v2/index.html\`, with the
  established 12-page V2 site at the approved public URL above.
- \`site/fx-quant-v2/next/index.html\` is a **separate editorial/research
  preview (Next V6 as of 2026-11-08)**. Its different navigation and visual
  experiments do not imply approval to replace V2 or any production entrypoint.
- Preserve shared feed dependencies. A Next improvement must not silently
  change V2, the FX Core, official-source classification, 28-pair calculations,
  triggers, schedules, or legacy-compatible publishers.
- Do not create another "canonical" directory, homepage, production URL, or
  parallel version merely to solve a design problem. Work on the requested
  surface; promotion requires explicit owner approval and a separate end-to-end
  release verification.
- Refer to the *current* source, published behavior, and recent changes before
  assuming that an old preview, document, or README describes production.

### Research must lead; indicators must support it

Every substantial Global Macro / FX research page or report should convey, in
natural, plain Italian, a coherent analytical reading:

1. **What is happening** in the economy and across markets.
2. **What has changed** versus the previous comparable observation, with the
   correct measurement and source dates.
3. **Why it matters** economically; what expectations/pricing may already
   incorporate, without asserting an unmeasured repricing.
4. **What confirms or challenges** the thesis: macro, front-end/long-end rates,
   positioning, relative FX, prices and cross-asset evidence, as appropriate.
5. **Desk judgment and what to watch next**, including counter-evidence,
   alternative interpretations and conditions that weaken the thesis.

This is editorial guidance, **not** a mandatory five-card UI or mechanical
macro-to-COT checklist. Lead with a readable argument and clear conclusions;
use supporting charts/tables only where they strengthen understanding.
Avoid repeated descriptions, disconnected metrics, generic "monitor" lists,
excessive labels and jargon, and pages that feel like dashboards rather than
research. Depth and simplicity must coexist.

A displayed thesis, number, chart, comparison or highlighted driver must be
traceable to the evidence actually loaded for that page. Align the narrative,
chart selection, relevant currencies/assets and source dates; when the evidence
changes, reassess the narrative, not just the timestamp. Do **not** make text
appear live by changing dates on static snapshots. If supporting evidence is
missing, delayed, mixed-basis, or contradictory, say so visibly and soften
the judgment. Never fabricate a causal explanation, consensus surprise, OIS
policy path, position flow, historical validation, or market reaction.

Separate **observation**, **interpretation**, **scenario**, and **trade idea**.
A plausible macro thesis is not quantitative proof and a solid thesis is not
automatically an attractive entry. Distinguish Thesis Strength from Trade
Attractiveness where a decision is actually being discussed.

### Market data and quantitative safety

- G8 refers to USD, EUR, GBP, JPY, CHF, AUD, NZD and CAD. Preserve the
  exact 28-pair universe and existing pair orientations.
- For each datum retain its **instrument**, **unit**, **maturity/contract**,
  **observation date**, **publication/first-seen date where available**,
  **source** and **quality class**. Separate observed official quotes,
  vendor/secondary futures, research proxies, estimates and historical
  fallback values. Cross-date or cross-benchmark contrasts are illustrative,
  not synchronized spreads or policy surprises.
- OIS, government yields, listed interest-rate futures and bank-bill
  proxies are different instruments. Never relabel one as another. Do not
  infer a genuine 1D repricing from stale quotes, mixed tenors, a contract
  roll or a modeled parallel shift. Preserve the documented CHF/NZD
  same-basis/source-access guards and their research-only boundaries.
- Quant changes require an economic hypothesis, data lineage, point-in-time
  availability, chronological validation and safeguards against look-ahead,
  revision leakage, overfitting and data snooping. Keep research candidates,
  Core, backtests and genuinely observed forward records separate.
- Exploratory estimates are permitted **if explicitly labelled and
  defensible**; their inclusion must never masquerade as an official quote,
  certified Core input or observed forward return.
- Do not add numbers simply to fill gaps or give artificial precision.

### Visual quality without over-engineering

- Use a clean, legible, professional DARK DESK/editorial experience on desktop
  and mobile. Favor restrained green, amber, red and neutral blue semantics;
  do not add purple as a negative-status convention.
- Preserve approved typography, interaction and page hierarchy unless the
  request explicitly changes them. A larger font, another box, or a new chart
  is not inherently an improvement.
- Prefer substantive Italian narrative with a clear analytical voice over
  repetitive cards, unexplained scores, decorative graphics and oversized
  navigation. Remove duplication only after verifying other sections do not
  depend on the same information.
- Accessible labels, responsiveness, readable tables, loading/empty/error
  states and visible as-of/source information are part of product quality.

### Verification and release evidence

For each change, identify the **exact surface and data contract** affected.
Make the smallest coherent change, then select the relevant existing checks:

- V2 browser, mobile and source-date behavior:
  \`validation/qa_fx_quant_v2_browser.cjs\`,
  \`.github/workflows/fx-quant-v2-browser-daily-qa.yml\`.
- Next evidence/story/chart coherence:
  \`validation/qa_next_research_coherence_v1.cjs\`,
  \`.github/workflows/fx-quant-next-research-coherence.yml\`.
- Publication path and source provenance:
  \`.github/workflows/publish-fx-quant-v2.yml\`,
  \`.github/workflows/fxv2-morning-public-proof.yml\`,
  plus any matching source-specific and regression gates.
- Dependence and safe retirement:
  \`MAINTENANCE_V2.md\` and the original producer/consumer contracts.

An automation run marked "success" is insufficient by itself. Check
required steps, actual written data, source freshness and the *publicly
served* site revision on GitHub Pages (\`main\` vs \`gh-pages\`) when relevant.
Do not claim a live update or complete 08:00 delivery without evidence
for that specific release and time window. A docs-only edit does not
certify production feeds or site behavior.

Before closing work, report in concise Italian:
**what changed; what was actually tested; what was actually published;
which data limitations or blockers remain**. Distinguish designed,
implemented, tested, merged, deployed and publicly verified. Do not
start indefinite redesign cycles or introduce unrequested improvements
after the requested task is complete.
