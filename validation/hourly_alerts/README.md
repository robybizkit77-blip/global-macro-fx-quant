# Hourly certified-alert readiness

`build_certified_alert_snapshot.py` creates a machine-readable eligibility receipt.  It is deliberately fail-closed: the receipt is not an alert message and does not send a notification.

The hourly GitHub Actions workflow runs every day, including weekends. It executes the classifier, builds a Macro Research Desk Compact outbox and publishes the receipt and alert as artifacts.

Delivery is pull-only. The GitHub workflow does not use a webhook, Discord, secret endpoint or any other external notification route. It writes a certified snapshot and a Desk outbox artifact. GitHub therefore never claims to have delivered a message to ChatGPT.

In the current certified-data state, the generated output is necessarily the exact fallback: `Controllo orario completato: nessuna novità significativa. Nessun setup chiaro.` A 250–350-word significant message can only be built from a separately supplied, timestamped event record, a non-recycled event id and a complete certified Macro → OIS/2Y → FX audit. The builder accepts certified OIS only for GBP, JPY, CAD and AUD; USD, EUR, CHF and NZD are rejected.

## Certified Macro G8 feed contract

The workflow reads `automation/macro_g8/certified-feed.json` from the checked-out `main` commit. It is deliberately absent until a collector can supply a real record; a missing file is a valid, fail-closed outcome. Each event must contain all of: `event_id`, G8 `currency`, indicator, period, `release_timestamp_utc`, `as_of_utc`, numeric `actual`, numeric `consensus`, numeric `previous`, explicit `revisions` list, and a source object with the official authority/release URL plus licensed consensus provider and its as-of timestamp. Any missing field, future/inconsistent timestamp, event older than six hours, duplicate event id, duplicate semantic release, or id in the optional immutable delivery ledger withholds the entire batch.

Official statistical agencies normally publish actuals, prior values and revisions but not market consensus. A genuine consensus field must come from a licensed provider, be timestamped before the release, and remain attributable in the committed snapshot. The validation layer never backfills it from a dashboard, newspaper or model estimate.

## Verifiable ChatGPT route (no push integration claimed)

1. A collector commits a fully validated feed snapshot to `main` (and, if used, an immutable delivered-event-id ledger) through the repository’s normal review path.
2. The hourly GitHub Actions job checks out that exact `main` commit and emits `certified-macro-g8-feed.json`, `hourly-alert-certification.json` and the Desk outbox as artifacts. This is a real workflow only after the workflow itself has been merged to `main` and its scheduled run succeeds.
3. In ChatGPT, connect the authorized GitHub repository and create an hourly Scheduled task that reads the committed `automation/macro_g8/certified-feed.json` and the committed validation/outbox evidence for the current `main` SHA. Its instructions must report only a valid, unseen event and otherwise emit the exact fallback. It should store/compare the delivered `event_id` in the task’s approved state or the repository ledger before posting the response here.

ChatGPT’s supported GitHub connection can retrieve authorized repository content on demand; scheduled tasks can use connected apps when the account/workspace makes them available. This is a pull/read path, not a GitHub-to-ChatGPT webhook, and availability, repository authorization and task state must be verified in the user’s ChatGPT account before relying on it.

Implemented inputs:

- OIS: GBP, JPY, CAD and AUD only, and only when the runtime marks the row official, certified and backtest-eligible.  USD, EUR and CHF remain non-certifiable secondary/estimated quotes; NZD remains a stale estimated/proxy input.
- US Treasury and G8 government-bond observations: official source, exact official freshness contract and three-day maximum age.  A 2Y government yield remains a bond/rates observation; it is never relabelled as OIS.
- COT G8: a coherent weekly CFTC Tuesday positioning date (currently 2026-10-13), with a ten-day maximum age.
- FX G8: the canonical pair runtime only when it states the ECB reference-rate source (currently 2026-10-16), with a three-day maximum age.

The receipt reports the last verified observation.  It does not claim a macro surprise or a post-event price reaction, because that needs an audited event timestamp, consensus and post-release price window.

Intentionally withheld lanes:

- Macro releases: no common audited G8 release/as-of contract.
- Credit: no certified IG/HY spread adapter.  Monetary and liquidity aggregates are not a substitute.
- Equity sectors: no certified adapter.

`summary.green` is permanently false.  A consumer must examine each lane's `alert_eligible`, source, as-of date and freshness; it must not infer readiness from an aggregate label.
