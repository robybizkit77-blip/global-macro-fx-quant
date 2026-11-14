'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),dir='site/fx-quant-v2/next/';
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const json=p=>JSON.parse(read(p));
const code=read(dir+'g8-pricing-evidence-v1.js');
new vm.Script(code,{filename:'g8-pricing-evidence-v1.js'});
globalThis.FXQuantPricingMoves=require('../../site/fx-quant-v2/next/rates-pricing-moves-v1.js');
globalThis.FXQuantPricingHistory=require('../../site/fx-quant-v2/next/rates-pricing-history-v1.js');
const {read:eval6,render,eligible,latestHistorical}=require('../../site/fx-quant-v2/next/g8-pricing-evidence-v1.js');
const snapshot=json('site/fx-quant-v2/ois-pricing-snapshot.json');
const inputs={today:snapshot.snapshot_built_from_repo_date||'2026-11-14',
 snapshot,operational:json('live_data/sections/OIS_OPERATIONAL_VIEW.json'),
 research:json('site/fx-quant-v2/ois-same-contract-repricing-research.json'),
 nzd:json('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),
 history:json(dir+'rates-pricing-history-v1.json')};
const CCY=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
for(const c of CCY){
 const data=eval6({...inputs,ccy:c});
 assert(data?.ccy===c,'No 6M evidence for '+c);
 assert(data.kind&&data.quality,'Source provenance missing '+c);
 assert(typeof data.rate==='number'&&Number.isFinite(data.rate),'Current or last dated 6M level missing '+c);
 assert(data.summary.includes('6M '+c),'Narrative must identify the currency '+c);
 assert(data.label.includes('6M '+c),'G8 board must show a monetary quote or change '+c);
 const html=render(data);
 assert(html.includes('data-g8-pricing-ccy="'+c+'"'));
 assert.equal((html.match(/class="g8-pricing-metric"/g)||[]).length,2);
 assert(html.includes('data-g8-pricing-window="1d"')&&html.includes('data-g8-pricing-window="1w"'));
 assert(html.includes('href="./rates-pricing-history-v1.json"'));
 assert(html.includes('href="../ois-pricing-snapshot.json"'));
 assert(html.includes('href="../ois-same-contract-repricing-research.json"'));
 assert(html.includes('href="#rates"'),'Evidence must link to complete OIS curves');
 assert(!html.includes('attese 6M da verificare'),'Do not discard existing G8 evidence');
 for(const e of [data.one,data.week].filter(Boolean)){
  assert(typeof e.bp==='number'&&Number.isFinite(e.bp));
  assert(e.to<=inputs.today,'No future source date');
  if(e.type!=='ULTIMA_FONTE'){
   assert(e.from<e.to,'No undated archival change');
   assert(['STORICO_CONFRONTABILE','PROXY_DELTA_RICOSTRUITO'].includes(e.type));
  }
 }
}
const eur=eval6({...inputs,ccy:'EUR'});
const usd=eval6({...inputs,ccy:'USD'});
assert(usd.one||usd.week,'USD archived same-contract historical 6M should show a move');
assert(eur.one||eur.week,'EUR archived listed futures 6M should show a move');
const nzd=eval6({...inputs,ccy:'NZD'});
assert(nzd.kind==='PROXY FUTURES'&&render(nzd).includes('proxy bank-bill'),
 'NZD bank-bill must be correctly labeled, not central bank OIS');
assert(!render(nzd).includes('OIS ufficiali'),'NZD proxy cannot be upgraded to OIS');
const a={date:'2026-11-11',rate:3.1,source_class:'SECONDARY_SAME_CONTRACT',contract:'A',derived:false};
const next={...a,date:'2026-11-12',rate:3.2};
assert.equal(eligible(a,next,'USD'),'CONTRATTO_IDENTICO');
assert.equal(eligible(a,{...next,contract:'B'},'USD'),null,'Changed futures contract cannot form daily delta');
assert.equal(eligible({...a,derived:true},next,'USD'),null,'Undocumented historical estimate is prohibited');
assert.equal(eligible({date:'2026-11-12',rate:3.65,source_class:'BANK_BILL_PROXY_DELTA_REFERENCE',contract:'Jun 2027',derived:true},
 {date:'2026-11-13',rate:3.79,source_class:'BANK_BILL_PROXY',contract:'Jun 2027',derived:false},'NZD'),
 'PROXY_RICOSTRUITO');
const weekly=latestHistorical('NZD',inputs.history,inputs.today,'1w');
if(weekly)assert(weekly.type==='PROXY_DELTA_RICOSTRUITO',
 'NZD weekly source is reconstructed from documented bank-bill proxy deltas');
const far=new Date(Date.parse(inputs.today+'T12:00:00Z')+32*864e5).toISOString().slice(0,10);
const old=eval6({...inputs,ccy:'EUR',today:far});
assert(old.one?.type!=='ULTIMA_FONTE','Stale source may not become latest daily pricing');
assert(old.rate===eur.rate,'Historical level should remain consultable, with date');
const poison=render({...usd,source:'<img src=x onerror=alert(1)>'});
assert(poison.includes('&lt;img')&&!poison.includes('<img'),'Untrusted source names must be escaped');
const index=read(dir+'index.html'),studio=read(dir+'currency-studio.js');
assert(index.indexOf('g8-pricing-evidence-v1.js?v=1')<index.indexOf('currency-studio.js?v=18'));
assert(index.includes('currency-studio.css?v=8'));
assert(studio.includes('FXQuantG8PricingEvidence?.read'));
assert(studio.includes('sixProof?.label||marketLabel'));
assert(studio.includes('sixProof?.summary||estimatedPolicy'));
assert(studio.includes('FXQuantG8PricingEvidence?.render'));
console.log('NEXT_G8_SOURCE_FIRST_6M_PASS: 8 currencies current/historical quotes, futures continuity, NZD proxy, public provenance and FX narrative');
