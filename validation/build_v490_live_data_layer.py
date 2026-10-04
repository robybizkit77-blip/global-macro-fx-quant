from pathlib import Path
import json,re,hashlib,subprocess,sys

ROOT=Path('.')
PAY=ROOT/'payload'
OUT=ROOT/'live_data'/'sections'
OUT.mkdir(parents=True,exist_ok=True)
parts=[PAY/f'part-{i:02d}.txt' for i in range(16)]
BASELINE_REF='497ceb7bd3f01e69965c05a54416dc07406ae28d'
from_frozen_baseline='--frozen-baseline' in sys.argv
texts=([subprocess.check_output(['git','show',f'{BASELINE_REF}:payload/part-{i:02d}.txt']).decode('utf-8') for i in range(16)]
       if from_frozen_baseline else [p.read_text(encoding='utf-8',errors='strict') for p in parts])
joined='\n'.join(texts)
orig_hash=hashlib.sha256(joined.encode('utf-8')).hexdigest()

TARGETS=[
'D','CERT53','COUNTRY_CTX','WHAT_CHANGED','NATIVE_RATES_DATA','OIS_DATA',
'MACRO_THERMOMETER_DATA','NATIVE_LIQ_DATA','NATIVE_CB_DATA','V250_COT_CHART_DATA',
'V247_COT_STORIES','TOP_THEMES','MACRO_SERIES'
]
# RATES_AUDIT_METADATA is injected at a stable runtime anchor rather than
# replacing a legacy literal.  It contains publication/audit context only.
INJECTED_TARGETS={'RATES_AUDIT_METADATA':'gmfq-runtime-secondary-metadata-completion-20261001'}

def scan(src,start,op,cl):
    depth=0; quote=None; esc=False
    for j in range(start,len(src)):
        ch=src[j]
        if quote:
            if esc: esc=False
            elif ch=='\\': esc=True
            elif ch==quote: quote=None
            continue
        if ch in ('"',"'"):
            quote=ch; continue
        if ch==op: depth+=1
        elif ch==cl:
            depth-=1
            if depth==0:return j+1
    raise RuntimeError('unclosed literal')

def extract(name):
    pat=re.compile(r'window\.__GMFQ_DATA\.'+re.escape(name)+r'\s*=\s*')
    for m in pat.finditer(joined):
        pos=m.end()
        while pos<len(joined) and joined[pos].isspace():pos+=1
        if pos>=len(joined) or joined[pos] not in '{[': continue
        end=scan(joined,pos,joined[pos],'}' if joined[pos]=='{' else ']')
        raw=joined[pos:end]
        try: json.loads(raw)
        except Exception: continue
        return m.start(),pos,end,raw
    raise RuntimeError(f'no parseable assignment for {name}')

manifest={'schema':'GMFQ_V490_LIVE_DATA_LAYER_V1','created_at':'2026-10-04','runtime_sha256_before':orig_hash,'sections':[]}
spans=[]
for name in TARGETS:
    a,b,c,raw=extract(name)
    fn=f'{name}.json'
    if not from_frozen_baseline:
        (OUT/fn).write_text(raw,encoding='utf-8')
    saved_raw=(OUT/fn).read_text(encoding='utf-8') if from_frozen_baseline else raw
    sha=hashlib.sha256(saved_raw.encode('utf-8')).hexdigest()
    manifest['sections'].append({'key':name,'file':fn,'assignment_start':a,'literal_start':b,'literal_end':c,'bytes':len(saved_raw.encode('utf-8')),'sha256':sha})
    spans.append((b,c,name,raw))

for name,anchor in INJECTED_TARGETS.items():
    marker=f'<script id="{anchor}">'
    if marker not in joined: raise RuntimeError(f'missing injection anchor {anchor}')
    raw=(OUT/f'{name}.json').read_text(encoding='utf-8') if from_frozen_baseline else json.dumps({'schema':'GMFQ_RATES_AUDIT_METADATA_V1','audit_date':'2026-10-04','expected_rates':{}},separators=(',',':'))
    if not from_frozen_baseline:
        (OUT/f'{name}.json').write_text(raw,encoding='utf-8')
    manifest['sections'].append({'key':name,'file':f'{name}.json','insertion_anchor':marker,'bytes':len(raw.encode('utf-8')),'sha256':hashlib.sha256(raw.encode('utf-8')).hexdigest()})

# Exact round trip: replace every extracted literal with its saved raw bytes.
rebuilt=joined
for b,c,name,raw in sorted(spans,reverse=True):
    rebuilt=rebuilt[:b]+raw+rebuilt[c:]
rebuilt_hash=hashlib.sha256(rebuilt.encode('utf-8')).hexdigest()
manifest['runtime_sha256_after_roundtrip']=rebuilt_hash
manifest['byte_identical_roundtrip']=rebuilt==joined
if not manifest['byte_identical_roundtrip']:
    raise RuntimeError('round trip changed runtime')

# Record original chunk lengths and verify we can split the exact joined runtime back.
manifest['parts']=[{'file':p.as_posix(),'chars':len(t),'bytes':len(t.encode('utf-8')),'sha256':hashlib.sha256(t.encode('utf-8')).hexdigest()} for p,t in zip(parts,texts)]
(ROOT/'live_data'/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'sections':len(manifest['sections']),'roundtrip':manifest['byte_identical_roundtrip'],'sha256':orig_hash}))
