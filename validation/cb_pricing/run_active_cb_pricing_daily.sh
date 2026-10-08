#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
WORKDIR="${CB_DAILY_WORKDIR:-/tmp/cb-pricing-daily}"
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"

CURRENCIES=(AUD CAD GBP JPY)
RUNTIME_FILES=(
  live_data/manifest.v2.json
  live_data/sections/OIS_DATA.json
  live_data/sections/NATIVE_CB_DATA.json
  payload/part-00.txt
)

python3 - <<'PY'
import json, pathlib
p=pathlib.Path('validation/cb_pricing/ACTIVE_REFRESH_READINESS_2026-10-08.json')
d=json.loads(p.read_text())
want=['AUD','CAD','GBP','JPY']
if sorted(d['summary']['active_currencies']) != want:
    raise SystemExit('active coverage mismatch')
if sorted(d['summary']['daily_ready']) != want:
    raise SystemExit('daily-ready coverage mismatch')
if d['summary']['active_but_not_daily_ready'] != []:
    raise SystemExit('active currency remains not DAILY_READY')
for c in want:
    x=d['currencies'][c]
    for k in ('source_collector_ready','candidate_builder_ready','dry_run_apply_certified'):
        if x.get(k) is not True:
            raise SystemExit(f'{c} missing {k}')
    if x.get('automatic_publication') is not False:
        raise SystemExit(f'{c} automatic publication must remain false')
print('ACTIVE_CB_COVERAGE_PREFLIGHT_PASS')
PY

cp live_data/sections/OIS_DATA.json "$WORKDIR/OIS.baseline.json"
cp live_data/sections/NATIVE_CB_DATA.json "$WORKDIR/NATIVE.baseline.json"
cp payload/part-00.txt "$WORKDIR/part-00.baseline.txt"
cp live_data/manifest.v2.json "$WORKDIR/manifest.baseline.json"
git diff --quiet

if ! curl -L --fail --retry 3 --user-agent 'GLOBAL-MACRO-FX-QUANT daily observation' \
  'https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/oisddata.zip' \
  -o "$WORKDIR/oisddata.zip"; then
  echo 'BoE archive download failed' > "$WORKDIR/GBP.error.txt"
  touch "$WORKDIR/GBP.failed"
fi

collect_build() {
  local c="$1"
  local snapshot="$WORKDIR/$c.snapshot.json"
  local candidate="$WORKDIR/$c.candidate.json"
  local rc=0
  case "$c" in
    AUD)
      python3 validation/cb_pricing/collect_aud_asx_ib.py --output "$snapshot" || rc=$?
      if [[ $rc -eq 0 ]]; then python3 validation/cb_pricing/build_aud_asx_ib_candidate.py --snapshot "$snapshot" --output "$candidate" || rc=$?; fi
      ;;
    CAD)
      python3 validation/cb_pricing/collect_cad_mx_corra.py --output "$snapshot" || rc=$?
      if [[ $rc -eq 0 ]]; then python3 validation/cb_pricing/build_cad_mx_corra_candidate.py --snapshot "$snapshot" --output "$candidate" || rc=$?; fi
      ;;
    GBP)
      if [[ -f "$WORKDIR/GBP.failed" ]]; then return 0; fi
      python3 validation/cb_pricing/collect_gbp_boe_ois.py --zip "$WORKDIR/oisddata.zip" --output "$snapshot" || rc=$?
      if [[ $rc -eq 0 ]]; then python3 validation/cb_pricing/build_gbp_boe_ois_candidate.py --snapshot "$snapshot" --output "$candidate" || rc=$?; fi
      ;;
    JPY)
      python3 validation/cb_pricing/collect_jpy_tfx_tona.py --output "$snapshot" || rc=$?
      if [[ $rc -eq 0 ]]; then python3 validation/cb_pricing/build_jpy_tfx_tona_candidate.py --snapshot "$snapshot" --output "$candidate" || rc=$?; fi
      ;;
    *) return 2 ;;
  esac
  if [[ $rc -ne 0 || ! -s "$candidate" ]]; then
    echo "collector/candidate failed rc=$rc" > "$WORKDIR/$c.error.txt"
    touch "$WORKDIR/$c.failed"
  fi
}

