'use strict';
/* Deterministic, data-date-safe interpretation of a research-only futures move.
 * Never tests market values against frozen expectations; moving live prices
 * and quote days remain valid when independently archived/proven.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
const load=p=>JSON.parse(fs.readFileSync(path.join(ROOT,p),'utf8'));
const {interpret,fmtBp,validMove,currentParity}=
  require('../site/fx-quant-v2/assets/ois-same-contract-reading-v1.js');
const research=load('site/fx-quant-v2/ois-same-contract-repricing-research.json');
const source=load('live_data/sections/CB_PRICING_ESTIMATED.json');
const T=['3m','6m','12m'];
const ccys=['USD','EUR','CHF'];
const displayed={};
for(const c of ccys){
  const e=source.currencies[c];
  assert.equal(e.status,'ESTIMATED_ACTIVE',c);
  displayed[c]={horizons:Object.fromEntries(T.map(t=>[t,{
    rate:e.horizons[t].rate,as_of:e.horizons[t].quote_as_of,
    contract:e.horizons[t].contract,kind:'FUTURES SECONDARI',
    quality:'STIMA INDICATIVA'
  }]))};
}
for(const c of ccys){
  const output=interpret(c,research,displayed[c]);
  assert.equal(output.status,'LETTURA_DESCRITTIVA_FUTURES',c);
  assert.equal(output.read_only,true);
  assert.equal(output.fx_signals,0);
  assert.equal(output.policy_deltas,0);
  assert.ok(output.narrative.includes('Ultima data osservata:'));
  assert.ok(output.narrative.includes('futures secondari'));
  assert.ok(output.narrative.includes('non dimostrano da soli'));
  assert.ok(output.matchedTenors.every(t=>T.includes(t)));
  assert.ok(output.latestTenors.every(t=>output.matchedTenors.includes(t)));
  assert.ok(output.latestTenors.length>=1);
  for(const t of output.matchedTenors){
    assert.ok(currentParity(c,t,research,displayed[c]));
    const d=research.currencies[c][t];
    assert.equal(d.as_of,displayed[c].horizons[t].as_of);
    assert.equal(d.rate_pct,displayed[c].horizons[t].rate);
  }
}
// Reproduce a clean 5 Nov session dynamically without relying on future
// market prices. One 12M move is latest, two older tenors have distinct
// quote dates. Do not claim the older futures moved on the latest session.
const fake=structuredClone(research);
const view=structuredClone(displayed.EUR);
for(const t of T){
  fake.currencies.EUR[t].status='VERIFIED_SAME_CONTRACT_PRICE_CHANGE';
  fake.currencies.EUR[t].rate_pct=3;
  fake.currencies.EUR[t].contract='FST3U2027';
  fake.currencies.EUR[t].as_of=t==='12m'?'2026-11-05':'2026-11-04';
  fake.currencies.EUR[t].one_week=null;
  fake.currencies.EUR[t].one_day={
    from_date:t==='12m'?'2026-11-04':'2026-11-03',
    to_date:fake.currencies.EUR[t].as_of,
    change_bp:t==='12m'?0.75:t==='6m'?-1:0.25,
    reference_rate_pct:3-(t==='12m'?0.0075:t==='6m'?-0.01:0.0025),
    current_rate_pct:3,same_contract:true,same_expiration:true,not_policy_rate:true
  };
  view.horizons[t]={rate:3,as_of:fake.currencies.EUR[t].as_of,
    contract:'FST3U2027',kind:'FUTURES SECONDARI',quality:'STIMA INDICATIVA'};
}
const mixedDates=interpret('EUR',fake,view);
assert.deepEqual(mixedDates.latestTenors,['12m']);
assert.deepEqual(mixedDates.olderTenors,['3m','6m']);
assert.equal(mixedDates.verified1D,1);
assert.match(mixedDates.narrative,/12M \+0,75 pb/);
assert.match(mixedDates.narrative,/3M fermo al 04\/11\/2026/);
assert.match(mixedDates.narrative,/6M fermo al 04\/11\/2026/);
assert.doesNotMatch(mixedDates.narrative,/6M −1 pb/);
assert.doesNotMatch(mixedDates.narrative,/3M \+0,25 pb/);
// Replacing one current displayed rate or contract must suppress exactly
// that tenor in narrative, not infer a stale event/cross-contract move.
const badView=structuredClone(view);
badView.horizons['12m'].contract='DIFFERENT_CONTRACT';
const stopped=interpret('EUR',fake,badView);
assert.deepEqual(stopped.latestTenors,['3m','6m']);
assert.deepEqual(stopped.matchedTenors,['3m','6m']);
assert.match(stopped.narrative,/Altri tenori sospesi/);
assert.doesNotMatch(stopped.narrative,/12M \+0,75 pb/);
const altered=structuredClone(fake);
altered.currencies.EUR['12m'].one_day.change_bp=99;
assert.equal(validMove(altered.currencies.EUR['12m'],
  altered.currencies.EUR['12m'].one_day,1),false);
const alteredWeek=structuredClone(fake);
alteredWeek.currencies.EUR['12m'].one_week={
  ...fake.currencies.EUR['12m'].one_day,
  from_date:'2026-11-03'
};
assert.equal(validMove(alteredWeek.currencies.EUR['12m'],
  alteredWeek.currencies.EUR['12m'].one_week,7),false);
// A newly selected listed contract may have a verified current quote but
// no previous same-contract observation. Show the quote, not a fake move.
const debut=structuredClone(fake);
debut.currencies.EUR['12m'].status='VERIFIED_CONTRACT_NO_MATCHED_REFERENCE';
debut.currencies.EUR['12m'].one_day=null;
debut.currencies.EUR['12m'].one_week=null;
const debutReading=interpret('EUR',debut,view);
assert.ok(debutReading.matchedTenors.includes('12m'));
assert.equal(debutReading.latestDate,'2026-11-05');
assert.equal(debutReading.verified1D,0);
assert.match(debutReading.narrative,/Manca il confronto verificato/);
assert.doesNotMatch(debutReading.narrative,/12M \+0,75 pb/);
assert.equal(interpret('GBP',fake,view).status,'NON_VERIFICABILE');
assert.equal(interpret('EUR',{...fake,eligible_for_fx_engine:true},view).matchedTenors.length,0);
assert.equal(fmtBp(-9.5),'−9,5 pb');
assert.equal(fmtBp(0),'0 pb');
console.log('FXV2_SAME_CONTRACT_READING_PASS',JSON.stringify({
  currencies:ccys.length,tenors:T.length,
  strict_mixed_date_exclusion:true,
  mismatched_contract_exclusion:true,invalid_move_rejected:true,
  signal_effect:'NONE',official_ois_created:false
}));