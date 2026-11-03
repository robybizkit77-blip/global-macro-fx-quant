# FX Quant V2 — new independent website

Public preview: https://robybizkit77-blip.github.io/global-macro-fx-quant/site/fx-quant-v2/

This is an additive unified 11-page site. It does **not** change the current Control Room V10, Design Studio, Core, weights, price/rates datasets, alert jobs, or automation triggers.

Shared navigation assets: `assets/site-nav.css` and `assets/site-nav.js`.

The 11 content pages are carried over from the approved Design Studio with internal links remapped to the V2 paths. Each page retains its own approved analytical visuals, charts and source logic. Where the approved page embeds research snapshots, those remain snapshots with their original per-series as-of; six accompanying JSON data files are copied as reference assets. Pages using `raw.githubusercontent.com/.../main/live_data/sections/` read ongoing canonical feeds. No Core source has been duplicated or modified.

Site navigation and data lineage are distinct: an available link does not guarantee freshness of every underlying series. Source-level dates and classifications still apply. FX thesis is not a trade-entry signal.

**No promotion to primary site until end-to-end QA (all pages, on-device/browser, data freshness, mobile navigation, report URLs, chart interactions) and owner approval.**
