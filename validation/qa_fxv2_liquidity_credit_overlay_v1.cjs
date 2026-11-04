'use strict';
const assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const ROOT=path.resolve(__dirname,'..');
const {merge}=require('../site/fx-quant-v2/assets/liquidity-credit-feed-v1.js');
const snap=JSON.parse(fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/design-studio-cross-asset-v1-data.json')));
const live=JSON.parse(fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/cross-asset-live-data.json')));
const originalSnapshot=JSON.stringify(snap),originalFeed=JSON.stringify(live);
const today='2026-11-04',copy=x=>JSON.parse(JSON.stringify(x));
const actual=merge(snap,live,today);
assert.equal(actual.source_status,'CREDIT_2_OF_2_LIVE_SOURCE');
assert.deepEqual(actual.applied.map(x=>x.ccy),['IG','HY']);
for(const c of ['IG','HY']){
 const src=live.streams[c+'_OAS'],row=actual.data.credit[c];
 assert.equal(row.date,src.date);
 assert.equal(row.value,src.value);
 assert.equal(row.unit,'% OAS');
 assert.equal(row.source_type,'AUTOMATIC_FRED_PUBLISHED_CREDIT_OAS');
 assert.match(row.quality,/RICERCA V2/);
}
assert.equal(JSON.stringify(snap),originalSnapshot,'source snapshot must be immutable');
assert.equal(JSON.stringify(live),originalFeed,'cross feed must be immutable');
const broken=copy(live);
broken.streams.IG_OAS.source_url='https://example.org/not-credit';
assert.equal(merge(snap,broken,today).source_status,'CREDIT_1_OF_2_PARTIAL');
assert.equal(merge(snap,broken,today).data.credit.IG.date,snap.credit.IG.date,
 'one bad IG feed cannot erase good snapshot IG');
assert.equal(merge(snap,broken,today).data.credit.HY.source_type,'AUTOMATIC_FRED_PUBLISHED_CREDIT_OAS',
 'valid HY should advance independently');
broken.streams.IG_OAS=copy(live.streams.IG_OAS);
broken.streams.IG_OAS.date='2026-11-05';
assert.equal(merge(snap,broken,today).applied.length,1,'future IG is rejected');
broken.streams.IG_OAS=copy(live.streams.IG_OAS);
broken.streams.IG_OAS.history.at(-1)[1]+=0.2;
assert.equal(merge(snap,broken,today).applied.length,1,'inconsistent last history rejected');
broken.streams.IG_OAS=copy(live.streams.IG_OAS);
broken.streams.IG_OAS.kind='GOVERNMENT_YIELD';
assert.equal(merge(snap,broken,today).applied.length,1,'wrong instrument must not be accepted');
broken.streams.IG_OAS=copy(live.streams.IG_OAS);
broken.streams.IG_OAS.history.reverse();
assert.equal(merge(snap,broken,today).applied.length,1,'out-of-order data must be rejected');
broken.streams.IG_OAS=copy(live.streams.IG_OAS);
broken.streams.IG_OAS.date='2026-10-01';
assert.equal(merge(snap,broken,today).applied.length,1,'older than snapshot must be rejected');
const stale=merge(snap,live,'2026-12-01');
assert.equal(stale.source_status,'SNAPSHOT_ONLY','never rebrand old data as live');
const shape=copy(live);shape.eligible_for_fx_core=true;
assert.equal(merge(snap,shape,today).source_status,'SNAPSHOT_ONLY','no core eligible source');
assert.equal(merge(snap,null,today).source_status,'SNAPSHOT_ONLY');
console.log('FXV2_LIQUIDITY_CREDIT_FRED_IG_HY_TESTS PASS',actual.applied);
