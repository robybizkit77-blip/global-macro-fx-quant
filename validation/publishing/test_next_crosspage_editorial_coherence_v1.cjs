'use strict';
/* Editorial contract: three routes, one economic narrative, no duplicated price claims.
 * This is a presentation-only QA; source snapshots, estimates and rankings are unchanged. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const next='site/fx-quant-v2/next/';
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const json=p=>JSON.parse(read(p));
const ranking=require(path.join(root,next,'pair-rankings.js'));
const engine=require(path.join(root,next,'macro-strength-estimated-v1.js'));
const observed=json('site/control-room-preview/macro-v3-current-evidence.json');
const prices=json('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const now=observed.generated_europe_rome_day;
const estimated=engine.evaluate({
 observed,prices,
 ois:json('site/fx-quant-v2/ois-pricing-snapshot.json'),
 rates:json('live_data/sections/NATIVE_RATES_DATA.json'),
 model:json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 now,rankingFn:ranking.currencyRanking
});
assert.equal(estimated.status,'STIMA_OPERATIVA_NON_VALIDATA',estimated.reason);
assert.equal(estimated.pairs.length,28);
assert.equal(estimated.currencies.length,8);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({
 '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
})[c]);
const sample=ranking.render({
 get:k=>k==='estimatedMacro'?estimated:null,
 FLAGS:{USD:'USD',EUR:'EUR',GBP:'GBP',JPY:'JPY',CHF:'CHF',CAD:'CAD',AUD:'AUD',NZD:'NZD'},
 state:{pair:'EURUSD',pairDetailOpen:false},
 esc,date:x=>x,sign:x=>String(x)
});
const shortlist=ranking.selectResearchPairs(estimated.pairs,5);
const rows=[...sample.matchAll(/<span class="fx-rank-pair-copy"><strong>(.*?)<\/strong><small>(.*?)<\/small><\/span>/g)];
assert.equal(rows.length,28+shortlist.length,'Preserve 28 pairs plus the actual (not forced) shortlist');
for(const [,economic,observedPrice] of rows){
 assert(!/prezzo|fixing BCE|20 fixing/i.test(economic),
  'Price is a separate observed line, not repeated as part of the fundamental thesis');
 assert(/20 fixing BCE/.test(observedPrice),'The observed daily-price window stays explicit');
 assert(economic.length<=170,'Each first-read row must fit one short narrative sentence');
}
assert(sample.includes('Macro e movimento monetario convergono')||
 sample.includes('Macro a favore')||sample.includes('Tassi a favore')||
 sample.includes('driver fondamentali')||sample.includes('Macro e tassi non distinguono'),
 'One-line relative economic reading is visible');
const morningCtx={window:{},URL};
vm.runInNewContext(read(next+'morning-desk-v1.js'),morningCtx,
 {filename:'morning-desk-v1.js',timeout:5000});
const morning=morningCtx.window.FXQuantMorningDesk;
const feed=json(next+'morning-desk-current.json');
const calendar=json('live_data/sections/CALENDAR_OPERATIONAL_VIEW.json');
const currentResearch={
 estimated,calendar,
 selectResearchPairs:ranking.selectResearchPairs,
 watchForPair:p=>ranking.pairDecisionWatch(p,null)
};
const params={feed,plot:()=>'<div class="chart"></div>',
 esc,date:x=>x,dayNow:()=>now};
const original=morning.build(params);
const improved=morning.build({...params,currentResearch});
const pulse=morning.fxResearchPulse({...currentResearch,...params});
assert(pulse.includes('Il confronto combina macro, variazioni dei tassi e fixing'));
assert(pulse.includes('AGGIORNAMENTO SEPARATO'));
assert(!pulse.includes('L’inflazione è un contesto di pressione'),
 'Methodology belongs to the source audit, not the home reading');
assert(pulse.includes('Il dossier spiega anche ciò che potrebbe smentirle')||
 !shortlist.length);
const displayPairButtons=(pulse.match(/data-pair="/g)||[]).length;
assert.equal(displayPairButtons,Math.min(3,shortlist.length));
const top3=shortlist.slice(0,3);
for(const x of top3)assert(pulse.includes('data-pair="'+x.key+'"'));
assert.equal(improved.replace(/<details class="morning-secondary-research[\s\S]*?<\/details>/,''),original,
 'Frozen morning briefing must remain untouched by the current FX view');
const g8=read(next+'currency-studio.js');
const focus=g8.slice(g8.indexOf('function strengthFocus(){'),g8.indexOf('function ranking(){'));
assert(focus.includes('Il quadro interno risulta'));
assert(!focus.includes("'in miglioramento'"),
 'Positive economic level is not automatically an improving growth trend');
assert(focus.includes('cur.growthTrend===1')&&focus.includes('cur.growthTrend===-1'),
 'GDP acceleration is treated separately from the economic level');
assert(focus.includes('cur.macroScore>.2&&cur.policyScore<-.1')&&
 focus.includes('cur.macroScore<-.2&&cur.policyScore>.1'),
 'Policy divergence must generate currency-specific monitoring questions');
assert(focus.includes('cur.macroScore>.2&&cur.priceScore<-.1')&&
 focus.includes('cur.macroScore<-.2&&cur.priceScore>.1'),
 'Disagreement between economic lens and actual FX price remains visible');
assert(g8.includes("current.rate.quality==='UFFICIALE'?'Riferimento monetario in rialzo'"),
 'A real 6M reference is never labelled as if it were a 2Y proxy');
const index=read(next+'index.html');
for(const name of ['currency-studio.js?v=15','pair-rankings.js?v=8',
 'morning-desk-v1.js?v=6'])assert(index.includes(name),'Cache revision missing '+name);
console.log('NEXT_CROSSPAGE_EDITORIAL_V1_PASS: home = catalysts, G8 = level versus momentum, 28 FX pairs = relative thesis plus separate price; archive unchanged');
