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
    "OIS Estimated Snapshot Repricing V1",
    "FX Quant V2 Relative Pricing 28-Pair Research",
    "FX Quant Next Estimated Thesis History",
    "FX Quant V2 Rates FX Temporal Research Audit",
    "FX Quant V2 Preregistered 6M Prospective Research",
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

# The existing thesis publication event must verify both the receipt and the
# exact model input families from the recalculation audit, not merely the
# archived pair history. Other publishers retain ownership of their feeds.
import re
block=s.split('label = "NEXT_THESIS_HISTORY_PUBLIC_HTTP"',1)[1].split('proof = verify(',1)[0]
paths=set(re.findall(r'"([^"]+\.(?:json|js|html))"',block))
audit=(p.parents[2]/"validation/pair_thesis/audit_estimated_recalc_readiness_v1.cjs").read_text(encoding="utf-8")
inputs=audit.split("const paths={",1)[1].split("};",1)[0]
source_paths=set(re.findall(r"'([^']+\.json)'",inputs))
assert len(source_paths)==5,source_paths
required=source_paths | {
    "site/fx-quant-v2/next/pair-estimate-recalc-receipt-v1.json",
    "site/fx-quant-v2/next/pair-estimate-history-v1.json",
    "site/fx-quant-v2/next/macro-strength-estimated-v1.js",
    "site/fx-quant-v2/next/home-thesis-recalc-v1.js",
    "site/fx-quant-v2/next/pair-rankings.js",
    "site/fx-quant-v2/next/app.js",
    "site/fx-quant-v2/next/index.html",
}
assert paths == required, (required-paths, paths-required)
assert "if proof[\"status\"] != \"PASS\":" in s
print("NEXT_RECALC_PUBLIC_INPUT_PROOF_CONTRACT_PASS",len(paths))
