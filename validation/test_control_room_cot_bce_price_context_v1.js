'use strict';
// Independent ECB date-gated COT price-context regression. No trading signals.
const fs=require('node:fs'),assert=require('node:assert/strict');
const src=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const start=src.indexOf('function cotBcePriceContext(cftcDay, fx){');
const end=src.indexOf('async function mountCotFirstReading(doc){',start);
assert(start>=0&&end>start,'Context function not found');
const FX=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
const num=v=>typeof v==='number'&&Number.isFinite(v)?v:null;
const context=new Function('FX','num',src.slice(start,end)+';return cotBcePriceContext;')(FX,num);
const fx=JSON.parse(fs.readFileSync('live_data/sections/ECB_G8_PRICE_HISTORY.json','utf8'));
const cot=JSON.parse(fs.readFileSync('live_data/sections/V250_COT_CHART_DATA.json','utf8'));
const stories=JSON.parse(fs.readFileSync('live_data/sections/V247_COT_STORIES.json','utf8'));
const dates=new Set(FX.map(c=>cot[c].dates.at(-1)));
assert.equal(dates.size,1);
const tue=[...dates][0];
assert(FX.every(c=>stories[c].price==='WITHHELD'));
const days=(a,b)=>(Date.parse(b+'T00:00:00Z')-Date.parse(a+'T00:00:00Z'))/86400000;
const actualGap=days(tue,fx.last_as_of);
const actual=context(tue,fx);
if(actualGap>7){
 assert.equal(actual,null,'A COT report older than 7 days must not yield a price-context inference');
}else{
 assert(actual,'Recent COT-to-ECB context should remain available');
}
// Keep a point-in-time, date-consistent positive fixture; the production feed
// may legitimately advance beyond the CFTC guard window before weekly release.
const rowsInWindow=fx.rows.filter(x=>days(tue,x.Date)>0&&days(tue,x.Date)<=7);
assert(rowsInWindow.length>0,'No point-in-time ECB fixing within safe COT window');
const positive=structuredClone(fx);
const fixtureLast=rowsInWindow.at(-1).Date;
positive.rows=positive.rows.filter(x=>x.Date<=fixtureLast);
positive.row_count=positive.rows.length;
positive.last_as_of=fixtureLast;
const r=context(tue,positive);
assert(r,'A historically synchronized COT-to-ECB fixture should be available');
assert.equal(r.cftc_day,tue);
assert.equal(r.fx_end_day,fx.last_as_of);
assert.equal(r.lines.length,8);
assert.equal(r.is_position_price_confirmation,false);
assert.equal(r.causal_claim,false);
const eur=r.lines.find(x=>x.ccy==='EUR'),usd=r.lines.find(x=>x.ccy==='USD');
assert.equal(eur.side,'EUR/USD');assert.equal(usd.side,'USD/EUR');
assert(Math.abs(((1+eur.pct/100)*(1+usd.pct/100))-1)<1e-10,'inverse EUR/USD change');
const o=structuredClone(positive);
const bad=(x,why)=>assert.equal(context(tue,x),null,why);
o.last_as_of=tue;bad(o,'same-day move must not be inferred');
const wrong=structuredClone(positive);wrong.pair_count=27;bad(wrong,'partial G8 universe');
const forged=structuredClone(positive);forged.rows.at(-1).EUR=1.01;bad(forged,'EUR must equal one');
const missing=structuredClone(positive);missing.rows=missing.rows.filter(x=>x.Date!==tue);missing.row_count=missing.rows.length;
bad(missing,'missing exact Tuesday ECB fixing');
const stale=structuredClone(positive);const staleDate=new Date(Date.parse(tue+'T00:00:00Z')+8*86400000).toISOString().slice(0,10);stale.last_as_of=staleDate;stale.rows.at(-1).Date=staleDate;
bad(stale,'>7 days beyond positioning observation');
const future=structuredClone(positive);future.rows.at(-1).Date='2026-11-11';
bad(future,'inconsistent last fixing');
assert(src.includes("feed('ECB_G8_PRICE_HISTORY.json')"));
assert(src.includes("rail.dataset.bcePriceContext=priceContext?'DATED_ONLY':'UNAVAILABLE'"));
assert(src.includes("box.dataset.priceConfirmation='NONE'"));
assert(src.includes('NON dimostra conferma, causalità'));
assert(src.includes("contextHost.appendChild(box);"));
assert(src.includes("rail.appendChild(contextHost);"));
assert(src.includes("del cambio dopo martedì NON dimostra"));
console.log('COT_ECB_PRICE_CONTEXT_DATED_NONCAUSAL_PASS',
 JSON.stringify({cftc:tue,actual_ecb:fx.last_as_of,actual_gap_days:actualGap,fixture_ecb:fixtureLast,currencies:8,negative:6,signals:0}));
