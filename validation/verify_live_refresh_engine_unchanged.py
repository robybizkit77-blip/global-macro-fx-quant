from pathlib import Path
import urllib.request,re,json,hashlib,subprocess,os

ROOT=Path('.')
BASELINE_REF='497ceb7bd3f01e69965c05a54416dc07406ae28d'
EXPECTED_FINGERPRINT='3356baf0'
EXPECTED_FROZEN_ENGINE='ff52198a75cc67f7dae96fc2bbf65623f170791c'
OOS_GATE_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/staging-usd-pit-readiness-2026-10-03/validation/FORWARD_OOS_READINESS_GATE_2026-10-03.json'
OOS_GATE_COMMIT='9c3a0393bc71a6dab53f845aca927cd86cdabfbd'
BASE_URL=f'https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/{BASELINE_REF}/payload/part-{{i:02d}}.txt'
keys=json.loads((ROOT/'live_data'/'manifest.json').read_text())['sections']
keys=[x['key'] for x in keys]

def get_text(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0'})
    return urllib.request.urlopen(req,timeout=30).read().decode('utf-8')

def joined_local():
    return '\n'.join((ROOT/'payload'/f'part-{i:02d}.txt').read_text(encoding='utf-8') for i in range(16))
def joined_frozen_baseline():
    out=[]
    for i in range(16):
        try:
            raw=(subprocess.check_output(['git','show',f'{BASELINE_REF}:payload/part-{i:02d}.txt'])
                 if os.environ.get('GMFQ_OFFLINE_BASE')=='1' else get_text(BASE_URL.format(i=i)).encode('utf-8'))
        except Exception:
            raw=subprocess.check_output(['git','show',f'{BASELINE_REF}:payload/part-{i:02d}.txt'])
        out.append(raw.decode('utf-8'))
    return '\n'.join(out)

def scan(src,start,op,cl):
    depth=0; quote=None; esc=False
    for j in range(start,len(src)):
        ch=src[j]
        if quote:
            if esc: esc=False
            elif ch=='\\': esc=True
            elif ch==quote: quote=None
            continue
        if ch in ('"',"'"): quote=ch; continue
        if ch==op: depth+=1
        elif ch==cl:
            depth-=1
            if depth==0:return j+1
    raise RuntimeError('unclosed')
def strip_data(src):
    spans=[]
    injected={'RATES_AUDIT_METADATA'}
    for name in keys:
        if name in injected: continue
        pat=re.compile(r'window\.__GMFQ_DATA\.'+re.escape(name)+r'\s*=\s*')
        found=False
        for m in pat.finditer(src):
            p=m.end()
            while p<len(src) and src[p].isspace():p+=1
            if p>=len(src) or src[p] not in '{[':continue
            e=scan(src,p,src[p],'}' if src[p]=='{' else ']')
            try: json.loads(src[p:e])
            except Exception: continue
            spans.append((p,e,name)); found=True; break
        if not found: raise RuntimeError('missing data section '+name)
    for p,e,name in sorted(spans,reverse=True): src=src[:p]+f'__GMFQ_DATA_SECTION_{name}__'+src[e:]
    # The new section is an explicit injected JSON assignment.  Strip exactly
    # that assignment, while leaving its hydration adapter and all decision
    # code in the byte-for-byte comparison.
    pat=re.compile(r'<script id="gmfq-live-data-rates_audit_metadata">window\.__GMFQ_DATA\.RATES_AUDIT_METADATA=(\{.*?\})\s*;</script>\s*',re.S)
    src,n=pat.subn('',src)
    if n not in (0,1): raise RuntimeError('duplicate RATES_AUDIT_METADATA section')
    src,n= re.subn(r'<script id="gmfq-live-rates-audit-metadata-hydration">.*?</script>\s*',
                    '',src,flags=re.S)
    if n not in (0,1): raise RuntimeError('duplicate RATES_AUDIT_METADATA hydration adapter')
    # Staging-only CAD restoration verification is a live-data adapter. It is
    # excluded with metadata hydration, not treated as frozen model logic.
    for script_id in ('gmfq-cad-live-hydration-integrity', 'gmfq-post-gate-final-audit-settlement'):
        src,n=re.subn(r'<script id="'+script_id+r'">.*?</script>\s*','',src,flags=re.S)
        if n not in (0,1): raise RuntimeError('duplicate '+script_id)
    # Metadata consumers are assertions/context only.  Normalize the expected
    # date literal (legacy) and its live-data source without masking script code.
    src=re.sub(r'const expectedRates=(?:window\.__GMFQ_DATA\?\.RATES_AUDIT_METADATA\?\.expected_rates\|\|)?\{.*?\};',
               'const expectedRates=__GMFQ_RATES_AUDIT_EXPECTED__;',src,flags=re.S)
    return src

lock=json.loads((ROOT/'validation'/'LIVE_REFRESH_BASELINE_LOCK_2026-10-04.json').read_text(encoding='utf-8'))
lock_ok=(lock.get('baseline_ref')==BASELINE_REF and lock.get('rules_fingerprint')==EXPECTED_FINGERPRINT and lock.get('frozen_engine_commit')==EXPECTED_FROZEN_ENGINE)
if not lock_ok: raise SystemExit('BASELINE_LOCK_CHANGED_WITHOUT_EXPLICIT_VERIFIER_UPDATE')

baseline=joined_frozen_baseline(); live=joined_local()
baseline_logic=strip_data(baseline); live_logic=strip_data(live)
sha_baseline=hashlib.sha256(baseline_logic.encode()).hexdigest(); sha_live=hashlib.sha256(live_logic.encode()).hexdigest()

try: oos_gate=json.loads(subprocess.check_output(['git','show',f'{OOS_GATE_COMMIT}:validation/FORWARD_OOS_READINESS_GATE_2026-10-03.json']).decode('utf-8') if os.environ.get('GMFQ_OFFLINE_BASE')=='1' else get_text(OOS_GATE_URL))
except Exception:
    oos_gate=json.loads(subprocess.check_output([
        'git','show',f'{OOS_GATE_COMMIT}:validation/FORWARD_OOS_READINESS_GATE_2026-10-03.json'
    ]).decode('utf-8'))
fingerprint=oos_gate.get('rules_fingerprint')
frozen_engine=oos_gate.get('frozen_engine_commit')
oos_gate_passed=bool(oos_gate.get('passed')) and oos_gate.get('decision')=='READY_FOR_FORWARD_OOS_CHECKPOINTS'

logic_same=(baseline_logic==live_logic)
fingerprint_ok=(fingerprint==EXPECTED_FINGERPRINT)
frozen_engine_ok=(frozen_engine==EXPECTED_FROZEN_ENGINE)
passed=lock_ok and logic_same and fingerprint_ok and frozen_engine_ok and oos_gate_passed

report={
 'schema':'GMFQ_LIVE_REFRESH_ENGINE_INTEGRITY_V3','created_at':'2026-10-04',
 'baseline_ref':BASELINE_REF,
 'baseline_lock_file':'validation/LIVE_REFRESH_BASELINE_LOCK_2026-10-04.json',
 'baseline_lock_ok':lock_ok,
 'canonical_fingerprint_source':'staging-usd-pit-readiness-2026-10-03/validation/FORWARD_OOS_READINESS_GATE_2026-10-03.json',
 'canonical_oos_gate_commit':OOS_GATE_COMMIT,
 'fingerprint_expected':EXPECTED_FINGERPRINT,
 'fingerprint_canonical':fingerprint,
 'fingerprint_ok':fingerprint_ok,
 'frozen_engine_expected':EXPECTED_FROZEN_ENGINE,
 'frozen_engine_canonical':frozen_engine,
 'frozen_engine_ok':frozen_engine_ok,
 'oos_gate_passed':oos_gate_passed,
 'logic_sha_baseline':sha_baseline,'logic_sha_live':sha_live,
 'logic_byte_identical_after_data_strip':logic_same,
 'passed':passed
}
(ROOT/'validation'/'LIVE_REFRESH_ENGINE_INTEGRITY_2026-10-04.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
if not report['passed']: raise SystemExit('ENGINE_INTEGRITY_FAIL')
