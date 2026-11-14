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
assert(html.includes('./pairs-clarity.css?v=5'));
assert(/app\.js\?v=18/.test(html));
assert(css.includes('.pairs-reading-compact'));
assert(css.includes('@media(max-width:560px)'));
const begin=app.indexOf('function pairs(){'),end=app.indexOf('\nfunction macro(){',begin);
assert(begin>=0&&end>begin);
const pairs=app.slice(begin,end);
for(const key of ['id="pair-primary-select"','28 coppie G8, una sola tesi alla volta',
 'pairs-reading-compact','pairs-three-answers','pairs-vintage',
 'Come è cambiata la tesi?','Apri grafico, pricing e analisi completa',
 'FXQuantDecisionJourney?.build','FXQuantThesisMonitor?.render',
 'const pairCatalyst=','pairs-event-watch','pairs-compact-footer']){
 assert(pairs.includes(key),'Current pair research layout missing '+key);
}
assert(pairs.includes('FXQuantPairMonetary.render')&&pairs.includes('chooser+main+monetary+historyDetail+detail'),
 'Relative 6M must appear only inside the selected pair dossier before advanced pricing');
assert(pairs.includes('const historyDetail=monitor.ready?'),
 'Do not show an empty comparison if no dated thesis history exists');
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
assert(rankings.includes('fx-rank-currency-list')&&rankings.includes('fx-rank-all-list'),
 'Eight currency positions and the 28 relative crosses must lead the page');
assert(rankings.includes('fx-rank-featured')&&rankings.includes('selectResearchPairs(items,5)'),
 'Diversified shortlisting must be a research filter, never a forced trade portfolio');
assert(rankings.includes('fx-rank-method')&&rankings.includes('non una misura di aspettative'),
 'Source caveats must stay in the method audit instead of cluttering first read');
assert(app.includes("const closePair=e.target.closest('[data-pair-close]')")&&
 app.includes("state.pairDetailOpen=false")&&
 app.includes("state.pairDetailOpen=true"),
 'Open/close pair controls must actually change the same state');
assert(app.includes("if(e.target.id==='pair-primary-select')")&&
 app.includes("const p=e.target.closest('[data-pair]')")&&
 app.includes("const w=e.target.closest('[data-watch]')"),
 'Pair select, ranked row click and watchlist controls must remain wired');
const rootData=JSON.parse(read('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'));
assert.equal(Object.keys(rootData.pairs).length,28);
assert(rootData.pairs.EURUSD&&rootData.pairs.AUDCAD&&rootData.pairs.CADJPY);
console.log('NEXT_PAIRS_CURRENT_FIRST_READ_PASS: 8 G8, 28 ranked crosses, opt-in desk/catalyst/source audit, click/back/watchlist; no obsolete Compare/Filter duplicate');
