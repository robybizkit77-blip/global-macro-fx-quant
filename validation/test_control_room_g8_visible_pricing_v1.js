'use strict';
/* User-facing complete G8 table is immediately visible, dated and non-promotional. */
const fs=require('node:fs');
const assert=require('node:assert/strict');
const {matrix,view,coverage,calibratedNzdCarry,scenarioSixMonth,indicativeSixMonth,auditNzdBankBill}=require('../site/control-room-preview/ois-pricing-estimates-v1.js');
const ois=JSON.parse(fs.readFileSync('live_data/sections/OIS_OPERATIONAL_VIEW.json','utf8'));
const bill=JSON.parse(fs.readFileSync('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json','utf8'));
const g8=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
const when=[bill.as_of,...g8.map(c=>ois.currencies[c]?.as_of)]
 .filter(x=>/^20\d{2}-\d{2}-\d{2}$/.test(x||'')).sort().at(-1);
const future=new Date(Date.parse(when+'T00:00:00Z')+30*86400000)
 .toISOString().slice(0,10);
const rows=matrix(ois,bill,when);
assert.deepEqual(rows.map(x=>x.ccy),g8);
const rendered=view(rows);
assert.equal((rendered.match(/data-chart-ccy="/g)||[]).length,8,
 'All 8 G8 research mini charts must render, even with source grading');
assert(rendered.includes('data-mini-curves="8"'));
for(const r of rows){
 const mark=new RegExp('data-chart-ccy="'+r.ccy+'" data-quality="'+r.tier+'" data-points="3"');
 if(r.tier!=='WITHHELD'&&['3m','6m','12m'].every(t=>r.points[t]?.value!=null))
  assert(mark.test(rendered),'Missing source-graded 3-point chart for '+r.ccy);
}
if(rows.find(r=>r.ccy==='EUR')?.tier==='MIXED')
 assert(/data-chart-ccy="EUR"[^>]+data-joined="false"/.test(rendered),
  'Unsynchronised EUR contracts must not be joined into a fake OIS curve');
assert(rendered.includes('class="gmfq-est-disclosure" open data-default="OPEN"'),
 'All G8 rows must be expanded by default');
assert(rendered.includes('valute con riferimenti numerici'));
assert(rendered.includes('data-ccy="NZD"'));
assert(rendered.includes('data-ccy="EUR"'));
assert(rendered.includes('G8 · OIS e stime monetarie 3M / 6M / 12M'),
 'Rates page must identify certified versus estimated 3M/6M/12M values');
assert(rendered.includes('data-g8-estimated-curve-coverage='),
 'Rates page must make numeric G8 estimate coverage explicit');
if(rows.some(r=>r.tier==='MIXED'))
 assert(rendered.includes('STIMA · FUTURES / DATE NON SINCRONIZZATE'),
  'A true mixed-date quote must visibly remain an estimate');
if(rows.some(r=>r.tier==='CONFLICTED'))
 assert(rendered.includes('STIMA CONTESTATA · QUOTAZIONI NON CONVALIDATE'),
  'A source conflict must be visible as a disputed estimate, not a verified OIS');

assert(rendered.includes('non intervallo statistico'));
assert(rendered.includes('NESSUNA')===false);
const c=coverage(ois,bill,when);
assert.equal(c.total,8);
assert.equal(c.covered_count+c.incomplete_codes.length,8);
const eur=rows.find(x=>x.ccy==='EUR'),nzd=rows.find(x=>x.ccy==='NZD');
assert(['PROXY','MIXED','CONFLICTED','WITHHELD','OFFICIAL'].includes(eur.tier));
assert(['SCENARIO','WITHHELD','OFFICIAL'].includes(nzd.tier));
if(['PROXY','MIXED','CONFLICTED'].includes(eur.tier)){
 // A date mismatch may leave only 1-2 individually usable contracts.
 // Never demand all three or join tomorrow's bar to today's source vintage.
 const visible=Object.entries(eur.points).filter(([h,p])=>
  ['3m','6m','12m'].includes(h)&&p?.date);
 assert(visible.length>=1&&visible.length<=3,
  'EUR observations require independent dated contract receipts');
 assert(visible.every(([h,p])=>
  (p.source_quote_verified===true||p.source_quote_disputed===true)&&
  p.direct_ois_quote===false&&p.policy_repricing_allowed===false),
  'Dated EUR futures never certified as OIS or repricing');
 if(visible.length===3){
  const expected=visible.some(([,p])=>p.source_quote_disputed)?'CONFLICTED':
    new Set(visible.map(([,p])=>p.date)).size>1?'MIXED':'PROXY';
  assert.equal(eur.tier,expected,
   'Complete EUR futures must distinguish non-synchronized dates');
 }else{
  assert(['MIXED','CONFLICTED'].includes(eur.tier),'Incomplete EUR secondary quotes cannot become certified OIS');
  assert.equal(c.currency_tiers.EUR,'INCOMPLETE_OR_STALE',
   '1-2 individually dated futures must not count as complete 3M/6M/12M coverage');
  assert(c.incomplete_codes.includes('EUR'));
 }
}
// Reject an individual EUR bar that is newer than the declared view day
// without suppressing independently verified 3M/6M observations.
const eurSource=ois.currencies.EUR;
const eurFuture=eurSource.horizons?.['12m']?.quote_as_of;
if(eurSource.operational_status==='WITHHELD'&&eurFuture&&eurFuture>when&&
   eurSource.secondary_quote_context?.date_mismatch===true){
 assert(!eur.points['12m'],
  'A next-day 12M EUR bar must not be presented as observed at the prior close');
 assert(['3m','6m'].every(h=>!eur.points[h]||eur.points[h].date<=when));
 assert(c.incomplete_codes.includes('EUR'),
  'Partially observed EUR futures must not be counted as complete pricing');
}
if(ois.currencies.EUR.operational_status==='GREEN_ESTIMATED'&&
 ois.currencies.EUR.as_of===when)
 assert(['PROXY','MIXED','CONFLICTED'].includes(eur.tier),'Current EUR futures must retain transparent source status');
// Real source-conflict evidence must remain legible as research dots only.
// An audit-verified quote and an unverified same-day competing quote are
// intentionally different statuses; the latter can never become OIS or 1D/1W.
const contested=rows.filter(r=>r.tier==='CONFLICTED');
for(const row of contested){
 const src=ois.currencies[row.ccy];
 assert.equal(src.source_conflict_status,'UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT');
 const disputed=Object.entries(row.points).filter(([,p])=>p.source_quote_disputed);
 assert(disputed.length>=1,row.ccy+' conflict lost from graph');
 assert(rendered.includes('data-chart-ccy="'+row.ccy+'" data-quality="CONFLICTED" data-points="3" data-joined="false"'),
  row.ccy+' disputed points must be individually visible, never joined');
 for(const [term,p] of disputed){
  assert.equal(p.source_quote_verified,false);
  assert.equal(p.policy_repricing_allowed,false);
  assert.equal(p.direct_ois_quote,false);
  assert(/^[a-f0-9]{64}$/.test(p.dispute_event_id));
  const spoofed=structuredClone(ois);
  const bad=spoofed.currencies[row.ccy].source_conflict_keys.find(k=>k.horizon===term);
  bad.event_id='forged-not-an-event';
  assert(!matrix(spoofed,bill,when).find(x=>x.ccy===row.ccy).points[term]?.source_quote_disputed,
   'Unproven disputed futures may not be displayed as admissible evidence');
  const invalidPrice=structuredClone(ois);
  invalidPrice.currencies[row.ccy].horizons[term].futures_price+=0.1;
  assert(!matrix(invalidPrice,bill,when).find(x=>x.ccy===row.ccy).points[term]?.source_quote_disputed,
   'Contradictory futures arithmetic must fail closed');
 }
}
// A currency-wide conflict does not invalidate an independently verified 6M
// contract. It DOES invalidate a disputed 6M print: no fallback or repricing.
const individuallyVerified=indicativeSixMonth(ois,when);
for(const row of contested){
 const point=row.points['6m'];
 if(point?.source_quote_verified){
  assert.equal(individuallyVerified[row.ccy]?.type,'CONFLICTED');
  assert.equal(individuallyVerified[row.ccy]?.value,point.value);
  assert.equal(individuallyVerified[row.ccy]?.policy_delta_allowed,false);
  assert.equal(individuallyVerified[row.ccy]?.pair_effect,'NONE');
  assert(individuallyVerified[row.ccy]?.label.includes('verificato singolarmente'));
 }else{
  assert.equal(individuallyVerified[row.ccy],undefined,
   'A disputed 6M bar cannot be shown as verified individually');
 }
}
assert(!contested.some(r=>r.allow_repricing||r.allow_official_promotion||r.official_ois));
assert(!eur.allow_repricing&&!eur.allow_official_promotion&&eur.core_score_effect==='NONE');
assert(!nzd.allow_repricing&&!nzd.allow_official_promotion&&nzd.core_score_effect==='NONE');
// ASX NZD quote-quality invariants: reject synthetic rates, wrong ASX
// report date, expiry roll, settlement and changes BEFORE using cash basis.
// This validates the research display, NOT OIS market-pricing.
const validatedBB=auditNzdBankBill(bill,when);
assert(validatedBB&&Object.keys(validatedBB).length===3,
 'Official ASX source reference must provide three independently audited bills');
for(const term of ['3m','6m','12m'])
 assert.equal(validatedBB[term],bill.horizons[term].implied_bank_bill_rate);
function badBill(edit,reason){
 const bad=structuredClone(bill);
 edit(bad);
 assert.equal(auditNzdBankBill(bad,when),null,reason);
 assert(!scenarioSixMonth(ois,bad,when).NZD,
   'A contaminated ASX bankbill observation must NEVER become NZD research OIS: '+reason);
 assert.equal(matrix(ois,bad,when).find(x=>x.ccy==='NZD').tier,'WITHHELD',
   'Invalid ASX feed must fail closed in Rates matrix: '+reason);
}
badBill(b=>b.horizons['6m'].settlement_price+=.02,'rate / settlement mismatch');
badBill(b=>b.horizons['3m'].change_1d_bp*=-1,'daily settlement-change sign mismatch');
badBill(b=>b.horizons['12m'].expiry_label='Mar 2027','horizon / listed contract mismatch');
badBill(b=>b.horizons['6m'].expiration='2027-06-17','wrong ASX contract calendar');
badBill(b=>b.horizons['3m'].mapping='interpolated','no synthetic expiry interpolation');
badBill(b=>b.horizons['3m'].change_1w_bp=undefined,'incomplete weekly source proof');
badBill(b=>b.source_url='https://example.org/not-exchange','non-ASX source');
badBill(b=>b.as_of='2026-10-29','report date and ASX URL mismatch');
badBill(b=>b.governance.core_score_effect='NZD_LONG','FX score promotion');
badBill(b=>delete b.horizons['6m'],'missing 6M quote');

const shared=scenarioSixMonth(ois,bill,when);
if(nzd.tier==='SCENARIO'){
 assert.equal(nzd.points['3m'].date,bill.as_of);
 assert(nzd.points['3m'].range&&nzd.points['6m'].range&&nzd.points['12m'].range,
  'NZD scenario must display uncertainty bands');
 for(const t of ['3m','6m','12m']){
  const x=nzd.points[t];
  assert(Number.isFinite(x.value)&&x.range[0]<x.value&&x.value<x.range[1]);
  assert(rendered.includes(x.value.toFixed(2)+'%'));
 }
 assert.deepEqual(Object.keys(shared),['NZD']);
 assert.equal(shared.NZD.type,'SCENARIO');
 assert.equal(shared.NZD.value,nzd.points['6m'].value);
 assert.deepEqual(shared.NZD.range,nzd.points['6m'].range);
 assert.equal(shared.NZD.quote_as_of,nzd.points['6m'].date);
 assert.equal(shared.NZD.is_official_ois,false);
 assert.equal(shared.NZD.policy_delta_allowed,false);
 assert.equal(shared.NZD.backtest_eligible_as_official,false);
 assert.equal(shared.NZD.pair_effect,'NONE');
 assert.equal(shared.NZD.core_effect,'NONE');
}else{
 assert.deepEqual(Object.keys(shared),[],'Never invent an unavailable NZD scenario');
}
assert.deepEqual(Object.keys(scenarioSixMonth(ois,bill,future)),[],
 'stale 6M NZD research scenario rejected');
const broken=structuredClone(bill);broken.horizons['6m'].implied_bank_bill_rate=null;
assert.deepEqual(Object.keys(scenarioSixMonth(ois,broken,when)),[],
 'missing 6M input cannot become a scenario');
const misgoverned=structuredClone(bill);misgoverned.governance.policy_delta_from_proxy_allowed=true;
assert.deepEqual(Object.keys(scenarioSixMonth(ois,misgoverned,when)),[],
 'unsafe proxy governance rejected');
const home=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
assert(home.includes("fmt(x.level,2)+'%'"),
 'Home certified 6M is a rate level in percent, not a delta in bp');
assert(home.includes("host.dataset.gmfqSixMonthUnit='RATE_PCT'"),
 'Home all-eight unit contract must remain percentage levels');
assert(home.includes("data-six-month-coverage="),
 'Home must visibly disclose how many of the G8 have a numeric 6M');
assert(home.includes("Tutti i valori sono livelli di tasso in %"),
 'Home must not mix 6M deltas and absolute rate units');
assert(home.includes("state==='CASH_CARRY_SCENARIO'?'≈'+fmt(x.scenario.value,2)+'% ST'"),
 'Home uses NZD adjusted scenario');
assert(home.includes("pairMacroRatesComparison(code,setup.pairs[code],rates,ois,setup.price_asof,macroDay,proxy)"),
 'Pair loads same NZD feed');
assert(home.includes("6M scenario empirico ≈"),'Pair labels empirical level as research only');
const calibration=calibratedNzdCarry();
assert.equal(calibration.direct_nzbo_ois_quote,false);
assert.equal(calibration.forward_ois_curve,false);
assert.equal(calibration.policy_delta_allowed,false);
for(const ccy of ['EUR','NZD']){
 const source=ois.currencies[ccy];
 if(source.official_status!=='ACTIVE')
  assert.notEqual(rows.find(x=>x.ccy===ccy).tier,'OFFICIAL',
   'Uncertified source cannot be displayed as official OIS');
 assert(!rows.find(x=>x.ccy===ccy).allow_repricing);
}

const dead=coverage(ois,bill,future);
assert(dead.covered_count<8,'Expired prices cannot be presented as current estimates');
console.log('CONTROL_ROOM_G8_VISIBLE_DATED_PRICING_RESEARCH_PASS',
 JSON.stringify({date:when,covered:c.covered_count,official:c.official_count,context:c.context_count,
 missing:c.incomplete_codes,EUR:eur.tier,NZD:nzd.tier,score_effect:'NONE'}));
