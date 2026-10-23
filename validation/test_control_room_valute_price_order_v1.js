#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const start=source.indexOf('function valuteRelativeFixingRanks(fx,lookback){');
const end=source.indexOf('function mountValuteRelativeRanking(doc,strip,fx){',start);
assert(start!==-1&&end>start,'active ECB relative ranking must be extractable');
const FX=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
const data=JSON.parse(fs.readFileSync('live_data/sections/ECB_G8_PRICE_HISTORY.json','utf8'));
const context={FX,num:x=>typeof x==='number'&&Number.isFinite(x)?x:null,
  valuteFxSourceStatus:()=>({status:'OFFICIAL_FIXING_RECENT'})};
vm.createContext(context);
vm.runInContext(source.slice(start,end),context);
const rank=context.valuteRelativeFixingRanks;
assert.equal(typeof rank,'function');
const firstRead=context.valuteHorizonFirstRead;
assert.equal(typeof firstRead,'function','compared horizons use only verified ECB ranks');
assert.equal(data.currencies.length,8);
for(const h of [5,20]){
 const r=rank(data,h);
 assert(r,'valid recent official ECB fixing feed should be rankable');
 assert.equal(r.items.length,8);
 assert.equal(r.lookback,h);
 assert.equal(r.asof,data.last_as_of);
 assert.equal(r.from,data.rows.at(-h-1).Date);
 assert.equal(r.basis,'EQUAL_WEIGHT_G8');
 assert.equal(r.source,'ECB_G8_PRICE_HISTORY');
 assert.equal(new Set(r.items.map(x=>x.ccy)).size,8);
 assert.deepEqual(Array.from(r.items,x=>x.ccy).sort(),FX.slice().sort());
 for(let i=0;i<r.items.length;i++){
   const x=r.items[i];
   assert(Number.isFinite(x.percent));
   if(i)assert(r.items[i-1].percent>=x.percent,'rank not descending');
 }
 const recent=data.rows.at(-1),old=data.rows.at(-h-1);
 const returns=FX.map(c=>-Math.log(recent[c]/old[c]));
 const mean=returns.reduce((a,b)=>a+b,0)/8;
 for(const x of r.items){
   const expected=(Math.exp(-Math.log(recent[x.ccy]/old[x.ccy])-mean)-1)*100;
   assert(Math.abs(x.percent-expected)<1e-11,'currency return must be sourced from official fixing');
 }
 // The reference EUR fixing is always 1. Relative EUR movement should be the inverse G8 basket drift.
 assert.equal(recent.EUR,1);
 assert.equal(old.EUR,1);
}
for(const days of [5,20]){
 const x=firstRead(data,days),primary=rank(data,days),
       other=rank(data,days===5?20:5),ccy=primary.items[0].ccy;
 const idx=other.items.findIndex(r=>r.ccy===ccy);
 assert(x,'horizon first reading must be source derived');
 assert.equal(x.ccy,ccy);
 assert.equal(x.days,days);
 assert.equal(x.asof,data.last_as_of);
 assert.equal(x.source,'ECB_G8_PRICE_HISTORY');
 assert.equal(x.otherDays,days===5?20:5);
 assert.equal(x.otherRank,idx+1);
 assert(Math.abs(x.percent-primary.items[0].percent)<1e-11);
 assert(Math.abs(x.otherPercent-other.items[idx].percent)<1e-11);
}
assert.equal(firstRead(data,5).ccy,'AUD','AUD leads only the current recent 5-session window');
assert.equal(firstRead(data,5).otherRank,7,'AUD is seventh on the longer overlapping 20-session window');
assert.equal(firstRead(data,20).ccy,'GBP','GBP leads 20-day price momentum');
assert.equal(firstRead(data,20).otherRank,5,'GBP ranks fifth on 5-day relative price momentum');
assert.equal(firstRead(data,1),null,'cannot compare unsupported windows');
const missingOld=structuredClone(data);
missingOld.rows.at(-21).AUD=null;
assert(rank(missingOld,5),'short source horizon remains valid with a missing 20-session observation');
assert.equal(firstRead(missingOld,5),null,'no invented cross-horizon comparison for missing long history');
assert.equal(rank(data,1),null,'unsupported periods must not fabricate rankings');
assert.equal(rank(data,60),null);
function altered(fn){const x=structuredClone(data);fn(x);return rank(x,5);}
assert.equal(altered(x=>{x.row_count--}),null,'mismatched observation count');
assert.equal(altered(x=>{x.rows.at(-1).USD=null}),null,'missing recent observation');
assert.equal(altered(x=>{x.rows.at(-6).JPY=-10}),null,'negative source FX fixing');
assert.equal(altered(x=>{x.rows.at(-6).Date=x.last_as_of}),null,'no shared historical window');
context.valuteFxSourceStatus=()=>({status:'WITHHELD'});
assert.equal(rank(data,5),null,'stale or uncertified fixing cannot be ranked');
assert(source.includes("data-vsm-days=\"5\"")&&source.includes("data-vsm-days=\"20\""),
  'both sourced horizons must be available in currency UI');
assert(source.includes("mountValuteRelativeRanking(doc,strip,fx);"),
  'ranking should mount adjacent to validated currency provenance');
assert(source.includes("rank.dataset.comparisonStatus='WITHHELD'"),
 'invalid longer horizon must not be labeled as a verified comparison');
assert(source.includes('Le due finestre si sovrappongono: non prova una svolta.'),
 'never extrapolate an FX macro turning point from overlapping observed horizons');
assert(source.includes("rank.dataset.tradeSignals='NONE'"),
  'never promote price ranking as executable trade signal');
console.log('CONTROL_ROOM_V10_VALUTE_ECB_5_20_SESSION_RANKING_PASS');
