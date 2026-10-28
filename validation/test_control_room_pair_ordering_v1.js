#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const start=source.indexOf('function pairDeskOrdering(feedData,model){');
const end=source.indexOf('async function mountPairRankedList(doc){',start);
assert(start!==-1&&end>start,'exact active pair-ranking function must be extractable');
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const setup=JSON.parse(fs.readFileSync('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json','utf8'));
const model=JSON.parse(fs.readFileSync('live_data/sections/D.json','utf8'));
const context={FX,
 // Unit test the source contract independent of wall-clock expiry.
 // The browser QA still enforces real five-day freshness.
 fresh:(d,days)=>days===5?d===setup.price_asof:days===10?false:false,
 canonicalPairMacroBaseline:(s,m)=>m?.asOf===s.macro_baseline_asof?s.macro_baseline_asof:null};
vm.createContext(context);
vm.runInContext(source.slice(start,end),context);
const rank=context.pairDeskOrdering;
assert.equal(typeof rank,'function');
const overlap=context.pairDeskFocusOverlap;
assert.equal(typeof overlap,'function','top-eight overlap uses same canonical source order');
const result=rank(setup,model);
assert(result,'canonical source ordering must be available');
assert.equal(result.count,28);
assert.equal(result.priceAsOf,setup.price_asof);
assert.equal(result.macroAsOf,setup.macro_baseline_asof);
assert.equal(result.baselineHistorical,true);
for(const mode of ['setup','thesis']){
 const o=overlap(result,mode);
 assert(o,'valid top-eight overlap is available');
 assert.equal(o.total,8);
 assert.equal(Object.values(o.frequencies).reduce((a,b)=>a+b,0),16,'eight pair rows carry 16 currency legs');
 assert.equal(new Set(o.repeated).size,o.repeated.length);
 const first=result[mode].slice(0,8);
 for(const c of FX){
   const occ=first.filter(x=>x.code.slice(0,3)===c||x.code.slice(3)===c).length;
   assert.equal(o.frequencies[c],occ,'currency overlap must be recomputed from exact canonical pair legs');
   assert.equal(o.favored[c],first.filter(x=>x.fav===c).length,
     'favorite recurrence must be from canonical source, not an inferred trading direction');
 }
 assert.equal(o.withRisks,first.filter(x=>x.quality==='CON RISCHI').length);
 assert.equal(o.max,Math.max(...Object.values(o.frequencies)));
}
// Exact source-derived top-eight counts are asserted above for every currency.
// Never pin a dated snapshot's risk count or currency recurrence in a live-feed test.
assert.equal(overlap(result,'unapproved'),null);
assert.equal(overlap({setup:[{code:'EURUSD'}]},'setup'),null);
const invalidFocus=structuredClone(result);
invalidFocus.setup[0].fav='CAD';
assert.equal(overlap(invalidFocus,'setup'),null,'a source-contradicting favored currency fails closed');

