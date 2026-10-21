/* Pair What Changed: source-date provenance contract.
 * Model Growth/Labour/Rates belongs to D.json as-of, not later Price as-of. */
'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
const src=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const a=src.indexOf('function pairWhatChangedEvidence(');
const b=src.indexOf('\nfunction pairMarketReactionAudit(',a);
assert(a>=0&&b>a,'Pair What Changed source not found');
const model=JSON.parse(fs.readFileSync('live_data/sections/D.json','utf8'));
const pairs=JSON.parse(fs.readFileSync('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json','utf8'));
const rates=JSON.parse(fs.readFileSync('live_data/sections/NATIVE_RATES_DATA.json','utf8'));
assert.equal(model.asOf,pairs.macro_baseline_asof,'PIT macro source must match canonical model');
assert.notEqual(pairs.price_asof,model.asOf,'Fixture requires separate modern ECB price and historical Macro baseline');
const today='2026-10-21';
const dateAge=d=>(Date.parse(today+'T00:00:00Z')-Date.parse(d+'T00:00:00Z'))/86400000;
const romeCalendarAge=d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&
 !Number.isNaN(Date.parse(d+'T00:00:00Z'))&&new Date(d+'T00:00:00Z').toISOString().slice(0,10)===d?dateAge(d):null;
const fresh=(d,max)=>Number.isFinite(romeCalendarAge(d))&&romeCalendarAge(d)>=0&&romeCalendarAge(d)<=max;
const num=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
const fmt=(x,d=2)=>num(x)===null?'—':x.toFixed(d);
const htmlEscape=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const FLAG={EUR:'🇪🇺',USD:'🇺🇸',CHF:'🇨🇭'};
const render=new Function('romeCalendarAge','fresh','num','fmt','FLAG','htmlEscape',
 src.slice(a,b)+';return pairWhatChangedEvidence;')(
 romeCalendarAge,fresh,num,fmt,FLAG,htmlEscape);
const pair=pairs.pairs.EURUSD;
assert(pair?.relative_dynamics?.A?.details?.length>0);
const canonical=render('EURUSD',pair,rates,pairs.price_asof,model.asOf);
assert(canonical.includes('data-macro-baseline-as-of="'+model.asOf+'"'));
assert(canonical.includes('data-pair-price-as-of="'+pairs.price_asof+'"'));
assert(canonical.includes('data-macro-baseline-state="HISTORICAL"'));
assert(canonical.includes('BASELINE MACRO/TASSI '+model.asOf+' · STORICA, DA RIVALIDARE'));
assert(canonical.includes('Dinamica relativa del modello (baseline Macro/Tassi '+model.asOf+'; prezzo Pair '+pairs.price_asof+')'));
assert(canonical.includes('non aggiorna automaticamente quelle dinamiche'));
assert(canonical.includes('data-gmfq-yield-change="MEASURED"'));
assert(canonical.includes(pair.relative_dynamics.A.details.find(x=>x.startsWith('Crescita: '))));
assert(!canonical.includes('LETTURA MODELLO · '+pairs.price_asof),
 'The current ECB price date must not be represented as current Macro model as-of');
const withheld=render('EURUSD',pair,rates,pairs.price_asof,null);
assert(withheld.includes('data-macro-baseline-state="WITHHELD"'));
assert(withheld.includes('Lettura Macro del motore non disponibile o non aggiornata.'));
assert(!withheld.includes('>'+pair.relative_dynamics.A.details[0]+'<'));
assert(withheld.includes('data-gmfq-yield-change="MEASURED"'),
 'Absent Macro must not suppress independently observed and dated official 2Y');
const future=render('EURUSD',pair,rates,pairs.price_asof,'2026-10-22');
assert(future.includes('data-macro-baseline-state="WITHHELD"'));
const ahead=render('EURUSD',pair,rates,'2026-09-20','2026-09-25');
assert(ahead.includes('data-macro-baseline-state="WITHHELD"'));
const current=render('EURUSD',pair,rates,pairs.price_asof,'2026-10-19');
assert(current.includes('data-macro-baseline-state="DATED_SNAPSHOT"'));
assert(current.includes('BASELINE MACRO/TASSI 2026-10-19 · SNAPSHOT DATATO'));
assert(src.includes('pairWhatChangedEvidence(code,setup.pairs[code],rates,setup.price_asof,macroDay)'),
 'Every Pair Deep Dive must pass matched source macro date');
console.log('CONTROL_ROOM_PAIR_MODEL_MACRO_BASELINE_VS_PRICE_PROVENANCE_PASS',
 JSON.stringify({pair:'EURUSD',macro_as_of:model.asOf,price_as_of:pairs.price_asof,
 historical:true,independent_2y:true,negative:3}));
