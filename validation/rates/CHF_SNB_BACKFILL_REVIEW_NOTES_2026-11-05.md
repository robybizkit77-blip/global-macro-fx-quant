# CHF SNB paired 2Y/10Y source review

Swiss National Bank `rendeiduebd` official spot-yield API provides dated 2J and 10J observations. The V2 research layer holds its last matched observation from 2026-10-30 and an independently published 10Y spot observation dated 2026-11-04. Never join a new 10Y with an older 2Y as an observed same-day curve.

`recover_chf_snb_paired_history_v1.py` produces a read-only `/tmp` source-history receipt. Before a production Core promotion, independently verify both source series, units, date alignment, revisions, and benchmark consistency. No automatic Core, FX signal, OIS or backtest writes.
