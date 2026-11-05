'use strict';
// Offline adversarial test: no remote calls, no Core writes.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const load=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const model=require('../site/fx-quant-v2/assets/pair-relative-triangulation-v1.js');
const macroApi=require('../site/fx-quant-v2/assets/pair-macro-observed-context-v1.js');
const dynamics=require('../site/fx-quant-v2/assets/pair-macro-dynamics-research-v1.js');
const rates=load('site/fx-quant-v2/pricing-relative-28pairs-research.json');
const macro=load('site/control-room-preview/macro-v3-current-evidence.json');
const setups=load('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',
 year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const shift=(d,n)=>{const v=new Date(d+'T12:00:00Z');v.setUTCDate(v.getUTCDate()+n);return v.toISOString().slice(0,10);};
const formatBp=n=>(n>0?'+':n<0?'−':'')+Math.abs(n).toLocaleString('it-IT',{minimumFractionDigits:1,maximumFractionDigits:1});
const beforeCore=fs.readFileSync(path.join(root,'live_data/sections/D.json'),'utf8');
const beforePairs=fs.readFileSync(path.join(root,'live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),'utf8');
const priceMeta={as_of:setups.price_asof,verified:setups.price_audit.status==='PASS'&&
 setups.price_audit.returns_complete===true&&setups.price_audit.pair_count===28};
const clone=x=>JSON.parse(JSON.stringify(x));
const fmtPrice=(c)=>{
 const x=setups.pairs[c]?.setup;
 return x?{ret1m:x.extension?.move1m,pstate:x.price?.state}:null;
};
assert(model.validate(rates,today),'current 28 pair research source should pass');
assert(macroApi.validate(macro,today),'current published macro should pass');
assert(priceMeta.verified,'dated ECB FX history must pass before marking feed verified');
let count=0;
for(const pair of Object.keys(rates.pairs)){
 const compact=pair.replace('/','');
 const v=model.view(rates,compact,today,macro,macroApi,dynamics,
  fmtPrice(compact),priceMeta);
 assert(v,'every 28 pair must have independent evidence '+pair);
 assert.equal(v.pair,pair);
 assert(v.ratesText.includes('3M')&&v.ratesText.includes('6M')&&v.ratesText.includes('12M'));
 assert(v.ratesText.includes('non variazioni OIS'));
 assert(v.macroText.includes('MACRO V3'));
 assert(v.priceText.includes('PREZZO FX'));
 assert(v.priceText.includes('feed verificato'));
 assert(v.caveatText.includes('Nessun segnale'));
 assert.equal(v.isTradingSignal,false);
 assert.equal(v.policyRepricing,null);
 assert.equal(v.expectedReturn,null);
 count++;
}
assert.equal(count,28);
const eur=model.view(rates,'EURUSD',today,macro,macroApi,dynamics,
 fmtPrice('EURUSD'),priceMeta);
// A new real pricing spread or Macro period must never break the daily QA.
const eur6=rates.pairs['EUR/USD'].horizons['6m'];
assert(eur.ratesText.includes('6M '+formatBp(eur6.spread_bp)+' pb'),
 'displayed 6M spread must derive from current read-only pricing source');
const eurTenors=Object.values(rates.pairs['EUR/USD'].horizons);
const mixed=eurTenors.filter(x=>!x.same_date).length;
assert.equal(eur.mixedDates,mixed);
assert.equal(eur.estimateInvolved,eurTenors.some(x=>x.estimate_involved));
assert(eur.macroText.includes('inflazione periodi')&&eur.macroText.includes('disoccupazione periodi'));
assert(eur.priceText.includes('fixing '+priceMeta.as_of));
assert(eur.priceText.includes('variazione 1M'));
const aud=model.view(rates,'AUDNZD',today,macro,macroApi,dynamics,
 fmtPrice('AUDNZD'),priceMeta);
assert.equal(aud.proxyInvolved,
 Object.values(rates.pairs['AUD/NZD'].horizons).some(x=>x.proxy_involved));
assert(aud.ratesText.includes('Proxy NZD incluso'));
const missingPrice=model.view(rates,'EURUSD',today,macro,macroApi,dynamics,
 fmtPrice('EURUSD'),{as_of:shift(today,1),verified:true});
assert(missingPrice.priceText.includes('osservazione non verificata'));
const snapshot=model.view(rates,'EURUSD',today,macro,macroApi,dynamics,
 fmtPrice('EURUSD'),{as_of:shift(today,-3),verified:false});
assert(snapshot.priceText.includes('snapshot, verificare'));
const noMacro=model.view(rates,'EURUSD',today,null,macroApi,dynamics,
 fmtPrice('EURUSD'),priceMeta);
assert(noMacro.macroText.includes('non disponibile'));
const stale=model.view(rates,'EURUSD',shift(rates.pricing_source_snapshot_date,9),null,macroApi,dynamics,
 fmtPrice('EURUSD'),priceMeta);
assert(stale.ratesText.includes('snapshot oltre 7 giorni'));
for(const [label,make] of [
 ['signal',d=>{d.pairs['EUR/USD'].fx_signal='SELL'}],
 ['future',d=>{d.pairs['EUR/USD'].horizons['6m'].base_as_of=shift(today,30)}],
 ['wrong_bp',d=>{d.pairs['EUR/USD'].horizons['6m'].spread_bp=500}],
 ['invalid_flags',d=>{d.eligible_for_fx_engine=true}],
 ['missing_pair',d=>{delete d.pairs['EUR/USD']}],
 ['duplicate_orientation',d=>{d.pairs['USD/EUR']=d.pairs['EUR/USD'];delete d.pairs['EUR/USD']}],
 ['false_roll',d=>{const h=d.pairs['EUR/USD'].horizons['6m'];h.same_date=!h.same_date}]
]){
 const bad=clone(rates);make(bad);
 assert.equal(model.validate(bad,today),false,'must reject '+label);
}
assert.equal(model.view(rates,'USDEUR',today,macro,macroApi,dynamics,fmtPrice('EURUSD'),priceMeta),null);
assert.equal(fs.readFileSync(path.join(root,'live_data/sections/D.json'),'utf8'),beforeCore);
assert.equal(fs.readFileSync(path.join(root,'live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),'utf8'),beforePairs);
console.log('FXV2_MACRO_RATES_PRICE_EVIDENCE_PASS: 28 pairs; dated FX price; macro comparable flags; estimates/proxies; no signals');
