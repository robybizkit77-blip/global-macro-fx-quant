'use strict';
// Regression for V2 dated pricing only. Live rates/expiry dates evolve daily;
// static assertions belong to explicit synthetic fixtures, not live feeds.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
const load=n=>JSON.parse(fs.readFileSync(path.join(ROOT,n),'utf8'));
const {merge}=require('../site/fx-quant-v2/assets/rates-dated-pricing-v1.js');
const official=load('live_data/sections/OIS_OPERATIONAL_VIEW.json');
const estimated=load('live_data/sections/CB_PRICING_ESTIMATED.json');
const nzd=load('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json');
const snapshot=load('site/fx-quant-v2/ois-pricing-snapshot.json');
const cloned=x=>JSON.parse(JSON.stringify(x));
const before=[official,estimated,nzd,snapshot].map(x=>JSON.stringify(x));
const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',
 year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const shift=(date,days)=>{
 const x=new Date(date+'T12:00:00Z');x.setUTCDate(x.getUTCDate()+days);
 return x.toISOString().slice(0,10);
};
const ccy=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'],tenors=['3m','6m','12m'];
const seed=Object.fromEntries(Object.entries(snapshot.currencies).map(([c,v])=>[
 c,{as_of:v.as_of,source_type:v.kind,quality:v.quality,source:v.source,horizons:
 Object.fromEntries(Object.entries(v.horizons).map(([t,h])=>[t,{
 rate:h.rate,as_of:h.as_of,contract:h.contract}]))}]));
assert(snapshot.snapshot_built_from_repo_date<=today,
 'Real V2 snapshot date must not lie in the future');
assert.equal(Object.keys(snapshot.currencies).length,8);
assert.equal(official.schema,'GMFQ_OIS_OPERATIONAL_VIEW_V1');
assert.equal(estimated.schema,'GMFQ_CB_PRICING_ESTIMATED_V1');
assert.equal(nzd.schema,'GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1');

const source=merge(seed,official,estimated,nzd,today);
const {pricing:p,accepted,coverage}=source;
assert.equal(source.eligible_for_fx_engine,false);
assert.equal(source.eligible_for_backtests,false);
assert.equal(source.all_24_levels_present,true,
 '8x3 tenors stay available as explicitly labeled research, never fake official OIS');
assert.equal(source.loaded_levels,24);
const counts={official:0,secondary:0,proxy:0};
for(const c of ccy){
 assert.equal(coverage[c],3,c+' must have all 3 dated pricing horizons');
 for(const t of tenors){
  const h=p[c].horizons[t],prev=seed[c].horizons[t];
  assert(Number.isFinite(h.rate)&&h.as_of<=today,
   c+'/'+t+' needs valid nonfuture level');
  assert(h.as_of>=prev.as_of,
   c+'/'+t+' must not move backwards from a more recent dated snapshot');
  assert(h.kind&&h.quality&&h.source&&h.as_of,
   c+'/'+t+' must have independent tenor provenance');
  if(h.origin==='feed'){
   const cls=h.kind==='PROXY FUTURES'?'proxy':
     h.kind==='FUTURES SECONDARI'?'secondary':'official';
   counts[cls]++;
   assert.equal(h.quality,cls==='proxy'?'PROXY DIREZIONALE':
     cls==='secondary'?'STIMA INFORMATIVA':'FONTE UFFICIALE');
  }else{
   assert.equal(h.origin,undefined,'old quote not silently relabeled as live');
  }
 }
}
assert.deepEqual(accepted,counts,
 'Accepted instrument counts depend on actual valid current sources, not a fixed 4/3/1 split');
assert.equal(Object.values(counts).reduce((a,b)=>a+b,0),
 Object.values(p).flatMap(r=>Object.values(r.horizons)).filter(h=>h.origin==='feed').length);
