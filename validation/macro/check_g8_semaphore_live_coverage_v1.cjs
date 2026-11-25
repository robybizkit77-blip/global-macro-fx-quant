'use strict';
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const {model,coverage,inflationContext}=require(path.join(root,'site/fx-quant-v2/next/recession-traffic-light-v1.js'));
const catalog=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/MACRO_SERIES.json'),'utf8'));
const overlay=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const today=new Date().toISOString().slice(0,10);
const missing=[],manual=[],counts={};
for(const c of coverage){
 const rows=model(catalog,today,c,overlay);
 counts[c]=rows.filter(x=>x.signal.tone!=='neutral').length;
 for(const r of rows){
  if(r.signal.tone==='neutral')missing.push(c+'_'+r.key);
  else if(r.signalSource!=='original'&&overlay.series.some(s=>s.ccy===c&&s.area===r.key&&s.quality==='SOURCE_VERIFIED_MANUAL_NONPIT'))manual.push(c+'_'+r.key);
 }
}
const total=Object.values(counts).reduce((a,b)=>a+b,0);
console.log(JSON.stringify({status:total===56&&!manual.length?'COMPLETE_AUTOMATIC':total===56?'COMPLETE_WITH_MANUAL_FALLBACK':'PARTIAL',as_of:today,classified:total,total:56,counts,missing,manual,automatically_classified:total-manual.length}));
if(missing.length||manual.length)console.log('::warning title=G8 source continuity::Missing '+missing.join(', ')+'; manual '+manual.join(', '));

 // Separate the dashboard's usable annual rates from confirmed source freshness.
 const core=Object.fromEntries(coverage.map(c=>{
   const rows=inflationContext(catalog,today,c,overlay).filter(x=>/core|trimmed|median|\btrim\b/i.test(x.label));
   const sourceAudit=overlay.inflation_context?.audit?.[c]||null;
   return [c,{status:rows.length&&rows.every(x=>x.available&&!x.stale&&x.direction&&!x.annualGap)?'USABLE_MOMENTUM':'REVIEW_REQUIRED',
    series:rows.map(x=>({id:x.id,period:x.period||null,age:x.age??null,source:x.source||null,
      latest_index_period:x.latestIndexPeriod||null,annual_gap:!!x.annualGap,
      stale:x.stale??null,direction:x.direction||null,available:x.available})),source_audit:sourceAudit}];
 }));
 const usable=Object.values(core).filter(x=>x.status==='USABLE_MOMENTUM').length;
 console.log(JSON.stringify({status:'CORE_INFLATION_AUDIT',as_of:today,usable_momentum:usable,total:coverage.length,
    freshness_scope:'Age and available comparisons only; not a release-calendar freshness certification',countries:core}));
 if(usable<coverage.length)console.log('::warning title=G8 core inflation::Incomplete usable core momentum: '+usable+'/'+coverage.length);
