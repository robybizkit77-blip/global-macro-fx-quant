/* FX Quant V2 — render preregistered 50/50 *domestic* Macro research only.
 * Browser consumer has no access to D, FX signal logic or backtest journals.
 */
(function(root){"use strict";
const CCY=["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"];
const SCHEMA="GMFQ_FXV2_MACRO_SHADOW_FORMULA_RESEARCH_V1";
const num=x=>typeof x==="number"&&Number.isFinite(x)&&Math.abs(x)<=3.01;
const iso=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&!Number.isNaN(Date.parse(x+"T12:00:00Z"));
const n=x=>Number(x).toLocaleString("it-IT",{maximumFractionDigits:2,minimumFractionDigits:2});
const signed=x=>(x<0?"−":x>0?"+":"")+n(Math.abs(x));
function validate(doc,today){
 if(!doc||doc.schema!==SCHEMA||doc.status!=="RESEARCH_SHADOW_FORMULA_READY_NOT_FX_MODEL"||
    !iso(today)||!iso(doc.economic_source_cutoff_rome)||
    doc.economic_source_cutoff_rome>today||
    doc.formula_version!=="v2_domestic_activity_2026_10_27_FIXED_50_50"||
    doc.formula!=="Activity = 0.50 * GDP_z + 0.50 * (- unemployment_rate_z); inflation_pressure = CPI_z separately"||
    doc.weights?.growth_z!==.5||doc.weights?.labour_tightness_z!==.5||
    doc.weights?.inflation_in_activity!==0||doc.country_z_scores_not_cross_country_strength!==true||
    doc.source_and_revision_quality_is_not_historical_PIT!==true||
    doc.eligible_for_fx_core!==false||doc.eligible_for_pair_rankings!==false||
    doc.eligible_for_trading!==false||doc.eligible_for_forward!==false||
    doc.eligible_for_backtests!==false||doc.canonical_D_untouched!==true||
    doc.summary?.currencies!==8||doc.summary?.research_axes!==24||
    doc.summary?.fx_directional_signals_generated!==0||
    doc.summary?.fx_pairs_unchanged!==28||
    doc.original_frozen_legacy_D_asof!=="2026-09-25"||
    !doc.countries||Object.keys(doc.countries).length!==8||
    !CCY.every(c=>Object.prototype.hasOwnProperty.call(doc.countries,c)))return false;
 for(const c of CCY){
  const x=doc.countries[c];
  if(!x||!num(x.activity_z_research)||!num(x.growth_z_research)||
     !num(x.labour_tightness_z_research)||!num(x.inflation_pressure_z_research)||
     Math.abs(x.activity_z_research-.5*(x.growth_z_research+x.labour_tightness_z_research))>1e-8||
     typeof x.stable_for_continuous_growth_weight_25_to_75_pct!=="boolean"||
     x.fx_policy_or_return_signal!==null||
     x.official_first_publication_PIT_replay_complete!==false||
     !x.source_axes||!["growth","labour","inflation"].every(p=>{
       const s=x.source_axes[p];
       return s&&typeof s.period==="string"&&s.period.slice(0,4)<=today.slice(0,4)&&
         typeof s.quality==="string"&&typeof s.method==="string"&&
         typeof s.is_estimate==="boolean";
     }))return false;
 }
 return true;
}
function view(doc,ccy,today){
 if(!validate(doc,today)||!CCY.includes(ccy))return null;
 const x=doc.countries[ccy];
 const axes=x.source_axes;
 const isEstimate=Object.values(axes).some(x=>x.is_estimate);
 const stable=x.stable_for_continuous_growth_weight_25_to_75_pct;
 const stress=x.hypothetical_independent_axis_z_revision_stability||{};
 return {
  source_cutoff:doc.economic_source_cutoff_rome,
  period_summary:"PIL "+axes.growth.period+" · Lavoro "+axes.labour.period+
    " · Inflazione "+axes.inflation.period,
  text:"FORMULA MACRO SPERIMENTALE · A = 50% Crescita + 50% Tensione lavoro (z storici del singolo paese). "+
     "Attività A "+signed(x.activity_z_research)+"; crescita "+signed(x.growth_z_research)+
     "; lavoro "+signed(x.labour_tightness_z_research)+
     ". Pressione inflazione separata "+signed(x.inflation_pressure_z_research)+
     ". Sensibilità ai pesi 25–75%: "+(stable?"classe invariata":"CLASSE INSTABILE")+
     "; stress ipotetico ±0,25z: "+(stress["25"]===true?"invariante":"non robusto o da verificare")+
     ". "+(isEstimate?"Include almeno una STIMA dichiarata. ":"Nessuna stima dichiarata per queste tre coordinate. ")+
     "Periodi: PIL "+axes.growth.period+", lavoro "+axes.labour.period+
     ", inflazione "+axes.inflation.period+". Storici revisionati e first-web non PIT completo; "+
     "la data di calcolo "+doc.economic_source_cutoff_rome+" non è una nuova pubblicazione. "+
     "NON è un punteggio FX né un nuovo bias; baseline operativa 25/09/2026 invariata."
 };
}
const api=Object.freeze({validate,view,SCHEMA});
root.FXV2MacroShadow=api;
if(typeof module==="object"&&module&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
