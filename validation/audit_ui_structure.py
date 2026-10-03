import json,re,glob,collections,os
parts=sorted(glob.glob('payload/part-*.txt'))
text='\n'.join(open(p,encoding='utf-8',errors='ignore').read() for p in parts)
# HTML ids
ids=re.findall(r'\bid=["\']([^"\']+)["\']',text)
id_counts=collections.Counter(ids)
dup_ids={k:v for k,v in id_counts.items() if v>1}
# named function declarations + explicit window/global assignments
funcs=re.findall(r'\bfunction\s+([A-Za-z_$][\w$]*)\s*\(',text)
func_counts=collections.Counter(funcs)
dup_funcs={k:v for k,v in func_counts.items() if v>1}
window_names=re.findall(r'\bwindow\.([A-Za-z_$][\w$]*)\s*=',text)
window_counts=collections.Counter(window_names)
dup_window={k:v for k,v in window_counts.items() if v>1}
# Renderer-like symbols are especially relevant for UI overlap
renderer_pat=re.compile(r'(?i)(render|renderer|draw|mount|hydrate|refresh|update|apply).*')
renderer_dups={k:v for k,v in {**dup_funcs,**dup_window}.items() if renderer_pat.match(k)}
# Section markers / data-testid-ish selectors
sections=re.findall(r'\b(?:data-section|data-view|data-panel)=["\']([^"\']+)["\']',text)
section_counts=collections.Counter(sections)
dup_sections={k:v for k,v in section_counts.items() if v>1}
# Repeated exact DOM ids are hard failures. Function/window duplicates are review items because layered overrides may be intentional.
result={
 'schema':'GMFQ_UI_STRUCTURE_STATIC_AUDIT_V1',
 'engine_ref':'engine-freeze-v1-2026-10-02',
 'payload_files':len(parts),
 'payload_bytes':sum(os.path.getsize(p) for p in parts),
 'html_id_count':len(ids),
 'unique_html_ids':len(id_counts),
 'duplicate_html_ids':dup_ids,
 'duplicate_section_markers':dup_sections,
 'duplicate_named_functions':dup_funcs,
 'duplicate_window_assignments':dup_window,
 'renderer_related_duplicates':renderer_dups,
 'hard_fail':bool(dup_ids),
 'review_required':bool(renderer_dups or dup_sections),
 'interpretation':{
   'duplicate_html_id':'Potential DOM binding collision; must be fixed before UI redesign.',
   'duplicate_function_or_window':'May be deliberate override layering; requires manual lineage check before removal.',
   'renderer_duplicate':'High-priority review for double-render/overwritten renderer risk.'
 }
}
os.makedirs('validation',exist_ok=True)
with open('validation/UI_STRUCTURE_STATIC_AUDIT_2026-10-03.json','w',encoding='utf-8') as f:
 json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False,indent=2))
