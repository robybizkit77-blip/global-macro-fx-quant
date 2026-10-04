from pathlib import Path
import json,re,hashlib,sys
ROOT=Path('.')
PAY=ROOT/'payload'; SEC=ROOT/'live_data'/'sections'
parts=[PAY/f'part-{i:02d}.txt' for i in range(16)]
orig_parts=[p.read_text(encoding='utf-8') for p in parts]
joined='\n'.join(orig_parts)
manifest=json.loads((ROOT/'live_data'/'manifest.json').read_text(encoding='utf-8'))
keys=[s['key'] for s in manifest['sections']]

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

rebuilt=joined
for name in keys:
    a,b=locate(rebuilt,name)
    raw=(SEC/f'{name}.json').read_text(encoding='utf-8')
    json.loads(raw)
    rebuilt=rebuilt[:a]+raw+rebuilt[b:]

if 'GMFQ_RUNTIME_VALIDATION_MANIFEST' not in rebuilt:
    raise RuntimeError('runtime validation manifest missing after repack')

# Split on real newline positions close to original cumulative ratios. Joining the parts
# with the loader's single newline restores rebuilt byte-for-byte.
orig_join_len=len(joined)
orig_bounds=[]; cur=0
for t in orig_parts[:-1]:
    cur+=len(t)
    orig_bounds.append(cur)
    cur+=1
new_parts=[]; last=0
for bound in orig_bounds:
    target=round(bound/orig_join_len*len(rebuilt))
    lo=max(last+1,target-5000); hi=min(len(rebuilt)-1,target+5000)
    candidates=[i for i in range(lo,hi+1) if rebuilt[i]=='\n']
    if not candidates:
        # widen search safely to nearest actual newline
        left=rebuilt.rfind('\n',last+1,target)
        right=rebuilt.find('\n',target)
        candidates=[x for x in (left,right) if x>=last+1]
    if not candidates: raise RuntimeError('cannot find safe newline split')
    cut=min(candidates,key=lambda x:abs(x-target))
    new_parts.append(rebuilt[last:cut]); last=cut+1
new_parts.append(rebuilt[last:])
if len(new_parts)!=16: raise RuntimeError('part count mismatch')
if '\n'.join(new_parts)!=rebuilt: raise RuntimeError('split/join roundtrip failed')

changed=[i for i,(a,b) in enumerate(zip(orig_parts,new_parts)) if a!=b]
report={
 'schema':'GMFQ_V490_REPACK_AUDIT_V1','created_at':'2026-10-04',
 'runtime_sha256_before':hashlib.sha256(joined.encode()).hexdigest(),
 'runtime_sha256_after':hashlib.sha256(rebuilt.encode()).hexdigest(),
 'runtime_changed':rebuilt!=joined,'changed_parts':changed,
 'section_count':len(keys),'split_join_exact':True
}
(ROOT/'validation'/'V490_LIVE_DATA_REPACK_AUDIT_2026-10-04.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if '--write' in sys.argv:
    for p,t in zip(parts,new_parts): p.write_text(t,encoding='utf-8')
print(json.dumps(report))
