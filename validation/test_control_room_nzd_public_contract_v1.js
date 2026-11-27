'use strict';
const assert=require('node:assert/strict');
const {readApproved,verifyPublicNzd}=require('./control_room_nzd_public_contract_v1.js');
const {approved,canonical}=readApproved('.');
const shown=structuredClone(canonical);
const day=n=>new Date(Date.parse(canonical.date+'T12:00:00Z')+n*86400000);
assert.equal(verifyPublicNzd(shown,approved,canonical,'',day(4)).status,'PASS');
assert.equal(verifyPublicNzd(shown,approved,canonical,'NZD/AUD',day(5)).aud_proxy_allowed,true);
assert.throws(()=>verifyPublicNzd(shown,approved,canonical,'NZD/AUD',day(3)),/proxy/);
function blocked(change,label){
 const changed=structuredClone(shown);change(changed);
 assert.throws(()=>verifyPublicNzd(changed,approved,canonical,'',day(5)),undefined,label);
}
blocked(x=>x.date='2026-10-20','new date not reviewed');
blocked(x=>x['2Y']+=0.01,'2Y changed');
blocked(x=>x['10Y']+=0.01,'10Y changed');
blocked(x=>x.quality='FULL_CURRENT_OFFICIAL_STAGING_REVIEW_REQUIRED','staging not approved');
blocked(x=>x.history2.dates[x.history2.dates.length-1]='2026-10-15','2Y history mismatch');
blocked(x=>x.tenors.find(t=>t.tenor==='10Y').value+=0.2,'10Y tenor mismatch');
assert.throws(()=>verifyPublicNzd(shown,{...approved,current_snapshot:'2026-10-20'},canonical),'registry drift');
console.log('CONTROL_ROOM_NZD_PUBLIC_QA_REVIEWED_DYNAMIC_ASOF_PASS');
