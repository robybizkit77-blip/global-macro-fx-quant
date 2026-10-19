# Global Macro FX Quant — active website target (19 October 2026)

## Canonical active user interface — DO NOT CONFUSE WITH LEGACY

The active Control Room requested by the project owner is:

- **PUBLIC URL:** https://robybizkit77-blip.github.io/global-macro-fx-quant/site/control-room-preview/#/home
- **SOURCE LOADER:** `site/control-room-preview/index.html`
- **LIVE NAVIGATION / ADDITIVE HOME ADAPTER:** `site/control-room-preview/home-navigation-v10.js`
- **RENDERED DESIGN:** 32 `site/control-room-preview/parts/part-00.txt` … `part-31.txt` files published on the `gh-pages` branch.
- **PUBLIC BROWSER TEST:** `validation/qa_control_room_v10_public.js` / `.github/workflows/control-room-v10-public-browser-qa.yml`.
- **FEED PUBLISHER:** `.github/workflows/publish-control-room-market-data-v1.yml`.

### Historical / non-target UI

The GitHub Pages repository root `/global-macro-fx-quant/` (`index.html`, `payload/part-00.txt` … `part-15.txt`, `dashboard/*`) is an older dashboard **and is not the active Control Room UI**. `site/website-v1/` is also legacy. Do not present the root URL as the user's current Control Room; do not mistake CI success on the legacy UI for proof that the Preview changed.

Do not delete, redirect, overwrite, or visually redesign these historical pages without a specifically requested and tested migration. Preserve existing files and reports.

## Where to work

1. **UI changes** to the active Control Room: work in `site/control-room-preview/` and its authoritative design sources; check the 32-part published loader contract. Keep the approved dark institutional visual design, globe, flag labels, G8 charts and mobile layout. Do not regenerate or replace the approved visual design in an unrelated HTML root.
2. **Shared market-data pipeline** changes may correctly occur under `live_data/sections/`, `validation/`, `.github/workflows/`. Confirm that the active Preview actually consumes the affected file before claiming a visible change. In particular `home-navigation-v10.js` fetches `NATIVE_RATES_DATA.json`, `OIS_OPERATIONAL_VIEW.json`, `NZD_CB_PRICING_DIRECTIONAL_PROXY.json`, `DXY_SYNTHETIC_ECB.json` from the GitHub `main` raw feed, while other Preview views may read the published `gh-pages` data mirrors. The Price overlay in `payload/part-15.txt` belongs to the older root dashboard, not automatically to the Preview.
3. **Certification**: distinguish official, estimated, secondary and WITHHELD data. Do not promote incomplete or mismatched source-date curves into signals, official pricing, or backtests. Preserve no-impact isolation for presentation overlays.
4. **Verify the requested target**: on completion compare the *active Preview* source/gh-pages files, run its real public browser QA desktop + mobile, and quote its canonical URL. Do not cite unrelated legacy UI QA as proof for the Preview.
5. **Explain exact scope**: separate 'shared data improvement', 'active Preview improvement' and 'legacy-only change' in all future PR summaries.

**Current user directive:** active development targets the Control Room Preview route above. Existing historical sites are preserved, not the default target.
