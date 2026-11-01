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
// A growing 41-point source history can validly lose its last item when
// the previous observation equals the latest. Mutate the actual final value
// and below-minimum history length instead: each MUST fail independently.
degraded(x=>{x.history[x.history.length-1]=x.latest_value+1},'AUD','inflation');
degraded(x=>{x.history=x.history.slice(-23)},'AUD','inflation');
assert(source.includes('data-core-effect="NONE" data-bias-effect="NONE"'));
assert(source.includes("panel.dataset.observedStudyCount=String(overview.count)"));
assert(source.includes("Inflazione: '+(inflation?fmt(inflation.value,2)"));
// The production V3 verifier must treat 2026-09 and 2026-09-01
// as the SAME monthly economic observation, while never treating
// a quarterly 2026Q3 label as an unspecified month or FX signal.
const v3=JSON.parse(fs.readFileSync(
 'site/control-room-preview/macro-v3-current-evidence.json','utf8'));
const D=JSON.parse(fs.readFileSync('live_data/sections/D.json','utf8'));
const validateV3=new Function('FX','FLAG','num','fmt','htmlEscape',
 'romeTodayIso','romeCalendarAge',get+';return macroV3Verified;')(
 FX,FLAG,num,(n,d)=>Number.isFinite(n)?n.toFixed(d):'—',
 x=>String(x).replace(/[&<>"']/g,''),()=>today,()=>0);
assert.equal(validateV3(v3,D,therm),true,
 'All eight G8 V3 country periods must match observed series even with YYYY-MM-DD source-day precision');
for(const c of FX){
 for(const k of ['inflation','labour']){
  const t=therm.currencies[c][k],v=v3.countries[c][k];
  const expected=t.frequency==='Q'?
   t.as_of.slice(0,4)+'Q'+(Math.floor((Number(t.as_of.slice(5,7))-1)/3)+1):
   t.as_of.slice(0,7);
  assert.equal(v.observation_period,expected,c+' '+k+' economic period');
 }
}
const tampered=structuredClone(therm);
tampered.currencies.GBP.labour.latest_value+=0.5;
assert.equal(validateV3(v3,D,tampered),false,
 'A different observed source value must invalidate V3 admission');
const tamperedQuarter=structuredClone(v3);
tamperedQuarter.countries.AUD.inflation.observation_period='2026-09';
assert.equal(validateV3(tamperedQuarter,D,therm),false,
 'A Q3 inflation series cannot masquerade as monthly data');
assert.equal(validateV3(v3,{...D,asOf:'2026-10-30'},therm),false,
 'Historical structural D source version must remain unchanged');
console.log('MACRO_V3_G8_MONTH_DAY_PERIOD_PARITY_PASS',JSON.stringify({
 countries:FX.length,pairs:Object.keys(v3.pair_context).length,
 originalMacroAsOf:D.asOf,signals:v3.summary.pair_trade_signals_generated}));
console.log('MACRO_G8_OBSERVED_STUDY_READ_ONLY_PASS',JSON.stringify({rows:8,observations:16,no_model_promotion:true}));
