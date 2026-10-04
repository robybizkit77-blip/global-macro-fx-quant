from pathlib import Path
import json,re
from datetime import datetime

ROOT=Path('.')
parts=[ROOT/'payload'/f'part-{i:02d}.txt' for i in range(16)]
for p in parts:
    if not p.exists():
        raise SystemExit(f'missing {p}')
text='\n'.join(p.read_text(encoding='utf-8',errors='replace') for p in parts)

DATE_RE=re.compile(r'\b(20\d{2}-\d{2}-\d{2})\b')

def scan_balanced_object(src,start):
    i=src.find('{',start)
    if i<0:return None,None
    depth=0; quote=None; esc=False
    for j in range(i,len(src)):
        ch=src[j]
        if quote:
            if esc: esc=False
            elif ch=='\\': esc=True
            elif ch==quote: quote=None
            continue
        if ch in ('"',"'"):
            quote=ch; continue
        if ch=='{': depth+=1
        elif ch=='}':
            depth-=1
            if depth==0:return i,j+1
    return i,None

markers=['window.__GMFQ_DATA','GMFQ_RUNTIME_VALIDATION_MANIFEST']
marker_positions={m:[x.start() for x in re.finditer(re.escape(m),text)] for m in markers}

obj=None; parse_error=None; obj_span=None
m=text.find('window.__GMFQ_DATA')
if m>=0:
    eq=text.find('=',m)
    if eq>=0:
        a,b=scan_balanced_object(text,eq)
        obj_span=[a,b] if a is not None else None
        if a is not None and b is not None:
            raw=text[a:b]
            try: obj=json.loads(raw)
            except Exception as e: parse_error=f'{type(e).__name__}: {e}'

def all_dates(v):
    found=[]
    def walk(x):
        if isinstance(x,dict):
            for k,val in x.items():
                walk(k); walk(val)
        elif isinstance(x,list):
            for z in x: walk(z)
        elif isinstance(x,str): found.extend(DATE_RE.findall(x))
    walk(v)
    return sorted(set(found))

def summary_for(v):
    dates=all_dates(v)
    return {
      'type':type(v).__name__,
      'date_count':len(dates),
      'min_date':dates[0] if dates else None,
      'max_date':dates[-1] if dates else None,
      'keys':sorted(v.keys())[:100] if isinstance(v,dict) else None,
      'length':len(v) if isinstance(v,(dict,list,str)) else None,
    }

report={
 'schema':'GMFQ_V490_RUNTIME_DATA_INVENTORY_V1',
 'created_at':'2026-10-04',
 'parts':[{'file':str(p),'bytes':p.stat().st_size} for p in parts],
 'runtime_bytes':len(text.encode('utf-8')),
 'marker_positions':marker_positions,
 'gmfq_data_object_span':obj_span,
 'gmfq_data_json_parse_error':parse_error,
 'gmfq_data_json_parsed':obj is not None,
 'top_level':{},
 'global_date_range':None,
}
if obj is not None:
    report['top_level']={k:summary_for(v) for k,v in obj.items()}
    dates=all_dates(obj)
    report['global_date_range']={'count':len(dates),'min':dates[0] if dates else None,'max':dates[-1] if dates else None}
else:
    # Fallback: inventory known reference names and nearby assignment patterns.
    names=sorted(set(re.findall(r'__GMFQ_DATA\.([A-Z0-9_]+)',text)))
    report['referenced_data_keys']=names
    report['assignment_snippets']={}
    for name in names:
        pats=[f'__GMFQ_DATA.{name}=',f'__GMFQ_DATA["{name}"]=',f"__GMFQ_DATA['{name}']="]
        pos=-1
        for pat in pats:
            pos=text.find(pat)
            if pos>=0: break
        if pos>=0: report['assignment_snippets'][name]=text[max(0,pos-80):pos+240]
    dates=sorted(set(DATE_RE.findall(text)))
    report['global_date_range']={'count':len(dates),'min':dates[0] if dates else None,'max':dates[-1] if dates else None}

out=ROOT/'validation'/'LIVE_RUNTIME_DATA_INVENTORY_2026-10-04.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'parsed':report['gmfq_data_json_parsed'],'keys':list(report.get('top_level',{})),'dates':report['global_date_range']},ensure_ascii=False))
