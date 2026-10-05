# Canonical Macro Refresh V1

## Scope
This procedure governs production updates of `live_data/sections/MACRO_SERIES.json` and `live_data/sections/MACRO_THERMOMETER_DATA.json` without changing engine rules.

## Invariants
- Source collection and parsing must never write directly to `live_data`.
- Every new observation is first represented as a candidate JSON.
- `validation/build_macro_candidate.py` produces replacement artifacts only in a temporary candidate directory.
- Candidate validation must prove that only the intended currency/dimension changes.
- Engine rules, OOS T0 and runtime contracts remain frozen.
- Promotion is a separate action and is forbidden until all gates are green.

## Canonical sequence
1. Source -> raw observation.
2. Normalize to candidate JSON with source, series id, frequency, transformation, observation date and value.
3. Build candidate read-only with `validation/build_macro_candidate.py`.
4. Validate candidate scope with `validation/validate_macro_refresh_contract.py`.
5. Compare candidate vs live artifacts and retain evidence/hashes.
6. Run `Live Update Preflight V1`.
7. Run `Engine Logic Audit`.
8. Run browser/staging audit.
9. Only if all gates are green, promote the two validated data artifacts.
10. Re-run the same integrity/browser gates on the promoted commit.
11. Publish only after post-promotion gates are green.

## Failure policy
Any red gate stops promotion. No partial write, no fallback mutation of live data, no silent correction and no change to engine rules are allowed inside a data refresh.

## Historical revisions
Historical revisions remain blocked by default. They require an explicit candidate flag and a dedicated validation path before promotion.

## Automation boundary
Scheduling is intentionally out of scope for V1. Automation can be added only after one full manual end-to-end refresh has passed this exact sequence.
