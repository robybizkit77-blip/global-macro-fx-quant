'use strict';
const assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..');
const d=JSON.parse(fs.readFileSync(path.join(root,'site/control-room-preview/macro-v3-current-evidence.json'),'utf8'));
const native=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),'utf8'));
const {validate,view}=require('../site/fx-quant-v2/assets/pair-macro-observed-context-v1.js');
const copy=x=>JSON.parse(JSON.stringify(x)),prior=JSON.stringify(native);
const dateOffset=(day,delta)=>new Date(Date.parse(day+'T00:00:00Z')+delta*86400000).toISOString().slice(0,10);
const sourceDay=d.generated_europe_rome_day;
assert.match(sourceDay,/^\d{4}-\d{2}-\d{2}$/);
const todayRome=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
assert(sourceDay<=todayRome,'Macro V3 source cannot be dated in the future');
assert(validate(d,sourceDay),'8 currencies / 24 observed axes / 28 pairs must pass');
for(const pair of Object.keys(d.pair_context)){
 const text=view(d,pair.replace('/',''),sourceDay);
 assert(text?.text.includes('non nuovo bias FX'),pair);
 assert(text?.text.includes('Baseline del motore 2026-09-25 invariata'),pair);
 assert(text?.text.includes('disoccupazione'),pair);
 assert(text?.text.includes('Crescita'),pair);
}
assert.equal(view(d,'EURUSD',sourceDay).text.includes('annualizzato SAAR'),true);
assert.equal(view(d,'AUDCAD',sourceDay).text.includes('2026Q2'),true);
assert.equal(view(d,'UNKNOWN',sourceDay),null);
assert.equal(validate(d,dateOffset(sourceDay,11)),false,'stale research not disguised as current');
assert.equal(validate(d,dateOffset(sourceDay,-1)),false,'future research must be rejected');
for(const [label,mutate] of [
 ['recomputed signal',x=>x.safe_to_recompute_structural_pair_theses=true],
 ['pair signal',x=>x.pair_context['EUR/USD'].pair_trade_bias='LONG'],
 ['pair expectation',x=>x.pair_context['EUR/USD'].estimated_FX_expected_return=2],
 ['country score',x=>x.countries.AUD.macro_score=1.2],
 ['country strength',x=>x.countries.CHF.FX_strength=3],
 ['PIT false claim',x=>x.historic_PIT_OOS_not_certified=false],
 ['replaced legacy score',x=>x.summary.numeric_old_D_macro_scores_replaced=1],
 ['incomplete pairs',x=>delete x.pair_context['EUR/USD']],
 ['future date',x=>x.generated_europe_rome_day=dateOffset(sourceDay,1)]
]){
 const x=copy(d);mutate(x);
 assert(!validate(x,sourceDay),'must reject '+label);
}
assert.equal(JSON.stringify(native),prior,'28-pair Core unchanged');
console.log('FXV2_MACRO_V3_PAIR_OBSERVED_CONTEXT_PASS 8x3 observed axes, 28 independent pair views');
