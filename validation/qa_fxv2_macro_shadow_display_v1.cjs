'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {validate,view}=require('../site/fx-quant-v2/assets/macro-shadow-display-v1.js');
const codes=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const row=ccy=>({
 activity_z_research:.25,growth_z_research:.5,labour_tightness_z_research:0,
 inflation_pressure_z_research:1,
 stable_for_continuous_growth_weight_25_to_75_pct:true,
 hypothetical_independent_axis_z_revision_stability:{"10":true,"25":false,"50":false},
 official_first_publication_PIT_replay_complete:false,
 fx_policy_or_return_signal:null,
 source_axes:{
   growth:{period:'2026Q2',quality:'RESEARCH',method:'PRIOR_12_Q',is_estimate:false},
   labour:{period:'2026-09',quality:'REVISED',method:'PRIOR_24_M',is_estimate:ccy==='USD'},
   inflation:{period:'2026-09',quality:'REVISED',method:'PRIOR_24_M',is_estimate:false}
 }
});
const doc={
 schema:'GMFQ_FXV2_MACRO_SHADOW_FORMULA_RESEARCH_V1',
 status:'RESEARCH_SHADOW_FORMULA_READY_NOT_FX_MODEL',
 economic_source_cutoff_rome:'2026-11-04',
 formula_version:'v2_domestic_activity_2026_10_27_FIXED_50_50',
 formula:'Activity = 0.50 * GDP_z + 0.50 * (- unemployment_rate_z); inflation_pressure = CPI_z separately',
 weights:{growth_z:.5,labour_tightness_z:.5,inflation_in_activity:0},
 country_z_scores_not_cross_country_strength:true,
 source_and_revision_quality_is_not_historical_PIT:true,
 eligible_for_fx_core:false,eligible_for_pair_rankings:false,
 eligible_for_trading:false,eligible_for_forward:false,eligible_for_backtests:false,
 canonical_D_untouched:true,
 summary:{currencies:8,research_axes:24,fx_directional_signals_generated:0,fx_pairs_unchanged:28},
 original_frozen_legacy_D_asof:'2026-09-25',
 countries:Object.fromEntries(codes.map(c=>[c,row(c)]))
};
const copy=x=>JSON.parse(JSON.stringify(x));
assert(validate(doc,'2026-11-04'));
for(const c of codes){
 const v=view(doc,c,'2026-11-04');
 assert(v.text.includes('50% Crescita + 50% Tensione lavoro'));
 assert(v.text.includes('NON è un punteggio FX'));
 assert(v.text.includes('baseline operativa 25/09/2026 invariata'));
 assert(v.text.includes('±0,25z'));
}
assert(view(doc,'USD','2026-11-04').text.includes('STIMA dichiarata'));
const tamper=[
 x=>x.weights.inflation_in_activity=.2,
 x=>x.eligible_for_fx_core=true,
 x=>x.summary.fx_directional_signals_generated=1,
 x=>x.countries.USD.activity_z_research=.99,
 x=>x.countries.GBP.source_axes.labour.is_estimate='false',
 x=>x.countries.CAD.fx_policy_or_return_signal='BUY',
 x=>x.countries.NZD.source_axes.inflation.quality='',
 x=>x.countries.EUR.official_first_publication_PIT_replay_complete=true,
 x=>x.economic_source_cutoff_rome='2026-11-05'
];
for(const fn of tamper){const z=copy(doc);fn(z);assert(!validate(z,'2026-11-04'));}
const partial=copy(doc);
partial.status='PARTIAL_SHADOW_SOURCE_GAPS_RESEARCH_ONLY';
partial.countries.CHF.growth_z_research=null;
partial.countries.CHF.activity_z_research=null;
partial.countries.CHF.stable_for_continuous_growth_weight_25_to_75_pct=null;
partial.countries.CHF.hypothetical_independent_axis_z_revision_stability=null;
partial.countries.CHF.source_axes.growth.strict_z_available=false;
partial.countries.CHF.source_axes.growth.missing_reason='NO_Z_ZERO_ROBUST_DISPERSION';
partial.summary.countries_blocked_activity=1;
partial.summary.countries_with_calculable_activity=7;
assert(validate(partial,'2026-11-04'));
const blocked=view(partial,'CHF','2026-11-04');
assert(blocked.text.includes('Attività A NON CALCOLABILE'));
assert(blocked.text.includes('Nessuno zero imputato'));
assert(!blocked.text.includes('Attività A +0,00'));
const wrong=copy(partial);
wrong.countries.CHF.activity_z_research=0;
assert(!validate(wrong,'2026-11-04'),'no false-neutral zero when strict z missing');
const repo=path.resolve(__dirname,'..');
const macro=fs.readFileSync(path.join(repo,'site/fx-quant-v2/macro.html'),'utf8');
assert(macro.includes('macro-shadow-formula-v1.json'));
assert(macro.includes('macro-shadow-display-v1.js'));
const prior=fs.readFileSync(path.join(repo,'live_data/sections/D.json'),'utf8');
const legacy=JSON.parse(prior);
assert.equal(legacy.asOf,'2026-09-25');
assert(!macro.includes('window.D = shadowFormula'),'shadow must never override FX core');
console.log('FXV2_MACRO_SHADOW_BROWSER_CONTRACT_TEST_PASS 8 countries, no FX core mutation');
