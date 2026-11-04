/* FX Quant V2 · Macro Shadow Baseline V1
 * Predeclared deterministic descriptive balance, NOT inherited D.json,
 * NOT currency strength, NOT a policy forecast, NOT a trading model.
 * Deliberately uses currently revised research observations and no FX prices.
 */
(function(root){"use strict";
const FX=["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"];
const SCHEMA="GMFQ_FXV2_MACRO_SHADOW_BASELINE_V1";
const SPEC=Object.freeze({
 growth_qoq_scale_pp:1.0,
 unemployment_three_intervals_scale_pp:0.5,
 inflation_three_intervals_scale_pp:1.0,
 weights:Object.freeze({growth:1/3,labour:1/3,inflation:1/3}),
 score_scale:100,
 source_name:"Macro V3 observed, currently revised",
 engine_permission:false,
 backtest_permission:false
});
const value=x=>typeof x==="number"&&Number.isFinite(x);
const iso=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&
 new Date(x+"T12:00:00Z").toISOString().startsWith(x);
const age=(a,b)=>Math.round((Date.parse(a+"T12:00:00Z")-Date.parse(b+"T12:00:00Z"))/86400000);
const bounded=x=>Math.max(-1,Math.min(1,x));
const round=x=>Math.round((x+Number.EPSILON)*100)/100;
const qend=q=>{
 if(!/^\d{4}Q[1-4]$/.test(q))return null;
 const y=Number(q.slice(0,4)),m=3*Number(q.slice(-1));
 return new Date(Date.UTC(y,m,0)).toISOString().slice(0,10);
};
const periodValid=(s,today)=>{
 if(/^\d{4}-(0[1-9]|1[0-2])$/.test(s)){
  const [y,m]=s.split("-").map(Number);
  return new Date(Date.UTC(y,m,0)).toISOString().slice(0,10)<=today;
 }
 return !!qend(s)&&qend(s)<=today;
};
function validate(doc,today,validateV3){
 if(!iso(today)||!validateV3?.(doc,today)||
    doc.historic_PIT_OOS_not_certified!==true||
    doc.safe_to_republish_D!==false||
    doc.safe_to_recompute_structural_pair_theses!==false||
    doc.eligible_for_trading_or_forward_backtest!==false||
    doc.summary?.economic_dimensions!==24||
    doc.summary?.pairs!==28||
    doc.canonical_D_macro_baseline_as_of!=="2026-09-25")
  return false;
 return true;
}
function featureCountry(ccy,r,today){
 if(!r||r.FX_strength!==null||r.macro_score!==null||
    r.not_a_trade_or_policy_signal!==true)throw Error(ccy+": unapproved Macro V3 data");
 const g=r.growth||{},l=r.labour||{},i=r.inflation||{};
 if(!value(g.nonannualized_qoq_descriptive_pct)||!periodValid(g.reference_quarter,today)||
    !iso(g.publisher_release_day)||g.publisher_release_day>today||
    g.is_growth_strength_score!==false||g.historical_pit_training_vintages_certified===true||
    !value(l.change_over_three_observation_intervals_pp)||
    !value(i.change_over_three_observation_intervals_pp)||
    !periodValid(l.observation_period,today)||!periodValid(i.observation_period,today)||
    l.observation_period_is_not_release_instant!==true||
    i.observation_period_is_not_release_instant!==true||
    l.observed_history_revised_not_historic_PIT!==true||
    i.observed_history_revised_not_historic_PIT!==true)
  throw Error(ccy+": invalid observed economic period, vintage or feature");
 // Explicit, economically motivated signs; deliberately no cross-ccy z-score.
 // Growth = positive current activity level, NOT GDP acceleration.
 // Labour = unemployment rising means slack -> negative cyclical balance.
 // Inflation = rising headline inflation means price-stability pressure -> negative.
 // This is NOT a sign of FX policy surprise: inflation can raise policy pricing.
 const raw={
  growth:g.nonannualized_qoq_descriptive_pct,
  labour:l.change_over_three_observation_intervals_pp,
  inflation:i.change_over_three_observation_intervals_pp
 };
 const f={
  growth:bounded(raw.growth/SPEC.growth_qoq_scale_pp),
  labour:bounded(-raw.labour/SPEC.unemployment_three_intervals_scale_pp),
  inflation:bounded(-raw.inflation/SPEC.inflation_three_intervals_scale_pp)
 };
 const calc=w=>round(SPEC.score_scale*(w.growth*f.growth+w.labour*f.labour+w.inflation*f.inflation));
 const score=calc(SPEC.weights);
 const perturb=[
  calc({growth:.5,labour:.25,inflation:.25}),
  calc({growth:.25,labour:.5,inflation:.25}),
  calc({growth:.25,labour:.25,inflation:.5}),
  calc({growth:0,labour:.5,inflation:.5}),
  calc({growth:.5,labour:0,inflation:.5}),
  calc({growth:.5,labour:.5,inflation:0})
 ];
 const min=Math.min(...perturb,score),max=Math.max(...perturb,score);
 const prior=g.prior_documented_quarter;
 let gDelta=null;
 if(prior&&/^\d{4}Q[1-4]$/.test(prior.reference_quarter)&&
    value(prior.nonannualized_qoq_descriptive_pct)&&
    prior.reported_unit===g.reported_unit){
   const y=+prior.reference_quarter.slice(0,4),q=+prior.reference_quarter.slice(-1);
   const expected=q===4?(y+1)+"Q1":y+"Q"+(q+1);
   if(expected===g.reference_quarter)gDelta=round(raw.growth-prior.nonannualized_qoq_descriptive_pct);
 }
 return {
  ccy,shadow_index:score,
  raw_features:{gdp_nonannualized_qoq_pp:raw.growth,
   unemployment_change_3_intervals_pp:raw.labour,
   inflation_change_3_intervals_pp:raw.inflation},
  normalized_features:f,
  feature_sources:{
   growth:{period:g.reference_quarter,release_day:g.publisher_release_day,
     unit:g.reported_unit,source_url:g.publisher_source,
     gdp_acceleration_pp:gDelta},
   labour:{period:l.observation_period,source:l.source,series:l.series_id,
     observation_period_not_release_day:true},
   inflation:{period:i.observation_period,source:i.source,series:i.series_id,
     observation_period_not_release_day:true}
  },
  weight_sensitivity:{min,max,variants:perturb,range_is_not_confidence_interval:true},
  missing_growth_acceleration:gDelta===null,
  economy_regime_not_certified:true,
  cross_country_strength_comparable:false,
  score_is_fx_strength:false,
  rank:null,fx_bias:null,pair_preference:null
 };
}
function build(doc,today,validateV3){
 if(!validate(doc,today,validateV3))return null;
 const countries={};
 for(const c of FX)countries[c]=featureCountry(c,doc.countries?.[c],today);
 const pair_context={};
 for(const [name,row] of Object.entries(doc.pair_context||{})){
  const {base:a,quote:b}=row||{};
  if(!FX.includes(a)||!FX.includes(b)||a===b||name!==a+"/"+b||
     !countries[a]||!countries[b])throw Error("Invalid Macro V3 pair "+name);
  const A=countries[a].feature_sources,B=countries[b].feature_sources;
  pair_context[name]={
   base:a,quote:b,
   base_shadow_index:countries[a].shadow_index,
   quote_shadow_index:countries[b].shadow_index,
   inflation_same_period:A.inflation.period===B.inflation.period,
   labour_same_period:A.labour.period===B.labour.period,
   growth_same_quarter:A.growth.period===B.growth.period,
   pair_shadow_spread:null,
   fx_bias:null,trade_signal:null,
   estimated_fx_return:null,
   different_reference_periods_do_not_imply_fx_strength:true
  };
 }
 if(Object.keys(pair_context).length!==28)throw Error("Shadow G8 pair coverage incomplete");
 return {
  schema:SCHEMA,
  status:"RESEARCH_SHADOW_ONLY_NOT_VALIDATED_FOR_FX",
  source_generated_day:doc.generated_europe_rome_day,
  source_snapshot_sha256:doc.snapshot_content_sha256,
  canonical_core_baseline_untouched:doc.canonical_D_macro_baseline_as_of,
  economic_method:"CURRENT_QUARTER_GDP_QOQ_PLUS_LABOUR_AND_INFLATION_CHANGE_OVER_3_OBSERVATION_INTERVALS",
  formula:"100*[1/3 clip(GDP non-annualized QoQ / 1.0 pp,-1,1) + 1/3 clip(-delta unemployment / 0.5 pp,-1,1) + 1/3 clip(-delta inflation / 1.0 pp,-1,1)]",
  primary_weights:SPEC.weights,
  fixed_scales:{growth_qoq_pp:SPEC.growth_qoq_scale_pp,
   labour_three_intervals_pp:SPEC.unemployment_three_intervals_scale_pp,
   inflation_three_intervals_pp:SPEC.inflation_three_intervals_scale_pp},
  normalization:"FIXED_A_PRIORI_HEURISTIC_SCALES_NOT_ESTIMATED_FROM_8_CURRENCIES",
  weight_sensitivity_design:"0.5/0.25/0.25 each pillar, and three leave-one-pillar-out equal remaining weights; NOT statistical CI",
  economic_limitations:[
   "GDP current QoQ is a growth level, not acceleration where prior quarter absent",
   "Unemployment and CPI changes cover 3 observation intervals, not necessarily three months",
   "GDP/UR/CPI release dates, observation windows and definitions differ by currency",
   "Input histories are revised observations, NOT full first-release point-in-time",
   "A higher balance index does NOT imply higher FX expected return, hawkish policy or market outperformance",
   "Weights and scales are economic research hypotheses, not estimated or validated coefficients"
  ],
  countries,pair_context,
  summary:{
   currencies:FX.length,
   features:FX.length*3,
   pairs:Object.keys(pair_context).length,
   gdp_acceleration_available:FX.filter(x=>!countries[x].missing_growth_acceleration).length,
   score_range:[-100,100],
   historical_oos_backtests:0,
   fx_signals_generated:0,
   original_D_scores_replaced:0
  },
  eligible_for_trading_engine:false,
  eligible_for_backtest:false,
  safe_to_update_D_json:false,
  safe_to_update_pair_signals:false
 };
}
const api=Object.freeze({build,validate,featureCountry,SPEC,SCHEMA});
root.FXV2MacroShadow=api;
if(typeof module==="object"&&module&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
