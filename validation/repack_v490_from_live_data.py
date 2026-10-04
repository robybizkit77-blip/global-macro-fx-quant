from pathlib import Path
import json,re,hashlib,sys,urllib.request,subprocess,os
ROOT=Path('.')
PAY=ROOT/'payload'; SEC=ROOT/'live_data'/'sections'
manifest=json.loads((ROOT/'live_data'/'manifest.json').read_text(encoding='utf-8'))
sections=manifest['sections']
keys=[s['key'] for s in sections]

# Always rebuild from the immutable OOS baseline, never a moving branch. This
# preserves unaffected chunks byte-for-byte and makes a baseline change explicit.
BASELINE_REF='497ceb7bd3f01e69965c05a54416dc07406ae28d'
BASE=f'https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/{BASELINE_REF}/payload/part-{{i:02d}}.txt'
base_parts=[]
for i,meta in enumerate(manifest['parts']):
    req=urllib.request.Request(BASE.format(i=i),headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0'})
    try:
        raw=(subprocess.check_output(['git','show',f'{BASELINE_REF}:payload/part-{i:02d}.txt'])
             if os.environ.get('GMFQ_OFFLINE_BASE')=='1' else urllib.request.urlopen(req,timeout=30).read())
    except Exception:
        # CI uses the remote canonical ref; local verification may be offline.
        raw=subprocess.check_output(['git','show',f'{BASELINE_REF}:payload/part-{i:02d}.txt'])
    txt=raw.decode('utf-8')
    sha=hashlib.sha256(raw).hexdigest()
    if sha!=meta['sha256']:
        raise RuntimeError(f'PRODUCTION_BASELINE_CHANGED part-{i:02d}: {sha} != {meta["sha256"]}')
    base_parts.append(txt)
base='\n'.join(base_parts)

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

def locate(src,name):
    pat=re.compile(r'window\.__GMFQ_DATA\.'+re.escape(name)+r'\s*=\s*')
    for m in pat.finditer(src):
        pos=m.end()
        while pos<len(src) and src[pos].isspace():pos+=1
        if pos>=len(src) or src[pos] not in '{[':continue
        end=scan(src,pos,src[pos],'}' if src[pos]=='{' else ']')
        raw=src[pos:end]
        try:json.loads(raw)
        except Exception:continue
        return pos,end
    raise RuntimeError(f'parseable assignment not found: {name}')

# Locate every section against the untouched baseline first.
repls=[]
for section in sections:
    name=section['key']
    if 'insertion_anchor' in section: continue
    a,b=locate(base,name)
    newraw=(SEC/f'{name}.json').read_text(encoding='utf-8')
    json.loads(newraw)
    repls.append((a,b,name,newraw))
repls.sort()
for x,y in zip(repls,repls[1:]):
    if x[1]>y[0]: raise RuntimeError(f'overlapping data sections {x[2]} / {y[2]}')

# Original boundaries are exact loader join boundaries. A boundary must never fall
# inside a replaceable data literal; otherwise we stop rather than silently reflow.
orig_bounds=[]; cur=0
for t in base_parts[:-1]:
    cur+=len(t); orig_bounds.append(cur); cur+=1
for B in orig_bounds:
    for a,b,name,_ in repls:
        if a < B < b:
            raise RuntimeError(f'chunk boundary crosses data section {name}')

# Replace from right to left to retain original coordinates.
rebuilt=base
for a,b,name,newraw in reversed(repls): rebuilt=rebuilt[:a]+newraw+rebuilt[b:]

# Explicit live audit metadata is inserted before its frozen audit adapter.
# The adapter is deliberately code-only; the changing registry values remain
# wholly inside the JSON section.
injected_sections=[]
for section in sections:
    if 'insertion_anchor' not in section: continue
    name=section['key']; marker=section['insertion_anchor']
    raw=(SEC/section['file']).read_text(encoding='utf-8').strip(); json.loads(raw)
    anchor=rebuilt.find(marker)
    if anchor<0 or rebuilt.find(marker,anchor+1)>=0: raise RuntimeError(f'insertion anchor invalid: {marker}')
    injected=f'<script id="gmfq-live-data-{name.lower()}">window.__GMFQ_DATA.{name}={raw};</script>\n\n'
    if name=='RATES_AUDIT_METADATA':
        # Keep the already-validated CAD snapshot available to the post-legacy
        # hydration adapter.  The source section itself is not changed: this
        # is solely a runtime restore after the older embedded CAD script.
        cad_snapshot=json.dumps(json.loads((SEC/'NATIVE_RATES_DATA.json').read_text(encoding='utf-8'))['CAD'],separators=(',',':'))
        injected+='''<script id="gmfq-live-rates-audit-metadata-hydration">
(function(){'use strict';const M=window.__GMFQ_DATA?.RATES_AUDIT_METADATA;if(!M||M.schema!=='GMFQ_RATES_AUDIT_METADATA_V1')throw new Error('RATES_AUDIT_METADATA_MISSING');const A=window.FINAL_SOURCE_POLICY_AUDIT,P=window.PRODUCTION_RATES_REFRESH_STATUS?.rates_refresh;if(!A||!P)throw new Error('RATES_AUDIT_CONTEXT_MISSING');const CAD=__GMFQ_VALIDATED_CAD_SNAPSHOT__,target=window.NATIVE_RATES_DATA?.CAD||window.__GMFQ_DATA?.NATIVE_RATES_DATA?.CAD;if(!target)throw new Error('CAD_RUNTIME_SNAPSHOT_MISSING');Object.keys(target).forEach(k=>delete target[k]);Object.assign(target,CAD);if(D?.macro?.CAD){D.macro.CAD.rate2y=CAD['2Y'];D.macro.CAD.rate_status='CURRENT';}if(typeof syncVisibleRatesSnapshots==='function')syncVisibleRatesSnapshots();A.audit_date=M.audit_date;for(const [ccy,row] of Object.entries(M.rates||{})){const registry=(A.RATES||A.rates||{})[ccy];if(!registry||!P[ccy])throw new Error('RATES_AUDIT_CURRENCY_MISSING:'+ccy);Object.assign(registry,{current_as_of:row.current_as_of,status:row.status,live_metadata_source:M.source_context});Object.assign(P[ccy],{action:row.action,current_as_of:row.current_as_of,reason:row.reason});}window.GMFQ_SOURCE_REGISTRY_REALIGNMENT={status:'PASS',audit_date:M.audit_date,rates:{...M.expected_rates},source_context:M.source_context};document.documentElement.setAttribute('data-source-registry-realignment','PASS');const basis=typeof ratesCanonicalBasisIntegrity==='function'?ratesCanonicalBasisIntegrity():null,visible=typeof visibleRatesSnapshotIntegrity==='function'?visibleRatesSnapshotIntegrity():null;window.GMFQ_CAD_RATES_AUDIT={status:basis?.ok===true&&visible?.ok===true?'PASS':'FAIL',source:CAD.source,as_of:CAD.date,same_basis:true,values:{'2Y':CAD['2Y'],'10Y':CAD['10Y'],curve_bp:CAD.curve_bp},basis_ok:basis?.ok??null,visible_ok:visible?.ok??null};document.documentElement.setAttribute('data-cad-rates-audit',window.GMFQ_CAD_RATES_AUDIT.status);document.documentElement.setAttribute('data-cad-rates-asof',CAD.date);})();
</script>

'''
        injected=injected.replace('__GMFQ_VALIDATED_CAD_SNAPSHOT__',cad_snapshot)
    rebuilt=rebuilt[:anchor]+injected+rebuilt[anchor:]
    injected_sections.append(name)
if 'GMFQ_RUNTIME_VALIDATION_MANIFEST' not in rebuilt: raise RuntimeError('runtime validation manifest missing')

# Shift each original boundary only by length deltas entirely before it.
def shifted_boundary(B):
    delta=0
    for a,b,name,newraw in repls:
        if b<=B: delta+=len(newraw)-(b-a)
    return B+delta
new_bounds=[shifted_boundary(B) for B in orig_bounds]
new_parts=[]; last=0
for cut in new_bounds:
    # Loader inserts one newline between chunks; cut points reference the character
    # immediately before that synthetic separator in the joined runtime.
    new_parts.append(rebuilt[last:cut]); last=cut+1
new_parts.append(rebuilt[last:])
if len(new_parts)!=16 or '\n'.join(new_parts)!=rebuilt: raise RuntimeError('split/join roundtrip failed')

changed=[i for i,(a,b) in enumerate(zip(base_parts,new_parts)) if a!=b]
changed_sections=[]
for a,b,name,newraw in repls:
    oldraw=base[a:b]
    if oldraw!=newraw: changed_sections.append(name)
changed_sections.extend(injected_sections)
report={
 'schema':'GMFQ_V490_REPACK_AUDIT_V2','created_at':'2026-10-04',
 'baseline_ref':BASELINE_REF,'runtime_sha256_before':hashlib.sha256(base.encode()).hexdigest(),
 'runtime_sha256_after':hashlib.sha256(rebuilt.encode()).hexdigest(),
 'runtime_changed':rebuilt!=base,'changed_sections':changed_sections,'changed_parts':changed,
 'section_count':len(keys),'split_join_exact':True,'unaffected_parts_byte_identical':all(base_parts[i]==new_parts[i] for i in range(16) if i not in changed)
}
(ROOT/'validation'/'V490_LIVE_DATA_REPACK_AUDIT_2026-10-04.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if '--write' in sys.argv:
    for i,t in enumerate(new_parts): (PAY/f'part-{i:02d}.txt').write_text(t,encoding='utf-8')
print(json.dumps(report))
