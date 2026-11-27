'use strict';
/* The 28 pair first read is intentionally an overview, not an always-open
 * editor. Test the current decision path without reintroducing the removed
 * Compare/Filter explorer and redundant numeric panels. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const app=read('site/fx-quant-v2/next/app.js');
const html=read('site/fx-quant-v2/next/index.html');
const css=read('site/fx-quant-v2/next/pairs-clarity.css');
const rankings=read('site/fx-quant-v2/next/pair-rankings.js');
new vm.Script(app);
new vm.Script(rankings);
assert(html.includes('./pairs-clarity.css?v=8'));
assert(/app\.js\?v=18/.test(html));
assert(css.includes('.pairs-reading-compact'));
assert(css.includes('@media(max-width:560px)'));
const begin=app.indexOf('function pairs(){'),end=app.indexOf('\nfunction macro(){',begin);
assert(begin>=0&&end>begin);
const pairs=app.slice(begin,end);
for(const key of ['id="pair-primary-select"','28 coppie G8, una sola tesi alla volta',
 'pairs-reading-compact','pairs-three-answers','pairs-vintage',
 'Come è cambiata la tesi?','Grafico del cambio e analisi completa',
 'FXQuantDecisionJourney?.build','FXQuantThesisMonitor?.render',
 'const pairCatalyst=','const riskReading=','esc(riskReading)',
 'pairs-event-watch','pairs-compact-footer']){
 assert(pairs.includes(key),'Current pair research layout missing '+key);
}
assert(pairs.includes('FXQuantPairMonetary.render')&&pairs.includes('chooser+main+monetary+historyDetail+detail'),
 'Relative 6M must appear only inside the selected pair dossier before advanced pricing');
assert(pairs.includes('const historyDetail=(change||monitor.ready)?')&&
 pairs.includes("state.pair,get('estimatedThesisHistory'),estimate,today")&&
 pairs.includes('Archivio del modello strutturale'),
 'The visible comparison must use the Next archive and identify the separate structural history');
assert(pairs.includes('const drill=state.pairDetailOpen?'),
 'Pair detail must remain opt-in after the 8-currency/28-pair first read');
assert(pairs.includes('+ranking+drill+'),
 'The complete ranking must appear before the selected pair research');
assert(!pairs.includes('Confronta e filtra le 28 coppie'),
 'Do not restore the obsolete duplicated Compare/Filter panel');
for(const old of ['id="pair-search"','id="pair-results"','pairCoverageIntro()','pairFilterOptions()',
 'lens-grid','PAIR DEEP DIVE','DALLA TESI ALLA DECISIONE'])
 assert(!pairs.includes(old),'Removed or duplicated first-read panel returned: '+old);
assert(pairs.includes('const originalDecision='),
 'Full macro/rates/COT/price audit must remain accessible on request');
assert(pairs.includes("'+originalDecision+'"),
 'The original source research module must be retained within its disclosure');
assert(rankings.includes('function pairRiskReading('),
 'Risk explanation must be source-gated, never an inferred price entry');
assert(rankings.includes('fx-rank-currency-list')&&rankings.includes('fx-rank-all-list'),
 'Eight currency positions and the 28 relative crosses must lead the page');
assert(rankings.includes('fx-rank-featured')&&rankings.includes('selectResearchPairs(items,5)'),
 'Diversified shortlisting must be a research filter, never a forced trade portfolio');
assert(rankings.includes('fx-rank-method')&&rankings.includes('non una misura di aspettative'),
 'Source caveats must stay in the method audit instead of cluttering first read');
assert(app.includes("const closePair=e.target.closest('[data-pair-close]')")&&
 app.includes("history.pushState(null,'','#pairs')")&&
 app.includes("state.pairDetailOpen=Boolean(pair)"),
 'Opening and closing a pair must synchronize the URL and dossier state');
assert(app.includes("if(e.target.id==='pair-primary-select')")&&
 app.includes("const p=e.target.closest('[data-pair]')")&&
 app.includes("const w=e.target.closest('[data-watch]')"),
 'Pair select, ranked row click and watchlist controls must remain wired');
const rootData=JSON.parse(read('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'));
assert.equal(Object.keys(rootData.pairs).length,28);
assert(rootData.pairs.EURUSD&&rootData.pairs.AUDCAD&&rootData.pairs.CADJPY);
const rankingModule=require('../site/fx-quant-v2/next/pair-rankings.js');
const archived=(fixing,favored,thesis,timing,method='v1')=>({
 fixing,method,pairs:{CADJPY:{favored,thesis,timing}}
});
const estimatedHistory={schema:'GMFQ_NEXT_ESTIMATED_FX_THESIS_HISTORY_V1',snapshots:[
 archived('2026-11-19','JPY','PARZIALE','IN ATTESA'),
 archived('2026-11-20','JPY','PARZIALE','DA VALIDARE'),
 archived('2026-11-20',null,'NON DISTINTA','NON VALUTABILE')
]};
const datedEstimate={status:'STIMA_OPERATIVA_NON_VALIDATA',pricePriorAsOf:'2026-11-19',priceAsOf:'2026-11-20'};
const comparison=(estimate=datedEstimate,history=estimatedHistory)=>
 rankingModule.estimatedSessionChange('CADJPY',history,estimate,'2026-11-21');
assert.deepEqual(comparison(),{start:'2026-11-19',end:'2026-11-20',changes:[
 'Valuta favorita JPY → nessuna','Forza della tesi parziale → non distinta','Timing in attesa → non valutabile'
]});
assert.equal(comparison({...datedEstimate,priceAsOf:'2026-11-21'}),null,'No claim for a fixing still missing in the archive');
assert.equal(comparison({...datedEstimate,pricePriorAsOf:'2026-11-18'}),null,'Do not skip a missing fixing');
assert.equal(comparison(datedEstimate,{...estimatedHistory,snapshots:[
 estimatedHistory.snapshots[0],archived('2026-11-20',null,'NON DISTINTA','NON VALUTABILE','v2')
]}),null,'A method change is not a comparable daily change');
globalThis.FXQuantDecisionJourney=require('../site/fx-quant-v2/next/decision-journey.js');
const marketPrices={source:'ECB euro foreign exchange reference rates',rows:[
 {Date:'2026-11-12',EUR:1,CHF:.91},{Date:'2026-11-13',EUR:1,CHF:.92},{Date:'2026-11-16',EUR:1,CHF:.93}
]};
const estimate={status:'STIMA_OPERATIVA_NON_VALIDATA',priceAsOf:'2026-11-13',pricePriorAsOf:'2026-11-12',pairs:[{key:'EURCHF',favored:'CHF'}]};
const inputs={pairs:{pairs:{EURCHF:{}}},currencyPrices:marketPrices,estimatedMacro:estimate};
const renderWatch=()=>rankingModule.render({get:key=>inputs[key],state:{watch:new Set(['EURCHF']),pairListView:'watch'},
 esc:String,sign:(x,n,s)=>x.toFixed(n)+s,date:String,dayNow:()=> '2026-11-13'});
const normal=renderWatch();
assert.match(normal,/1\.10%.*In senso opposto alla tesi su CHF/);
assert.match(normal,/Fixing BCE del 2026-11-12 e del 2026-11-13/);
assert(!normal.includes('2026-11-16'),'Do not include a future fixing');
estimate.pairs[0].favored='EUR';
assert.match(renderWatch(),/Nella direzione della tesi su EUR/);
estimate.priceAsOf='2026-11-12';
assert.match(renderWatch(),/Movimento a favore di EUR/);
assert.doesNotMatch(renderWatch(),/direzione della tesi/);
marketPrices.rows[1].CHF=.910001;
assert.match(renderWatch(),/0\.00%.*Cambio fermo alla precisione mostrata/);
marketPrices.rows[1].CHF=null;
assert.match(renderWatch(),/Variazione tra fixing BCE non disponibile/);
inputs.currencyPrices={...marketPrices,source:'Other source'};
assert.match(renderWatch(),/Variazione tra fixing BCE non disponibile/);

console.log('NEXT_PAIRS_CURRENT_FIRST_READ_PASS: 8 G8, 28 ranked crosses, opt-in desk/catalyst/source audit, click/back/watchlist; no obsolete Compare/Filter duplicate');