for(const mode of ['setup','thesis']){
 const rows=result[mode];
 assert.equal(rows.length,28);
 assert.equal(new Set(rows.map(x=>x.code)).size,28);
 assert.equal(JSON.stringify(Array.from(rows,x=>x.code).sort()),JSON.stringify(Object.keys(setup.pairs).sort()));
 assert(rows.every(x=>x.quality===setup.pairs[x.code].setup.quality));
 assert(rows.every(x=>x.why.length>3));
 assert(rows.every(x=>x.firstCheck?.length>16));
 assert(rows.every(x=>!x.firstCheck.includes('previsione')&&!x.firstCheck.includes('compra')));
 const expectedFirstCheck={
  'Macro e Tassi/CB in conflitto':'Rivedere se Macro e Tassi/CB convergono sulla stessa valuta',
  'Solo spread 2Y; tesi assente':'Cercare una tesi Macro/Tassi; lo spread 2Y non basta',
  'Nessuna preferenza Macro/Tassi':'Attendere un contrasto strutturale verificabile',
  'Prezzo contro la tesi':'Verificare se il prezzo smette di opporsi alla tesi',
  'Prezzo non conferma':'Cercare conferma del prezzo nella direzione favorita',
  'Timing contrario':'Controllare se la dinamica relativa smette di essere contraria',
  'Prezzo già avanzato':'Controllare consolidamento o retest, senza inseguire',
  'Dinamica relativa divergente':'Verificare se la divergenza relativa rientra',
  'Timing incerto':'Attendere dinamica relativa più leggibile',
  'Timing misto':'Controllare se il timing diventa coerente',
  'Timing solo parziale':'Verificare un miglioramento del timing relativo',
  'COT affollato/estremo':'Controllare se il crowding COT si riduce',
  'COT contrario':'Controllare se il posizionamento COT smette di opporsi',
  'Liquidità sfavorevole':'Verificare se il contesto di liquidità migliora',
  'Tesi sorretta da un solo pilastro':'Cercare conferma dal pilastro Macro o Tassi/CB mancante',
  'Servono trigger e rapporto rischio/rendimento esterni al modello':'Definire trigger e rischio/rendimento separatamente'
 };
 for(const x of rows){
   const first=x.why.split(' · ')[0];
   assert.equal(x.firstCheck,expectedFirstCheck[first],'first actionable research check must correspond to first sourced concern: '+x.code);
 }

 assert(rows.some(x=>x.quality==='CON RISCHI'&&x.why.includes('Timing')));
 let seenNotEligible=false;
 for(const x of rows){
   assert(!x.thesis.includes('Signal')&&!x.why.includes('Ingresso automatico'));
   if(x.quality==='NON VALUTABILE')seenNotEligible=true;
   else assert(!seenNotEligible,'a no-thesis pair cannot outrank a sourced historical thesis');
 }
 const key=mode==='setup'?'setupKey':'thesisKey';
 for(let i=1;i<rows.length;i++){
   const a=rows[i-1][key],b=rows[i][key];let cmp=0;
   for(let k=0;k<a.length;k++)if(a[k]!==b[k]){cmp=a[k]>b[k]?-1:1;break;}
   if(!cmp)cmp=rows[i-1].code.localeCompare(rows[i].code);
   assert(cmp<=0,'list out of deterministic lexicographic order');
 }
}
// The live canonical source evolves daily; do not freeze a particular pair as
// the winner. The independent lexicographic checks above must hold for BOTH
// modes, with deterministic ties. Verify risk reasons from CURRENT source.
for(const mode of ['setup','thesis']){
 const rows=result[mode],first=rows[0],key=mode==='setup'?'setupKey':'thesisKey';
 assert(rows.every(row=>{
   for(let i=0;i<first[key].length;i++){
     if(row[key][i]!==first[key][i])return first[key][i]>=row[key][i];
   }
   return first.code.localeCompare(row.code)<=0;
 }),mode+' top choice must have highest canonical source-derived key');
}
function expectedSourcedReasons(code){
 const p=setup.pairs[code],x=p.setup;
 if(x.quality==='NON VALUTABILE'){
   return [p.decision_frame.quality==='PILASTRI DIVISI'?'Macro e Tassi/CB in conflitto':
     p.decision_frame.quality==='SEPARAZIONE RATES MATERIALE'?'Solo spread 2Y; tesi assente':
     'Nessuna preferenza Macro/Tassi'];
 }
 const reasons=[];
 if(x.price.state==='BAD')reasons.push('Prezzo contro la tesi');
 else if(x.price.state==='NEUTRAL')reasons.push('Prezzo non conferma');
 if(x.timing.state==='ADVERSE')reasons.push('Timing contrario');
 if(['ADVANCED','EXTENDED'].includes(x.extension.state))reasons.push('Prezzo già avanzato');
 if(p.transition.state==='DIVERGENZA RELATIVA DA MONITORARE')reasons.push('Dinamica relativa divergente');
 if(x.timing.state==='UNCERTAIN')reasons.push('Timing incerto');
 if(x.timing.state==='MIXED')reasons.push('Timing misto');
 if(x.timing.state==='PARTIAL')reasons.push('Timing solo parziale');
 if(x.cot.state==='HIGH')reasons.push('COT affollato/estremo');
 if(x.cot.state==='DIVERGENT')reasons.push('COT contrario');
 if(x.liquidity.state==='BAD')reasons.push('Liquidità sfavorevole');
 if(p.decision_frame.quality==='VANTAGGIO RELATIVO PARZIALE')
   reasons.push('Tesi sorretta da un solo pilastro');
 return reasons.length?reasons:['Servono trigger e rapporto rischio/rendimento esterni al modello'];
}
for(const row of result.setup){
 const canonical=expectedSourcedReasons(row.code).slice(0,2).join(' · ');
 assert.equal(row.why,canonical,'risk reasons must be derived from current issuer/feed states: '+row.code);
}
assert(result.setup.some(x=>x.quality==='CON RISCHI'&&x.why.length>5),
 'at least one current risk should be explained by a concrete feed constraint');
assert(result.setup.find(x=>x.code==='USDCHF')?.why.length>3,'USDCHF must preserve its current source-derived obstacle');
function mutate(fn){const input=structuredClone(setup);fn(input);return rank(input,model);}
// A quality category with zero observations may be omitted by the producer.
// Both implicit and explicit zeros are valid; nonzero fabrications are not.
const allBuckets=['DA CONFERMARE','DA MONITORARE','CON RISCHI','NON VALUTABILE'];
const counts=Object.fromEntries(allBuckets.map(k=>[k,Object.values(setup.pairs)
  .filter(p=>p.setup.quality===k).length]));
