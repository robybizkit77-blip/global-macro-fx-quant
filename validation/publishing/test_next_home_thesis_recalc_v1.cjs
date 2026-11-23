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
const ctx={
 receipt:raw,
 observed:{generated_europe_rome_day:raw.macroAsOf},
 prices:{last_as_of:raw.fixingAsOf},
 estimate:{status:'STIMA_OPERATIVA_NON_VALIDATA',asof:raw.macroAsOf,
  priceAsOf:raw.fixingAsOf,coverage:{currencies:8,pairs:28}},
 today:raw.checkedDay
};
assert.equal(api.receiptOK(raw),true,'Real produced audit receipt must validate');
const first=api.render(ctx);
assert.match(first,/id="fx-recalc-pulse"/);
assert.match(first,/data-recalc-state="same"/);
assert.match(first,/nessuna delle 28 tesi FX stimate ha cambiato/);
assert.match(first,/La variazione delle posizioni G8 non è confrontabile/);
assert.match(first,/Macro [\d/]+/);
assert.match(first,/FX [\d/]+/);
assert.match(first,/verifica la ricevuta originale/i);
assert.match(first,/un backtest/);
assert.doesNotMatch(first,/data-recalc-state="changed"/);
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
assert.equal(api.receiptOK(changed),true);
const displayed=api.render({...ctx,receipt:changed});
assert.match(displayed,/data-recalc-state="changed"/);
assert.match(displayed,/1 tesi FX e 1 posizioni/);
assert.match(displayed,/EUR\/USD/);
assert.match(displayed,/preferenza USD → EUR/);
assert.match(displayed,/attrattività DA VALIDARE → BASSA ORA/);
assert.match(displayed,/Macro G8, Prezzi BCE/);
assert.match(displayed,/href="#pairs\?pair=EURUSD"/);
const malicious=structuredClone(changed);
malicious.changedPairs[0].previous.thesis='<img src=x onerror=alert(1)>';
const escaped=api.render({...ctx,receipt:malicious});
assert(escaped.includes('&lt;img'));
assert(!escaped.includes('<img'));
const baseline=structuredClone(raw);
baseline.status='BASELINE_RECALC';baseline.changedPairs=null;baseline.changedRanks=null;
assert.match(api.render({...ctx,receipt:baseline}),/Prima fotografia verificata/);
const index=read(next+'index.html'),app=read(next+'app.js'),css=read(next+'home-thesis-recalc-v1.css');
assert(index.includes('home-thesis-recalc-v1.js?v=1')&&index.includes('home-thesis-recalc-v1.css?v=1'));
assert(index.indexOf('home-thesis-recalc-v1.js?v=1')<index.indexOf('app.js?v='));
assert(app.includes("fetch('./pair-estimate-recalc-receipt-v1.json'"));
assert(app.includes("receipt:get('thesisRecalcReceipt')"));
assert(app.includes("recalcProof+moneyProof+'<section"));
assert(app.includes("post+recalcProof+moneyProof+'<section"));
assert(app.includes("+recalcProof\n +'<section"));
assert(css.includes('@media(max-width:640px)'));
console.log('NEXT_HOME_G8_28_RECALC_PASS: source dates, 28-pair receipt, no-change, changed thesis/rank, future/stale/mismatch, XSS, all Home modes');
