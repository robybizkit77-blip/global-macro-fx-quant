'use strict';
// Regression for the Pages data-boundary migration. No prices, calculations or signals are rewritten.
const fs=require('node:fs'),assert=require('node:assert/strict');
const pages=['banche','cot','calendario-news','macro','valute','coppie','cross-asset','tassi','ois','liquidita-credito'];
const upstream='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/';
for(const p of pages){
 const html=fs.readFileSync('site/fx-quant-v2/'+p+'.html','utf8');
 assert(html.includes('../../live_data/sections/')||html.includes("const RAW='../../';"),p+': no same-origin canonical feed');
 const stillRaw=html.match(/https:\/\/raw\.githubusercontent\.com\/robybizkit77-blip\/global-macro-fx-quant\/main\//g)||[];
 const allowable=0;
 assert.equal(stillRaw.length,allowable,p+': unexpected external endpoint');

 const scripts=[...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)].filter(m=>!/type=[\"']application\/(?:json|ld\+json)[\"']/.test(m[1])).map(m=>m[2]).filter(x=>x.trim());
 const vm=require('node:vm');
 for(const [i,script] of scripts.entries())new vm.Script(script,{filename:p+':inline-script-'+i});
 console.log('FXV2_PAGES_FEED_SCOPE_PASS',p,'same_origin=yes','unpublished_external_fallbacks='+allowable);
}
assert(pages.length===10);
assert(!pages.some(p=>fs.readFileSync('site/fx-quant-v2/'+p+'.html','utf8').includes(upstream)),'Raw GitHub data source still embedded in migrated pages');
console.log('FXV2_MULTI_PAGE_SAME_ORIGIN_QA_PASS',JSON.stringify({migrated:pages.length,excluded:null,signal_changes:0}));
