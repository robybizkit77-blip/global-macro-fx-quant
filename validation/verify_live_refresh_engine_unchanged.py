from pathlib import Path
import urllib.request,re,json,hashlib

ROOT=Path('.')
keys=json.loads((ROOT/'live_data'/'manifest.json').read_text())['sections']
keys=[x['key'] for x in keys]

def joined_local():
    return '\n'.join((ROOT/'payload'/f'part-{i:02d}.txt').read_text(encoding='utf-8') for i in range(16))
def joined_main():
    out=[]
    for i in range(16):
        url=f'https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/payload/part-{i:02d}.txt'
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0'})
        out.append(urllib.request.urlopen(req,timeout=30).read().decode('utf-8'))
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
report={
 'schema':'GMFQ_LIVE_REFRESH_ENGINE_INTEGRITY_V2','created_at':'2026-10-04',
 'fingerprint_reference':'3356baf0','fingerprint_check_scope':'OOS_VALIDATION_METADATA_NOT_RUNTIME_LITERAL',
 'logic_sha_main':sha_main,'logic_sha_live':sha_live,
 'logic_byte_identical_after_data_strip':main_logic==live_logic,
 'passed':main_logic==live_logic
}
(ROOT/'validation'/'LIVE_REFRESH_ENGINE_INTEGRITY_2026-10-04.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
if not report['passed']: raise SystemExit('ENGINE_INTEGRITY_FAIL')
