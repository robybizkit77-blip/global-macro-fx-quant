import json,re,glob,collections,os
parts=sorted(glob.glob('payload/part-*.txt'))
texts={p:open(p,encoding='utf-8',errors='ignore').read() for p in parts}
text='\n'.join(texts.values())

def locations(pattern, flags=0):
    rx=re.compile(pattern,flags)
    out=collections.defaultdict(list)
    for p,t in texts.items():
        for m in rx.finditer(t):
            name=m.group(1)
            line=t.count('\n',0,m.start())+1
            out[name].append({'file':p,'line':line})
    return out

# HTML ids
id_locs=locations(r'\bid=["\']([^"\']+)["\']')
id_counts={k:len(v) for k,v in id_locs.items()}
dup_ids={k:id_locs[k] for k,v in id_counts.items() if v>1}

# named function declarations + explicit window/global assignments
func_locs=locations(r'\bfunction\s+([A-Za-z_$][\w$]*)\s*\(')
func_counts={k:len(v) for k,v in func_locs.items()}
dup_funcs={k:func_locs[k] for k,v in func_counts.items() if v>1}
window_locs=locations(r'\bwindow\.([A-Za-z_$][\w$]*)\s*=')
window_counts={k:len(v) for k,v in window_locs.items()}
dup_window={k:window_locs[k] for k,v in window_counts.items() if v>1}

renderer_pat=re.compile(r'(?i)(render|renderer|draw|mount|hydrate|refresh|update|apply).*')
renderer_dups={}
for src in (dup_funcs,dup_window):
    for k,v in src.items():
        if renderer_pat.match(k): renderer_dups[k]=v

section_locs=locations(r'\b(?:data-section|data-view|data-panel)=["\']([^"\']+)["\']')
section_counts={k:len(v) for k,v in section_locs.items()}
dup_sections={k:section_locs[k] for k,v in section_counts.items() if v>1}

# Flag symbols redefined across different payload files more strongly than same-scope helper duplicates.
def cross_file(entries):
    return len({x['file'] for x in entries})>1
renderer_cross_file={k:v for k,v in renderer_dups.items() if cross_file(v)}

# Known likely-intentional state assignments are recorded separately from callable/UI renderer collisions.
state_like=re.compile(r'(?i)(state|generation|audit|freshness|baseline|manifest|status|memory|watchlist|summary|coverage|health)')
window_callable_risk={k:v for k,v in dup_window.items() if not state_like.search(k) and cross_file(v)}

result={
 'schema':'GMFQ_UI_STRUCTURE_STATIC_AUDIT_V2',
 'engine_ref':'engine-freeze-v1-2026-10-02',
 'payload_files':len(parts),
 'payload_bytes':sum(os.path.getsize(p) for p in parts),
 'html_id_count':sum(id_counts.values()),
 'unique_html_ids':len(id_counts),
 'duplicate_html_ids':dup_ids,
 'duplicate_section_markers':dup_sections,
 'duplicate_named_functions':dup_funcs,
 'duplicate_window_assignments':dup_window,
 'renderer_related_duplicates':renderer_dups,
 'renderer_cross_file_duplicates':renderer_cross_file,
 'window_callable_cross_file_review':window_callable_risk,
 'hard_fail':bool(dup_ids),
 'review_required':bool(renderer_cross_file or dup_sections or window_callable_risk),
 'interpretation':{
   'duplicate_html_id':'Potential DOM binding collision; must be fixed before UI redesign.',
   'same_file_function_duplicate':'Could be nested/local helpers; lower risk until scope is inspected.',
   'cross_file_renderer_duplicate':'High-priority override-lineage review; later payload may silently replace earlier renderer.',
   'duplicate_section_marker':'May be intentional repeated component, but verify only one canonical section is visible per view.'
 }
}
os.makedirs('validation',exist_ok=True)
with open('validation/UI_STRUCTURE_STATIC_AUDIT_2026-10-03.json','w',encoding='utf-8') as f:
 json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False,indent=2))
