'use strict';
/* The Home receipt is a dated VIEW of an existing estimated engine, never a signal. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'../..');
const next='site/fx-quant-v2/next/';
const read=p=>fs.readFileSync(path.join(ROOT,p),'utf8');
const json=p=>JSON.parse(read(p));
const api=require(path.join(ROOT,next,'home-thesis-recalc-v1.js'));
const raw=json(next+'pair-estimate-recalc-receipt-v1.json');
const snapshotEstimate={
 status:'STIMA_OPERATIVA_NON_VALIDATA',
 schema:'GMFQ_MACRO_STRENGTH_ESTIMATED_V1',
 asof:raw.macroAsOf,priceAsOf:raw.fixingAsOf,
 coverage:raw.coverage,
 currencies:raw.currencies.map(c=>({...c,rate:{
  quality:c.monetaryQuality,asof:c.monetaryAsOf
 }})),
 pairs:Object.entries(raw.pairs).map(([key,p])=>({
  key,favored:p.favored,thesisStrength:p.thesis,tradeAttractiveness:p.timing
 }))
};
const ctx={
 receipt:raw,
 observed:{generated_europe_rome_day:raw.macroAsOf},
 prices:{last_as_of:raw.fixingAsOf},
 estimate:snapshotEstimate,sourceHashes:{...raw.sourceHashes},
 today:raw.checkedDay
};
assert.equal(api.sourceMatches(raw,ctx.sourceHashes),true);
assert.equal(api.outputMatches(raw,ctx.estimate),true);
assert.equal(api.receiptOK(raw),true,'Real produced audit receipt must validate');
const first=api.render(ctx);
assert.match(first,/id="fx-recalc-pulse"/);
const statusToUi={
 BASELINE_RECALC:'baseline',
 NO_MATERIAL_THESIS_CHANGE:'same',
 RECALCULATED_WITH_CHANGES:'changed'
};
const expectedUi=statusToUi[raw.status];
assert(expectedUi,'The current production receipt has an unsupported audit status');
assert(first.includes('data-recalc-state="'+expectedUi+'"'),
 'Home must represent the actual new/recomputed production receipt, not yesterday\'s status');
if(raw.status==='RECALCULATED_WITH_CHANGES'){
 assert.match(first,/Cambiamenti da verificare/);
 assert.match(first,/tesi FX e/);
 assert.equal(raw.changedPairs.length>0||raw.changedRanks.length>0,true);
}else if(raw.status==='NO_MATERIAL_THESIS_CHANGE'){
 assert.match(first,/nessuna delle 28 tesi FX stimate ha cambiato/);
}else assert.match(first,/Prima fotografia verificata/);
if(raw.status==='RECALCULATED_WITH_CHANGES'){
 assert.match(first,/Che cosa ha modificato la stima/);
 assert.match(first,/Cosa potrebbe smentirla/);
}
if(raw.changedRanks===null)
 assert.match(first,/La variazione delle posizioni G8 non è confrontabile/);
assert.match(first,/Macro (?:al )?\d{2}\/\d{2}\/\d{4}/,
 'The macro observation date must be visible for both same-period and updated receipts');
assert.match(first,/FX [\d/]+/);
assert.match(first,/verifica la ricevuta originale/i);
assert.match(first,/un backtest/);
// Independently exercise the NO CHANGE branch regardless of the day's real
// market inputs. Do not rewrite the real receipt or turn it into a signal.
const unchanged=structuredClone(raw);
unchanged.status='NO_MATERIAL_THESIS_CHANGE';
unchanged.changedPairs=[];
unchanged.changedRanks=[];
const unchangedHtml=api.render({...ctx,receipt:unchanged});
assert.match(unchangedHtml,/data-recalc-state="same"/);
assert.match(unchangedHtml,/nessuna delle 28 tesi FX stimate ha cambiato/);
assert.doesNotMatch(unchangedHtml,/Che cosa ha modificato la stima/);
assert.equal(api.driverReading(unchanged,ctx.estimate),null);
const initialRankUnknown=structuredClone(unchanged);
initialRankUnknown.changedRanks=null;
assert.match(api.render({...ctx,receipt:initialRankUnknown}),
 /La variazione delle posizioni G8 non è confrontabile/);
const sameDateNewInputs=api.render({...ctx,sourceHashes:{...raw.sourceHashes,ois:'0'.repeat(64)}});
assert.match(sameDateNewInputs,/data-recalc-state="UNVERIFIED"/);
assert.match(sameDateNewInputs,/file sorgente sono cambiati/);
const sameDateChangedThesis=structuredClone(ctx.estimate);
sameDateChangedThesis.pairs.find(p=>p.key==='EURUSD').favored='CHF';
assert.match(api.render({...ctx,estimate:sameDateChangedThesis}),/data-recalc-state="UNVERIFIED"/);
const sameDateChangedRank=structuredClone(ctx.estimate);
const two=sameDateChangedRank.currencies.slice(0,2);
[two[0].rank,two[1].rank]=[two[1].rank,two[0].rank];
assert.match(api.render({...ctx,estimate:sameDateChangedRank}),/data-recalc-state="UNVERIFIED"/);
const oldPrice=api.render({...ctx,prices:{last_as_of:'2026-11-21'}});
assert.match(oldPrice,/data-recalc-state="UNVERIFIED"/);
assert.doesNotMatch(oldPrice,/nessuna delle 28 tesi FX stimate/);
const oldMacro=api.render({...ctx,observed:{generated_europe_rome_day:'2026-11-22'}});
assert.match(oldMacro,/data-recalc-state="UNVERIFIED"/);
assert.match(api.render({...ctx,estimate:{...ctx.estimate,status:'STIMA_SOSPESA'}}),/VERIFICA SOSPESA/);
const before=new Date(Date.parse(raw.checkedDay+'T12:00:00Z')-864e5).toISOString().slice(0,10);
const after=new Date(Date.parse(raw.checkedDay+'T12:00:00Z')+8*864e5).toISOString().slice(0,10);
assert.match(api.render({...ctx,today:before}),/VERIFICA SOSPESA/,'No future-date leakage');
assert.match(api.render({...ctx,today:after}),/VERIFICA SOSPESA/,'Old receipt is not a current calculation');
assert.match(api.render({...ctx,receipt:null}),/Ricevuta assente/);
const invalid=structuredClone(raw);
invalid.governance.recomputedCanonicalD=true;
assert.equal(api.receiptOK(invalid),false,'Reject promoted estimates as certified Core');
const incomplete=structuredClone(raw);
delete incomplete.pairs[Object.keys(incomplete.pairs)[0]];
assert.equal(api.receiptOK(incomplete),false,'Reject partial 27-pair audit');
const changed=structuredClone(raw);
changed.status='RECALCULATED_WITH_CHANGES';
changed.changedPairs=[{key:'EURUSD',
 previous:{favored:'USD',thesis:'PARZIALE',timing:'DA VALIDARE'},
 current:{favored:'EUR',thesis:'CONTRASTATA',timing:'BASSA ORA'}}];
changed.changedRanks=[{ccy:'EUR',previous:5,current:4}];
changed.inputChanges=['observed','prices'];
changed.methodChanged=false; // Isolate the input-change scenario from the current real receipt.
changed.factorChanges=null; // Do not invent historical numeric deltas.
changed.pairs.EURUSD={...changed.changedPairs[0].current};
const changedEstimate=structuredClone(ctx.estimate);
Object.assign(changedEstimate.pairs.find(p=>p.key==='EURUSD'),{
 favored:'EUR',thesisStrength:'CONTRASTATA',tradeAttractiveness:'BASSA ORA'
});
assert.equal(api.receiptOK(changed),true);
const displayed=api.render({...ctx,receipt:changed,estimate:changedEstimate});
assert.match(displayed,/data-recalc-state="changed"/);
assert.match(displayed,/1 tesi FX e 1 posizioni/);
assert.match(displayed,/EUR\/USD/);
assert.match(displayed,/preferenza USD → EUR/);
assert.match(displayed,/attrattività DA VALIDARE → BASSA ORA/);
assert.match(displayed,/Macro G8, Prezzi BCE/);
assert.match(displayed,/href="#pairs\?pair=EURUSD"/);
assert.match(displayed,/Che cosa ha modificato la stima/);
assert.match(displayed,/Sono cambiate più famiglie/);
assert.match(displayed,/Cosa potrebbe smentirla/);
// Isolate a same-day government-rate proxy source change from official OIS.
const ratesEvidence=structuredClone(changed);
ratesEvidence.inputChanges=['rates'];
ratesEvidence.methodChanged=false;
const ratesEstimate=structuredClone(changedEstimate);
const eurProxy=ratesEstimate.currencies.find(c=>c.ccy==='EUR');
eurProxy.rate={quality:'PROXY',asof:raw.fixingAsOf,
 kind:'GOV_2Y_PROXY',changeBp:-4.2};
// Keep the synthetic audit receipt consistent with the changed proxy metadata.
// The production guard must still reject mismatched receipt/output sources.
const eurReceipt=ratesEvidence.currencies.find(c=>c.ccy==='EUR');
eurReceipt.monetaryQuality='PROXY';
eurReceipt.monetaryAsOf=raw.fixingAsOf;
const ratesHtml=api.render({...ctx,receipt:ratesEvidence,estimate:ratesEstimate});
assert.match(ratesHtml,/dataset dei rendimenti governativi/);
assert.match(ratesHtml,/Per EUR il 2Y settimanale è -4,2 pb/);
assert.match(ratesHtml,/proxy, NON un OIS/);
assert.match(ratesHtml,/6M OIS ufficiale confrontabile/);
assert.match(ratesHtml,/Il 2Y governativo non misura soltanto/);
// The upcoming producer can include prior and current factor scores.
// Ensure no historical delta may be fabricated by malformed source metadata.
const scoredReceipt=structuredClone(ratesEvidence);
const refEUR=scoredReceipt.currencies.find(c=>c.ccy==='EUR');
const component=(current,previous)=>({previous,current,
 delta:Number((current-previous).toFixed(6))});
scoredReceipt.factorChanges=[{
 ccy:'EUR',rank:{previous:refEUR.rank===1?2:refEUR.rank-1,current:refEUR.rank},
 changes:{
  score:component(refEUR.score,refEUR.score+0.15),
  macroScore:component(refEUR.macroScore,refEUR.macroScore),
  policyScore:component(refEUR.policyScore,refEUR.policyScore+0.5),
  priceScore:component(refEUR.priceScore,refEUR.priceScore)
 },
 monetaryQuality:{previous:'PROXY',current:refEUR.monetaryQuality}
}];
assert.equal(api.receiptOK(scoredReceipt),true);
const factorHtml=api.render({...ctx,receipt:scoredReceipt,estimate:ratesEstimate});
assert.match(factorHtml,/Confronto misurato dei punteggi/);
assert.match(factorHtml,/monetaria/);
assert.match(factorHtml,/non cause dimostrate del prezzo/);
const invalidFactors=structuredClone(scoredReceipt);
invalidFactors.factorChanges[0].changes.policyScore.delta=999;
assert.equal(api.receiptOK(invalidFactors),false);
const malicious=structuredClone(changed);
malicious.changedPairs[0].previous.thesis='<img src=x onerror=alert(1)>';
const escaped=api.render({...ctx,receipt:malicious,estimate:changedEstimate});
assert(escaped.includes('&lt;img'));
assert(!escaped.includes('<img'));
const baseline=structuredClone(raw);
baseline.status='BASELINE_RECALC';baseline.changedPairs=null;baseline.changedRanks=null;
assert.match(api.render({...ctx,receipt:baseline}),/Prima fotografia verificata/);
const index=read(next+'index.html'),app=read(next+'app.js'),css=read(next+'home-thesis-recalc-v1.css');
assert(index.includes('home-thesis-recalc-v1.js?v=3')&&index.includes('home-thesis-recalc-v1.css?v=2'));
assert(index.indexOf('home-thesis-recalc-v1.js?v=3')<index.indexOf('app.js?v='));
assert(app.includes("fetch('./pair-estimate-recalc-receipt-v1.json'"));
assert(app.includes("receipt:get('thesisRecalcReceipt')"));
assert(app.includes("sourceHashes:get('thesisSourceHashes')"));
assert(app.includes('crypto.subtle.digest(\'SHA-256\''));
assert(app.includes("const auditEstimate=state?.data?.thesisRecalcReceipt?"));
assert(app.includes('estimate:auditEstimate'));
assert(app.includes("recalcProof+moneyProof+'<section"));
assert(app.includes("post+recalcProof+moneyProof+'<section"));
assert(app.includes("+recalcProof\n +'<section"));
assert(css.includes('@media(max-width:640px)'));
assert(css.includes('.fx-recalc-driver')&&css.includes('.fx-recalc-invalidation'));
require('./test_next_home_recalc_endtoend_v1.cjs');
console.log('NEXT_HOME_G8_28_RECALC_PASS: source dates, 28-pair receipt, no-change, changed thesis/rank, future/stale/mismatch, XSS, all Home modes');
