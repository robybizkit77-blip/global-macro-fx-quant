import json, collections, os
src='validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json'
with open(src,encoding='utf-8') as f: d=json.load(f)
rows=d['comparisons']
summary=collections.Counter()
examples={'growth_only_macro_flip':[],'labour_only_macro_flip':[],'both_changed_macro_flip':[],'block_change_no_macro_flip':[]}
for r in rows:
    g=bool(r.get('growth_direction_changed'))
    l=bool(r.get('labour_direction_changed'))
    m=bool(r.get('macro_polarity_changed'))
    t=bool(r.get('macro_turning_changed'))
    if g: summary['growth_changed']+=1
    if l: summary['labour_changed']+=1
    if g and l: summary['both_blocks_changed']+=1
    if g and not l: summary['growth_only_changed']+=1
    if l and not g: summary['labour_only_changed']+=1
    if m:
        summary['macro_flips']+=1
        if g and not l:
            summary['macro_flip_growth_only']+=1
            examples['growth_only_macro_flip'].append(r['checkpoint'])
        elif l and not g:
            summary['macro_flip_labour_only']+=1
            examples['labour_only_macro_flip'].append(r['checkpoint'])
        elif g and l:
            summary['macro_flip_both']+=1
            examples['both_changed_macro_flip'].append(r['checkpoint'])
        else:
            summary['macro_flip_without_block_dir_change']+=1
    elif g or l:
        summary['block_change_no_macro_flip']+=1
        examples['block_change_no_macro_flip'].append(r['checkpoint'])
    if t:
        if g and not l: summary['turning_change_growth_only']+=1
        elif l and not g: summary['turning_change_labour_only']+=1
        elif g and l: summary['turning_change_both']+=1
        else: summary['turning_change_without_block_dir_change']+=1
out={
 'schema':'GMFQ_CAD_PIT_REVISION_BLOCK_ATTRIBUTION_V1',
 'source':src,
 'engine_ref':'engine-freeze-v1-2026-10-02',
 'totals':dict(summary),
 'rates':{
   'growth_revision_effect_pct':round(100*summary['growth_changed']/len(rows),2),
   'labour_revision_effect_pct':round(100*summary['labour_changed']/len(rows),2),
   'macro_flip_from_growth_only_pct_of_flips':round(100*summary['macro_flip_growth_only']/summary['macro_flips'],2),
   'macro_flip_from_labour_only_pct_of_flips':round(100*summary['macro_flip_labour_only']/summary['macro_flips'],2),
   'macro_flip_from_both_pct_of_flips':round(100*summary['macro_flip_both']/summary['macro_flips'],2),
 },
 'examples':{k:v[:12] for k,v in examples.items()},
 'interpretation':{
   'dominant_block':'growth' if summary['growth_changed']>summary['labour_changed'] else 'labour' if summary['labour_changed']>summary['growth_changed'] else 'balanced',
   'note':'Attribution is descriptive only. No threshold or model-rule changes are permitted from this audit.'
 }
}
os.makedirs('validation',exist_ok=True)
with open('validation/CAD_PIT_REVISION_BLOCK_ATTRIBUTION_2026-10-03.json','w',encoding='utf-8') as f: json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False,indent=2))
