'use strict';
/* User-facing complete G8 table is immediately visible, dated and non-promotional. */
const fs=require('node:fs');
const assert=require('node:assert/strict');
const {matrix,view,coverage,calibratedNzdCarry}=require('../site/control-room-preview/ois-pricing-estimates-v1.js');
const ois=JSON.parse(fs.readFileSync('live_data/sections/OIS_OPERATIONAL_VIEW.json','utf8'));
const bill=JSON.parse(fs.readFileSync('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json','utf8'));
const when='2026-10-23',g8=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
const rows=matrix(ois,bill,when);
assert.deepEqual(rows.map(x=>x.ccy),g8);
const rendered=view(rows);
assert(rendered.includes('class="gmfq-est-disclosure" open data-default="OPEN"'),
 'All G8 rows must be expanded by default');
assert(rendered.includes('valute con riferimenti numerici'));
assert(rendered.includes('data-ccy="NZD"'));
assert(rendered.includes('data-ccy="EUR"'));
assert(rendered.includes('non intervallo statistico'));
assert(rendered.includes('NESSUNA')===false);
const c=coverage(ois,bill,when);
assert.equal(c.total,8);
assert.equal(c.covered_count+c.incomplete_codes.length,8);
const eur=rows.find(x=>x.ccy==='EUR'),nzd=rows.find(x=>x.ccy==='NZD');
assert.equal(eur.tier,'MIXED');
assert.equal(nzd.tier,'SCENARIO');
assert(eur.points['3m']?.date&&eur.points['6m']?.date&&eur.points['12m']?.date,
 'EUR must display dated futures observations');
assert(eur.points['3m'].date!==eur.points['12m'].date,'EUR mixed dates are not a synchronized curve');
assert(!eur.allow_repricing&&!eur.allow_official_promotion&&eur.core_score_effect==='NONE');
assert(!nzd.allow_repricing&&!nzd.allow_official_promotion&&nzd.core_score_effect==='NONE');
assert.equal(nzd.points['3m'].date,'2026-10-22');
assert(nzd.points['3m'].range&&nzd.points['6m'].range&&nzd.points['12m'].range,
 'NZD scenario must display uncertainty bands');
for(const t of ['3m','6m','12m']){
 const x=nzd.points[t];
 assert(Number.isFinite(x.value)&&x.range[0]<x.value&&x.value<x.range[1]);
 assert(rendered.includes(x.value.toFixed(2)+'%'));
}
const calibration=calibratedNzdCarry();
assert.equal(calibration.direct_nzbo_ois_quote,false);
assert.equal(calibration.forward_ois_curve,false);
assert.equal(calibration.policy_delta_allowed,false);
for(const ccy of ['EUR','NZD'])
 assert.equal(ois.currencies[ccy].operational_status,'WITHHELD',
  'Canonical official/operational audit must stay unchanged');
const dead=coverage(ois,bill,'2026-11-10');
assert(dead.covered_count<8,'Expired prices cannot be presented as current estimates');
console.log('CONTROL_ROOM_G8_VISIBLE_DATED_PRICING_RESEARCH_PASS',
 JSON.stringify({date:when,covered:c.covered_count,official:c.official_count,context:c.context_count,
 missing:c.incomplete_codes,EUR:eur.tier,NZD:nzd.tier,score_effect:'NONE'}));
