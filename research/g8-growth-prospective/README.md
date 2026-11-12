# G8 Growth — frozen prospective research register

This directory stores **append-only first-seen-by-FX-Quant** macro observation histories and their accompanying shadow-model outputs. It is research evidence, **not** a certified issuer first-release/PIT macro database.

## Every capture
The existing `Macro Persistent Daily V1` workflow collects a fresh main-branch commit, runs the same `g8-growth-shadow.js` model used in the site, and attempts to **create one file per Europe/Rome day**:

`observations/YYYY-MM-DD.json`.

The persisted receipt includes UTC/Europe-Rome capture time, exact main commit, SHA-256 hashes of model and macro feed, selected historical series observation/value pairs, all eight candidate/withheld decisions, fixed benchmark MAEs, target observation periods, and limits. The writer refuses an overwrite and never backdates a GitHub commit. A rerun on the same day reports `ALREADY_CAPTURED_IMMUTABLE` rather than replacing the record.

## Interpretation
- `source_main_commit` and the hashes prove which repository data/model were **seen** by the collector.
- An observation month is **not** a date/time when the issuer first released that value.
- The historic source can contain revisions that occurred before our capture. None of the existing backtest's historical rows becomes genuine past point-in-time evidence from recording it today.
- A forecast is for the **next change of the selected indicator**, not aggregate GDP, policy, spot FX, risk, or position sizing.
- There are **no** operational forecast signals and no effects on FX G8 rankings, the 28-pair engine, historical backtests, or daily macro data.

## Future validation
Once a newly observed target period appears in a **subsequent** immutable capture, measure its first-seen error against the earlier frozen forecast and a frozen no-change baseline. Do not replace the earlier prediction with the newest fit, and track subsequent revised outcomes separately. A genuine issuer first-release PIT test still requires timestamped release-vintage acquisition, verified release calendars, and adequate genuine prospective samples.

The workflow also retains its research capture file in the existing `macro-persistent-evidence-<run_id>` artifact. GH Actions success alone is not evidence of a new macro data point.
