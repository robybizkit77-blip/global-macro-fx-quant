'use strict';
/* Time-safe FX thesis tests. Never require the newest source to remain on Nov 10. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const history=JSON.parse(read('site/fx-quant-v2/next/pair-thesis-history.json'));
const current=JSON.parse(read('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'));
const {snapshot,validate,update}=require('./update_history_v1.cjs');
const monitor=require('../../site/fx-quant-v2/next/pair-thesis-monitor.js');
new vm.Script(read('site/fx-quant-v2/next/pair-thesis-monitor.js'),{filename:'pair-thesis-monitor.js'});
new vm.Script(read('site/fx-quant-v2/next/app.js'),{filename:'app.js'});
const html=read('site/fx-quant-v2/next/index.html');
const css=read('site/fx-quant-v2/next/pair-thesis-monitor.css');
const app=read('site/fx-quant-v2/next/app.js');
assert.match(html,/pair-thesis-monitor\.js\?v=3/);
assert.match(html,/pair-thesis-monitor\.css\?v=2/);
assert.match(app,/thesisHistory:'\.\/pair-thesis-history\.json'/);
assert.match(app,/FXQuantThesisMonitor\?\.render/);
assert.match(css,/max-width:560px/);
assert.equal(validate(history),true);
assert(history.snapshots.length>=2&&history.snapshots.length<=35);
assert.deepEqual(history.dates_available,history.snapshots.map(x=>x.price_asof));
assert(history.snapshots.every(x=>x.pair_count===28));
const latest=history.snapshots.at(-1),previous=history.snapshots.at(-2);
assert(latest.price_asof>previous.price_asof);
function modelFromSnapshot(s){
 const pairs=Object.fromEntries(Object.entries(s.pairs).map(([k,p])=>[k,{
  setup:{structuralFav:p.fav,quality:p.quality,price:p.price,timing:p.timing,cot:p.cot,liquidity:p.liquidity},
  decision_frame:p.structural
 }]));
 return {price_asof:s.price_asof,macro_baseline_asof:s.macro_baseline_asof,pairs};
}
const canonical=modelFromSnapshot(latest);
assert.deepEqual(snapshot(canonical,'source-test').pairs,latest.pairs);
assert.equal(Object.keys(canonical.pairs).length,28);
for(const key of Object.keys(canonical.pairs)){
 const res=monitor.analyze(canonical,history,key);
 assert.equal(res.ready,true,'Every dated historical cross should be comparable: '+key);
 assert(res.summary.any>=0&&res.summary.any<=28);
 assert.equal(res.previousAsOf,previous.price_asof);
 assert.equal(res.asof,latest.price_asof);
 assert.equal(res.baseline,latest.macro_baseline_asof);
}
assert.match(monitor.render(canonical,history,'AUDCAD'),/Baseline macro/);
assert.match(monitor.render(canonical,history,'AUDCAD'),/non flussi istituzionali osservati/);
assert.match(monitor.render(canonical,history,'AUDCAD'),/non sono flussi istituzionali osservati|non flussi istituzionali osservati/);
assert(!app.includes("+ranking+(window.FXQuantThesisMonitor?.renderPulse"),
 'Legacy same-session changes must not be shown in new live ranking');
const dailyPulse=monitor.overview(canonical,history);
assert.equal(dailyPulse.ready,true);
assert.equal(dailyPulse.total,28);
assert.equal(dailyPulse.previousAsOf,previous.price_asof);
assert.equal(dailyPulse.asof,latest.price_asof);
assert.equal(dailyPulse.baseline,latest.macro_baseline_asof);
assert.equal(dailyPulse.changedCount,dailyPulse.changes.length);
assert.match(monitor.renderPulse(canonical,history),/Riferimento macro/);
assert.match(monitor.renderPulse(canonical,history),/Non significa|non prove|non sono|Sono cambiamenti|non dimostra/i);
const synthetic=structuredClone(history);
const alternative=synthetic.snapshots.at(-1).pairs.AUDCAD.quality==='PULITO'?'CON RISCHI':'PULITO';
synthetic.snapshots.at(-2).pairs.AUDCAD.quality=alternative;
const withChange=monitor.overview(canonical,synthetic);
assert.equal(withChange.ready,true);
assert(withChange.changedCount>=1);
assert(withChange.changes.some(x=>x.pair==='AUDCAD'&&x.keys.includes('quality')));
assert.match(monitor.renderPulse(canonical,synthetic),/AUD\/CAD/);
assert.match(monitor.renderPulse(canonical,synthetic),/Quali coppie richiedono una nuova verifica/);
assert.equal(monitor.overview({...canonical,price_asof:'2099-01-01'},history).ready,false,
 'Future or unsynchronized pair snapshots must never show daily changes');
assert.match(monitor.renderPulse({...canonical,price_asof:'2099-01-01'},history),/non verificabile/);

const seed6=history.snapshots.find(x=>x.price_asof==='2026-11-06');
const seed10=history.snapshots.find(x=>x.price_asof==='2026-11-10');
if(seed6&&seed10){
 assert.equal(seed6.source_commit,'57c67d394f64bb0e7473c39faf7e36114edfae09');
 assert.equal(seed10.source_commit,'24b5d3c1e474393f7bd1da34bb3511d409234fd8');
 assert.deepEqual([seed6.macro_baseline_asof,seed10.macro_baseline_asof],['2026-09-25','2026-09-25']);
 const pair6to10={...history,snapshots:[seed6,seed10]};
 const report=monitor.analyze(modelFromSnapshot(seed10),pair6to10,'AUDCAD');
 assert.equal(report.ready,true);
 assert.equal(report.summary.any,17);
 assert.equal(report.summary.quality,2);
 assert.equal(report.summary.price,0);
 assert.equal(report.summary.fav,0);
 assert.equal(report.summary.timing,8);
 assert.equal(report.summary.cot,14);
 assert.deepEqual(report.changed.map(x=>x.key),['quality','cot.text']);
 assert.match(monitor.render(modelFromSnapshot(seed10),pair6to10,'AUDCAD'),/17\/28/);
}
assert.equal(monitor.analyze(canonical,null,'AUDCAD').ready,false);
assert.match(monitor.render(canonical,null,'AUDCAD'),/non verificabile/);
const outOfSync=structuredClone(canonical);outOfSync.price_asof='2099-01-01';
assert.equal(monitor.analyze(outOfSync,history,'AUDCAD').ready,false,'No comparison of future model with old history');
const syntheticDrift=structuredClone(canonical);
syntheticDrift.pairs.AUDCAD.setup.timing.text='Etichetta aggiornata con la stessa data';
const explanation=monitor.overview(syntheticDrift,history);
assert.equal(explanation.ready,true,'The verified archived daily comparisons must remain readable');
assert.equal(explanation.archivedOnly,true,'A same-fixing revision is not the displayed current dossier');
assert.deepEqual(explanation.recalculatedPairs,['AUDCAD']);
assert.deepEqual(explanation.changes,dailyPulse.changes,
 'Recomputed timing labels must NOT be counted as new day-to-day changes');
assert.equal(monitor.readiness(syntheticDrift,history).ready,false,
 'Unreconciled current model remains correctly withheld as LIVE evidence');
assert.match(monitor.renderPulse(syntheticDrift,history),/Solo storico archiviato/);
assert.match(monitor.render(syntheticDrift,history,'AUDCAD'),/Solo confronto storico archiviato/);
assert.doesNotMatch(monitor.render(syntheticDrift,history,'AUDCAD'),
 /Etichetta aggiornata con la stessa data/,
 'Unarchived same-day timing text must never appear as historical evidence');
const sameDayDrift=structuredClone(canonical);
sameDayDrift.pairs.AUDCAD.setup.cot.text='Unpersisted intraday label';
const archival=monitor.analyze(sameDayDrift,history,'AUDCAD');
assert.equal(archival.ready,true,'Archive can still be read when one current label has drifted');
assert.equal(archival.archivedOnly,true);
assert.deepEqual(archival.recalculatedPairs,['AUDCAD']);
assert.equal(archival.current.cotText,latest.pairs.AUDCAD.cot.text,
 'Archive comparison must NEVER use same-session unarchived COT or timing changes');
const rejected=structuredClone(history);rejected.snapshots.push({...latest});
assert.throws(()=>validate(rejected),/sorted unique/);
assert.equal(update(canonical,history,'new-source').changed,false,'No duplicate snapshots for same as-of');
const next=structuredClone(canonical);
next.price_asof=new Date(Date.parse(latest.price_asof+'T12:00:00Z')+864e5).toISOString().slice(0,10);
const added=update(next,history,'new-source');
assert.equal(added.changed,true);
assert.equal(added.history.snapshots.at(-1).source_commit,'new-source');
assert.equal(added.history.snapshots.at(-1).price_asof,next.price_asof);
assert.equal(added.history.snapshots.length,Math.min(35,history.snapshots.length+1));
assert.equal(validate(added.history),true);
const older=structuredClone(canonical);older.price_asof='2026-10-01';
assert.throws(()=>update(older,history),/precedes newest history/);
const invalid=structuredClone(canonical);delete invalid.pairs.AUDCAD;
assert.throws(()=>snapshot(invalid),/exactly 28/);
assert.equal(monitor.analyze(canonical,{...history,snapshots:[]},'AUDCAD').ready,false);
if(current.price_asof===latest.price_asof&&
   current.macro_baseline_asof===latest.macro_baseline_asof){
 const currentAudit=monitor.overview(current,history);
 assert.equal(currentAudit.ready,true,'Historical snapshot remains readable at matching source date');
 if(currentAudit.archivedOnly){
  assert(currentAudit.recalculatedPairs.length>0);
  assert.deepEqual(currentAudit.changes,dailyPulse.changes,
   'Live same-date rebuild must not contaminate two dated archived snapshots');
  assert.match(monitor.render(current,history,'AUDCAD'),/Solo confronto storico archiviato/);
 }else assert.deepEqual(currentAudit.recalculatedPairs,[]);
}else{
 assert.equal(monitor.analyze(current,history,'AUDCAD').ready,false,
  'Unarchived different-date model must not show invented changes');
}
console.log('PAIR_THESIS_MONITOR_28_DATED_HISTORY_ROLLING_SAFE_NO_FAKE_MACRO_OR_SIGNAL_PASS');
