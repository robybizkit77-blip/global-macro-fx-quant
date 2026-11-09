#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const a=src.indexOf('function homeDatedFxRiskObservations(');
const b=src.indexOf('function mountHomeDatedFxRisk(',a);
assert(a>=0&&b>a,'FX/VIX first read must stay separately testable');
const ctx={FX:['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'],
  num:x=>typeof x==='number'&&Number.isFinite(x)?x:null,Date};
const f=vm.runInNewContext(src.slice(a,b)+'\nhomeDatedFxRiskObservations',ctx);
const fx=JSON.parse(fs.readFileSync('live_data/sections/ECB_G8_PRICE_HISTORY.json','utf8'));
const d=JSON.parse(fs.readFileSync('live_data/sections/D.json','utf8'));
// Use the source's actual latest observation, not a frozen calendar day.
const shift=(day,n)=>new Date(Date.parse(day+'T00:00:00Z')+n*86400000).toISOString().slice(0,10);
const now=shift(fx.last_as_of,1),actual=f(fx,d,now);
assert.equal(actual.sourceEffect,'NONE');
assert.equal(actual.pairEffect,'NONE');
assert.equal(actual.fx.asof,fx.last_as_of);
assert.equal(actual.fx.pairsChecked,7);
const last=fx.rows.at(-1),prev=fx.rows.at(-2);
const changes=['USD','GBP','JPY','AUD','CAD','NZD','CHF']
 .map(c=>({code:c,pct:100*(last[c]/prev[c]-1)}));
assert.equal(actual.fx.strongest.code,changes.reduce((a,b)=>a.pct>b.pct?a:b).code);
assert.equal(actual.fx.weakest.code,changes.reduce((a,b)=>a.pct<b.pct?a:b).code);
// Production may advance the ECB fixing before the independently dated VIX feed.
// Absence is the correct fail-closed outcome, never a synthetic same-day VIX.
const vixDates=d.risk.VIX.dates;
const aligned=last.Date===vixDates.at(-1)&&prev.Date===vixDates.at(-2);
if(!aligned)assert.equal(actual.vix,null,'No VIX claim when the latest FX and risk sessions differ');
// Independently verify that matching genuine dates DO show the published VIX,
// without changing the live FX/VIX files or weakening source provenance.
const matchIndex=fx.rows.findIndex(row=>row.Date===vixDates.at(-1));
assert(matchIndex>=1,'Official ECB FX history must contain the dated VIX close');
const matchedFx=structuredClone(fx);
matchedFx.rows=matchedFx.rows.slice(0,matchIndex+1);
matchedFx.row_count=matchedFx.rows.length;
matchedFx.last_as_of=matchedFx.rows.at(-1).Date;
assert.equal(matchedFx.rows.at(-2).Date,vixDates.at(-2),'A genuine previous matching session is required');
const matched=f(matchedFx,d,shift(matchedFx.last_as_of,1));
assert(matched.fx&&matched.vix,'Dated FX/VIX from the same actual sessions must validate');
assert.equal(matched.vix.asof,matchedFx.last_as_of);
assert.equal(matched.vix.previous,matchedFx.rows.at(-2).Date);
assert.equal(matched.vix.value,d.risk.VIX.values.at(-1));
assert.equal(matched.vix.points,d.risk.VIX.values.at(-1)-d.risk.VIX.values.at(-2));
assert.equal(matched.vix.source,'VIX · dated close in operational risk dataset');
if(aligned)assert.deepEqual(actual.vix,matched.vix,'Current aligned data must agree with historical test');
const reject=(edit,reason)=>{
 const x=structuredClone(fx),y=structuredClone(d);edit(x,y);
 assert.equal(f(x,y,now).fx,null,reason);
};
reject((x)=>{x.source='Secondary FX provider'},'ECB official provenance');
reject((x)=>{x.last_as_of='2026-10-29'},'date metadata parity');
reject((x)=>{x.rows.at(-1).CHF=null},'complete G8 validated quotes');
reject((x)=>{x.rows.at(-1).USD=0},'no invalid denominator');
reject((x)=>{x.row_count=10},'row count parity');
reject((x)=>{const future=shift(now,1);x.rows.at(-1).Date=future;x.last_as_of=future},'future close rejection');
assert.equal(f(fx,d,shift(now,7)).fx,null,'stale official FX rejected');
const mismatch=structuredClone(d);
mismatch.risk.VIX.dates[mismatch.risk.VIX.dates.length-1]=shift(fx.last_as_of,-1);
assert.equal(f(matchedFx,mismatch,shift(matchedFx.last_as_of,1)).vix,null,'VIX cannot join unsynchronized trading sessions');
const spoof=structuredClone(d);spoof.risk.VIX.last_value=1234;
assert.equal(f(matchedFx,spoof,shift(matchedFx.last_as_of,1)).vix,null,'VIX last value must match stored history');
assert.equal(f(matchedFx,{risk:{VIX:{}}},shift(matchedFx.last_as_of,1)).vix,null,'no invented VIX value');
assert.equal(f(fx,null,now).fx.asof,last.Date,'FX source independent of missing cross asset');
assert(src.includes("root.dataset.sourceEffect='NONE';root.dataset.pairEffect='NONE'"));
assert(src.includes('non è un ranking G8 né un prezzo intraday.'));
assert(src.includes('non è un segnale risk-off'));
console.log('HOME_ECB_FX_VIX_DATED_FIRST_READ_GREEN',
 JSON.stringify({asof:actual.fx.asof,previous:actual.fx.previous,
  strongest:actual.fx.strongest,weakest:actual.fx.weakest,currentVix:actual.vix,matchedVix:matched.vix,sourceEffect:'NONE'}));
