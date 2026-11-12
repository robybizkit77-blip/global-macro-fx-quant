'use strict';
/* A pair thesis must come from macro/rates, NEVER from FX price.
 * Price can describe preliminary timing, not a validated trade. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'../..');
const read=p=>JSON.parse(fs.readFileSync(path.join(ROOT,p),'utf8'));
const web='site/fx-quant-v2/next/';
const engine=require(path.join(ROOT,web,'macro-strength-estimated-v1.js'));
const ranking=require(path.join(ROOT,web,'pair-rankings.js'));
const desk=require(path.join(ROOT,web,'pair-desk-narrative.js'));
const observed=read('site/control-room-preview/macro-v3-current-evidence.json');
const prices=read('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const ois=read('site/fx-quant-v2/ois-pricing-snapshot.json');
const rates=read('live_data/sections/NATIVE_RATES_DATA.json');
const model=read('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const now=observed.generated_europe_rome_day;
const est=engine.evaluate({observed,prices,ois,rates,model,now,rankingFn:ranking.currencyRanking});
assert.equal(est.status,'STIMA_OPERATIVA_NON_VALIDATA',est.reason);
assert.equal(est.pairs.length,28);
const strengthLabels=new Set(['COERENTE','PARZIALE','CONTRASTATA','NON DISTINTA']);
const tradeLabels=new Set(['DA VALIDARE','IN ATTESA','BASSA ORA','NON SUPPORTATA','NON VALUTABILE']);
for(const x of est.pairs){
 assert(strengthLabels.has(x.thesisStrength),x.key+' thesis label');
 assert(tradeLabels.has(x.tradeAttractiveness),x.key+' trade label');
 assert.equal(x.entryValidated,false,x.key+' cannot claim an entry');
 assert.equal(x.thesisValidatedOOS,false,x.key+' no fitted edge');
 assert.equal(typeof x.thesisReason,'string');
 assert(x.tradeReason.length>=30,x.key+' meaningful trade reasoning');
 assert(Number.isFinite(x.move5Percent),x.key+' requires genuine five-fixing price');
 assert(Number.isFinite(x.thesisGap));
 const expected=Math.abs(x.thesisGap)>=.22?(x.thesisGap>0?x.base:x.quote):null;
 assert.equal(x.favored,expected,x.key+' pair directional thesis excludes the FX price vote');
 if(x.thesisStrength==='NON DISTINTA'||x.thesisStrength==='CONTRASTATA')
  assert(x.tier>=3,x.key+' no strong priority for unsupported fundamentals');
 if(x.tradeAttractiveness==='BASSA ORA')
  assert(x.tier>=3,x.key+' contradictory short-term momentum cannot be top tier');
}
const pick=ranking.selectResearchPairs(est.pairs);
assert(pick.length<=5);
assert(pick.every(x=>['COERENTE','PARZIALE'].includes(x.thesisStrength)));
assert(pick.every(x=>['DA VALIDARE','IN ATTESA'].includes(x.tradeAttractiveness)));
// Same economic inputs and direction: price can flip trade readiness, NOT thesis strength.
const A={ccy:'EUR',partial:false,rate:{quality:'UFFICIALE'}};
const B={ccy:'USD',partial:false,rate:{quality:'UFFICIALE'}};
const input={favored:'USD',base:A,quote:B,macroGap:-0.7,policyGap:-0.8};
const aligned=engine.assessThesisTrade({...input,aligned:true,opposite:false,move5:-0.2});
const contrary=engine.assessThesisTrade({...input,aligned:false,opposite:true,move5:0.4});
assert.equal(aligned.thesisStrength,'COERENTE');
assert.equal(contrary.thesisStrength,aligned.thesisStrength);
assert.equal(aligned.tradeAttractiveness,'DA VALIDARE');
assert.equal(contrary.tradeAttractiveness,'BASSA ORA');
const incomplete=engine.assessThesisTrade({...input,
 base:{...A,partial:true,rate:{quality:'ASSENTE'}},aligned:true,opposite:false,move5:-0.2});
assert.equal(incomplete.policyState,'ASSENTE','Missing rate stays missing, not neutral');
assert.equal(incomplete.thesisStrength,'PARZIALE','Missing sources cannot produce full thesis');
assert.equal(incomplete.entryValidated,false);
const conflicting=engine.assessThesisTrade({...input,policyGap:0.8,aligned:true,opposite:false,move5:-0.2});
assert.equal(conflicting.thesisStrength,'CONTRASTATA','Rates contrary to macro disallow coherent thesis');
assert.equal(conflicting.tradeAttractiveness,'NON SUPPORTATA');
const none=engine.assessThesisTrade({...input,favored:null});
assert.equal(none.thesisStrength,'NON DISTINTA');
assert.equal(none.tradeAttractiveness,'NON VALUTABILE');
// The first read and the opened dossier must agree on pair-specific evidence.
const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=x=>String(x||'');
const html=ranking.render({
 get:k=>k==='estimatedMacro'?est:null,
 FLAGS:{USD:'USD',EUR:'EUR',GBP:'GBP',JPY:'JPY',CHF:'CHF',AUD:'AUD',NZD:'NZD',CAD:'CAD'},
 state:{pair:'EURUSD',pairDetailOpen:false},
 esc,date:fmt,sign:fmt
});
assert(html.includes('TESI ·')&&html.includes('TRADE ·'));
assert(html.includes('Thesis Strength e Trade Attractiveness'));
assert.equal((html.match(/class="fx-rank-pair /g)||[]).length,28+pick.length,
 'The full 28 ranking must survive separately from the shortlist');
assert(!/NaN|undefined|Infinity/.test(html));
const thesis=desk.interpret({
 key:'EURUSD',model,macro:null,ois,cot:null,estimatedMacro:est,now
});
assert.equal(thesis.available,true);
assert(thesis.economicPoint.includes('Thesis Strength:'));
assert(thesis.decisionPoint.includes('Trade Attractiveness:'));
assert(thesis.price.includes('5 fixing')&&thesis.price.includes('20 fixing'));
assert(thesis.decisionPoint.includes('non un ingresso'));
const index=fs.readFileSync(path.join(ROOT,web,'index.html'),'utf8');
assert(index.includes('pair-rankings.js?v=5'));
assert(index.includes('macro-strength-estimated-v1.js?v=2'));
assert(index.includes('pair-desk-narrative.js?v=22'));
console.log('NEXT_THESIS_VS_TRADE_V1_PASS: 28 relative macro/rates theses distinct from 5/20d price, shortlist and no fake entry');