for(const [c,t,kind] of [['GBP','6m','OIS'],['JPY','6m','FUTURES'],
                         ['NZD','6m','PROXY FUTURES'],
                         ['EUR','6m','FUTURES SECONDARI']]){
 if(p[c].horizons[t].origin==='feed')assert.equal(p[c].horizons[t].kind,kind);
}
// Each tenor must follow its own source observation date. A quote with an
// older as-of must leave a newer snapshot intact; no currency-header dates.
for(const [c,t] of [['EUR','6m'],['CHF','6m'],['USD','3m'],['EUR','3m']]){
 const h=estimated.currencies?.[c]?.horizons?.[t];
 const d=h?.quote_as_of||h?.as_of||estimated.currencies?.[c]?.as_of;
 if(p[c].horizons[t].origin==='feed'&&p[c].horizons[t].kind==='FUTURES SECONDARI'){
  assert.equal(p[c].horizons[t].as_of,d,c+'/'+t+' individual quote date');
  assert.equal(p[c].horizons[t].contract,h.contract);
 }
}
if(p.NZD.horizons['6m'].origin==='feed'&&p.NZD.horizons['6m'].kind==='PROXY FUTURES'){
 assert.equal(p.NZD.horizons['6m'].as_of,nzd.as_of);
 assert.equal(p.NZD.horizons['6m'].contract,nzd.horizons['6m'].expiry_label);
 assert.equal(p.NZD.horizons['6m'].change_1w_bp,nzd.horizons['6m'].change_1w_bp);
}

// Synthetic adversarial cases use dates relative to current observation
// horizon, so Nov 6 or an authentic contract rollover never breaks the QA.
const future=cloned(estimated);
future.currencies.CHF.status='ESTIMATED_ACTIVE';
future.currencies.CHF.horizons['6m'].quote_as_of=shift(today,1);
const blocked=merge(seed,official,future,nzd,today);
assert.deepEqual(blocked.pricing.CHF.horizons['6m'],
 seed.CHF.horizons['6m'],
 'Future CHF quote must preserve original dated snapshot');
assert(blocked.rejected.some(x=>x.currency==='CHF'&&x.tenor==='6m'),
 'Future CHF quote must be rejected');
const nullRate=cloned(estimated);
nullRate.currencies.EUR.horizons['6m'].rate=null;
const absent=merge(seed,official,nullRate,nzd,today);
assert.deepEqual(absent.pricing.EUR.horizons['6m'],seed.EUR.horizons['6m'],
 'Missing estimate must preserve dated fallback');
const older=cloned(estimated);
older.currencies.USD.horizons['3m'].quote_as_of=shift(seed.USD.horizons['3m'].as_of,-20);
const notDowngraded=merge(seed,official,older,nzd,today);
assert.equal(notDowngraded.pricing.USD.horizons['3m'].as_of,
 seed.USD.horizons['3m'].as_of,
 'Older official/secondary quote cannot overwrite newer snapshot');
const latest=cloned(estimated);
latest.currencies.EUR.horizons['6m'].quote_as_of=today;
const upgraded=merge(seed,official,latest,nzd,today);
assert.equal(upgraded.pricing.EUR.horizons['6m'].as_of,today,
 'Valid newly dated EUR quote must be allowed to advance');
assert.equal(upgraded.pricing.EUR.horizons['6m'].kind,'FUTURES SECONDARI');
const fake=cloned(official);fake.currencies.GBP.operational_status='WITHHELD';
const noFake=merge(seed,fake,estimated,nzd,today);
assert.equal(noFake.pricing.GBP.horizons['6m'].origin,undefined,
 'WITHHELD source cannot be reported as official OIS');
const badOfficial=cloned(official);badOfficial.currencies.GBP.horizons['6m'].rate=null;
const invalidOfficial=merge(seed,badOfficial,estimated,nzd,today);
assert.equal(invalidOfficial.pricing.GBP.horizons['6m'].rate,
 seed.GBP.horizons['6m'].rate,
 'Null official OIS cannot overwrite dated fallback');
for(const [i,x] of [official,estimated,nzd,snapshot].entries())
 assert.equal(JSON.stringify(x),before[i],'source was mutated');

const html=fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/tassi.html'),'utf8');
assert(html.includes('rates-dated-pricing-v1.js'));
assert(html.includes('FXV2RatesDatedPricing.merge('));
assert(html.includes('per scadenza')&&html.includes('date e qualità'));
console.log('FXV2_RATES_8X3_PER_TENOR_DATES_PASS: 24 horizons; dynamic dated source precedence; synthetic future, absent, stale; no Core');
