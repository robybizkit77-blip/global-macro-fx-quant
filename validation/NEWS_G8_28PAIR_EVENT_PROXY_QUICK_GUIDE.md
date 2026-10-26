# Quick extension complete — 28 G8 ECB daily-reference pairs

**Purpose:** cover the 28 unique pairs of the eight G8 currencies using already-present official ECB fixing history. Purely research-only. This is the capped, quick follow-up to the BLS October 2 daily proxy; it does not delay the Control Room launch.

Run:
```bash
python -m unittest validation.test_news_g8_28pair_daily_event_proxy_v1 -v
python -m validation.news_g8_28pair_daily_event_proxy_v1 \
  --event-date 2026-10-02 --as-of 2026-10-26 \
  --event-label BLS_US_JOBS_OCT2_2026 \
  --out /tmp/gmfq-g8-28pair-daily-context.json
```

What this produces: the three nearby fixing dates (before, event day, after), 28 ECB-derived reference crosses, the change measured in standard pair pip units, the percentage reference-rate change, and an explicit observation-gap disclaimer. All crosses use (ECB quote-currency per EUR) / (ECB base-currency per EUR); JPY-quoted pairs use a 0.01 pip; other quotes 0.0001. This chooses a *single fixed orientation per pair* rather than a ranking.

**NOT:** intraday FX prices; OIS 6M repricing; causal reaction; event surprise; a backtested strategy; PIT certified raw vintage; a new published live feed. A calendar date by itself is not enough to infer a price response to an announcement. Missing weekend / source / currency / date data produce visible unavailability, never invented values. In particular, the next ECB fixing after Friday Oct 2, 2026 is Monday Oct 5 — a three-calendar-day span, not a five-minute event window.

Outputs can be inspected locally under `/tmp` only. The CI is **unscheduled**. No new vendor acquisition, no paid license, no written permission request, no external automated scraping. No edits to the active Preview site, live scores, 28-pair ranking, Beta, Forward Test or trade alerts.

**Stop condition:** Once this PR passes, this optional research expansion is complete. Return to mandatory 08:00 freshness SLA, Beta, Forward Test, deep final QA and visual refinement. Do not automatically expand this into a new event data platform.
