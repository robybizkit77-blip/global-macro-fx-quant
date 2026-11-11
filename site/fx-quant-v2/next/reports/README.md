# FX Quant NEXT — Research Library publication contract

This directory is the public, append-only home for **approved final HTML reports**, not for drafts or unreviewed prototypes.

- The Next Research Library shows **only one report per canonical category** (latest dated edition, then highest approved version on identical dates): Daily Forex, Weekly Global Macro, Weekly Bank FX, Weekly CB Sentiment, Weekly CB Pricing G8 / OIS curves, COT FX G8, Cross-Asset, and Weekly Pair Selection.
- The HTML files remain unchanged, retaining their original style, editorial structure, source references, data provenance and edition dates. Do **not** copy non-public Library items automatically without validating that they are the approved final report.
- A published report must use a dated filename and the existing canonical prefixes. For example: `Briefing_Forex_Commodities_YYYY-MM-DD_VN_DEFINITIVO.html` or `Weekly_CB_Pricing_G8_YYYY-MM-DD_VN_DEFINITIVO.html`.
- Avoid filenames containing `PROVA`, `TEST`, `BOZZA`, `DRAFT`, `BACKUP`, `ANTEPRIMA`, `PREVIEW`, `OLD`, or `LEGACY`. Those are excluded by the site's automatic latest-edition discovery.
- COT filenames use the actual *Tuesday positioning observation date*, e.g. `COT_FX_G8_03_NOV_2026_...html`, **not** the Friday release date. Distinguish release and reference dates inside the report.
- The existing `Publish FX Quant V2 (isolated site)` workflow mirrors only `site/fx-quant-v2/**` to `gh-pages`. Do not publish new reports under `site/website-v1/reports` alone.
- After a new approved HTML is committed to `main` under this folder, the existing publisher copies it to `gh-pages`. Next Library then discovers the newer file through GitHub's public directory API and validates its GitHub Pages HTTP HEAD before replacing the visible card. If API access fails it falls back to the eight pinned, validated editions in `research-library.js`.
- **This does not create a report, schedule ChatGPT, or automatically move ChatGPT Library files into GitHub.** Production-to-repository publication must be executed separately by the existing report automation, with a success/failure receipt. No claim of end-to-end autonomy without a successful scheduled publication test.
- Keep reports at their actual cadence: Daily on weekdays; weekly reports only once new source evidence exists. Never fabricate new edition dates, data or unchanged content to satisfy a daily schedule.
- Do not introduce new GitHub Actions workflows merely for Library listing or write to operational FX Core, OIS or pair engines from this directory.
