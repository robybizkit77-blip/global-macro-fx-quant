'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const path=require('node:path'),root=path.resolve(__dirname,'../..');
const get=p=>fs.readFileSync(path.join(root,p),'utf8'),json=p=>JSON.parse(get(p));
const base='site/fx-quant-v2/next/';
new vm.Script(get(base+'rates-relative-pricing-v1.js'),{filename:'rates-relative-pricing-v1.js'});
globalThis.FXQuantPricingMoves=require('../../site/fx-quant-v2/next/rates-pricing-moves-v1.js');
globalThis.FXQuantPricingHistory=require('../../site/fx-quant-v2/next/rates-pricing-history-v1.js');
const {read,historicalIntervals,render}=require('../../site/fx-quant-v2/next/rates-relative-pricing-v1.js');
const snapshot=json('site/fx-quant-v2/ois-pricing-snapshot.json'),
 operational=json('live_data/sections/OIS_OPERATIONAL_VIEW.json'),
 research=json('site/fx-quant-v2/ois-same-contract-repricing-research.json'),
 nzd=json('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),
 history=json(base+'rates-pricing-history-v1.json');
const inputs={snapshot,operational,research,nzd,history,today:'2026-11-14',
 pairs:{pairs:{EURGBP:{},USDJPY:{},EURUSD:{},NZDJPY:{}}}};
const a=read({...inputs,ccy:'EUR',other:'GBP'});
assert(a&&a.a.kind==='FUTURES SECONDARI'&&a.b.kind==='OIS');
assert(a.live&&a.live.grade==='SAME_END_REFERENCE_UNVERIFIED',
 'Same end date but unknown official prior baseline is indicative, not fully verified');
assert.equal(a.live.asof,'2026-11-12');
assert(Math.abs(a.live.aBp-.75)<.01);
assert(Math.abs(a.live.bBp-2.3)<.01);
assert(Math.abs(a.live.relativeBp-(-1.55))<.01);
assert(a.observations.length>=3,'At least three actual common observations for EUR/GBP');
assert(a.observations.some(x=>x.to==='2026-11-12'&&x.from==='2026-11-11'),
 'Historical interval must use identical origin and destination dates for both currencies');
assert.equal(a.pair,'EURGBP');
const html=render({...inputs,ccy:'EUR',other:'GBP'});
assert(html.includes('data-rr6-status="SAME_END_REFERENCE_UNVERIFIED"'));
assert(html.includes('−1,55 pb'),'Expected source-derived 6M repricing divergence');
assert(html.includes('data-rates-openpair="EURGBP"'));
assert(html.includes('data-rr6-day='));
assert(html.includes('Fonti, limiti e date dei confronti'));
assert(html.includes('non è una tesi direzionale'));
const mis=read({...inputs,ccy:'USD',other:'EUR'});
assert(mis&&!mis.live&&mis.ar.asof!==mis.br.asof,
 'USD 13 Nov / EUR 12 Nov cannot be presented as a live synchronized delta');
const bad=render({...inputs,ccy:'USD',other:'EUR'});
assert(bad.includes('data-rr6-status="NOT_ALIGNED"'));
assert(bad.includes('Non confrontabile'));
assert(bad.includes('sedute differenti'));
assert(!bad.includes('Δ6M RELATIVO</span><strong class="rr6-neg">'),
 'Mismatched last-day source dates cannot expose a numerical recent divergence');
const withJPY=read({...inputs,ccy:'USD',other:'JPY'});
assert(withJPY.live&&withJPY.live.asof==='2026-11-13');
assert.equal(withJPY.live.relativeBp,-2);
const proxy=read({...inputs,ccy:'NZD',other:'JPY'});
assert(proxy.live&&proxy.live.relativeBp===9,
 'ASX bank-bill proxy must be covered while labeled as indicative');
assert.equal(proxy.observations.length,0,
 'Derived NZD 1D reference may not become a second independent historical observation');
const week=read({...inputs,ccy:'EUR',other:'GBP',window:'1w'});
assert(week.live&&week.live.relativeBp===-9,
 'Matched end-day 1W source deltas EUR +9 GBP +18');
assert(week.live.grade==='SAME_END_REFERENCE_UNVERIFIED');
const fabricated=structuredClone(history);
for(const point of fabricated.currencies.EUR.tenors['6m']){
 if(point.date==='2026-11-12')point.contract='SWITCHED_CONTRACT';
}
const contaminated=read({...inputs,history:fabricated,ccy:'EUR',other:'GBP'});
assert(!contaminated.observations.some(x=>x.to==='2026-11-12'&&x.from==='2026-11-11'),
 'Changing a secondary futures contract forbids plotting a same-contract movement');
const nohistory=render({...inputs,history:null,ccy:'EUR',other:'GBP'});
assert(nohistory.includes('nessuna barra artificiale')||
 nohistory.includes('Non ci sono ancora intervalli'));
const originalReader=globalThis.FXQuantPricingMoves.readCurrency;
try{
 globalThis.FXQuantPricingMoves.readCurrency=(c,...rest)=>{
  const row=originalReader(c,...rest);
  if(c==='GBP')row.rows[1].one={...row.rows[1].one,from:'2026-11-10'};
  if(c==='EUR')row.rows[1].one={...row.rows[1].one,from:'2026-11-11'};
  return row;
 };
 const inconsistent=read({...inputs,ccy:'EUR',other:'GBP'});
 assert(!inconsistent.live,
  'Two sources with known but different origin dates must not show comparable repricing');
}finally{globalThis.FXQuantPricingMoves.readCurrency=originalReader;}
const future=render({...inputs,today:'2026-12-15',ccy:'EUR',other:'GBP'});
assert(future.includes('data-rr6-status="NOT_ALIGNED"'),
 'Stale observations must not be promoted to current pricing');
const invalid=read({...inputs,ccy:'EUR',other:'EUR'});
assert.equal(invalid,null,'Same-currency relative spread is meaningless');
const page=get(base+'index.html'),studio=get(base+'rates-studio.js');
assert(page.indexOf('rates-pricing-history-v1.js?v=1')<
 page.indexOf('rates-relative-pricing-v1.js?v=1')&&
 page.indexOf('rates-relative-pricing-v1.js?v=1')<
 page.indexOf('rates-studio.js?v=6'),
 'Relative bridge must load after both pricing source modules and before rates studio');
assert(page.includes('rates-studio.css?v=5'));
assert(page.includes('app.js?v=18.56-relative-pricing'));
assert(studio.includes('FXQuantRelativePricing?.render'));
assert(get(base+'rates-studio.css').includes('.rates-relative-pricing'));
console.log('NEXT_RELATIVE_6M_REPRICING_PASS: matched end dates, mismatched sources, roll, 1W, NZD proxy and Fx dossier');
