# Canonical Macro Refresh V1 — PR Summary

This branch formalizes and validates the production macro-data refresh protocol without changing live macro data, payload data, or frozen engine rules.

## Included

- Read-only macro refresh contract validator.
- Canonical refresh runbook.
- Contract CI gate.
- Historical JPY end-to-end promotion rehearsal using the current generic builder.
- Persisted E2E validation evidence.
- Production promotion checklist.

## Validation

On commit `c4853f6234876915899a00e236fe43b110f57354` the following all passed:

- Macro Refresh E2E Rehearsal V1
- Engine Logic Audit
- Staging Browser Audit

The rehearsal reconstructed the approved JPY labour refresh from the historical pre-refresh snapshot, obtained exact `MACRO_SERIES` and heatmap parity, validated the promoted state in a temporary sandbox, and confirmed that tracked production `live_data` / `payload` remained untouched.

## Safety

No source collector or scheduler is enabled here. No automatic production promotion is introduced. Every future production refresh remains gated by candidate validation, engine/browser checks, controlled promotion, and post-promotion verification.
