'use strict';
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const {model,coverage}=require(path.join(root,'site/fx-quant-v2/next/recession-traffic-light-v1.js'));
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
