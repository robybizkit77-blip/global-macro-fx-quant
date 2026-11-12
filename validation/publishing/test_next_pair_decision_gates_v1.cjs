'use strict';
/* Pair first read: a decision framework, NOT a trading trigger generator.
 * Tests both proof of provenance and a concise explanation without repetition. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const next='site/fx-quant-v2/next/';
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const ranking=require(path.join(root,next,'pair-rankings.js'));
const observe=ranking.pairDecisionWatch;

const p={key:'EURUSD',base:'EUR',quote:'USD',favored:'USD',
 macroState:'FAVOREVOLE',policyState:'FAVOREVOLE',fiveState:'COERENTE',
 thesisStrength:'PARZIALE',tradeAttractiveness:'DA VALIDARE'};
const profile={key:'EURUSD',source:'STIMA_ESPLICITA_V1',fresh:true,asof:'2026-11-12',
 watch:{ready:true,asof:'2026-11-12',favorable:1.05123,
  adverse:1.10543,favorableDirection:'Sotto',adverseDirection:'Sopra',
  favorablePassed:false,adversePassed:false}};
const x=observe(p,profile);
assert.match(x.improve,/sotto 1,05123/,'For a USD-favoured EURUSD, a lower fixing is supportive');
assert.match(x.weaken,/sopra 1,10543/,'For a USD-favoured EURUSD, an upper fixing is adverse');
assert.match(x.note,/20 fixing BCE precedenti al 2026-11-12/);
assert.match(x.note,/non sono massimi\/minimi intraday/);
assert(!x.improve.includes('stop') && !x.weaken.includes('ingresso'));
const crossed=structuredClone(profile);
crossed.watch.favorablePassed=true;
crossed.watch.adversePassed=true;
const already=observe(p,crossed);
assert.match(already.improve,/ha già superato/,'Do not recommend an already-passed breakout as future');
assert.match(already.improve,/senza inseguire/);
assert.match(already.weaken,/è già oltre/,'Already breached adverse reference is not a prediction');
const stale=structuredClone(profile);stale.fresh=false;
assert(!observe(p,stale).improve.includes('1,05123'));
assert.match(observe(p,stale).note,/nessun livello di prezzo inventato/i);
const wrongDate=structuredClone(profile);wrongDate.watch.asof='2026-11-11';
assert(!observe(p,wrongDate).weaken.includes('1,10543'));
const legacy=structuredClone(profile);legacy.source='STORICO_D';
assert(!observe(p,legacy).improve.includes('1,05123'));
const none=observe({...p,favored:null},profile);
assert.match(none.improve,/Il solo prezzo non crea una tesi/);
assert.match(none.weaken,/non c’è una tesi direzionale/);
const missingRate=observe({...p,policyState:'ASSENTE'},profile);
assert.match(missingRate.improve,/proxy non può essere chiamato conferma OIS/);
const opposed=observe({...p,macroState:'CONTRARIA'},profile);
assert.match(opposed.improve,/momentum economico relativo/);
const noInput=observe(null,null);
assert.match(noInput.note,/Nessuna soglia operativa/);
const gbpjpy=observe({...p,key:'GBPJPY',base:'GBP',quote:'JPY',favored:'GBP'},{
 ...profile,key:'GBPJPY',watch:{...profile.watch,adverse:196.228,
  favorable:200.5,favorableDirection:'Sopra',adverseDirection:'Sotto'}});
assert.match(gbpjpy.improve,/sopra 200,500/,'JPY reference displays three decimals');
assert.match(gbpjpy.weaken,/sotto 196,228/);
const app=read(next+'app.js');
const html=read(next+'index.html');
const start=app.indexOf('function pairs(){'),end=app.indexOf('\nfunction macro(){',start);
assert(start>=0 && end>start);
const pairs=app.slice(start,end);
for(const required of [
 'const pairProfile=','pairDecisionWatch?.(activePair,pairProfile)',
 'TESI FONDAMENTALE','TRADE ATTRACTIVENESS','PERCHÉ NON È UN INGRESSO',
 'Rafforzerebbe il quadro.','Lo indebolirebbe.','pairs-vintage',
 'pairs-three-answers','pairs-next-action'])assert(pairs.includes(required),required);
assert(!pairs.includes("const next=activePair?.missing"),'No duplicated generic watch paragraph');
assert(pairs.includes("esc(gate.improve)")&&pairs.includes("esc(gate.weaken)"),
 'Every gate must be HTML-escaped');
assert(html.includes('./pair-rankings.js?v=6'));
assert(html.includes('./app.js?v=18.43-pulse2'));
assert.equal(typeof ranking.selectResearchPairs,'function','Current Top5 remains available');
console.log('NEXT_PAIR_DECISION_GATES_V1_PASS: directional levels, passed/stale guards, first-read clarity, no fake H4 entries');
