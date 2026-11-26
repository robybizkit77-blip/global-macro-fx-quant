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
    "site/fx-quant-v2/next/data-health-v1.js",
    "site/fx-quant-v2/next/activity-momentum-v1.js",
}
assert paths == required, (required-paths, paths-required)
assert "if proof[\"status\"] != \"PASS\":" in s
print("NEXT_RECALC_PUBLIC_INPUT_PROOF_CONTRACT_PASS",len(paths))

# Completion-driven recovery must remain available even when the source
# collector's next run makes no change. Verify every registered producer.
from ast import literal_eval
research_block=s.split("research_sources = {",1)[1].split("pricing_paths =",1)[0]
research_sources=literal_eval("{"+research_block.strip())
expected_workflows={
    "g8-economic-semaphore-source-recovery-v1.yml",
    "fx-next-rbnz-liquidity.yml",
    "boe-gbp-reserves-research-refresh-v1.yml",
    "us-h8-bank-credit-research-refresh-v1.yml",
    "cad-business-credit-official-research-refresh-v1.yml",
    "ecb-eur-nfc-credit-research-refresh-v1.yml",
    "rba-aud-business-credit-growth-research-refresh-v1.yml",
    "rba-aud-es-balances-research-refresh-v1.yml",
    "boe-gbp-secured-credit-research-refresh-v1.yml",
    "boj-jpy-bank-credit-research-refresh-v1.yml",
}
workflow_dir=p.parent
root=p.parents[2]
names={(workflow_dir/f).read_text(encoding="utf-8").splitlines()[0].removeprefix("name: ") for f in expected_workflows}
assert set(research_sources)==names
triggers=s.split("  workflow_run:",1)[1].split("permissions:",1)[0]
proof_if=s.split("      - name: Verify the updated Next data",1)[1].split("        env:",1)[0]
for name,file in research_sources.items():
    assert "'"+name+"'" in triggers and "'"+name+"'" in proof_if,name
    assert (root/"site/fx-quant-v2/next"/file).is_file(),file
semaphore=(workflow_dir/"g8-economic-semaphore-source-recovery-v1.yml").read_text(encoding="utf-8")
assert "gh workflow run publish-fx-quant-v2.yml" not in semaphore
assert "live_data/sections/NATIVE_LIQ_DATA.json" in s
assert "live_data/sections/MACRO_SERIES.json" in s
print("NEXT_SEMAPHORE_LIQUIDITY_PUBLIC_DELIVERY_CONTRACT_PASS",len(names))

# Pushes that change the approved reader, and explicit dispatches, must
# certify the same source-to-reader path instead of reporting a branch-only success.
assert "github.event_name == 'push' || github.event_name == 'workflow_dispatch' ||" in proof_if
block=s.split('label = "NEXT_G8_LIQUIDITY_PUBLIC_HTTP"',1)[1].split("elif source_workflow in research_sources:",1)[0]
for file in ("index.html","app.js","liquidity-credit-studio.js","liquidity-source-policy-gate-v1.js",
             "live_data/sections/NATIVE_LIQ_DATA.json","live_data/sections/ESTIMATED_RESIDUAL_GAPS.json"):
    assert '"'+file+'"' in block,file
assert "research_sources.items()" in block
assert 'git show "origin/gh-pages:$f" > "$f"' in s
assert "budget_seconds=480" in s
print("NEXT_G8_LIQUIDITY_PUBLIC_DELIVERY_CONTRACT_PASS",len(names)-1+6)

# The economic monitor must reach public Pages as an entire reader/data chain
# on both source completion and approved code changes. CSS is not optional.
for file in ("semaphore-supplement-v1.json","recession-traffic-light-v1.js",
             "recession-traffic-light-v1.css","macro-studio.js",
             "live_data/sections/MACRO_SERIES.json"):
    assert '"'+file+'"' in block,file
semaphore_branch=s.split('if source_workflow == "G8 Economic Semaphore Source Recovery V1":',1)[1].split("else:",1)[0]
for file in ("recession-traffic-light-v1.js","recession-traffic-light-v1.css","macro-studio.js","live_data/sections/MACRO_SERIES.json"):
    assert '"'+file+'"' in semaphore_branch,file
assert "live_data/sections/MACRO_SERIES.json; do" in s
print("NEXT_G8_ECONOMIC_MONITOR_PUBLIC_DELIVERY_CONTRACT_PASS")

# Market-source updates must verify both consumers and the public feed.
assert "'FX Quant V2 Cross-Asset Published Source Refresh'" in proof_if
market_block=s.split('label = "CROSS_ASSET_PUBLIC_HTTP"',1)[1].split("elif source_workflow in research_sources:",1)[0]
for file in ("cross-asset-live-data.json","cross-asset.html","next/app.js","next/index.html"):
    assert '"site/fx-quant-v2/'+file+'"' in market_block,file
print("CROSS_ASSET_PUBLIC_DELIVERY_CONTRACT_PASS")

# The OIS producers can succeed without any public HTTP proof under the old
# condition. Both source completion and code pushes must check the data and
# the readers, not just branch equality. All paths here are owned by V2.
pricing_block=s.split("pricing_paths = ",1)[1].split("government_paths =",1)[0].strip()
government_block=s.split("government_paths = ",1)[1].split("rate_workflows =",1)[0].strip()
pricing_paths=set(literal_eval(pricing_block))
government_paths=set(literal_eval(government_block))
expected_pricing={
    "ois-pricing-snapshot.json","ois-same-contract-repricing-research.json",
    "pricing-relative-28pairs-research.json","next/rates-pricing-history-v1.json",
    "next/rates-pricing-history-v1.js","next/rates-pricing-moves-v1.js",
    "next/rates-relative-pricing-v1.js","next/rates-studio.js",
    "next/central-bank-studio.js","next/g8-rates-shadow.js",
}
expected_government={
    "chf-2y-estimate-research.json","chf-snb-paired-history.json",
    "nzd-rbnz-b2-reconciled-research.json","next/fx-rates-bridge.js",
    "next/decision-journey.js","next/currency-studio.js",
    "next/currency-data-fallback.js","next/rates-studio.js",
}
assert pricing_paths=={"site/fx-quant-v2/"+f for f in expected_pricing}
assert government_paths=={"site/fx-quant-v2/"+f for f in expected_government}
for file in pricing_paths|government_paths:
    assert (root/file).is_file(),file
for producer in ("OIS G8 History Persistent Daily V1","OIS Estimated Snapshot Repricing V1",
                 "FX Quant V2 Relative Pricing 28-Pair Research",
                 "CHF SNB 10Y Informational Context V1","FX Quant V2 CHF NZD Same-Basis Research Refresh"):
    assert "'"+producer+"'" in triggers and "'"+producer+"'" in proof_if,producer
assert "paths += pricing_paths + government_paths" in s
assert 'elif source_workflow in rate_workflows:' in s
assert 'label = "OIS_RATES_PUBLIC_HTTP"' in s
assert "paths = pricing_paths + (" in s and "paths = government_paths + (" in s
assert "paths = tuple(dict.fromkeys(paths))" in s
print("OIS_GOVERNMENT_READER_PUBLIC_DELIVERY_CONTRACT_PASS",len(pricing_paths|government_paths))
