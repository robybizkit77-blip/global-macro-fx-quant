'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {schema,version,update}=require('./update_estimated_history_v1.cjs');
const {render}=require('../../site/fx-quant-v2/next/pair-rankings.js');
const {pairs}=require('../../live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const sample={status:'STIMA_OPERATIVA_NON_VALIDATA',schema:version,priceAsOf:'2026-11-12',asof:'2026-11-12',
 pairs:Object.keys(pairs).map(key=>({key,favored:key.slice(0,3),thesisStrength:'PARZIALE',tradeAttractiveness:'IN ATTESA'}))};
const context={checked:{day:'2026-11-16',utc:'2026-11-16T15:00:00Z'},commit:'test',method:'same-method',sourceHashes:{observed:'source'}};
const later={...context,checked:{...context.checked,utc:'2026-11-16T16:00:00Z'}};
const afterMacro={...later,checked:{...later.checked,utc:'2026-11-16T17:00:00Z'},
 sourceHashes:{...later.sourceHashes,observed:'new-macro'}};
const empty={schema,snapshots:[]};
const publicArchive=require('../../site/fx-quant-v2/next/pair-estimate-history-v1.json');
assert.equal(update(publicArchive,{status:'STIMA_SOSPESA'},context).status,'ESTIMATE_SUSPENDED');
for(const record of publicArchive.snapshots){
 assert.match(record.commit,/^[a-f0-9]{40}$/);
 assert.match(record.method,/^[a-f0-9]{64}$/);
 assert.equal(Object.keys(record.sourceHashes).length,5);
 assert(Object.values(record.sourceHashes).every(hash=>/^[a-f0-9]{64}$/.test(hash)));
 assert(Number.isFinite(Date.parse(record.capturedAt)));
}
const first=update(empty,sample,context);
assert.equal(first.status,'RECORDED');
assert.equal(empty.snapshots.length,0);
assert.equal(Object.keys(first.history.snapshots[0].pairs).length,28);
const next=structuredClone(sample);
next.priceAsOf='2026-11-13';
next.pairs.find(x=>x.key==='EURCHF').favored='CHF';
next.pairs.find(x=>x.key==='EURCHF').tradeAttractiveness='BASSA ORA';
const second=update(first.history,next,later);
assert.equal(second.status,'RECORDED');
assert.equal(update(second.history,next,afterMacro).status,'NO_MATERIAL_THESIS_CHANGE');
assert.equal(update(second.history,sample,afterMacro).status,'OLDER_INPUTS');
assert.equal(update(empty,{status:'STIMA_SOSPESA'},context).status,'ESTIMATE_SUSPENDED');
assert.throws(()=>update(empty,{...sample,priceAsOf:'2026-11-17'},context),/Invalid fixing/);
const renderWatch=history=>render({get:k=>({pairs:{pairs},estimatedThesisHistory:history})[k],
 state:{watch:new Set(['EURCHF','AUDCAD']),pairListView:'watch'},esc:String,date:String,sign:String,dayNow:()=>context.checked.day});
assert.match(renderWatch(first.history),/Storico della tesi in raccolta/);
const compared=renderWatch(second.history);
assert.match(compared,/Valuta favorita EUR → CHF/);
assert.match(compared,/Timing in attesa → bassa ora/);
assert.match(compared,/Giudizi su tesi e timing invariati/);
assert.match(compared,/Stime archiviate con fixing del 2026-11-12 e del 2026-11-13/);
const different=update(first.history,next,{...later,method:'different-method'});
assert.doesNotMatch(renderWatch(different.history),/Valuta favorita EUR → CHF/);
const macroUpdate=structuredClone(next);
macroUpdate.asof='2026-11-16';
macroUpdate.pairs.find(x=>x.key==='EURCHF').favored='EUR';
const sameFixing=update(second.history,macroUpdate,afterMacro);
assert.equal(sameFixing.status,'RECORDED');
assert.equal(sameFixing.changedPairs,1);
assert.equal(sameFixing.history.snapshots[1],second.history.snapshots[1]);
assert.equal(sameFixing.history.snapshots.at(-1).sourceHashes.observed,'new-macro');
assert.match(renderWatch(sameFixing.history),/Valuta favorita CHF → EUR/);
assert.match(renderWatch(sameFixing.history),/Stime sullo stesso fixing BCE del 2026-11-13.*17:00.*18:00 IT/);
assert.equal(update(sameFixing.history,macroUpdate,afterMacro).status,'NO_MATERIAL_THESIS_CHANGE');
assert.equal(update(sameFixing.history,next,afterMacro).status,'OLDER_INPUTS');
assert.throws(()=>update(second.history,macroUpdate,later),/New capture must follow/);
const workflow=fs.readFileSync(path.join(__dirname,'../../.github/workflows/fx-quant-next-estimated-thesis-history.yml'),'utf8');
const triggers=workflow.split('  workflow_run:')[1].split('  schedule:')[0];
for(const name of ['Price History Persistent Daily V1','Macro V3 Observed G8 28-Pair Public Context V1',
 'OIS Estimated Snapshot Repricing V1','Rates Persistent Daily V1'])assert(triggers.includes(name),name);
console.log('NEXT_ESTIMATED_THESIS_FORWARD_HISTORY_PASS');
