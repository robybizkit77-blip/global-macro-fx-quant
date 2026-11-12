'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const load=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const {read,macroAxis,money,flow}=require(path.join(root,'site/fx-quant-v2/next/currency-relative-reading.js'));
const macro=load('live_data/sections/MACRO_THERMOMETER_DATA.json').currencies;
const gov=load('live_data/sections/NATIVE_RATES_DATA.json');
const ois=load('site/fx-quant-v2/ois-pricing-snapshot.json');
const cot=load('live_data/sections/V250_COT_CHART_DATA.json');
const fx=load('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const ccys=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const now='2026-11-10',rows=fx.rows.filter(r=>r.Date<=now);
const quote=(a,b,n=20)=>{
 const aligned=rows.filter(r=>Number.isFinite(r[a])&&r[a]>0&&Number.isFinite(r[b])&&r[b]>0);
 if(aligned.length<=n)return null;
 const last=aligned.at(-1),prev=aligned.at(-n-1);
 return {move:(last[b]/last[a]/(prev[b]/prev[a])-1)*100,asof:last.Date};
};
let total=0,matched2Y=0,blocked2Y=0;
for(const a of ccys)for(const b of ccys){
 if(a===b)continue;
 const px=quote(a,b),args={base:a,quote:b,macro,gov,ois,cot,now,price20:px?.move,priceAsOf:px?.asof};
 const x=read(args);
 assert.equal(x.available,true,a+'/'+b);
 assert(x.macroStory.includes(a)&&x.macroStory.includes(b),'Bilateral macro '+a+b);
 assert(x.govStory.includes(a)&&x.govStory.includes(b),'Bilateral rates '+a+b);
 assert(x.moneyStory.includes('6M'),'Money-market scope '+a+b);
 assert(x.cotStory.includes('COT'),'Positioning scope '+a+b);
 assert(x.verdict.length>35&&x.timing.includes('Trade Attractiveness'),'Distinguish hypothesis/trade '+a+b);
 assert(x.watch.length>35);
 assert(!/undefined|NaN|Infinity/.test(Object.values(x).filter(v=>typeof v==='string').join(' ')),a+b);
 assert(!x.moneyStory.includes('differenziale OIS'),'No fictitious OIS spread');
 const aligned=gov[a]?.date===gov[b]?.date&&gov[a]?.date<=now;
 if(aligned){assert(x.spreadComparable,a+b);matched2Y++;}
 else {assert.equal(x.spreadComparable,false,a+b);assert.match(x.govStory,/Non calcolo uno spread 2Y corrente/);blocked2Y++;}
 total++;
}
assert.equal(total,56);
assert(matched2Y>0&&blocked2Y>0,'Both genuine and rejected bilateral spread cases');
assert.match(read({base:'AUD',quote:'CAD',macro,gov,ois,cot,now,price20:2,priceAsOf:'2026-11-09'}).verdict,/AUD contro CAD/);
assert.match(read({base:'AUD',quote:'CAD',macro,gov,ois,cot,now,price20:-2,priceAsOf:'2026-11-09'}).verdict,/CAD contro AUD/);
assert.equal(money('USD',ois,'2026-11-01'),null,'Cannot import future money-market data');
assert.equal(flow('USD',cot,'2026-10-31'),null,'Cannot import future CFTC data');
assert.equal(macroAxis('EUR','inflation',macro,'2026-09-01'),null,'Macro observation cannot come from future');
const unpaired=structuredClone(gov);
unpaired.EUR.date=gov.GBP?.date==='2026-11-09'?'2026-11-08':'2026-11-09';
const mismatch=read({base:'EUR',quote:'GBP',macro,gov:unpaired,ois,cot,now,price20:0,priceAsOf:'2026-11-09'});
assert.equal(mismatch.spreadComparable,false);
assert.match(mismatch.govStory,/date diverse/);
const missing=read({base:'USD',quote:'NZD',macro:{},gov:{},ois:{},cot:{},now,price20:null,priceAsOf:null});
assert.equal(missing.available,true);
assert.match(missing.verdict,/non offrono una direzione relativa/);
const page=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
const studio=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/currency-studio.js'),'utf8');
assert(page.includes('currency-relative-reading.js?v=21'));
assert(page.includes('currency-studio.js?v=5'));
assert(page.indexOf('currency-relative-reading.js')<page.indexOf('currency-studio.js'));
assert(studio.includes('root.FXQuantCurrencyRelative?.read?.'));
for(const k of ['macroText','ratesText','cotText','judgement'])assert(studio.includes('esc('+k+')'),'Escaping in live Country Desk');
console.log('NEXT_CURRENCY_BILATERAL_V21_PASS: '+total+' ordered G8 comparisons; '+matched2Y+
 ' same-date 2Y spreads, '+blocked2Y+' rejected mismatches, macro/6M/COT/date/XSS guards.');
