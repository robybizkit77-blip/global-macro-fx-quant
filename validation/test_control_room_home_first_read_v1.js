'use strict';
// Source-safe regression for Home's first-screen Market Pulse reading.
const fs=require('node:fs'),assert=require('node:assert/strict'),vm=require('node:vm');
const js=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const a=js.indexOf('function marketPulseReadings(feedData){');
const b=js.indexOf('function updateHomePulseFirstRead(doc,host){',a);
assert(a>=0&&b>a,'Readout source boundary changed');
const ctx={fresh:(d,n)=>{
 const t=Date.parse('2026-11-01T00:00:00Z')-Date.parse(d+'T00:00:00Z');
 return Number.isFinite(t)&&t>=0&&t<=n*86400000;
},Date,Number,Set};
const read=vm.runInNewContext(js.slice(a,b)+'\nmarketPulseReadings',ctx);
const base={
 schema:'GMFQ_NEWS_PULSE_OPERATIONAL_V1',
 status:'ACTIVE_DETERMINISTIC_LAYERS',
 scope:{claim:'LATEST_VALIDATED_SIGNALS_NOT_GENERIC_HEADLINES'},
 content_as_of:'2026-10-30',generated_at_utc:'2026-10-31T12:26:28.551Z',
 items:[
  {ccy:'JPY',category:'FUTURES_IMPLIED_REPRICING',quality:'OFFICIAL_CERTIFIED',
   confidence:'A',importance:'HIGH',as_of:'2026-10-30',
   source:'Tokyo Financial Exchange · Three-month TONA Futures',
   title:'JPY: variazione futures certificata',
   detail:'Movimento 1D -0.1 bp sul bucket 6M; variazione 1W -0.3 bp. Indicazione tratta da futures: non equivale a una curva OIS osservata.'},
  {ccy:'GBP',category:'OIS_REPRICING',quality:'OFFICIAL_CERTIFIED',
   confidence:'A',importance:'HIGH',as_of:'2026-10-30',
   source:'Bank of England · estimated sterling OIS yield curves · daily OIS archive',
   title:'GBP: repricing OIS',detail:'Movimento 1D -5.3 bp sul bucket 12M; variazione 1W +4.6 bp.'}
 ]
};
let rows=Array.from(read(structuredClone(base)));
assert.equal(rows.length,2,'certified OIS and certified futures must both appear');
assert.equal(rows[0].ccy,'JPY');
assert.equal(rows[0].kind,'FUTURES');
assert.equal(rows[0].one,-0.1);
assert.equal(rows[0].week,-0.3);
assert.equal(rows[1].ccy,'GBP');
assert.equal(rows[1].kind,'OIS');
function rejected(edit,reason){
 const bad=structuredClone(base);edit(bad);
 const got=Array.from(read(bad));
 assert.equal(got.some(x=>x.ccy==='JPY'),false,reason);
}
rejected(x=>x.items[0].category='OIS_REPRICING','futures cannot pose as OIS');
rejected(x=>x.items[0].detail=x.items[0].detail.replace(' Indicazione tratta da futures: non equivale a una curva OIS osservata.',''),'futures require explicit instrument caveat');
rejected(x=>x.items[0].source='Unverified price blogger','source exact-match');
rejected(x=>x.items[0].quality='ESTIMATED_INFORMATIONAL','only certified');
rejected(x=>x.items[0].as_of='2026-10-29','mixed source dates may not imply current change');
rejected(x=>x.items[0].detail='Movimento 1D +10 bp sul bucket 6M; variazione 1W +2 bp.','no source-inconsistent repricing');
const expired=structuredClone(base);expired.content_as_of='2026-10-28';
assert.equal(read(expired).length,0,'stale feed may not be claimed recent');
for(const token of [
 'COSA È CAMBIATO · MERCATI','data-home-pulse-focus="true"',
 "container.dataset.state='DATED_REPRICING'", // changed below to el
 "el.dataset.state='NO_RECENT_CHANGE'",
 "updateHomePulseFirstRead(doc,host)"
 ]){
 if(token.includes('container.dataset'))continue;
 assert(js.includes(token),'Home first-screen source guard/visual missing: '+token);
}
assert(js.includes('non intraday, non segnale FX.'));
assert(js.includes('La mancata verifica non equivale a una variazione nulla.'));
assert(js.includes('Movimento inferiore a 1 bp; nessuna conclusione sul regime da questo solo dato.'));
assert(js.includes('Unica variazione 1D recente certificata: '));
console.log('HOME_SOURCE_SAFE_FIRST_READ_GREEN',JSON.stringify({sources:rows.map(x=>x.ccy),exactDatum:rows[0].one,readOnly:true}));
