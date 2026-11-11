'use strict';
// Regression: V9 window (20/60/120) and V12 references must not collapse
// the expanded pair chart or return the reader to the pair rankings.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const app=fs.readFileSync(path.join(__dirname,'../../site/fx-quant-v2/next/app.js'),'utf8');
const start=app.indexOf('function refreshPairPriceChart(focusSelector){');
const end=app.indexOf('\n}\n',start);
assert(start!==-1&&end>start,'targeted pair chart refresh helper must exist');
const helper=app.slice(start,end+2);
const priceHandler=app.match(/const pv9=e\.target\.closest\('\[data-v9-price-window\]'\);[^\n]+/);
const referenceHandler=app.match(/const pv12=e\.target\.closest\('\[data-v12-reference-toggle\]'\);[^\n]+/);
assert(priceHandler&&referenceHandler,'both price chart controls must be delegated');
assert.match(priceHandler[0],/refreshPairPriceChart/);
assert.match(referenceHandler[0],/refreshPairPriceChart/);
assert.doesNotMatch(priceHandler[0],/render\(\)/);
assert.doesNotMatch(referenceHandler[0],/render\(\)/);

const accordion={open:true};
const body={innerHTML:'',querySelector(selector){this.focusSelector=selector;return {focus:({preventScroll})=>{this.preventScroll=preventScroll}}}};
let fullRenders=0,scroll;
const state={route:'pairs',pairDetailOpen:true,pairPriceWindow:60,pairShowReferences:true,charts:{stale:1},chartIndex:9};
const context={
 state,
 document:{querySelector:()=>body},
 window:{scrollY:746,scrollTo:o=>{scroll=o},FXQuantDecisionJourney:{build:({state:s})=>({pair:()=>'<div>window='+s.pairPriceWindow+' refs='+s.pairShowReferences+'</div>'})}},
 get:()=>null,plot:()=>null,fmt:()=>null,sign:()=>null,date:()=>null,dayNow:()=>null,esc:()=>null,
 render:()=>{fullRenders++}
};
vm.runInNewContext(helper+'\nrefreshPairPriceChart(\'[data-v9-price-window="60"]\');',context);
assert.equal(accordion.open,true);
assert.equal(fullRenders,0,'full page must not be re-rendered');
assert.equal(body.innerHTML,'<div>window=60 refs=true</div>');
assert.equal(body.focusSelector,'[data-v9-price-window="60"]');
assert.equal(body.preventScroll,true);
assert.equal(scroll.top,746);
assert.equal(state.chartIndex,0);
assert.equal(Object.keys(state.charts).length,0);

state.pairPriceWindow=120;
state.pairShowReferences=false;
vm.runInNewContext(helper+'\nrefreshPairPriceChart(\'[data-v12-reference-toggle]\');',context);
assert.equal(accordion.open,true);
assert.equal(fullRenders,0);
assert.equal(body.innerHTML,'<div>window=120 refs=false</div>');
assert.equal(body.focusSelector,'[data-v12-reference-toggle]');

context.document.querySelector=()=>null;
vm.runInNewContext(helper+'\nrefreshPairPriceChart(\'[data-v12-reference-toggle]\');',context);
assert.equal(fullRenders,1,'fallback only when chart is absent');
console.log('PASS pair chart 20/60/120 and reference controls keep open panel and scroll');
