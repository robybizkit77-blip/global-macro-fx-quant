'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const load=p=>JSON.parse(read(p));
const base='site/fx-quant-v2/next/';
const ctx={window:{}};
for(const p of ['pair-rankings.js','currency-data-fallback.js','currency-strength-reading.js','currency-studio.js'])
 vm.runInNewContext(read(base+p),ctx,{filename:p,timeout:5000});
const F=ctx.window.FXQuantCurrencyFallback,Strength=ctx.window.FXQuantCurrencyStrength;
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const prices=load('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const macroSeries=load('live_data/sections/MACRO_SERIES.json');
const estimated=load('live_data/sections/CB_PRICING_ESTIMATED.json');
const macro=load('live_data/sections/MACRO_THERMOMETER_DATA.json');
const rates=load('live_data/sections/NATIVE_RATES_DATA.json');
const ois=load('site/fx-quant-v2/ois-pricing-snapshot.json');
const cot=load('live_data/sections/V250_COT_CHART_DATA.json');
const cb=load('live_data/sections/NATIVE_CB_DATA.json');
const pairs=load('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const now='2026-11-12';
const context=F.evaluate({macroSeries,estimated,now});
assert.equal(Object.keys(context.currencies).length,8);
for(const ccy of FX){
 const g=context.currencies[ccy].growth;
 assert.equal(g.status,'STORICO_DESCRITTIVO',ccy+' must surface an observed growth series');
 assert(g.label.includes('2026-'),'Growth display must show observation period: '+ccy);
 assert.equal(g.forecastValue,null,'No fabricated nowcast: '+ccy);
}
for(const ccy of ['USD','EUR','CHF']){
 const p=context.currencies[ccy].pricingProxy;
 assert.equal(p.status,'PROXY_INFORMATIVO',ccy+' secondary futures available');
 assert(p.label.includes('proxy'));
 assert(!p.label.startsWith('+')&&!p.label.startsWith('−'),'Rate levels do not show change sign');
 assert.match(p.description,/non fornisce un repricing settimanale verificato/);
}
assert.equal(context.currencies.NZD.pricingProxy.status,'NON_DISPONIBILE');
const fake={...estimated,currencies:{...estimated.currencies,
 USD:{...estimated.currencies.USD,governance:{...estimated.currencies.USD.governance,pair_engine_effect:'ACTIVE'}}}};
assert.equal(F.pricingProxy(fake,'USD',now).status,'NON_DISPONIBILE','Any impact on pair engine forbids informational quote');
assert.equal(F.pricingProxy(estimated,'USD','2026-12-10').status,'NON_DISPONIBILE','Stale quote rejected');
assert.equal(F.pricingProxy(estimated,'USD','2026-11-09').status,'NON_DISPONIBILE','Future quote rejected');
const future={USD:[{id:'US_PCEC96_history_value',category:'Crescita',frequency:'M',label:'Fake future GDP',
 dates:['2026-12','2027-01'],values:[99,999]}]};
assert.equal(F.growthAxis(future,'USD',now).status,'NON_DISPONIBILE','Future macro observations excluded');
const baseArgs={prices,macro:macro.currencies,rates,ois:ois.currencies,cot,now,
 rankingFn:ctx.window.FXQuantPairRankings.currencyRanking};
const original=Strength.analyze(baseArgs);
const enriched=Strength.analyze({...baseArgs,fallback:context});
assert.deepEqual(enriched.rows.map(x=>x.ccy),original.rows.map(x=>x.ccy),'Price order unchanged');
assert.deepEqual(enriched.rows.map(x=>x.evidenceCount),original.rows.map(x=>x.evidenceCount),
 'Proxy cannot certify official evidence');
assert.deepEqual(enriched.rows.map(x=>x.pricing.ok),original.rows.map(x=>x.pricing.ok),
 'Proxy cannot promote 6M OIS/futures weekly repricing');
const data={currencyPrices:prices,macroSeries,cbEstimated:estimated,macro,rates,ois,cotHistory:cot,cb,pairs};
const esc=x=>String(x??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const fmt=(x,n=2)=>finite(x)?x.toFixed(n):'—';
const sign=(x,n=2,suffix='')=>finite(x)?(x>0?'+':x<0?'−':'')+fmt(Math.abs(x),n)+suffix:'—';
const flags=Object.fromEntries(FX.map(k=>[k,k]));
const html=ctx.window.FXQuantCurrencies.render({
 get:k=>data[k],FX,FLAGS:flags,NAMES:flags,pageHero:()=>'<header>G8</header>',
 esc,fmt,sign,date:x=>x||'n.d.',finite,validDay:x=>/^\d{4}-\d\d-\d\d$/.test(x||''),dayNow:()=>now,
 state:{ccy:'USD',csOther:'EUR',csReturnWindow:20}
});
assert(html.includes('Consumi reali'), 'Observed growth reaches G8 UI');
assert(html.includes('proxy'), 'Indicative quote reaches G8 UI');
assert(html.includes('4,50%')||html.includes('4.50%'), 'Indicative USD 6M quote is dated and displayed');
assert(!/\bNaN\b|\bundefined\b|\[object Object\]/.test(html));
const idx=read(base+'index.html');
const app=read(base+'app.js');
assert(idx.includes('currency-data-fallback.js?v=1'));
assert(idx.indexOf('currency-data-fallback.js')<idx.indexOf('currency-studio.js'));
assert(idx.includes('currency-studio.js?v=6')&&idx.includes('app.js?v=18.38'));
assert(app.includes("cbEstimated:'../../../live_data/sections/CB_PRICING_ESTIMATED.json'"));
console.log('G8_DATA_FALLBACK_V1_PASS: observed growth, indicative 6M proxy, no official promotion, stale/future guard, unchanged rankings');
