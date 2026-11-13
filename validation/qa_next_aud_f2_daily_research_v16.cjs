'use strict';
/* V16 AUD F2: strict research-only daily coverage is never Core or live OIS. */
const fs=require('node:fs'),assert=require('node:assert/strict');
const json=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const rates=json('live_data/sections/NATIVE_RATES_DATA.json');
const price=json('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const model=json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const sidecar=json('site/fx-quant-v2/aud-rba-f2-history-research.json');
const mod=require('../site/fx-quant-v2/next/fx-rates-bridge.js');
// The 6 Nov 2026 research fixture must not inherit tomorrow's live FX fixing.
const audDate=rates.AUD.date,now='2026-11-08',base='2026-11-06';
const later=(day,n)=>new Date(Date.parse(day+'T12:00:00Z')+n*864e5).toISOString().slice(0,10);
// A synthetic *test-only* daily F2 layer must follow the actual AUD source
// date, rather than invent a 6 Nov publication for 11 Nov observations.
const fixtureModelDay=later(audDate,2),fixtureNow=fixtureModelDay;
assert(sidecar.schema==='GMFQ_AUD_RBA_F2_DAILY_HISTORY_RESEARCH_V1');
assert(sidecar.eligible_for_core===false&&sidecar.eligible_for_fx_pair_engine===false);
assert(sidecar.eligible_for_backtests===false);
assert(mod.snapshot(rates,price,'AUDCAD',base,now).ready===false,
 'Canonical weekly-sampled AUD history alone must not be treated as daily FX/2Y evidence');
const dates=price.rows.map(x=>x.Date).filter(x=>x<=audDate).slice(-70);
assert(dates.length===70&&dates.at(-1)===audDate,'Fixture dates must be real ECB fixing dates');
const fake=JSON.parse(JSON.stringify(sidecar));
fake.status='OFFICIAL_F2_DAILY_RESEARCH_ONLY_NOT_POINT_IN_TIME';
fake.schema='GMFQ_AUD_RBA_F2_DAILY_HISTORY_RESEARCH_V1';
fake.source_url='https://www.rba.gov.au/statistics/tables/csv/f2-data.csv';
fake.series_2Y='FCMYGBAG2D';fake.series_10Y='FCMYGBAG10D';
fake.source_response_sha256='a'.repeat(64);
fake.publication_date=audDate;
fake.last_observation_date=audDate;
fake.research_only=true;
fake.no_interpolation=true;fake.same_date_same_source=true;
fake.eligible_for_core=false;
fake.eligible_for_fx_pair_engine=false;
fake.eligible_for_backtests=false;
fake.observations=dates.map((date,i)=>({
 date,'2Y':Math.round((4.4+i*.006)*1000)/1000,'10Y':Math.round((4.7+i*.006)*1000)/1000
}));
fake.observations.at(-1)['2Y']=rates.AUD['2Y'];
fake.observations.at(-1)['10Y']=rates.AUD['10Y'];
const before=structuredClone(rates); // Preserves signed zero; JSON stringify normalizes -0 to 0.
const improved=mod.snapshot(rates,price,'AUDJPY',fixtureModelDay,fixtureNow,fake);
assert(improved.ready&&improved.short&&improved.medium,'70 synthetic QA fixture dates must validate both horizons');
assert(improved.researchOnly&&improved.kind.includes('RBA F2 RICERCA'));
assert.equal(improved.latest.date,audDate);
assert.equal(improved.lag,2);
assert.equal(improved.rows.at(-1).date,audDate);
assert.deepEqual(rates,before,'Canonical rates must remain unchanged after research overlay');
assert.match(mod.brief(improved).label,/RBA F2 ricerca/);
for(const [label,mutation] of [
 ['wrong source',x=>x.source_url='https://example.invalid'],
 ['bad authority',x=>x.series_2Y='WRONG'],
 ['no digest',x=>x.source_response_sha256='unknown'],
 ['not research',x=>x.research_only=false],
 ['forbidden promotion',x=>x.eligible_for_core=true],
 ['date mismatch',x=>x.last_observation_date='2026-11-05'],
 ['source rollback',x=>x.publication_date='2026-11-03'],
 ['duplicate dates',x=>x.observations[1].date=x.observations[0].date],
 ['broken history',x=>x.observations=x.observations.slice(0,10)],
 ['last yield mismatch',x=>x.observations.at(-1)['2Y']+=0.01],
 ['last 10y mismatch',x=>x.observations.at(-1)['10Y']+=0.01],
 ['future release',x=>x.publication_date=later(fixtureNow,1)]
]){
 const changed=JSON.parse(JSON.stringify(fake));
 mutation(changed);
 assert(!mod.snapshot(rates,price,'AUDJPY',fixtureModelDay,fixtureNow,changed).ready,label+' must not produce false ready status');
}
assert(!mod.snapshot(rates,price,'EURCHF',base,now,fake).ready,'CHF remains separate and stale');
assert(!mod.snapshot(rates,price,'NZDUSD',base,now,fake).ready,'NZD remains separate and stale');
assert(!mod.snapshot(rates,price,'AUDJPY',fixtureModelDay,later(fixtureNow,30),fake).ready,
 'Old research cannot remain current');
// Separately exercise the actual moving model date. A source that was valid
// on 6 Nov must not be promoted when the FX snapshot has moved past its 3d lag.
const liveAsOf=model.price_asof;
assert(/^\d{4}-\d{2}-\d{2}$/.test(liveAsOf),'Live pair FX as-of missing');
const liveResearch=mod.snapshot(rates,price,'AUDCAD',liveAsOf,liveAsOf,sidecar);
if(liveResearch.ready){
 assert(liveResearch.researchOnly&&liveResearch.lag<=3&&liveResearch.age<=5&&liveResearch.short,
  'Live AUD 2Y research must satisfy provenance, date match and continuity gates');
}else assert.equal(mod.brief(liveResearch).ready,false,'Stale AUD research cannot become live FX/2Y confirmation');
const page=fs.readFileSync('site/fx-quant-v2/next/index.html','utf8');
const code=fs.readFileSync('site/fx-quant-v2/next/app.js','utf8');
const dossier=fs.readFileSync('site/fx-quant-v2/next/decision-journey.js','utf8');
assert(/app\.js\?v=\d+/.test(page)&&/fx-rates-bridge\.js\?v=\d+/.test(page),'Next must load versioned app and rates research components');
assert(code.includes("audDailyResearch:'../aud-rba-f2-history-research.json'"));
assert(dossier.includes("get('audDailyResearch')"));
assert(code.includes("get('audDailyResearch')"));
if(sidecar.status==='OFFICIAL_F2_DAILY_RESEARCH_ONLY_NOT_POINT_IN_TIME'){
 const actual=mod.snapshot(rates,price,'AUDCAD',base,now,sidecar);
 // The historical 6 Nov sidecar is only usable if the currently stored
 // AUD source still matches its own vintage. A newer official yield must
 // never be backfilled into this old source as if observed then.
 if(actual.ready){
  assert(actual.researchOnly,'Matching dated official RBA history is research-only');
  assert(actual.rows.length>30);
 } else {
  assert(!actual.researchOnly,'Stale RBA F2 sidecar must not silently override current AUD yields');
 }
 if(sidecar.last_observation_date==='2026-11-04'&&model.price_asof==='2026-11-06'){
  const all=Object.keys(model.pairs);
  const matched=all.map(key=>({key,info:mod.snapshot(rates,price,key,base,now,sidecar)}));
  const short=matched.filter(x=>x.info.ready&&x.info.short).map(x=>x.key);
  const medium=matched.filter(x=>x.info.ready&&x.info.medium).map(x=>x.key);
  const aud=matched.filter(x=>x.info.ready&&x.info.researchOnly).map(x=>x.key).sort();
  assert.equal(short.length,15,'Verified official RBA daily history must cover 15/28 short rates research comparisons');
  assert.equal(medium.length,10,'Actual daily source must cover 10/28 medium rates comparisons');
  assert.deepEqual(aud,['AUDCAD','AUDJPY','AUDUSD','EURAUD','GBPAUD'],'Five genuine AUD research comparisons, not synthetic live quotes');
  assert(matched.filter(x=>x.info.researchOnly).every(x=>x.key.includes('AUD')),'RBA research must not contaminate unrelated FX crosses');
 }
}else assert.equal(sidecar.status,'AWAITING_OFFICIAL_F2_DAILY_HISTORY');
console.log('NEXT_V16_AUD_F2_RESEARCH_PASS',JSON.stringify({
 sidecar:sidecar.status,syntheticTestOnly:true,
 officialReady:mod.snapshot(rates,price,'AUDCAD',base,now,sidecar).ready}));
