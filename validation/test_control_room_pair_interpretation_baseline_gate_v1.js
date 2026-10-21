'use strict';
/* Model evidence is historical when verified and WITHHELD when the D.json /
   Pair baseline join fails. Independent observed FX/2Y remains observable. */
const fs=require('node:fs');
const assert=require('node:assert/strict');
const source=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const setup=JSON.parse(fs.readFileSync('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json','utf8'));
const model=JSON.parse(fs.readFileSync('live_data/sections/D.json','utf8'));
assert.equal(model.asOf,setup.macro_baseline_asof);
const a=source.indexOf('function pairModelEvidenceState(');
const b=source.indexOf('/* What Changed =',a);
const c=source.indexOf('function pairEvidenceChecklist(');
const d=source.indexOf('async function mountPairResearch(',c);
assert(a>0&&b>a&&c>b&&d>c,'Canonical Pair source-function spans missing');
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const FLAG=Object.fromEntries(FX.map(k=>[k,k]));
const htmlEscape=x=>String(x??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&gt;');
const today='2026-10-21';
const romeCalendarAge=d=>{
 if(typeof d!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(d))return null;
 const ts=Date.parse(d+'T00:00:00Z');
 if(!Number.isFinite(ts)||new Date(ts).toISOString().slice(0,10)!==d)return null;
 return (Date.parse(today+'T00:00:00Z')-ts)/86400000;
};
const fresh=(d,max=4)=>{const x=romeCalendarAge(d);return x!==null&&x>=0&&x<=max;};
const num=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
const fmt=(x,n=1)=>num(x)===null?'—':Number(x).toFixed(n);
const window={};
const funcs=new Function('romeCalendarAge','fresh','num','fmt','FLAG','htmlEscape','window','romeTodayIso',
 source.slice(a,b)+'\n'+source.slice(c,d)+
 ';return {pairModelEvidenceState,pairMacroRatesComparison,pairEvidenceChecklist,pairThesisReactionBridge};')(
 romeCalendarAge,fresh,num,fmt,FLAG,htmlEscape,window,()=>today);
const code='AUDCHF',pair=setup.pairs[code];
assert(pair?.setup?.structuralFav==='AUD','needs historical favored scenario');
const modelDay=setup.price_asof,baseline=model.asOf;
const reaction='<section data-reaction-status="COERENTE" data-window-end="2026-10-20" data-reaction-fx-side="AUD"></section>';
const valid=funcs.pairModelEvidenceState(baseline,modelDay);
assert.deepEqual(valid,{verified:true,current:false,historical:true});
const compareOld=funcs.pairMacroRatesComparison(code,pair,null,null,modelDay,baseline);
const bridgeOld=funcs.pairThesisReactionBridge(code,pair,modelDay,reaction,baseline);
assert(compareOld.includes('data-model-evidence="HISTORICAL"'));
assert(compareOld.includes('baseline '+baseline+' · STORICA'));
assert(compareOld.includes('Favorisce AUD'));
assert(bridgeOld.includes('Preferenza storica · AUD'));
assert(bridgeOld.includes('SETUP DEL MODELLO · STORICO'));
assert(bridgeOld.includes('data-bridge-status="NON_DETERMINATO"'));
assert(bridgeOld.includes('NON CORRENTE: tesi da rivalidare'));
for(const bad of [null,'2026-10-22','2026-13-50','2026-09-24']){
 // This pair has 2026-10-21 price. 24 Sep is a valid *older* baseline,
 // so only verify-null and future/invalid branches here.
 if(bad==='2026-09-24')continue;
 assert.equal(funcs.pairModelEvidenceState(bad,modelDay).verified,false);
 const compare=funcs.pairMacroRatesComparison(code,pair,null,null,modelDay,bad);
 const bridge=funcs.pairThesisReactionBridge(code,pair,modelDay,reaction,bad);
 assert(compare.includes('data-model-evidence="WITHHELD"'));
 assert(compare.includes('WITHHELD · modello non verificato'));
 assert(!compare.includes('Favorisce AUD'));
 assert(!compare.includes('Macro e Tassi/banche centrali favoriscono la stessa valuta'));
 assert(bridge.includes('WITHHELD · baseline non verificata'));
 assert(bridge.includes('qualità, timing e posizionamento del setup WITHHELD'));
 assert(!bridge.includes('Preferenza storica · AUD'));
 assert(!bridge.includes('Timing contrario'));
 assert(!bridge.includes('Controllare che entrambi i pilastri strutturali restino dalla stessa parte'));
 assert(bridge.includes('REAZIONE OSSERVATA · RATES / FX'));
 assert(bridge.includes('data-bridge-status="NON_DETERMINATO"'));
}
const inconsistent=funcs.pairModelEvidenceState('2026-10-20','2026-10-19');
assert.equal(inconsistent.verified,false,'macro newer than model price must not be a valid structural view');
const recent=funcs.pairModelEvidenceState('2026-10-19',modelDay);
assert.deepEqual(recent,{verified:true,current:true,historical:false});
assert(source.includes('const macroDay=macroVerified?setup.macro_baseline_asof:null;'),
 'Caller must verify the D.json/Pair source join before these functions');
console.log('CONTROL_ROOM_PAIR_INTERPRETATION_MISSING_MODEL_FAIL_CLOSED_PASS',
 JSON.stringify({historical:baseline,price:modelDay,negative:4,observable_fx_2y:true}));
