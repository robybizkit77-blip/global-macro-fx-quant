'use strict';
/* Reproducibility, economic sign checks and adversarial boundaries.
 * This is an accounting/feature model test, NOT a realized-return backtest.
 */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'..');
const INPUT=path.join(ROOT,'site/control-room-preview/macro-v3-current-evidence.json');
const CORE=path.join(ROOT,'live_data/sections/D.json');
const PAIRS=path.join(ROOT,'live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const source=JSON.parse(fs.readFileSync(INPUT,'utf8'));
const originalSource=JSON.stringify(source),oldCore=fs.readFileSync(CORE,'utf8'),oldPairs=fs.readFileSync(PAIRS,'utf8');
const {validate}=require('../site/fx-quant-v2/assets/pair-macro-observed-context-v1.js');
const {build,featureCountry,SPEC}=require('../site/fx-quant-v2/assets/macro-shadow-baseline-v1.js');
const today=source.generated_europe_rome_day,data=build(source,today,validate),copy=x=>JSON.parse(JSON.stringify(x));
const plusDays=(s,n)=>new Date(Date.parse(s+'T12:00:00Z')+n*86400000).toISOString().slice(0,10);
assert.equal(data.schema,'GMFQ_FXV2_MACRO_SHADOW_BASELINE_V1');
assert.equal(data.summary.features,24);
assert.equal(data.summary.currencies,8);
assert.equal(data.summary.pairs,28);
assert.equal(data.summary.gdp_acceleration_available,2);
assert.equal(data.summary.fx_signals_generated,0);
assert.equal(data.summary.original_D_scores_replaced,0);
assert.equal(data.eligible_for_trading_engine,false);
assert.equal(data.eligible_for_backtest,false);
assert.equal(data.safe_to_update_D_json,false);
assert.equal(data.safe_to_update_pair_signals,false);
assert.equal(data.canonical_core_baseline_untouched,'2026-09-25');
assert.equal(data.primary_weights.growth,data.primary_weights.labour);
assert.equal(data.primary_weights.labour,data.primary_weights.inflation);
for(const [ccy,x] of Object.entries(data.countries)){
 assert(x.shadow_index>=-100&&x.shadow_index<=100,ccy);
 assert(x.weight_sensitivity.min<=x.shadow_index&&x.weight_sensitivity.max>=x.shadow_index,ccy);
 assert.equal(x.weight_sensitivity.variants.length,6,ccy);
 assert.equal(x.weight_sensitivity.range_is_not_confidence_interval,true,ccy);
 assert.equal(x.score_is_fx_strength,false,ccy);
 assert.equal(x.rank,null,ccy);
 assert.equal(x.fx_bias,null,ccy);
 assert.equal(x.pair_preference,null,ccy);
 assert.equal(x.feature_sources.labour.observation_period_not_release_day,true,ccy);
 assert.equal(x.feature_sources.inflation.observation_period_not_release_day,true,ccy);
}
for(const [name,row] of Object.entries(data.pair_context)){
 assert.equal(name,row.base+'/'+row.quote);
 assert.equal(row.pair_shadow_spread,null,name);
 assert.equal(row.fx_bias,null,name);
 assert.equal(row.trade_signal,null,name);
 assert.equal(row.estimated_fx_return,null,name);
}
for(const [ccy,x] of Object.entries(data.countries)){
 const raw=x.raw_features;
 const clip=n=>Math.max(-1,Math.min(1,n));
 const expected=Math.round(100*(clip(raw.gdp_nonannualized_qoq_pp/1.0)-
   clip(raw.unemployment_change_3_intervals_pp/0.5)-
   clip(raw.inflation_change_3_intervals_pp/1.0))/3*100)/100;
 assert(Math.abs(x.shadow_index-expected)<.011,ccy+' source-dependent independent formula replay');
 const latest=source.countries[ccy];
 assert.equal(x.feature_sources.labour.period,latest.labour.observation_period,ccy);
 assert.equal(x.feature_sources.inflation.period,latest.inflation.observation_period,ccy);
}
const synthetic=copy(source);
synthetic.countries.USD.growth.nonannualized_qoq_descriptive_pct=.5;
synthetic.countries.USD.labour.change_over_three_observation_intervals_pp=0;
synthetic.countries.USD.inflation.change_over_three_observation_intervals_pp=0;
assert.equal(build(synthetic,today,validate).countries.USD.shadow_index,16.67,
 'fixed controlled 3-pillar formula fixture');
assert.equal(data.summary.gdp_acceleration_available,
 Object.values(data.countries).filter(x=>x.feature_sources.growth.gdp_acceleration_pp!==null).length);

assert.equal(data.pair_context['AUD/NZD'].inflation_same_period,true);
assert.equal(data.pair_context['AUD/NZD'].labour_same_period,false);
assert.equal(data.pair_context['EUR/USD'].growth_same_quarter,true);
assert.equal(data.pair_context['EUR/USD'].inflation_same_period,
 source.countries.EUR.inflation.observation_period===source.countries.USD.inflation.observation_period,
 'Macro shadow must check current economic observation periods independently');
// Verify deterministic result for same observed inputs and as-of.
assert.equal(JSON.stringify(data),JSON.stringify(build(source,today,validate)));
assert.equal(build(source,plusDays(today,-1),validate),null,'future observation guard');
assert.equal(build(source,plusDays(today,11),validate),null,'stale source guard');
for(const [label,mutate] of [
 ['wrong PIT claim',x=>x.historic_PIT_OOS_not_certified=false],
 ['scoring promotion',x=>x.safe_to_recompute_structural_pair_theses=true],
 ['missing pair',x=>delete x.pair_context['EUR/USD']],
 ['future source generated',x=>x.generated_europe_rome_day='2026-11-05']
]){
 const x=copy(source);mutate(x);assert.equal(build(x,today,validate),null,label);
}
for(const [label,mutate] of [
 ['missing CPI change',x=>x.countries.USD.inflation.change_over_three_observation_intervals_pp=null],
 ['GDP released in the future',x=>x.countries.EUR.growth.publisher_release_day='2026-11-06'],
 ['unemployment release-day confusion',x=>x.countries.GBP.labour.observation_period_is_not_release_instant=false],
 ['bad past period',x=>x.countries.CHF.inflation.observation_period='2027Q1']
]){
 const x=copy(source);mutate(x);
 assert.throws(()=>build(x,today,validate),/invalid/,label);
}
const optimistic=copy(source);
optimistic.countries.USD.labour.change_over_three_observation_intervals_pp=-0.5;
const changed=build(optimistic,today,validate);
assert(changed.countries.USD.shadow_index>=data.countries.USD.shadow_index,
 'unemployment falling should improve the descriptive macro balance');
const worse=copy(source);
worse.countries.USD.inflation.change_over_three_observation_intervals_pp=1;
assert(build(worse,today,validate).countries.USD.shadow_index<=data.countries.USD.shadow_index,
 'inflation acceleration should worsen the predeclared descriptive price-stability component');
assert.equal(JSON.stringify(source),originalSource,'Macro V3 input was mutated');
assert.equal(fs.readFileSync(CORE,'utf8'),oldCore,'D.json macro model mutated');
assert.equal(fs.readFileSync(PAIRS,'utf8'),oldPairs,'28-pair production baseline mutated');
// Persist a machine-readable shadow observation in Actions artifacts; never commit to Core.
if(process.env.FXV2_SHADOW_EVIDENCE==='1'){
 const out=path.resolve('fxv2-shadow-baseline-evidence');
 fs.mkdirSync(out,{recursive:true});
 fs.writeFileSync(path.join(out,'shadow-baseline.json'),JSON.stringify(data,null,2)+'\n');
 const rows=['# FX Quant V2 · Macro Shadow Baseline (NOT a trading signal)','',
 'Macro V3 source snapshot: '+data.source_generated_day,
 'Legacy FX Core macro baseline: '+data.canonical_core_baseline_untouched+' (unchanged)',
 '8 currencies, 24 observed features, 28 no-trade pair contexts.',
 'Formula: '+data.formula,
 'Research scores are not cross-currency FX strengths, recommendations or backtested forecasts.',
 '',
 '| Economia | Bilancio sintetico | Sensibilità pesi min–max | PIL accel. |',
 '|:--|--:|--:|--:|'];
 for(const [ccy,x] of Object.entries(data.countries))
  rows.push('| '+ccy+' | '+x.shadow_index+' | '+x.weight_sensitivity.min+' → '+x.weight_sensitivity.max+
   ' | '+(x.feature_sources.growth.gdp_acceleration_pp??'N/D')+' |');
 rows.push('','*No point-in-time historical OOS validation. The sensitivity span is not a confidence interval.*');
 fs.writeFileSync(path.join(out,'shadow-baseline-summary.md'),rows.join('\n')+'\n');
 if(process.env.GITHUB_STEP_SUMMARY)fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,rows.join('\n')+'\n');
}
console.log('FXV2_MACRO_SHADOW_BASELINE_PASS 8 economies, 24 features, 28 no-signal pairs; shadow GDP growth + labour slack + inflation pressure; 2/8 GDP acceleration comparisons');
