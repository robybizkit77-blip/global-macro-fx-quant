'use strict';
const assert=require('node:assert/strict');
const {expectedOfficialCurrencies,dateAge}=require('./control_room_public_ois_eligibility_v1.js');
const H=['3m','6m','12m'],C=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
const base=Object.fromEntries(C.map(c=>[c,{as_of:'2026-10-23',
 status:'ACTIVE',horizons:Object.fromEntries(H.map(h=>[h,{rate:3,policy_delta_bp:5}]))}]));
const view={schema:'GMFQ_OIS_OPERATIONAL_VIEW_V1',currencies:Object.fromEntries(C.map(c=>[c,{
 operational_status:'WITHHELD',official_status:'WITHHELD',quality:'ESTIMATED_INFORMATIONAL',
 backtest_eligible_as_official:false,as_of:'2026-10-23',
 horizons:Object.fromEntries(H.map(h=>[h,{rate:null,policy_delta_bp:null}]))
}]))};
const official={currencies:base};
for(const c of ['GBP','JPY','CAD','AUD']){
 view.currencies[c]={...JSON.parse(JSON.stringify(base[c])),operational_status:'GREEN_OFFICIAL',
  official_status:'ACTIVE',quality:'OFFICIAL_CERTIFIED',backtest_eligible_as_official:true};
}
const check=(date)=>expectedOfficialCurrencies(view,official,date);
assert.deepEqual(check('2026-10-26'),['GBP','JPY','AUD','CAD']);
assert.deepEqual(check('2026-10-28'),[]);
const save=view.currencies.GBP.as_of;
view.currencies.GBP.as_of='2026-10-21';
assert.deepEqual(check('2026-10-26'),['JPY','AUD','CAD'],'aged GBP must not be demanded by browser QA');
view.currencies.GBP.as_of=save;
view.currencies.CHF.operational_status='GREEN_ESTIMATED';
view.currencies.CHF.horizons=JSON.parse(JSON.stringify(base.CHF.horizons));
assert.deepEqual(check('2026-10-26'),['GBP','JPY','AUD','CAD'],'informational futures never official');
view.currencies.GBP.horizons['6m'].rate=null;
assert.deepEqual(check('2026-10-26'),['JPY','AUD','CAD'],'missing official curve tenor excludes source');
view.currencies.GBP.horizons['6m'].rate=3;
official.currencies.GBP.horizons['6m'].rate=4;
assert.throws(()=>check('2026-10-26'),/not backed by canonical official source/);
assert.equal(dateAge('2026-10-23','2026-10-26'),3);
assert.equal(dateAge('invalid','2026-10-26'),null);
console.log('PUBLIC_OIS_DYNAMIC_AGE_SOURCE_PARITY_FAIL_CLOSED_PASS');
