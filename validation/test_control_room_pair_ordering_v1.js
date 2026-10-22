#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const start=source.indexOf('function pairDeskOrdering(feedData,model){');
const end=source.indexOf('async function mountPairRankedList(doc){',start);
assert(start!==-1&&end>start,'exact active pair-ranking function must be extractable');
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const setup=JSON.parse(fs.readFileSync('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json','utf8'));
const model=JSON.parse(fs.readFileSync('live_data/sections/D.json','utf8'));
const context={FX,
 fresh:(d,days)=>days===5?d==='2026-10-22':days===10?false:false,
 canonicalPairMacroBaseline:(s,m)=>m?.asOf===s.macro_baseline_asof?s.macro_baseline_asof:null};
vm.createContext(context);
vm.runInContext(source.slice(start,end),context);
const rank=context.pairDeskOrdering;
assert.equal(typeof rank,'function');
const result=rank(setup,model);
assert(result,'canonical source ordering must be available');
assert.equal(result.count,28);
assert.equal(result.priceAsOf,setup.price_asof);
assert.equal(result.macroAsOf,setup.macro_baseline_asof);
assert.equal(result.baselineHistorical,true);
for(const mode of ['setup','thesis']){
 const rows=result[mode];
 assert.equal(rows.length,28);
 assert.equal(new Set(rows.map(x=>x.code)).size,28);
 assert.deepEqual(rows.map(x=>x.code).slice().sort(),Object.keys(setup.pairs).sort());
 assert(rows.every(x=>x.quality===setup.pairs[x.code].setup.quality));
 assert(rows.every(x=>x.why.length>3));
 assert(rows.some(x=>x.quality==='CON RISCHI'&&x.why.includes('Timing')));
 let seenNotEligible=false;
 for(const x of rows){
   assert(!x.thesis.includes('Signal')&&!x.why.includes('Ingresso automatico'));
   if(x.quality==='NON VALUTABILE')seenNotEligible=true;
   else assert(!seenNotEligible,'a no-thesis pair cannot outrank a sourced historical thesis');
 }
 const key=mode==='setup'?'setupKey':'thesisKey';
 for(let i=1;i<rows.length;i++){
   const a=rows[i-1][key],b=rows[i][key];let cmp=0;
   for(let k=0;k<a.length;k++)if(a[k]!==b[k]){cmp=a[k]>b[k]?-1:1;break;}
   if(!cmp)cmp=rows[i-1].code.localeCompare(rows[i].code);
   assert(cmp<=0,'list out of deterministic lexicographic order');
 }
}
assert.equal(result.setup[0].code,'NZDUSD','setup order should reflect current source price/timing/extension');
assert.equal(result.thesis[0].code,'USDCHF','structural order should privilege joint macro/policy agreement');
assert(result.setup.find(x=>x.code==='AUDCHF').why.includes('Timing contrario'));
assert(result.setup.find(x=>x.code==='EURUSD').why.includes('Prezzo già avanzato'));
assert(result.setup.find(x=>x.code==='USDCHF').why.includes('Timing solo parziale'));
function mutate(fn){const input=structuredClone(setup);fn(input);return rank(input,model);}
assert.equal(mutate(x=>{x.quality_distribution['CON RISCHI']+=1}),null);
assert.equal(mutate(x=>{x.pairs.AUDCHF.setup.price.state='UNVERIFIED'}),null);
assert.equal(mutate(x=>{x.pairs.AUDCHF.setup.structural.quality='NOISE'}),null);
assert.equal(mutate(x=>{x.pairs.AUDCHF.setup.structuralFav='NZD'}),null);
assert.equal(mutate(x=>{x.pairs.AUDCHF.setup.timing.state='PREDICTED'}),null);
assert.equal(mutate(x=>{x.entry_level_published=true}),null);
assert.equal(mutate(x=>{x.price_audit.status='FAIL'}),null);
assert.equal(rank(setup,{asOf:'2026-09-24'}),null);
assert(source.includes('MutationObserver(()=>apply())'),'native search/re-render reordering contract');
assert(source.includes("tbody.append(...sorted)"),'native 28-row table, not a new duplicative list');
assert(source.includes("hasTradeRanking='false'"),'must never claim score or trade signal');
console.log('CONTROL_ROOM_V10_PAIR_ORDERING_28_SOURCE_GUARDS_PASS');
