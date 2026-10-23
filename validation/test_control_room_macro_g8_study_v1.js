'use strict';
/* Observed G8 Macro levels are independent study context, never refreshed scores. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const source=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const therm=JSON.parse(fs.readFileSync('live_data/sections/MACRO_THERMOMETER_DATA.json','utf8'));
const from=source.indexOf('function macroSeriesPeriod(raw){');
const to=source.indexOf('function macroBaselineValid(',from);
assert(from>=0&&to>from,'Macro source guard or overview missing');
const get=source.slice(from,to);
const FX=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
const FLAG=Object.fromEntries(FX.map(x=>[x,x]));
const num=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
const today='2026-10-23';
const macro=new Function('FX','FLAG','num','fmt','htmlEscape','romeTodayIso',
 get+';return macroStudyOverview;')(FX,FLAG,num,(n,d)=>Number.isFinite(n)?n.toFixed(d):'—',
 x=>String(x).replace(/[&<>"']/g,''),()=>today);
const live=macro(therm);
assert.equal(live.rows.length,8);
assert.equal(live.count,16,'8 G8 inflation + 8 unemployment independently validated');
assert.equal((live.html.match(/data-g8-ccy=/g)||[]).length,8);
assert(!live.html.includes('data-core-signal='));
assert(live.html.includes('2026-06'),'older quarterly periods must remain visible');
for(const c of live.rows){
 assert(c.inflation&&c.labour,'both observed series for '+c.ccy);
 assert(live.html.includes(c.inflation.period));
}
function degraded(change,ccy,column){
 const altered=structuredClone(therm);change(altered.currencies[ccy][column]);
 const v=macro(altered),row=v.rows.find(r=>r.ccy===ccy);
 assert.equal(row[column],null,'reject altered '+ccy+' '+column);
 assert.equal(v.count,15,'bad observation must not be replaced');
}
degraded(x=>x.latest_value+=10,'EUR','inflation');
degraded(x=>x.validation.latest=false,'USD','labour');
degraded(x=>x.transformation='arbitrary','CAD','inflation');
degraded(x=>x.as_of='2027-01','NZD','labour');
degraded(x=>x.history.pop(),'AUD','inflation');
assert(source.includes('data-core-effect="NONE" data-bias-effect="NONE"'));
assert(source.includes("panel.dataset.observedStudyCount=String(overview.count)"));
assert(source.includes("Inflazione: '+(inflation?fmt(inflation.value,2)"));
console.log('MACRO_G8_OBSERVED_STUDY_READ_ONLY_PASS',JSON.stringify({rows:8,observations:16,no_model_promotion:true}));
