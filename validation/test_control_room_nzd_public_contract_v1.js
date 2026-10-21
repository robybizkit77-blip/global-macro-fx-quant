'use strict';
const assert=require('node:assert/strict');
const {readApproved,normalized,verifyPublicNzd}=require('./control_room_nzd_public_contract_v1.js');
const {approved,canonical}=readApproved('.');
const shown=normalized(canonical);
assert.equal(verifyPublicNzd(shown,approved,canonical,'',new Date('2026-10-20T23:59:00Z')).status,'PASS');
assert.equal(verifyPublicNzd(shown,approved,canonical,'NZD/AUD',new Date('2026-10-21T06:00:00Z')).aud_proxy_allowed,true);
assert.throws(()=>verifyPublicNzd(shown,approved,canonical,'NZD/AUD',new Date('2026-10-19T12:00:00Z')),/proxy/);
function blocked(change,label){
 const changed=structuredClone(shown);change(changed);
 assert.throws(()=>verifyPublicNzd(changed,approved,canonical,'',new Date('2026-10-21T06:00:00Z')),undefined,label);
}
blocked(x=>x.date='2026-10-20','new date not reviewed');
blocked(x=>x.y2+=0.01,'2Y changed');
blocked(x=>x.y10+=0.01,'10Y changed');
blocked(x=>x.quality='FULL_CURRENT_OFFICIAL_STAGING_REVIEW_REQUIRED','staging not approved');
blocked(x=>x.history2.tailDate='2026-10-15','2Y history mismatch');
blocked(x=>x.tenor10.value+=0.2,'10Y tenor mismatch');
assert.throws(()=>verifyPublicNzd(shown,{...approved,current_snapshot:'2026-10-20'},canonical),'registry drift');
console.log('CONTROL_ROOM_NZD_PUBLIC_QA_REVIEWED_DYNAMIC_ASOF_PASS');
