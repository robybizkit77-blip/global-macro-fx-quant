'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const load=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const {priceEvidence,flowReading}=require(path.join(root,'site/fx-quant-v2/next/cot-evidence-reading.js'));
const cot=load('live_data/sections/V250_COT_CHART_DATA.json');
const fx=load('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const names=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const today='2026-11-10';
for(const name of names){
 const s=cot[name],h=s.dates.map((date,i)=>({date,net:s.net[i],long:s.long[i],short:s.short[i]}));
 const p=priceEvidence(name,h,fx,today),f=flowReading({hist:h});
 assert(p.aligned,name+' ECB price not aligned to latest CFTC Tuesday');
 assert.equal(p.priceRow.as_of,'2026-11-03',name+' source vintage');
 assert(p.prices.length>40,name+' historical ECB samples missing');
 assert(p.prices.at(-1).label==='2026-11-03',name+' latest date');
 assert(p.prices.at(-2).label==='2026-10-27',name+' previous date');
 assert(Number.isFinite(p.price1),name+' 1W aligned price delta missing');
 assert(['coerente','divergente','non conclusivo'].includes(p.priceState));
 assert(f.headline.length>15&&f.detail.length>100&&f.monitor.length>35,name+' incomplete desk narrative');
 assert.equal(f.delta1,s.net.at(-1)-s.net.at(-2),name+' net decomposition');
 assert.equal(f.delta4,s.net.at(-1)-s.net.at(-5),name+' 4W persistence');
 assert(!/undefined|NaN|Infinity/.test(f.detail+p.priceState),name+' fabricated output');
}
const h=cot.USD.dates.map((date,i)=>({date,net:cot.USD.net[i],long:cot.USD.long[i],short:cot.USD.short[i]}));
const usd=priceEvidence('USD',h,fx,today);
const x03=fx.rows.find(x=>x.Date==='2026-11-03'),x27=fx.rows.find(x=>x.Date==='2026-10-27');
const expectedUSD=((1/x03.USD)/(1/x27.USD)-1)*100;
assert(Math.abs(usd.price1-expectedUSD)<1e-10,'USD/EUR inverse FX convention');
const eur=priceEvidence('EUR',cot.EUR.dates.map((date,i)=>({date,net:cot.EUR.net[i]})),fx,today);
assert(Math.abs(eur.price1-((x03.USD/x27.USD)-1)*100)<1e-10,'EUR/USD FX convention');
const missing=structuredClone(fx);
missing.rows=missing.rows.filter(x=>x.Date!=='2026-11-03');
const absent=priceEvidence('USD',h,missing,today);
assert.equal(absent.aligned,false,'Do not forward-fill missing Tuesday');
assert.equal(absent.priceState,'non conclusivo');
assert(absent.prices.at(-1).label==='2026-10-27','Missing Tuesday must not be interpolated');
const future=priceEvidence('USD',h,fx,'2026-10-27');
assert.equal(future.aligned,false,'No future COT/release alignment');
const q=priceEvidence('GBP',h,{source:'random spot',rows:fx.rows},today);
assert.equal(q.aligned,false,'Reject unverified FX origin');
const synthetic=(n1,l1,s1,prior=5)=>({
 hist:[
 {net:0,long:50,short:50},{net:prior,long:55,short:50},
 {net:2*prior,long:60,short:50},{net:3*prior,long:65,short:50},
 {net:3*prior+n1,long:65+l1,short:50+s1}
 ]
});
assert.match(flowReading(synthetic(8,8,0)).detail,/crescita dei long/);
assert.match(flowReading(synthetic(8,0,-8)).detail,/copertura degli short/);
assert.match(flowReading(synthetic(-8,-8,0)).detail,/riduzione dei long/);
assert.match(flowReading(synthetic(-8,0,8)).detail,/aumento degli short/);
assert.match(flowReading(synthetic(8,12,4)).detail,/Aumentano sia long sia short/);
assert.match(flowReading(synthetic(8,-2,-10)).detail,/Si riducono entrambe/);
assert.match(flowReading(synthetic(5,5,0,5)).detail,/tutte le ultime quattro settimane/);
const page=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
const app=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/app.js'),'utf8');
const studio=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/cot-studio.js'),'utf8');
assert(page.indexOf('cot-evidence-reading.js?v=22')<page.indexOf('cot-studio.js?v=2'));
assert(/app\\.js\\?v=18\\.\\d+/.test(page),'COT requires versioned Next application asset');
assert(app.includes("route==='overview'||route==='pairs'||route==='cot'"));
assert(studio.includes("get('currencyPrices')"));
assert(!studio.includes("get('cotPrice')"),'Stale price pack should no longer control COT comparison');
console.log('NEXT_COT_V22_PASS: 8/8 current COT/ECB Tuesday prices 2026-11-03, CFTC gross/4W persistence, missing/future and quote-direction guards.');
