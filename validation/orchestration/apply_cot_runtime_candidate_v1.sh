#!/usr/bin/env bash
set -euo pipefail

receipt_dir=${1:?COT candidate directory required}
chart=live_data/sections/V250_COT_CHART_DATA.json
stories=live_data/sections/V247_COT_STORIES.json
manifest=live_data/manifest.v2.json

python validation/update_live_direct_section.py \
  --section V250_COT_CHART_DATA --replacement "$receipt_dir/V250_COT_CHART_DATA.json" \
  --apply > "$receipt_dir/direct-apply.json"
python validation/update_live_derived_sections.py \
  --cot "$receipt_dir/V247_COT_STORIES.json" --apply > "$receipt_dir/derived-apply.json"
python validation/build_live_manifest_v2.py --write "$manifest" > "$receipt_dir/manifest-build.json"
python validation/check_live_update_contract.py > "$receipt_dir/live-contract.json"
python validation/rebuild_live_data_runtime.py --verify-only > "$receipt_dir/runtime-roundtrip.json"
python - "$receipt_dir" "$chart" "$stories" "$manifest" <<'PY'
import json
from pathlib import Path
import subprocess
import sys

directory, chart, stories, manifest = sys.argv[1:]
receipts = Path(directory)
contract = json.loads((receipts / 'live-contract.json').read_text())
runtime = json.loads((receipts / 'runtime-roundtrip.json').read_text())
assert contract['status'] == 'PASS', contract
assert runtime['status'] == 'PASS' and runtime['noop_roundtrip_byte_identical'] is True, runtime
changed = sorted(subprocess.check_output(['git', 'diff', '--name-only'], text=True).splitlines())
assert {chart, stories}.issubset(changed), changed
assert all(p in {chart, stories, manifest} or p.startswith('payload/part-') for p in changed), changed
(receipts / 'changed.txt').write_text('\n'.join(changed) + '\n')
print('COT_PERSISTENT_CONTRACT_AND_SCOPE_PASS', changed)
PY
