'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const load=p=>JSON.parse(read(p));
const dir='site/fx-quant-v2/next/';
const ctx={window:{}};
for(const file of ['pair-rankings.js','currency-relative-reading.js','currency-strength-reading.js','macro-strength-estimated-v1.js','currency-studio.js']){
  vm.runInNewContext(read(dir+file),ctx,{filename:file,timeout:5000});
}
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const FLAGS=Object.fromEntries(FX.map(x=>[x,x]));
const NAMES=Object.fromEntries(FX.map(x=>[x,x]));
const data={
currencyPrices:load('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
rates:load('live_data/sections/NATIVE_RATES_DATA.json'),
macro:load('live_data/sections/MACRO_THERMOMETER_DATA.json'),
cb:load('live_data/sections/NATIVE_CB_DATA.json'),
ois:load('site/fx-quant-v2/ois-pricing-snapshot.json'),
cotHistory:load('live_data/sections/V250_COT_CHART_DATA.json'),
pairs:load('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
macroObserved:load('site/control-room-preview/macro-v3-current-evidence.json')
};
const now=data.macroObserved.generated_europe_rome_day;
assert.match(now,/^\d{4}-\d{2}-\d{2}$/);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const fmt=(x,n=2)=>finite(x)?x.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const sign=(x,n=1,suffix='')=>finite(x)?(x>0?'+':x<0?'−':'')+fmt(Math.abs(x),n)+suffix:'—';
const date=d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)?d.slice(8,10)+'/'+d.slice(5,7)+'/'+d.slice(0,4):'n.d.';
const estimate=ctx.window.FXQuantMacroEstimated.evaluate({
 observed:data.macroObserved,prices:data.currencyPrices,ois:data.ois,rates:data.rates,
 model:data.pairs,now,rankingFn:ctx.window.FXQuantPairRankings.currencyRanking});
assert.equal(estimate.status,'STIMA_OPERATIVA_NON_VALIDATA',estimate.reason);
const common={get:k=>k==='estimatedMacro'?estimate:data[k],FX,FLAGS,NAMES,pageHero:()=>'<header>G8</header>',
esc,fmt,sign,date,finite,validDay:d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d),dayNow:()=>now};
const canonical=ctx.window.FXQuantPairRankings.currencyRanking(data.currencyPrices,now,FX);
assert(canonical&&canonical.items.length===8);
for(const ccy of FX){
  const html=ctx.window.FXQuantCurrencies.render({...common,state:{ccy,csOther:ccy==='EUR'?'USD':'EUR',csReturnWindow:20}});
  assert.equal((html.match(/class="orient-rank-row /g)||[]).length,8,'Eight ranked G8 rows: '+ccy);
  assert.equal((html.match(/class="orient-first-read"/g)||[]).length,1,'First read: '+ccy);
  const rows=[...html.matchAll(/class="orient-rank-row[^"]*" data-cs-country="([A-Z]{3})"/g)].map(x=>x[1]);
  assert.deepEqual(rows,canonical.items.map(x=>x.ccy),'Same ranking as Pair Explorer: '+ccy);
   const estimateRows=[...html.matchAll(/class="strength-name"><b>#[1-8]<\/b><strong>[^<]* ([A-Z]{3})<\/strong>/g)].map(m=>m[1]);
   assert.deepEqual(estimateRows,Array.from(estimate.currencies,x=>x.ccy),'Estimated operational G8 order');
  assert(html.includes('class="orient-rank-row selected '),'Selected currency highlighted: '+ccy);
  assert(html.includes('class="orient-thesis-details"'),'Macro/rates/COT details still available: '+ccy);
  assert(html.includes('class="strength-method-fold"')&&
    (html.match(/class="orient-evidence-item"/g)||[]).length===4,
    'Four supporting facts accessible: '+ccy);
  assert(html.indexOf('id="orient-strength-board"')<html.indexOf('id="orient-strength-focus"'),
    'Macro/rates/pricing/price board precedes country analysis: '+ccy);
  assert.equal((html.match(/class="strength-row /g)||[]).length,8,'Eight evidence rows: '+ccy);
  assert.equal((html.match(/class="strength-card"/g)||[]).length,4,'Four source-qualified dimensions: '+ccy);
  assert(html.includes('class="strength-pair-fold"')&&html.includes('class="strength-method-fold"'),
    'Legacy bilateral deep-dive and details remain accessible');
  for(const label of ['COSA VEDIAMO','COSA DICONO I TASSI','COSA CONTROLLARE']){
    assert(html.includes(label),'Missing concise action question '+label);
  }
  assert(!/\bundefined\b|\bNaN\b|\[object Object\]/.test(html), 'No broken narrative '+ccy);
}
const fallback=ctx.window.FXQuantCurrencies.render({...common,get:k=>k==='currencyPrices'?{}:k==='estimatedMacro'?{status:'STIMA_SOSPESA',reason:'no fixing'}:data[k],
 state:{ccy:'USD',csOther:'EUR',csReturnWindow:20}});
assert(fallback.includes('orient-ranking-unavailable'),'Do not rank absent common fixing prices');
assert(fallback.includes('class="country-orient-list"'),'Keep currency selection even without rank data');
assert(!fallback.includes('class="orient-rank-row '),'Do not fabricate ranking rows');
const page=read(dir+'index.html');
assert(page.includes('currency-studio.js?v=16')&&page.includes('currency-studio.css?v=7'));
assert(page.includes('currency-strength-reading.js?v=1'));
assert(page.indexOf('currency-strength-reading.js')<page.indexOf('currency-studio.js'));
assert(page.indexOf('pair-rankings.js')<page.indexOf('app.js'),
 'Shared currency rank must be available before route render');
console.log('NEXT_CURRENCY_FIRST_READ_PASS: 8 G8 currencies, current estimated G8 ordering and archived price rank and missing-data fallback');
