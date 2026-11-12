'use strict';
/* FX Quant Next: shortlist is research only and must not fabricate five trades. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const rel='site/fx-quant-v2/next/';
const ranking=require(path.join(root,rel,'pair-rankings.js'));
const pick=ranking.selectResearchPairs;

const entries=[
 ['EURUSD','USD',1],['GBPUSD','USD',1],['USDJPY','USD',1],
 ['AUDUSD','USD',1],['USDCHF','USD',1],
 ['AUDCAD','AUD',2],['EURGBP','EUR',2],['NZDJPY','NZD',2],
 ['CADCHF','CAD',2],['GBPNZD','GBP',3],['EURCHF',null,4]
].map(([key,favored,tier])=>({key,base:key.slice(0,3),quote:key.slice(3),
 favored,tier,thesisStrength:'PARZIALE',tradeAttractiveness:'DA VALIDARE',macroGap:0.4,policyGap:0.5,scoreGap:0.6,
 aligned:tier===1,opposite:tier===3,source:'STIMA_ESPLICITA_V1'}));
const original=entries.map(x=>x.key);
const chosen=pick(entries);
assert.deepEqual(chosen.map(x=>x.key),['EURUSD','GBPUSD','AUDCAD','EURGBP','NZDJPY'],
 'Prefer varied economic/FX themes while preserving ranking order');
assert.equal(chosen.length,5);
const counts={};
for(const x of chosen){
 counts[x.base]=(counts[x.base]||0)+1;
 counts[x.quote]=(counts[x.quote]||0)+1;
 assert(x.tier===1||x.tier===2,'No opposing-price or no-edge case in Top 5');
}
assert(Object.values(counts).every(n=>n<=2),'Avoid concentration when possible');
assert.equal(chosen.filter(x=>x.favored==='USD').length,2);
assert.deepEqual(entries.map(x=>x.key),original,'The full 28 ordering must not mutate');
assert.deepEqual(pick(entries.slice(0,5)).map(x=>x.key),['EURUSD','GBPUSD'],
 'Five copies of the same USD theme do not become five trade ideas');
assert.deepEqual(pick(entries.slice(-2)),[],'No forced fill from tier 3/4');
assert.deepEqual(pick(null),[],'No shortlist without reliable input');
assert.deepEqual(pick(entries,0),[],'Invalid shortlist size');
assert.equal(pick(entries,3).length,3,'Honor explicit cap');

const src=fs.readFileSync(path.join(root,rel,'pair-rankings.js'),'utf8');
const index=fs.readFileSync(path.join(root,rel,'index.html'),'utf8');
assert(index.includes('./pair-rankings.js?v=6'),'New cache version required');
assert(src.includes('Fino a 5 coppie da studiare'));
assert(src.includes('non inseriamo casi senza vantaggio netto'));
assert(src.includes('fonti anche proxy'));
assert(src.includes('data-pair=') && src.includes('fx-rank-all-list'),
 'Every ranked pair must retain its deep-dive navigation');
console.log('NEXT_PAIR_SHORTLIST_DIVERSIFICATION_V1_PASS: diversified, no forced trade list, stable full ranking');
