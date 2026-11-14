'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..'),rel='site/fx-quant-v2/next/';
const load=p=>fs.readFileSync(path.join(root,p),'utf8');
const json=p=>JSON.parse(load(p));
new vm.Script(load(rel+'pair-monetary-bridge-v1.js'),{filename:'pair-monetary-bridge-v1.js'});
globalThis.FXQuantPricingMoves=require('../../site/fx-quant-v2/next/rates-pricing-moves-v1.js');
globalThis.FXQuantPricingHistory=require('../../site/fx-quant-v2/next/rates-pricing-history-v1.js');
globalThis.FXQuantRelativePricing=require('../../site/fx-quant-v2/next/rates-relative-pricing-v1.js');
const {evaluate,render}=require('../../site/fx-quant-v2/next/pair-monetary-bridge-v1.js');
const ois=json('site/fx-quant-v2/ois-pricing-snapshot.json');
const inputs={
 today:ois.snapshot_built_from_repo_date||'2026-11-14',
 ois,
 operational:json('live_data/sections/OIS_OPERATIONAL_VIEW.json'),
 research:json('site/fx-quant-v2/ois-same-contract-repricing-research.json'),
 nzd:json('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),
 history:json(rel+'rates-pricing-history-v1.json'),
 pairs:json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 prices:json('live_data/sections/ECB_G8_PRICE_HISTORY.json')
};
const keys=Object.keys(inputs.pairs.pairs||{});
assert.equal(keys.length,28,'Pair dossier must cover 28 real G8 crosses');
for(const pair of keys){
 const favored=pair.slice(0,3),m=evaluate({...inputs,pair,favored});
 const html=render({...inputs,pair,favored});
 assert(m.ready&&m.pair===pair,'Missing actual pair '+pair);
 assert(html.includes('data-pair-monetary-pair="'+pair+'"'),'Wrong pair orientation '+pair);
 assert(html.includes('data-pair-open-rates="'+pair+'"'),'Missing direct Rates link '+pair);
 assert(html.includes('data-pair-monetary-window="1d"')&&
        html.includes('data-pair-monetary-window="1w"'),'Both pricing horizons needed '+pair);
 assert(html.includes('Fonte')||html.includes('strumenti')||html.includes('Strumenti'),
  'Missing source classification '+pair);
 assert(html.includes('La verifica sul Forex.')&&
        html.includes('non una conferma causale')===false,
   'Price caution must survive '+pair);
 if(m.lead){
  const x=m.lead.data;
  assert.equal(x.relativeBp,Math.round((x.aBp-x.bBp)*100)/100,
   'Current relative 6M must equal leg-by-leg sourced repricing '+pair);
  if(x.grade!=='MATCHED_EXACT_INTERVAL')
   assert.equal(m.directional,null,'A same-end-only comparison may not confirm macro '+pair);
 }else{
  assert(html.includes('non sono confrontabili')||html.includes('non sono confrontabili'),
   'Unmatched current dates need a clear missing-data status '+pair);
 }
}
const eur=evaluate({...inputs,pair:'EURGBP',favored:'EUR'});
assert(eur.ready);
if(eur.lead){
 const x=eur.lead.data;
 assert.equal(x.relativeBp,Math.round((x.aBp-x.bBp)*100)/100);
 if(x.grade==='SAME_END_REFERENCE_UNVERIFIED'){
  assert.equal(eur.directional,null,'Indicative source cannot give directional confirmation');
  assert(render({...inputs,pair:'EURGBP',favored:'EUR'}).includes('lettura indicativa'));
 }
}
const reversed=structuredClone(inputs.pairs);
reversed.pairs.GBPEUR=reversed.pairs.EURGBP;
const forward=evaluate({...inputs,pair:'EURGBP',favored:'EUR'});
const reverse=evaluate({...inputs,pairs:reversed,pair:'GBPEUR',favored:'EUR'});
if(forward.lead&&reverse.lead)
 assert(Math.abs(forward.lead.data.relativeBp+reverse.lead.data.relativeBp)<.011,
  'Pair quote direction must invert the sign of the relative 6M change');
const usd=evaluate({...inputs,pair:'EURUSD',favored:'EUR'});
if(usd.one.ar.asof!==usd.one.br.asof)
 assert.equal(usd.one.live,null,'Unsynchronised dates cannot become a current spread');
const absent=render({...inputs,pair:'ABCDEF'});
assert(absent.includes('data-pair-monetary-status="UNAVAILABLE"'));
assert(!absent.includes('data-pair-open-rates'),'No invented target without model pair');
const staleDay=new Date(Date.parse(inputs.today+'T12:00:00Z')+32*864e5).toISOString().slice(0,10);
const stale=evaluate({...inputs,today:staleDay,pair:'EURGBP',favored:'EUR'});
assert(!stale.one.live&&!stale.week.live,
 'Outdated 6M sources cannot be passed off as up-to-date on future sessions');
const injected=render({...inputs,pair:'EURGBP',favored:'<img src=x onerror=alert(1)>'});
assert(!injected.includes('<img'),'Untrusted favored view must never inject markup');
const html=load(rel+'index.html'),app=load(rel+'app.js');
assert(html.indexOf('rates-relative-pricing-v1.js?v=1')<
       html.indexOf('pair-monetary-bridge-v1.js?v=1')&&
       html.indexOf('pair-monetary-bridge-v1.js?v=1')<
       html.indexOf('app.js?v=18.57-pair-monetary-bridge'));
assert(html.includes('pairs-clarity.css?v=4'));
assert(app.includes('FXQuantPairMonetary.render'));
assert(app.includes("e.target.closest('[data-pair-open-rates]')"));
assert(app.includes('state.ccy=k.slice(0,3);state.against=k.slice(3);'));
const css=load(rel+'pairs-clarity.css');
assert(css.includes('.pair-monetary-bridge')&&css.includes('max-width:560px')&&css.includes(':focus-visible'));
console.log('NEXT_PAIR_MONETARY_BRIDGE_PASS: 28 pairs, 1D/1W, stale dates, quote inversion, indicative OIS/futures, FX checks');
