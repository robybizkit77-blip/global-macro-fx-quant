'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
const load=n=>JSON.parse(fs.readFileSync(path.join(ROOT,n),'utf8'));
const {merge}=require('../site/fx-quant-v2/assets/rates-dated-pricing-v1.js');
const official=load('live_data/sections/OIS_OPERATIONAL_VIEW.json');
const estimated=load('live_data/sections/CB_PRICING_ESTIMATED.json');
const nzd=load('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json');
const snapshot=load('site/fx-quant-v2/ois-pricing-snapshot.json');
const before=[JSON.stringify(official),JSON.stringify(estimated),JSON.stringify(nzd),JSON.stringify(snapshot)];
const seed=Object.fromEntries(Object.entries(snapshot.currencies).map(([c,v])=>[
 c,{as_of:v.as_of,source_type:v.kind,quality:v.quality,source:v.source,horizons:
 Object.fromEntries(Object.entries(v.horizons).map(([t,h])=>[t,{
 rate:h.rate,as_of:h.as_of,contract:h.contract}]))}]));
const source=merge(seed,official,estimated,nzd,'2026-11-05');
const {pricing:p,accepted,coverage}=source;
assert.equal(source.eligible_for_fx_engine,false);
assert.equal(source.eligible_for_backtests,false);
assert.equal(source.all_24_levels_present,true,'8x3 rates must be present as tagged research, not fake official');
assert.equal(source.loaded_levels,24);
for(const c of ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']){
 assert.equal(coverage[c],3,c+' must have all 3 dated pricing horizons');
 for(const t of ['3m','6m','12m']){
  const h=p[c].horizons[t];
  assert(Number.isFinite(h.rate)&&h.as_of<='2026-11-05',
    c+'/'+t+' must have a valid nonfuture level');
  assert(h.kind&&h.quality&&h.source&&h.as_of,c+'/'+t+' must have provenance');
 }
}
assert.equal(p.EUR.horizons['6m'].as_of,
 estimated.currencies.EUR.horizons['6m'].quote_as_of,
 'EUR 6M individual quote date must not be taken from older currency header');
assert.equal(p.CHF.horizons['6m'].as_of,
 estimated.currencies.CHF.horizons['6m'].quote_as_of,
 'CHF 6M individual quote date must not be taken from older currency header');
assert.equal(p.USD.horizons['3m'].as_of,
 estimated.currencies.USD.horizons['3m'].quote_as_of);
assert.equal(p.EUR.horizons['3m'].as_of,
 estimated.currencies.EUR.horizons['3m'].quote_as_of);
assert.equal(p.EUR.horizons['6m'].kind,'FUTURES SECONDARI');
assert.equal(p.EUR.horizons['6m'].quality,'STIMA INFORMATIVA');
assert.equal(p.EUR.horizons['6m'].contract,
 estimated.currencies.EUR.horizons['6m'].contract);
assert.equal(p.GBP.horizons['6m'].kind,'OIS');
assert.equal(p.GBP.horizons['6m'].origin,'feed');
assert.equal(p.JPY.horizons['6m'].kind,'FUTURES');
assert.equal(p.NZD.horizons['6m'].kind,'PROXY FUTURES');
assert.equal(p.NZD.horizons['6m'].as_of,nzd.as_of);
assert.equal(p.NZD.horizons['6m'].change_1w_bp,
 nzd.horizons['6m'].change_1w_bp);
assert.equal(p.NZD.horizons['6m'].contract,
 nzd.horizons['6m'].expiry_label);
assert.equal(accepted.official,12,'4 official classes * 3 horizons');
assert.equal(accepted.secondary,9,'3 official WITHHELD currencies filled as indicative');
assert.equal(accepted.proxy,3,'NZD directional bank-bill proxy, not OIS');

const cloned=x=>JSON.parse(JSON.stringify(x));
const bad=cloned(estimated);
bad.currencies.CHF.horizons['6m'].quote_as_of='2026-11-06';
const future=merge(seed,official,bad,nzd,'2026-11-05');
assert.equal(future.pricing.CHF.horizons['6m'].as_of,
 snapshot.currencies.CHF.horizons['6m'].as_of,
 'a future source cannot promote the CHF 6M feed');
assert(!future.pricing.CHF.horizons['6m'].origin,
 'snapshot must stay snapshot if future live quote rejected');
assert(future.rejected.some(x=>x.currency==='CHF'&&x.tenor==='6m'));
const nullRate=cloned(estimated);
nullRate.currencies.EUR.horizons['6m'].rate=null;
const absent=merge(seed,official,nullRate,nzd,'2026-11-05');
assert.equal(absent.pricing.EUR.horizons['6m'].rate,
 seed.EUR.horizons['6m'].rate,'missing value cannot overwrite snapshot');
const older=cloned(estimated);
older.currencies.USD.horizons['3m'].quote_as_of='2026-10-20';
const notDowngraded=merge(seed,official,older,nzd,'2026-11-05');
assert.equal(notDowngraded.pricing.USD.horizons['3m'].as_of,
 seed.USD.horizons['3m'].as_of,
 'older quote cannot overwrite more recent research snapshot');
const newer=cloned(estimated);
newer.currencies.EUR.horizons['6m'].quote_as_of='2026-11-05';
const upgraded=merge(seed,official,newer,nzd,'2026-11-05');
assert.equal(upgraded.pricing.EUR.horizons['6m'].as_of,'2026-11-05');
const fake=cloned(official);fake.currencies.GBP.operational_status='WITHHELD';
const noFake=merge(seed,fake,estimated,nzd,'2026-11-05');
assert.equal(noFake.pricing.GBP.horizons['6m'].origin,undefined,
 'WITHHELD source cannot be called official OIS');
const badOfficial=cloned(official);
badOfficial.currencies.GBP.horizons['6m'].rate=null;
const invalidOfficial=merge(seed,badOfficial,estimated,nzd,'2026-11-05');
assert.equal(invalidOfficial.pricing.GBP.horizons['6m'].rate,
 seed.GBP.horizons['6m'].rate,
 'null official OIS cannot overwrite a dated fallback');
for(const [i,x] of [official,estimated,nzd,snapshot].entries())
 assert.equal(JSON.stringify(x),before[i],'original source immutable');

const html=fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/tassi.html'),'utf8');
assert(html.includes('rates-dated-pricing-v1.js'),
 'V2 Tassi must load exact source-dated adapter');
assert(html.includes('FXV2RatesDatedPricing.merge('),
 'V2 Tassi must consume the same tested source-normalizer');
assert(html.includes('per scadenza')&&html.includes('date e qualità'),
 'V2 Tassi must describe per-tenor provenance to the user');
console.log('FXV2_RATES_8X3_PER_TENOR_DATES_PASS: 24 horizons; EUR/CHF 6M quote dates; OIS vs futures vs proxy; no Core');