for c in "${CURRENCIES[@]}"; do
  collect_build "$c"
done

validate_candidate_contract() {
  local c="$1"
  if [[ -f "$WORKDIR/$c.failed" ]]; then return 0; fi
  CURRENCY="$c" WORKDIR="$WORKDIR" python3 - <<'PY' || {
import json, os, pathlib
c=os.environ['CURRENCY']; root=pathlib.Path(os.environ['WORKDIR'])
s=json.loads((root/f'{c}.snapshot.json').read_text())
x=json.loads((root/f'{c}.candidate.json').read_text())
if s.get('currency') != c or s.get('schema') != 'GMFQ_CB_PRICING_SOURCE_SNAPSHOT_V1':
    raise SystemExit(f'{c} snapshot contract mismatch')
if x.get('currency') != c or x.get('schema') != 'GMFQ_CB_PRICING_CANDIDATE_V1' or x.get('status') != 'READY_FOR_DRY_RUN':
    raise SystemExit(f'{c} candidate contract mismatch')
if x.get('as_of') != s.get('as_of'):
    raise SystemExit(f'{c} as-of mismatch')
print(c, 'CANDIDATE_CONTRACT_PASS', x['as_of'])
PY
    echo 'candidate contract failed' > "$WORKDIR/$c.error.txt"
    touch "$WORKDIR/$c.failed"
  }
}

for c in "${CURRENCIES[@]}"; do
  validate_candidate_contract "$c"
done

restore_runtime() {
  git checkout -- "${RUNTIME_FILES[@]}" >/dev/null 2>&1 || true
}
trap restore_runtime EXIT

apply_script() {
  case "$1" in
    AUD) echo validation/cb_pricing/apply_aud_asx_ib_candidate.py ;;
    CAD) echo validation/cb_pricing/apply_cad_mx_corra_candidate.py ;;
    GBP) echo validation/cb_pricing/apply_gbp_boe_ois_candidate.py ;;
    JPY) echo validation/cb_pricing/apply_jpy_tfx_tona_candidate.py ;;
  esac
}

dry_run_currency() {
  local c="$1"
  if [[ -f "$WORKDIR/$c.failed" ]]; then return 0; fi
  restore_runtime
  local script
  script="$(apply_script "$c")"
  if (
    set -euo pipefail
    python3 "$script" --candidate "$WORKDIR/$c.candidate.json"
    python3 validation/build_live_manifest_v2.py --write live_data/manifest.v2.json >"$WORKDIR/$c.manifest.json"
    python3 validation/check_cb_pricing_source_registry.py >"$WORKDIR/$c.registry.json"
    python3 validation/check_live_update_contract.py >"$WORKDIR/$c.contract.json"
    python3 validation/rebuild_live_data_runtime.py --verify-only >"$WORKDIR/$c.roundtrip.json"
    CURRENCY="$c" WORKDIR="$WORKDIR" python3 - <<'PY'
import json, os, pathlib, subprocess
c=os.environ['CURRENCY']; root=pathlib.Path(os.environ['WORKDIR'])
bo=json.loads((root/'OIS.baseline.json').read_text())
ao=json.loads(pathlib.Path('live_data/sections/OIS_DATA.json').read_text())
bn=json.loads((root/'NATIVE.baseline.json').read_text())
an=json.loads(pathlib.Path('live_data/sections/NATIVE_CB_DATA.json').read_text())
co=[k for k in bo['currencies'] if bo['currencies'][k] != ao['currencies'][k]]
cn=[k for k in bn if bn[k] != an[k]]
if co != [c] or cn != [c]:
    raise SystemExit(f'{c} semantic scope failure OIS={co} NATIVE={cn}')
changed=sorted(subprocess.check_output(['git','diff','--name-only'], text=True).splitlines())
expected=sorted(['live_data/manifest.v2.json','live_data/sections/NATIVE_CB_DATA.json','live_data/sections/OIS_DATA.json','payload/part-00.txt'])
if changed != expected:
    raise SystemExit(f'{c} file scope failure {changed}')
print(c, 'ISOLATED_DRY_RUN_PASS')
PY
  ); then
    echo PASS > "$WORKDIR/$c.dryrun.txt"
  else
    echo 'isolated dry-run failed' > "$WORKDIR/$c.error.txt"
    touch "$WORKDIR/$c.failed"
  fi
  restore_runtime
  git diff --quiet || {
    echo 'working tree dirty after restore' > "$WORKDIR/$c.error.txt"
    touch "$WORKDIR/$c.failed"
    restore_runtime
  }
}

