from pathlib import Path
import json,re

ROOT=Path('.')
parts=[ROOT/'payload'/f'part-{i:02d}.txt' for i in range(16)]
for p in parts:
    if not p.exists(): raise SystemExit(f'missing {p}')
text='\n'.join(p.read_text(encoding='utf-8',errors='replace') for p in parts)
DATE_RE=re.compile(r'\b(20\d{2}-\d{2}-\d{2})\b')

def scan_balanced(src,start,open_ch,close_ch):
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
        if ch==open_ch: depth+=1
        elif ch==close_ch:
            depth-=1
            if depth==0:return j+1
    return None

def parse_rhs(pos):
    n=len(text)
    while pos<n and text[pos].isspace(): pos+=1
    if pos>=n:return None,None,None,'empty rhs'
    ch=text[pos]
    if ch in '{[':
        end=scan_balanced(text,pos,ch,'}' if ch=='{' else ']')
        if end is None:return pos,None,None,'unclosed literal'
        raw=text[pos:end]
        try:return pos,end,json.loads(raw),None
        except Exception as e:return pos,end,None,f'{type(e).__name__}: {e}'
    if ch in ('"',"'"):
        q=ch; esc=False
        for j in range(pos+1,n):
            c=text[j]
            if esc:esc=False
            elif c=='\\':esc=True
            elif c==q:
                raw=text[pos:j+1]
                try:return pos,j+1,json.loads(raw if q=='"' else json.dumps(raw[1:-1])),None
                except Exception as e:return pos,j+1,None,f'{type(e).__name__}: {e}'
        return pos,None,None,'unclosed string'
    end=text.find(';',pos)
    if end<0:end=min(n,pos+1000)
    return pos,end,None,'non-json expression'

def all_dates(v):
    found=[]
    def walk(x):
        if isinstance(x,dict):
            for k,val in x.items(): walk(k); walk(val)
        elif isinstance(x,list):
            for z in x: walk(z)
        elif isinstance(x,str): found.extend(DATE_RE.findall(x))
    walk(v)
    return sorted(set(found))

def summary_for(v):
    dates=all_dates(v)
    return {'type':type(v).__name__,'date_count':len(dates),'min_date':dates[0] if dates else None,'max_date':dates[-1] if dates else None,'keys':sorted(v.keys())[:150] if isinstance(v,dict) else None,'length':len(v) if isinstance(v,(dict,list,str)) else None}

assign_re=re.compile(r'window\.__GMFQ_DATA\.([A-Za-z0-9_]+)\s*=\s*')
assignments={}
for m in assign_re.finditer(text):
    name=m.group(1)
    a,b,val,err=parse_rhs(m.end())
    rec={'assignment_pos':m.start(),'rhs_span':[a,b],'json_parsed':val is not None,'parse_error':err}
    if val is not None: rec['summary']=summary_for(val)
    assignments.setdefault(name,[]).append(rec)

# bracket notation too
bracket_re=re.compile(r'window\.__GMFQ_DATA\[(?:"|\')([^"\']+)(?:"|\')\]\s*=\s*')
for m in bracket_re.finditer(text):
    name=m.group(1)
    a,b,val,err=parse_rhs(m.end())
    rec={'assignment_pos':m.start(),'rhs_span':[a,b],'json_parsed':val is not None,'parse_error':err,'notation':'bracket'}
    if val is not None: rec['summary']=summary_for(val)
    assignments.setdefault(name,[]).append(rec)

parsed_latest={}
for name,recs in assignments.items():
    parsed=[r for r in recs if r['json_parsed']]
    if parsed: parsed_latest[name]=parsed[-1]['summary']

all_runtime_dates=sorted(set(DATE_RE.findall(text)))
report={
 'schema':'GMFQ_V490_RUNTIME_DATA_INVENTORY_V2',
 'created_at':'2026-10-04',
 'parts':[{'file':str(p),'bytes':p.stat().st_size} for p in parts],
 'runtime_bytes':len(text.encode('utf-8')),
 'runtime_date_range':{'count':len(all_runtime_dates),'min':all_runtime_dates[0] if all_runtime_dates else None,'max':all_runtime_dates[-1] if all_runtime_dates else None},
 'runtime_validation_manifest_positions':[x.start() for x in re.finditer('GMFQ_RUNTIME_VALIDATION_MANIFEST',text)],
 'data_assignment_keys':sorted(assignments),
 'assignments':assignments,
 'latest_parsed_assignment_summary':parsed_latest,
 'reference_keys':sorted(set(re.findall(r'__GMFQ_DATA\.([A-Z0-9_]+)',text))),
}
out=ROOT/'validation'/'LIVE_RUNTIME_DATA_INVENTORY_2026-10-04.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'keys':report['data_assignment_keys'],'parsed_latest':parsed_latest,'runtime_dates':report['runtime_date_range']},ensure_ascii=False))
