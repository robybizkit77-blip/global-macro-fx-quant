from pathlib import Path
import urllib.request,re,json,hashlib

ROOT=Path('.')
EXPECTED_FINGERPRINT='3356baf0'
EXPECTED_FROZEN_ENGINE='ff52198a75cc67f7dae96fc2bbf65623f170791c'
OOS_GATE_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/staging-usd-pit-readiness-2026-10-03/validation/FORWARD_OOS_READINESS_GATE_2026-10-03.json'
keys=json.loads((ROOT/'live_data'/'manifest.json').read_text())['sections']
keys=[x['key'] for x in keys]

def get_text(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0'})
    return urllib.request.urlopen(req,timeout=30).read().decode('utf-8')

def joined_local():
    return '\n'.join((ROOT/'payload'/f'part-{i:02d}.txt').read_text(encoding='utf-8') for i in range(16))
def joined_main():
    out=[]
    for i in range(16):
        out.append(get_text(f'https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/payload/part-{i:02d}.txt'))
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
    for name in keys:
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
    return src

main=joined_main(); live=joined_local()
main_logic=strip_data(main); live_logic=strip_data(live)
sha_main=hashlib.sha256(main_logic.encode()).hexdigest(); sha_live=hashlib.sha256(live_logic.encode()).hexdigest()

oos_gate=json.loads(get_text(OOS_GATE_URL))
fingerprint=oos_gate.get('rules_fingerprint')
frozen_engine=oos_gate.get('frozen_engine_commit')
oos_gate_passed=bool(oos_gate.get('passed')) and oos_gate.get('decision')=='READY_FOR_FORWARD_OOS_CHECKPOINTS'

logic_same=(main_logic==live_logic)
fingerprint_ok=(fingerprint==EXPECTED_FINGERPRINT)
frozen_engine_ok=(frozen_engine==EXPECTED_FROZEN_ENGINE)
passed=logic_same and fingerprint_ok and frozen_engine_ok and oos_gate_passed

report={
 'schema':'GMFQ_LIVE_REFRESH_ENGINE_INTEGRITY_V3','created_at':'2026-10-04',
 'canonical_fingerprint_source':'staging-usd-pit-readiness-2026-10-03/validation/FORWARD_OOS_READINESS_GATE_2026-10-03.json',
 'fingerprint_expected':EXPECTED_FINGERPRINT,
 'fingerprint_canonical':fingerprint,
 'fingerprint_ok':fingerprint_ok,
 'frozen_engine_expected':EXPECTED_FROZEN_ENGINE,
 'frozen_engine_canonical':frozen_engine,
 'frozen_engine_ok':frozen_engine_ok,
 'oos_gate_passed':oos_gate_passed,
 'logic_sha_main':sha_main,'logic_sha_live':sha_live,
 'logic_byte_identical_after_data_strip':logic_same,
 'passed':passed
}
(ROOT/'validation'/'LIVE_REFRESH_ENGINE_INTEGRITY_2026-10-04.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
if not report['passed']: raise SystemExit('ENGINE_INTEGRITY_FAIL')
