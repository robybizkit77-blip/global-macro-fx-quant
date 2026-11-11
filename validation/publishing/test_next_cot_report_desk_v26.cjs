'use strict';
/* Read-only COT V26 website regression: no weekly report, COT producers,
 * automations or non-COT sections are modified.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const {validatePrior,statistics,reading,desk}=require(
 path.join(root,'site/fx-quant-v2/next/cot-report-reading-v26.js'));
const {priceEvidence}=require(
 path.join(root,'site/fx-quant-v2/next/cot-evidence-reading.js'));
const source=read('live_data/sections/V250_COT_CHART_DATA.json');
const archived=read('site/fx-quant-v2/design-studio-cot-v1-data.json');
const fx=read('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const names=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const historicalP={CHF:100,CAD:84,USD:84,JPY:79,GBP:24,NZD:3,EUR:0,AUD:0};
const expectedZ={CHF:2.19,CAD:1.04,USD:1.21,JPY:0.91,GBP:-0.79,NZD:-1.49,EUR:-2.42,AUD:-1.78};
const reports=[];
for(const ccy of names){
 const a=source[ccy];
 const hist=a.dates.map((date,i)=>({date,net:a.net[i],long:a.long[i],
  short:a.short[i],netoi:a.netoi[i],percentile:a.percentile[i]}));
 const price=priceEvidence(ccy,hist,fx,new Date().toISOString().slice(0,10));
 const item={ccy,hist,last:hist.at(-1),price1:price.price1,
  priceState:price.priceState,priceRow:price.priceRow};
 const prior=validatePrior(hist,archived,ccy);
 assert(prior&&prior.prior.length===104,ccy+' 104 strict previous weeks');
 assert(prior.priorFirst<hist[0].date,ccy+' archival predecessor');
 assert.equal(prior.priorLast,hist.at(-2).date);
 assert(prior.verifiedOverlaps>=8,ccy+' archival intersection');
 if(hist.at(-1).date==='2026-11-03'){
  assert.equal(prior.priorFirst,'2024-11-05');
  assert.equal(prior.verifiedOverlaps,103);
 }
 const v=statistics(item,archived);
 assert(v&&v.rounded!==null,ccy+' report-grade percentile');
 const independently=100*prior.prior.filter(n=>n<=v.net).length/104;
 assert(Math.abs(v.p-independently)<1e-10,'P104 independent calculation '+ccy);
 if(hist.at(-1).date==='2026-11-03'){
  assert.equal(v.rounded,historicalP[ccy],ccy+' vs approved Nov 06 report');
  assert(Math.abs(v.z-expectedZ[ccy])<.005,ccy+' Z-score vs approved report');
 }
 assert.equal(v.delta1,a.net.at(-1)-a.net.at(-2),ccy+' delta 1W');
 assert.equal(v.delta4,a.net.at(-1)-a.net.at(-5),ccy+' delta 4W');
 assert.equal(v.delta8,a.net.at(-1)-a.net.at(-9),ccy+' delta 8W');
 assert.equal(v.dLong-v.dShort,v.delta1,ccy+' exact CFTC long/short decomposition');
 assert(Number.isFinite(v.velocity),ccy+' OI-implied velocity');
 assert.equal(v.crowd,Math.abs(Number(a.netoi.at(-1).toFixed(1)))>=30);
 assert(v.level=== (v.rounded>=80?'EXTREME LONG':v.rounded<=20?'EXTREME SHORT':'NEUTRALE'));
 const story=reading(v);
 assert(story&&story.fact.includes('Motore principale:')&&story.fact.includes('Variazione normalizzata:')&&story.judgment.length>80&&story.verify.includes('prezzo'),ccy+' complete Serafini desk interpretation');
 item.deskStats=v;reports.push(item);
}
assert.equal(reports.length,8);
const g=desk(reports);
assert(g&&g.asof===source.USD.dates.at(-1));
if(g.asof==='2026-11-03'){
 // Rankings use normalized 1W/OI, not raw contract changes or a historic label.
 const normalized=[...reports].map(x=>x.deskStats).sort((a,b)=>b.velocity-a.velocity);
 assert.equal(g.up?.ccy,normalized.find(x=>x.velocity>0)?.ccy);
 assert.equal(g.down?.ccy,[...normalized].reverse().find(x=>x.velocity<0)?.ccy);
 assert.equal(g.crowd[0].ccy,'NZD');
 assert.deepEqual(g.crowd.map(x=>x.ccy),['NZD','AUD']);
 assert(g.divergent.some(x=>x.ccy==='EUR'));
 assert(!g.divergent.some(x=>x.ccy==='USD'),'Tiny USD gross-net imbalance must not be forced into price divergence');
}
const chf=reports.find(x=>x.ccy==='CHF').deskStats;
if(g.asof==='2026-11-03'){
 assert(chf.rounded===100&&chf.net<0,'EXTREME LONG is historical rank, not necessarily net long');
 assert(!chf.crowd);
}
const cad=reports.find(x=>x.ccy==='CAD').deskStats;
if(g.asof==='2026-11-03')assert(cad.dLong>0&&cad.dShort<0,'CAD mixed new long/short covering');
const eur=reports.find(x=>x.ccy==='EUR').deskStats;
if(g.asof==='2026-11-03'){
 assert(eur.dLong<0&&eur.dShort>0,'EUR new shorts and long liquidation');
 assert(eur.priceState==='divergente','EUR current COT vs same-Tuesday price diverge');
}
// Fail closed when the old archive no longer matches live CFTC source.
// The original inclusive percentile must NEVER silently substitute for P104.
const forged=structuredClone(archived);
forged.currencies.EUR.history.net[10]+=1;
assert.equal(validatePrior(reports.find(x=>x.ccy==='EUR').hist,forged,'EUR'),null);
assert.equal(statistics(reports.find(x=>x.ccy==='EUR'),forged).rounded,null);
const absent=structuredClone(archived);
delete absent.currencies.NZD.history;
assert.equal(statistics(reports.find(x=>x.ccy==='NZD'),absent).rounded,null);
const future=structuredClone(source.USD);
const fake=future.dates.map((date,i)=>({date,net:future.net[i],long:future.long[i],short:future.short[i],netoi:future.netoi[i]}));
fake[fake.length-1].date='2099-12-01';
assert.equal(validatePrior(fake,archived,'USD'),null,'Future/no-overlap fails closed');
// Keep the previous source-based protection from V22. No stale cached FX comparator.
const page=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
const studio=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/cot-studio.js'),'utf8');
const app=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/app.js'),'utf8');
assert(page.indexOf('cot-evidence-reading.js?v=22')<page.indexOf('cot-report-reading-v26.js?v=27'));
assert(page.indexOf('cot-report-reading-v26.js?v=27')<page.indexOf('cot-studio.js?v=29'));
assert(page.includes('cot-studio.css?v=29'));
assert(app.includes("cotPriorReference:'../design-studio-cot-v1-data.json'"));
assert(!app.includes("cotPrice:'../design-studio-cot-v1-data.json'"));
assert(studio.includes("get('currencyPrices')"));
assert(!studio.includes("get('cotPrice')"));
assert(studio.includes("get('cotPriorReference')"));
for(const term of ['deskOverview(all)','interpretation(a)','last12(a)','universe()','classify(a)','cot-proofline','cot-desk-breakdown','P104','Z-score 104W','Velocity 1W/OI']){
 assert(studio.includes(term),'Missing COT V26 feature '+term);
}
const bridge=app.slice(app.indexOf('const SOURCES'),app.indexOf('const state='));
assert((bridge.match(/cotPriorReference/g)||[]).length===1);
console.log('NEXT_COT_V26_PASS: 8/8 exclusive-current P104 and Z104 match Nov 06 canonical report; G8 CAD/EUR/NZD, gross/1W/4W/8W, ECB same-Tuesday, crowding, source mismatch/future guards. REPORT UNCHANGED.');
