'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..'),rel='site/fx-quant-v2/next/';
const load=p=>fs.readFileSync(path.join(root,p),'utf8');
const json=p=>JSON.parse(load(p));
new vm.Script(load(rel+'pair-monetary-bridge-v1.js'),{filename:'pair-monetary-bridge-v1.js'});
globalThis.FXQuantPricingMoves=require('../../site/fx-quant-v2/next/rates-pricing-moves-v1.js');
globalThis.FXQuantPricingHistory=require('../../site/fx-quant-v2/next/rates-pricing-history-v1.js');
globalThis.FXQuantRelativePricing=require('../../site/fx-quant-v2/next/rates-relative-pricing-v1.js');
const {evaluate,historicalWindow,validLeg,render}=
 require('../../site/fx-quant-v2/next/pair-monetary-bridge-v1.js');
const ois=json('site/fx-quant-v2/ois-pricing-snapshot.json');
const inputs={
 today:ois.snapshot_built_from_repo_date||'2026-11-14',ois,
 operational:json('live_data/sections/OIS_OPERATIONAL_VIEW.json'),
 research:json('site/fx-quant-v2/ois-same-contract-repricing-research.json'),
 nzd:json('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),
 history:json(rel+'rates-pricing-history-v1.json'),
 pairs:json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 prices:json('live_data/sections/ECB_G8_PRICE_HISTORY.json')
};
const keys=Object.keys(inputs.pairs.pairs||{});
assert.equal(keys.length,28,'All 28 true G8 crosses must be covered');
const normal=[];
for(const pair of keys){
 const favored=pair.slice(0,3),m=evaluate({...inputs,pair,favored});
 const html=render({...inputs,pair,favored});
 assert(m.ready&&m.pair===pair,'Missing model pair '+pair);
 assert(html.includes('data-pair-monetary-pair="'+pair+'"'));
 assert(html.includes('data-pair-open-rates="'+pair+'"'));
 assert(html.includes('data-pair-monetary-window="1d"')&&
        html.includes('data-pair-monetary-window="1w"'));
 assert(html.includes('La verifica sul Forex.')&&html.includes('Rispetto alla tesi macro.'));
 assert(!html.includes('non allineato')&&!html.includes('NON CONFRONTABILE'),
  'Front read must not lead with two unavailable boxes '+pair);
 assert(html.includes('href="./rates-pricing-history-v1.json"')&&
  html.includes('href="../ois-pricing-snapshot.json"')&&
  html.includes('href="../ois-same-contract-repricing-research.json"')&&
  html.includes('href="../../../live_data/sections/OIS_OPERATIONAL_VIEW.json"'),
  'Sources must be directly consultable '+pair);
 for(const [period,e] of [['1d',m.oneEvidence],['1w',m.weekEvidence]]){
  assert(html.includes('data-pair-monetary-window="'+period+'"'));
  if(e){
   assert.equal(e.relativeBp,Math.round((e.aBp-e.bBp)*100)/100,
    'Relative change must equal the two instrument changes '+pair+'/'+period);
   assert(e.to<=inputs.today,'Future research dates cannot masquerade as history');
   if(e.type!=='FONTE_ULTIMA_RILEVAZIONE'){
    assert(e.from<e.to,'Historical interval must have two dates '+pair);
    assert(['HISTORICAL_COMMON','HISTORICAL_PROXY_REFERENCE'].includes(e.grade));
    assert(html.includes('data-pair-monetary-evidence="'+e.grade+'"'));
    if(m.lead?.grade!=='MATCHED_EXACT_INTERVAL')
     assert.equal(m.directional,null,
      'Historical or proxy-only leading evidence may never certify a contemporary FX thesis '+pair);
   }
  }else{
   assert(html.includes('data-pair-monetary-evidence="LEVEL_CONTEXT"'),
    'Lacking a common variation must show actual dated published levels instead '+pair);
   assert(typeof m.levels.base.rate==='number'&&typeof m.levels.quote.rate==='number',
    'Standalone fallback must have two actual sourced levels '+pair);
  }
 }
 if(!m.one.live&&!m.week.live){
  assert(m.directional===null,'Unsynchronised current dates never prove macro alignment');
 }
 normal.push({pair,day:m.oneEvidence?.grade||'LEVEL_CONTEXT',week:m.weekEvidence?.grade||'LEVEL_CONTEXT'});
}
const eur=evaluate({...inputs,pair:'EURUSD',favored:'USD'});
assert(eur.ready,'EURUSD must be available');
const eu1=historicalWindow(inputs.history,'EUR','USD',inputs.today,'1d');
assert(eu1&&eu1.from==='2026-11-11'&&eu1.to==='2026-11-12',
 'EURUSD must use the last common dated Nov 11 to Nov 12 source bars');
assert.equal(eu1.relativeBp,-2.75,'EURUSD historical difference must reconcile to -2.75 pb');
if(!eur.one.live)assert.deepEqual(eur.oneEvidence,eu1,
 'EURUSD should promote useful historical evidence, not two blank 1D/1W boxes');
const euroText=render({...inputs,pair:'EURUSD',favored:'USD'});
assert(euroText.includes('−2,75 pb'),'EURUSD must display its real historical relative 6M variation');
assert(euroText.includes('11/11/2026 → 12/11/2026'));
assert(euroText.includes('non un repricing della seduta corrente'),
 'Retrospective archive must never become a contemporaneous price claim');
assert(!euroText.includes('non allineato'),'EURUSD first read should not repeat empty flags');
const neg=evaluate({...inputs,pair:'EURGBP',favored:'EUR'});
assert(neg.ready);
const mirrored=structuredClone(inputs.pairs);
mirrored.pairs.GBPEUR=mirrored.pairs.EURGBP;
const reverse=evaluate({...inputs,pairs:mirrored,pair:'GBPEUR',favored:'EUR'});
if(neg.oneEvidence&&reverse.oneEvidence)
 assert(Math.abs(neg.oneEvidence.relativeBp+reverse.oneEvidence.relativeBp)<.011,
  'Reversing base and quote must reverse the monetary sign');
const same={date:'2026-11-12',rate:4.5,source_class:'SECONDARY_SAME_CONTRACT',contract:'AAA',derived:false};
const before={...same,date:'2026-11-11',rate:4.3};
assert.equal(validLeg(before,same,'USD'),'SAME_LISTED_CONTRACT');
assert.equal(validLeg(before,{...same,contract:'BBB'},'USD'),null,'Rollover cannot form a false 1D change');
assert.equal(validLeg({...before,derived:true},same,'USD'),null,
 'Non-NZD inferred historical bars are disallowed');
assert.equal(validLeg({date:'2026-11-12',rate:3.7,contract:'Jun 2027',derived:true,
 source_class:'BANK_BILL_PROXY_DELTA_REFERENCE'},
 {date:'2026-11-13',rate:3.79,contract:'Jun 2027',derived:false,
 source_class:'BANK_BILL_PROXY'},'NZD'),'PROXY_DELTA_RECONSTRUCTED');
const noData=render({...inputs,pair:'ABCDEF'});
assert(noData.includes('data-pair-monetary-status="SOURCE_MISSING"'));
assert(!noData.includes('data-pair-open-rates'));
const staleDay=new Date(Date.parse(inputs.today+'T12:00:00Z')+32*864e5).toISOString().slice(0,10);
const future=evaluate({...inputs,today:staleDay,pair:'EURGBP',favored:'EUR'});
assert(!future.one.live&&!future.week.live,'Stale quoted moves cannot be called current pricing');
assert(!future.lead||future.lead.type!=='FONTE_ULTIMA_RILEVAZIONE',
 'Expired feed must fall back to explicitly historical references');
const injection=render({...inputs,pair:'EURGBP',favored:'<img src=x onerror=alert(1)>'});
assert(!injection.includes('<img'));
const html=load(rel+'index.html'),app=load(rel+'app.js');
assert(html.indexOf('rates-relative-pricing-v1.js?v=1')<
 html.indexOf('pair-monetary-bridge-v1.js?v=2')&&
 html.indexOf('pair-monetary-bridge-v1.js?v=2')<
 html.indexOf('app.js?v=18.57-pair-monetary-bridge'));
assert(html.includes('pairs-clarity.css?v=5'));
assert(app.includes('FXQuantPairMonetary.render'));
assert(app.includes("e.target.closest('[data-pair-open-rates]')"));
assert(app.includes('state.ccy=k.slice(0,3);state.against=k.slice(3);'));
const css=load(rel+'pairs-clarity.css');
assert(css.includes('.pair-monetary-links')&&css.includes(':focus-visible'));
console.log('NEXT_PAIR_MONETARY_SOURCE_COVERAGE_PASS: 28/28 pairs, dated EURUSD -2.75pb, weekly, proxy, rollover, quality, linked sources',JSON.stringify({normal}));
