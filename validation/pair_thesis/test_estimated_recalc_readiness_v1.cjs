'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {inspect,live,paths}=require('./audit_estimated_recalc_readiness_v1.cjs');
const receipt=JSON.parse(fs.readFileSync(
 'site/fx-quant-v2/next/pair-estimate-recalc-receipt-v1.json','utf8'));
const day=receipt.checkedDay,sourceHashes={...receipt.sourceHashes},method=receipt.method;
const estimate={status:'STIMA_OPERATIVA_NON_VALIDATA',
 schema:'GMFQ_MACRO_STRENGTH_ESTIMATED_V1',
 asof:receipt.macroAsOf,priceAsOf:receipt.fixingAsOf,coverage:receipt.coverage,
 currencies:receipt.currencies.map(c=>({...c,rate:{
  quality:c.monetaryQuality,asof:c.monetaryAsOf
 }})),
 pairs:Object.entries(receipt.pairs).map(([key,p])=>({
  key,favored:p.favored,thesisStrength:p.thesis,tradeAttractiveness:p.timing
 }))};
const current={receipt,estimate,sourceHashes,method,day};
const baseline=inspect(current);
assert.equal(baseline.status,'CURRENT');
assert.deepEqual(baseline.changedSources,[]);
assert.deepEqual(baseline.changedRanks,[]);
assert.deepEqual(baseline.changedPairs,[]);
assert.deepEqual(Object.keys(paths).sort(),['model','observed','ois','prices','rates']);
const ratesMoved=inspect({...current,sourceHashes:{...sourceHashes,rates:'f'.repeat(64)}});
assert.equal(ratesMoved.status,'INPUT_CHANGED_PENDING_RECALC');
assert.deepEqual(ratesMoved.changedSources,['rates']);
assert.equal(ratesMoved.outputsMatch,true,
 'Source changed while same-date model output stayed constant still needs a new receipt');
const macroMoved=inspect({...current,sourceHashes:{...sourceHashes,observed:'a'.repeat(64),
  ois:'b'.repeat(64)}});
assert.deepEqual(macroMoved.changedSources,['observed','ois']);
const decisionMoved=structuredClone(estimate);
decisionMoved.pairs.find(p=>p.key==='EURUSD').favored='JPY';
const changedPair=inspect({...current,estimate:decisionMoved});
assert.equal(changedPair.status,'OUTPUT_CHANGED_PENDING_RECALC');
assert.deepEqual(changedPair.changedPairs,['EURUSD']);
const rankingMoved=structuredClone(estimate);
const rows=rankingMoved.currencies.slice(0,2);
[rows[0].rank,rows[1].rank]=[rows[1].rank,rows[0].rank];
const changedRank=inspect({...current,estimate:rankingMoved});
assert.equal(changedRank.status,'OUTPUT_CHANGED_PENDING_RECALC');
assert.equal(changedRank.changedRanks.length,2);
const methodChanged=inspect({...current,method:'new method'});
assert.equal(methodChanged.status,'METHOD_CHANGED_PENDING_RECALC');
const dayAfter=new Date(Date.parse(day+'T12:00:00Z')+864e5).toISOString().slice(0,10);
assert.equal(inspect({...current,day:dayAfter}).status,'DAY_CHECK_PENDING');
const suspended=inspect({...current,estimate:{...estimate,status:'STIMA_SOSPESA'}});
assert.equal(suspended.status,'ESTIMATE_SUSPENDED');
const invalid=inspect({...current,receipt:{schema:'WRONG'}});
assert.equal(invalid.status,'RECEIPT_INVALID');
const operational=live();
assert(operational&&typeof operational.status==='string');
assert(Array.isArray(operational.changedSources)||operational.status==='RECEIPT_INVALID');
assert.equal(operational.governance.estimatedResearchOnly,true);
assert.equal(operational.governance.recomputedCanonicalD,false);
assert.equal(operational.governance.tradeSignal,false);
const workflow=fs.readFileSync('.github/workflows/fx-quant-next-estimated-thesis-history.yml','utf8');
assert(workflow.includes("cron: '35 8,17 * * 1-5'"));
assert(workflow.includes("cron: '5 12-16 * * 1-5'"));
assert(workflow.includes("'Rates Persistent Daily V1'"));
assert(workflow.includes("'Price History Persistent Daily V1'"));
assert(workflow.includes("node validation/pair_thesis/audit_estimated_recalc_readiness_v1.cjs"));
assert(workflow.includes('Record verified G8/28 estimated FX recalculation receipt'));
console.log('G8_28_RECALC_READINESS_PASS: raw SHA mismatch, same-day pair/rank change, model method, daily check, suspended/future, current live status='+operational.status);
