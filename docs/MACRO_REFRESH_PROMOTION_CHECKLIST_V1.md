# Macro Refresh Promotion Checklist V1

Use this checklist for every production macro refresh after the canonical protocol is merged.

- [ ] Source observation is identified with date, value, series ID and transformation.
- [ ] Candidate is generated read-only.
- [ ] Candidate scope is restricted to the intended currency and macro dimension.
- [ ] Candidate diff is reviewed; unrelated currencies/dimensions are unchanged.
- [ ] Generic macro builder completes successfully.
- [ ] `MACRO_SERIES` and macro heatmap outputs pass schema/contract checks.
- [ ] Frozen engine contract passes; model rules/fingerprint are unchanged.
- [ ] Engine Logic Audit is green on the exact promotion candidate commit.
- [ ] Staging Browser Audit is green on the exact promotion candidate commit.
- [ ] Production promotion changes only the expected data/runtime files.
- [ ] Post-promotion live contract/runtime verification is green.
- [ ] Browser smoke/audit after promotion is green.
- [ ] Evidence artifact/commit is retained.

A failure at any step blocks promotion. Source collection or scheduling must never bypass these gates.
