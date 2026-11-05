#!/usr/bin/env python3
"""Guard against FXV2 publication gaps after GITHUB_TOKEN-backed producer commits."""
from pathlib import Path
p=Path(__file__).resolve().parents[2]/".github/workflows/publish-fx-quant-v2.yml"
s=p.read_text(encoding="utf-8")
must=[
    "workflow_run:",
    "FX Quant V2 AUD Official RBA F2 Research Refresh",
    "FX Quant V2 CHF NZD Same-Basis Research Refresh",
    "FX Quant V2 Cross-Asset Published Source Refresh",
    "OIS G8 History Persistent Daily V1",
    "FX Quant V2 Relative Pricing 28-Pair Research",
    "types: [completed]",
    "github.event.workflow_run.conclusion == 'success'",
    "github.event.workflow_run.head_branch == 'main'",
    "github.event_name != 'pull_request'",
    "git add -A -- site/fx-quant-v2",
    "git diff --cached --name-only | grep -v '^site/fx-quant-v2/'",
    "rsync -a --delete \"$source_root/\" \"$target/site/fx-quant-v2/\"",
    "cancel-in-progress: false",
]
assert all(x in s for x in must),[x for x in must if x not in s]
assert "workflow_run:" in s[s.index("on:"):s.index("permissions:")]
assert s.count("  sync-v2:")==1
assert s.count("  contract:")==1
assert "git push origin HEAD:gh-pages" in s
assert "git add -A -- site/fx-quant-v2" in s
print("FXV2_SOURCE_TRIGGER_TO_PUBLICATION_CONTRACT_PASS")