for c in "${CURRENCIES[@]}"; do
  dry_run_currency "$c"
done

WORKDIR="$WORKDIR" python3 - <<'PY'
import datetime as dt
import json
import os
import pathlib
import subprocess
from zoneinfo import ZoneInfo

root=pathlib.Path(os.environ['WORKDIR'])
market_tz={
    'AUD':'Australia/Sydney',
    'CAD':'America/Toronto',
    'GBP':'Europe/London',
    'JPY':'Asia/Tokyo',
}

def business_day_lag(as_of, local_today):
    if as_of > local_today:
        return -1
    lag=0
    cur=as_of + dt.timedelta(days=1)
    while cur <= local_today:
        if cur.weekday() < 5:
            lag += 1
        cur += dt.timedelta(days=1)
    return lag

now=dt.datetime.now(dt.timezone.utc)
currencies={}
for c in ('AUD','CAD','GBP','JPY'):
    failed=(root/f'{c}.failed').exists()
    item={'runtime_publication':False}
    if failed:
        item['status']='FAILED'
        err=root/f'{c}.error.txt'
        item['error']=err.read_text().strip() if err.exists() else 'unknown failure'
    else:
        snap=json.loads((root/f'{c}.snapshot.json').read_text())
        cand=json.loads((root/f'{c}.candidate.json').read_text())
        as_of=dt.date.fromisoformat(cand['as_of'])
        local_today=now.astimezone(ZoneInfo(market_tz[c])).date()
        lag=business_day_lag(as_of, local_today)
        status='GREEN' if 0 <= lag <= 2 else 'STALE'
        item.update({
            'status':status,
            'as_of':cand['as_of'],
            'source':cand['source'],
            'candidate_status':cand['status'],
            'source_local_date':local_today.isoformat(),
            'business_day_lag':lag,
            'freshness_policy':'GREEN when source as-of is no more than 2 weekdays behind source-local date; weekends excluded, holidays not inferred',
            'isolated_dry_run':'PASS',
            'isolated_semantic_scope':[c],
        })
    currencies[c]=item

statuses=[x['status'] for x in currencies.values()]
if 'FAILED' in statuses:
    overall='FAILED_NO_PUBLICATION'
elif 'STALE' in statuses:
    overall='STALE_NO_PUBLICATION'
else:
    overall='ALL_GREEN_NO_PUBLICATION'
receipt={
    'schema':'GMFQ_ACTIVE_CB_PRICING_DAILY_RECEIPT_V1',
    'generated_at_utc':now.isoformat(),
    'status':overall,
    'currencies':currencies,
    'all_or_nothing_gate':True,
    'promotion_performed':False,
    'live_data_published':False,
    'gh_pages_published':False,
    'automatic_publication':False,
    'working_tree_clean':subprocess.call(['git','diff','--quiet']) == 0,
}
if not receipt['working_tree_clean']:
    receipt['status']='FAILED_NO_PUBLICATION'
    receipt['working_tree_error']='working tree dirty after orchestrated dry-runs'
(root/'DAILY_RECEIPT.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False)+'\n')
print(json.dumps(receipt, indent=2, ensure_ascii=False))
PY

restore_runtime
if ! git diff --quiet; then
  echo 'FINAL_RESTORE_FAILED' >&2
  exit 1
fi

echo "DAILY_RECEIPT=$WORKDIR/DAILY_RECEIPT.json"
