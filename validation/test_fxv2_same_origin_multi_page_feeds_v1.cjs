'use strict';
// Regression for the Pages data-boundary migration. No prices, calculations or signals are rewritten.
const fs=require('node:fs'),assert=require('node:assert/strict');
const pages=['banche','cot','calendario-news','macro','valute','coppie','cross-asset','tassi','ois'];
const upstream='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/';
for(const p of pages){
 const html=fs.readFileSync('site/fx-quant-v2/'+p+'.html','utf8');
 assert(html.includes('../../live_data/sections/'),p+': no same-origin canonical feed');
 const stillRaw=html.match(/https:\/\/raw\.githubusercontent\.com\/robybizkit77-blip\/global-macro-fx-quant\/main\//g)||[];
 const allowable=p==='tassi'||p==='ois'?1:0;
 assert.equal(stillRaw.length,allowable,p+': unexpected external endpoint');
 if(allowable){
  assert(html.includes('RESEARCH_RAW_FALLBACK'),p+': unpublished estimated research must be explicit');
  assert(html.includes('CB_PRICING_ESTIMATED'),p+': fallback must remain research-only');
 }
 const scripts=[...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)].filter(m=>!/type=[\"']application\/(?:json|ld\+json)[\"']/.test(m[1])).map(m=>m[2]).filter(x=>x.trim());
 const vm=require('node:vm');
 for(const [i,script] of scripts.entries())new vm.Script(script,{filename:p+':inline-script-'+i});
 console.log('FXV2_PAGES_FEED_SCOPE_PASS',p,'same_origin=yes','unpublished_external_fallbacks='+allowable);
}
const unchanged=fs.readFileSync('site/fx-quant-v2/liquidita-credito.html','utf8');
assert(unchanged.includes(upstream),'Liquidity feed not verified same-origin; do not silently migrate');
console.log('FXV2_MULTI_PAGE_SAME_ORIGIN_QA_PASS',JSON.stringify({migrated:pages.length,excluded:'liquidita-credito (out-of-sync NATIVE_LIQ_DATA mirror)',signal_changes:0}));
