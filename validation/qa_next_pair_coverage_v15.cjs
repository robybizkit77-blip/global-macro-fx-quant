'use strict';
/* NEXT V15: all-28 pair coverage audit, source-derived, no fake green indicators. */
const fs=require('node:fs'),assert=require('node:assert/strict'),vm=require('node:vm');
const json=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const model=json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const prices=json('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const rates=json('live_data/sections/NATIVE_RATES_DATA.json');
const audResearch=json('site/fx-quant-v2/aud-rba-f2-history-research.json');
const fx=require('../site/fx-quant-v2/next/decision-journey.js');
const rate=require('../site/fx-quant-v2/next/fx-rates-bridge.js');
const keys=Object.keys(model.pairs||{}).sort();
assert.equal(keys.length,28,'28 actual FX pairs must be supported');
const source=fs.readFileSync('site/fx-quant-v2/next/app.js','utf8');
const start=source.indexOf('function pairCoverage(k){');
const end=source.indexOf('\nfunction riskAligned(){',start);
assert(start>=0&&end>start,'Coverage module in the FX pair explorer is absent');
const normalToday=new Date(Date.parse(model.price_asof+'T12:00:00Z')+2*86400000).toISOString().slice(0,10);
const context={
 window:{FXQuantDecisionJourney:fx,FXQuantRatesBridge:rate},
 get:key=>({pairs:model,currencyPrices:prices,rates,audDailyResearch:audResearch})[key],
 dayNow:()=>normalToday,
 eurPairs:()=>model.pairs,
 state:{pair:'EURUSD'},
 pQuality:s=>s?.quality||'NON VALUTABILE',
 qBadge:quality=>'<span>'+quality+'</span>',
 getPairName:key=>key.slice(0,3)+'/'+key.slice(3),
 esc:value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))
};
vm.createContext(context);
new vm.Script(source.slice(start,end)).runInContext(context,{timeout:2000});
const coverage=keys.map(key=>({key,c:context.pairCoverage(key)}));
for(const {key,c}of coverage){
 const p=fx.profile(key,model,prices,normalToday);
 const r=rate.snapshot(rates,prices,key,model.price_asof,normalToday,audResearch);
 assert.equal(c.price,!!(p.fresh&&p.closes.length>=22),key+' fixing evidence');
 assert.equal(c.reference,!!p.watch.ready,key+' directional reference');
 assert.equal(c.rateShort,!!(r.ready&&r.short),key+' source-dated 2Y short');
 assert.equal(c.rateMedium,!!(r.ready&&r.medium),key+' source-dated 2Y medium');
 assert.equal(c.rateResearch,!!(r.ready&&r.researchOnly),key+' source-dated RBA research indicator');
 assert(!c.reference||c.price,'Cannot show levels with unusable price history');
 assert(!c.rateMedium||c.rateShort,'20-period rate evidence cannot bypass short-date gate');
 const html=context.pairRow(key);
 assert(html.includes('data-pair="'+key+'"'));
 assert((html.match(/class="pair-data-state/g)||[]).length===4,'Four source-tracked states per pair');
 assert(html.includes('2Y breve')&&html.includes('2Y medio'));
}
const totals={price:0,reference:0,rateShort:0,rateMedium:0};
for(const {c}of coverage)for(const key of Object.keys(totals))if(c[key])totals[key]++;
const summary=context.pairCoverageIntro();
for(const key of Object.keys(totals))assert(summary.includes(totals[key]+'/28'),key+' summary value must match actual data');
assert(summary.includes('non OIS'));
assert(summary.includes('trattino')&&summary.includes('direzione non definita'),'missing evidence is not an adverse trade signal');
assert.equal(totals.price,coverage.filter(x=>x.c.price).length);
assert.equal(totals.rateShort,coverage.filter(x=>x.c.rateShort).length);
assert.equal(totals.reference,coverage.filter(x=>x.c.reference).length);
const missingSrc={...context,get:key=>({pairs:model})[key]};
vm.createContext(missingSrc);new vm.Script(source.slice(start,end)).runInContext(missingSrc,{timeout:2000});
const notLoaded=missingSrc.pairCoverage('EURUSD');
assert(Object.values(notLoaded).every(v=>v===false),'No feed means no coverage claims');
assert(missingSrc.pairCoverageIntro().includes('0/28'));
const staleDay=new Date(Date.parse(model.price_asof+'T12:00:00Z')+45*86400000).toISOString().slice(0,10);
const stale={...context,dayNow:()=>staleDay};
vm.createContext(stale);new vm.Script(source.slice(start,end)).runInContext(stale,{timeout:2000});
assert(Object.values(stale.pairCoverage('EURUSD')).every(v=>!v),'Old data must not claim daily coverage');
const page=fs.readFileSync('site/fx-quant-v2/next/index.html','utf8');
assert(page.includes('app.js?v=17')&&page.includes('editorial-v4.css?v=17'));
assert(source.includes("'+pairCoverageIntro()+'"),'Coverage counter not visible in existing explorer');
console.log('NEXT_V15_COVERAGE_PASS',JSON.stringify(totals), 'of',keys.length,'G8 FX pairs');
