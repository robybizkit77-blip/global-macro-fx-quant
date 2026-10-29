'use strict';
/* Deterministic browser-helper regression tests: research-only disclosure,
   issuer decision remains separate from market-quote observation dates. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const s=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const a=s.indexOf('function fedPricingFreshnessAudit(');
const b=s.indexOf('\nfunction htmlEscape(',a);
assert(a>0&&b>a,'Fed pricing disclosure must be in active v10 adapter');
const audit=vm.runInNewContext('('+s.slice(a,b)+')',{});
const fed={bank:'Fed',last_date:'2026-10-28',market_pricing:{as_of:'2026-09 (latest surfaced)'}};
const dated='2026-10-27';
const row=(contract,price,date=dated)=>({
 contract,quote_as_of:date,rate:100-price,futures_price:price,
 quote_timestamp_verified:true
});
const source=()=>({
 operational_status:'GREEN_ESTIMATED',quality:'ESTIMATED_INFORMATIONAL',
 backtest_eligible_as_official:false,
 source:'TradingView public server-rendered contract pages · exchange-labelled dated futures',
 as_of:dated,horizons:{
  '3m':row('ZQZ2026',95.95),
  '6m':row('ZQJ2027',95.62),
  '12m':row('ZQV2027',95.38)
 }
});
const today='2026-10-29';
const x=audit(fed,source(),today);
assert.equal(x.state,'LEGACY_STALE_PRE_DECISION');
assert.equal(x.legacy_month,'2026-09');
assert.equal(x.quote_date,'2026-10-27');
assert.equal(x.pre_decision,true);
assert.equal(x.quoted_levels_visible,true);
assert.match(x.text,/PRECEDENTI alla decisione Fed/);
assert.match(x.text,/non misurano il repricing successivo/);
assert.match(x.text,/non OIS/);
assert.match(x.text,/3M 4\.05%/);
assert.match(x.text,/6M 4\.38%/);
assert.match(x.text,/12M 4\.62%/);
// No false synchronous curve: a mixed source date does not qualify.
let y=source();y.horizons['6m'].quote_as_of='2026-10-26';
let z=audit(fed,y,today);
assert.equal(z.quoted_levels_visible,false);
assert.equal(z.quote_date,null);
assert.doesNotMatch(z.text,/6M 4\.38%/);
// No priceValidUntil or unverified timestamp treated as an observation.
y=source();y.horizons['3m'].quote_timestamp_verified=false;
assert.equal(audit(fed,y,today).quoted_levels_visible,false);
// No unauthorized official promotion of arbitrary OIS or official status.
y=source();y.operational_status='GREEN_OFFICIAL';
assert.equal(audit(fed,y,today).quoted_levels_visible,false);
y=source();y.backtest_eligible_as_official=true;
assert.equal(audit(fed,y,today).quoted_levels_visible,false);
// Old quote is not current just because the current policy is unchanged.
y=source();y.as_of='2026-10-20';
for(const h of ['3m','6m','12m'])y.horizons[h].quote_as_of='2026-10-20';
assert.equal(audit(fed,y,today).quoted_levels_visible,false);
// A newly verified observation can be displayed as a dated secondary quote,
// but must not be reported as a certified meeting repricing or OIS.
y=source();y.as_of='2026-10-29';
for(const h of ['3m','6m','12m'])y.horizons[h].quote_as_of='2026-10-29';
z=audit(fed,y,today);
assert.equal(z.pre_decision,false);
assert.equal(z.quoted_levels_visible,true);
assert.match(z.text,/non certificano un repricing di meeting/);
assert.match(z.text,/non OIS/);
// Malformed source data fail closed.
assert.equal(audit(fed,null,today).quoted_levels_visible,false);
assert.equal(audit({last_date:'invalid'},source(),today).pre_decision,false);
// Official CME source must be opened by the user, never harvested into v10.
const cbStart=s.indexOf('async function mountCentralBankFirstReading(');
const cbEnd=s.indexOf('function cotQuantitativeAudit(',cbStart);
const cb=s.slice(cbStart,cbEnd);
assert(cbStart>0&&cbEnd>cbStart);
assert.match(cb,/https:\/\/www\.cmegroup\.com\/markets\/interest-rates\/cme-fedwatch-tool/);
assert.match(cb,/fedWatch\.target='_blank'/);
assert.match(cb,/fedWatch\.rel='noopener noreferrer'/);
assert.match(cb,/fedNote\.appendChild\(fedWatch\)/);
assert.doesNotMatch(cb,/fetch\([^)]*cmegroup/i);
console.log('FED_PRE_FOMC_PRICING_FRESHNESS_DISCLOSURE_FAIL_CLOSED_PASS');
