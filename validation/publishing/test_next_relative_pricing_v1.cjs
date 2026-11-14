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
const inputs={snapshot,operational,research,nzd,history,today:snapshot.snapshot_built_from_repo_date||'2026-11-14',
 pairs:{pairs:{EURGBP:{},USDJPY:{},EURUSD:{},NZDJPY:{}}}};
const a=read({...inputs,ccy:'EUR',other:'GBP'});
assert(a&&a.a.kind==='FUTURES SECONDARI'&&a.b.kind==='OIS');
assert(a.observations.length>=3,'Actual EUR/GBP common-date 6M history must be present');
assert(a.observations.every(x=>x.from<x.to),'Intervals must be chronological');
assert.equal(a.pair,'EURGBP');
const html=render({...inputs,ccy:'EUR',other:'GBP'});
assert(html.includes('data-rr6-status='));
assert(html.includes('data-rates-openpair="EURGBP"'));
assert(html.includes('data-rr6-day='));
assert(html.includes('Fonti, limiti e date dei confronti'));
assert(html.includes('non è una tesi direzionale'));
if(a.live){
 assert(a.ar.asof===a.br.asof,'Recent relative delta must have identical end date');
 assert.equal(a.live.relativeBp,Math.round((a.live.aBp-a.live.bBp)*100)/100);
 assert(html.includes('data-rr6-status="'+a.live.grade+'"'));
 assert(html.includes('pb'),'Valid recent relative repricing must be displayed in basis points');
}else{
 assert(html.includes('data-rr6-status="NOT_ALIGNED"'));
 assert(html.includes('Non confrontabile'));
}
const usdEur=read({...inputs,ccy:'USD',other:'EUR'});
if(usdEur.ar.asof!==usdEur.br.asof){
 assert(!usdEur.live,'Mismatched USD/EUR latest source dates cannot produce a live relative move');
 const mismatch=render({...inputs,ccy:'USD',other:'EUR'});
 assert(mismatch.includes('data-rr6-status="NOT_ALIGNED"'));
 assert(mismatch.includes('Non confrontabile'));
}
const withJPY=read({...inputs,ccy:'USD',other:'JPY'});
if(withJPY.live)assert.equal(withJPY.live.relativeBp,
 Math.round((withJPY.live.aBp-withJPY.live.bBp)*100)/100);
const proxy=read({...inputs,ccy:'NZD',other:'JPY'});
if(proxy.live)assert.equal(proxy.live.relativeBp,
 Math.round((proxy.live.aBp-proxy.live.bBp)*100)/100);
assert.equal(proxy.observations.length,0,
 'NZD reconstructed prior levels cannot be treated as two independent observations');
const week=read({...inputs,ccy:'EUR',other:'GBP',window:'1w'});
if(week.live)assert.equal(week.live.relativeBp,
 Math.round((week.live.aBp-week.live.bBp)*100)/100);
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
const expiry=new Date(Date.parse(inputs.today+'T12:00:00Z')+32*864e5).toISOString().slice(0,10);
const future=render({...inputs,today:expiry,ccy:'EUR',other:'GBP'});
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
assert(page.includes('app.js?v=18.58-home-money-pricing'));
assert(studio.includes('FXQuantRelativePricing?.render'));
assert(get(base+'rates-studio.css').includes('.rates-relative-pricing'));
console.log('NEXT_RELATIVE_6M_REPRICING_PASS: matched end dates, mismatched sources, roll, 1W, NZD proxy and Fx dossier');