const zeroBucket=allBuckets.find(k=>counts[k]===0);
assert(zeroBucket,'fixture must exercise an empty quality bucket');
const withExplicitZero=structuredClone(setup);
withExplicitZero.quality_distribution[zeroBucket]=0;
assert(rank(withExplicitZero,model),'explicit zero count must equal omitted zero');
assert.equal(mutate(x=>{x.quality_distribution[zeroBucket]=1}),null,
  'invented positive count in empty bucket must be rejected');
assert.equal(mutate(x=>{x.quality_distribution.UNKNOWN=0}),null,
  'unknown category cannot be treated as a certified bucket');
assert.equal(mutate(x=>{x.quality_distribution[zeroBucket]=-1}),null,
  'negative counts are rejected');
assert.equal(mutate(x=>{x.quality_distribution['CON RISCHI']+=1}),null);
// The canonical runtime can emit EXTENDED for an overextended price. The
// previously recognized ADVANCED and current EXTENDED are both bearish for
// entry attractiveness (not a new directional FX signal). Unknown enums
// must still fail closed rather than silently count as NORMAL.
const eligibleExtension=Object.keys(setup.pairs).find(code=>
  setup.pairs[code].setup.quality!=='NON VALUTABILE');
assert(eligibleExtension,'needs an eligible setup to test extension semantics');
const previousLabel=structuredClone(setup),currentLabel=structuredClone(setup);
previousLabel.pairs[eligibleExtension].setup.extension.state='ADVANCED';
currentLabel.pairs[eligibleExtension].setup.extension.state='EXTENDED';
const oldRank=rank(previousLabel,model),newRank=rank(currentLabel,model);
assert(oldRank&&newRank,'both provenance-supported extension spellings must be accepted');
for(const mode of ['setup','thesis']){
  const oldRow=oldRank[mode].find(x=>x.code===eligibleExtension);
  const newRow=newRank[mode].find(x=>x.code===eligibleExtension);
  assert.equal(JSON.stringify(Array.from(oldRow[mode+'Key'])),
               JSON.stringify(Array.from(newRow[mode+'Key'])),
               'EXTENDED cannot improve an already-advanced setup rank');
  assert.equal(oldRow.why,newRow.why,'risk reading must remain identical');
}
assert.equal(mutate(x=>{x.pairs[eligibleExtension].setup.extension.state='UNVERIFIED'}),null,
  'unknown extension must remain fail-closed');
assert.equal(mutate(x=>{x.pairs.AUDCHF.setup.price.state='UNVERIFIED'}),null);
assert.equal(mutate(x=>{x.pairs.AUDCHF.setup.structural.quality='NOISE'}),null);
assert.equal(mutate(x=>{x.pairs.AUDCHF.setup.structuralFav='NZD'}),null);
assert.equal(mutate(x=>{x.pairs.AUDCHF.setup.timing.state='PREDICTED'}),null);
assert.equal(mutate(x=>{x.entry_level_published=true}),null);
assert.equal(mutate(x=>{x.price_audit.status='FAIL'}),null);
assert.equal(rank(setup,{asOf:'2026-09-24'}),null);
assert(source.includes("if(modelState.verified&&['ADVANCED','EXTENDED'].includes(src.extension?.state))"),
 'canonical extended-price blocker remains visible in Pair Deep Dive');
assert(source.includes('MutationObserver(()=>apply())'),'native search/re-render reordering contract');
assert(source.includes("check.textContent='Primo controllo · '+r.firstCheck"),'each native pair risk has a visible first research check');
assert(source.includes("tbody.append(...sorted)"),'native 28-row table, not a new duplicative list');
assert(source.includes("hasTradeRanking='false'"),'must never claim score or trade signal');
assert(source.includes("panel.dataset.readingMode=reading"),
  'source-agnostic reading level must be a presentation setting only');
assert(source.includes("tbody.dataset.researchReading=reading"),
  'reading mode must survive native pair row redraw and native filters');
assert(source.includes('data-pair-reading="compact" aria-pressed="true"'),
  'compact native first reading must be the default');
assert(source.includes('data-pair-reading="details" aria-pressed="false"'),
  'verification lenses and next check remain one click away');
assert(source.includes('data-research-reading=\\"compact\\"')||
  source.includes('data-research-reading="compact"'),
  'compact CSS should collapse secondary lines, not delete canonical source data');
assert(source.includes("gmfq-row-why"),
  'source-derived first obstacle must remain visible even in compact mode');
assert(source.includes('<details class="gmfq-rank-method-detail">'),
  'lengthy model method is disclosed without overwhelming first viewport');

assert(source.includes('Sovrapposizione valutaria, non correlazione né rischio portafoglio stimati.'),
  'currency overlap must never be presented as statistical or portfolio risk');
assert(source.includes("overlap.dataset.status='OBSERVED'"),
  'first-reading overlap should show source provenance in native pair panel');
console.log('CONTROL_ROOM_V10_PAIR_ORDERING_28_SOURCE_GUARDS_PASS');
